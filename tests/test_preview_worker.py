import io
import pickle
import socket
import sys
import threading
import time
from unittest.mock import patch, MagicMock

import pandas as pd

from ktfigure.preview_worker import (
    PreviewJob, render_thumbnail, main, _binary_stream, _command, _READY, _RENDERING,
    _FINISHED,
)


def request(df=None, plot_type="scatter"):
    return {
        "width": 240, "height": 180, "dpi": 48,
        "df": df if df is not None else pd.DataFrame({"x": [1, 2], "y": [2, 3]}),
        "plot_type": plot_type, "col_x": "x", "col_y": "y",
        "col_hue": None, "col_size": None,
    }


def test_worker_samples_scatter_only():
    df = pd.DataFrame({"x": range(20001), "y": range(20001)})
    with patch("ktfigure.PlotRenderer._render_to_ax") as render:
        render_thumbnail(request(df))
        sample = render.call_args.args[0].df
        assert len(sample) == 20000
        assert sample.index.equals(df.sample(n=20000, random_state=0).index)
        render_thumbnail(request(df, "line"))
        assert render.call_args.args[0].df is df
    assert len(df) == 20001


def test_fast_render_and_error_are_returned():
    job = PreviewJob(request())
    assert job.done.wait(5)
    assert job.result[0] == "ok"
    assert job.result[1].startswith(b"\x89PNG\r\n\x1a\n")
    assert job._process.poll() == 0

    bad = request()
    bad["col_x"] = "missing"
    job = PreviewJob(bad)
    assert job.done.wait(5)
    assert job.result[0] == "error"
    assert "missing" in job.result[1]
    assert job._process.poll() == 0


def test_large_scatter_is_sampled_before_worker_transfer():
    df = pd.DataFrame({"x": range(20001), "y": range(20001)})
    original = pickle.dumps
    sizes = []

    def serialize(value, **kwargs):
        sizes.append(len(value["df"]))
        return original(value, **kwargs)

    with patch("ktfigure.preview_worker.pickle.dumps", side_effect=serialize):
        job = PreviewJob(request(df))
        assert job.done.wait(5)
    assert job.result[0] == "ok"
    assert sizes == [20000]
    assert len(df) == 20001


def test_slow_actual_render_is_killed_and_reaped():
    df = pd.DataFrame({"x": ["same"] * 5000, "y": [1] * 5000})
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10)
        port = listener.getsockname()[1]
        code = (
            "import socket\n"
            "from ktfigure import PlotRenderer\n"
            "from ktfigure.preview_worker import main\n"
            "original = PlotRenderer._render_to_ax\n"
            "def signal_then_render(*args, **kwargs):\n"
            f"    socket.create_connection(('127.0.0.1', {port})).close()\n"
            "    return original(*args, **kwargs)\n"
            "PlotRenderer._render_to_ax = signal_then_render\n"
            "main()\n"
        )
        with patch("ktfigure.preview_worker._command", return_value=[sys.executable, "-c", code]):
            job = PreviewJob(request(df, "swarm"))
            connection, _ = listener.accept()
            connection.close()
            started = time.monotonic()
            assert job.done.wait(4)
    assert job.result == ("timeout", None)
    assert time.monotonic() - started < 3.5
    assert job._process is not None
    assert job._process.poll() is not None
    job._thread.join(1)
    assert not job._thread.is_alive()


def test_cancel_kills_and_reaps_worker():
    df = pd.DataFrame({"x": ["same"] * 5000, "y": [1] * 5000})
    job = PreviewJob(request(df, "swarm"))
    deadline = time.monotonic() + 1
    while job._process is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert job._process is not None
    job.cancel()
    assert job.done.wait(3)
    assert job._process.poll() is not None
    job._thread.join(1)
    assert not job._thread.is_alive()


def test_worker_entry_protocol_and_error():
    for failure in (False, True):
        source = MagicMock(buffer=io.BytesIO(pickle.dumps(request())))
        target = MagicMock(buffer=io.BytesIO())
        with patch("sys.stdin", source), patch("sys.stdout", target), patch(
            "ktfigure.preview_worker.render_thumbnail",
            side_effect=ValueError("broken render") if failure else None,
            return_value=b"png",
        ):
            main()
        data = target.buffer.getvalue()
        assert data.startswith(_READY + _RENDERING)
        offset = len(_READY) + len(_RENDERING) + 8
        assert data[offset:].startswith(_FINISHED)
        status, value = pickle.loads(data[offset + len(_FINISHED) + 8:])
        assert (status, value) == (
            ("error", "broken render") if failure else ("ok", b"png")
        )


def test_worker_start_failure_and_crash():
    with patch("ktfigure.preview_worker._command", return_value=["missing-preview-executable"]):
        job = PreviewJob(request())
        assert job.done.wait(3)
        assert job.result[0] == "error"
    with patch("ktfigure.preview_worker._command", return_value=[
        sys.executable, "-c", "import sys; sys.stderr.write('worker crashed'); sys.exit(3)"
    ]):
        job = PreviewJob(request())
        assert job.done.wait(3)
        assert job.result == ("error", "worker crashed")
        assert job._process.poll() == 3


def test_serialization_error_and_expired_request_never_launch():
    bad = request()
    bad["df"] = lambda: None
    job = PreviewJob(bad)
    assert job.done.wait(3)
    assert job.result[0] == "error"
    assert job._process is None

    job = PreviewJob(request(), startup_timeout=0)
    assert job.done.wait(3)
    assert job.result == ("startup_timeout", None)
    assert job._process is None


def test_cancel_during_serialization_prevents_launch():
    entered, release = threading.Event(), threading.Event()
    original = pickle.dumps

    def serialize(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)

    with patch("ktfigure.preview_worker.pickle.dumps", side_effect=serialize):
        job = PreviewJob(request())
        try:
            assert entered.wait(3)
            job.cancel()
        finally:
            release.set()
        assert job.done.wait(3)
    assert job._process is None


def test_invalid_worker_output_and_silent_crash():
    for code, expected in (
        ("print('not a pickle')", "error"),
        ("import sys; sys.exit(1)", "Preview worker exited unexpectedly."),
    ):
        with patch("ktfigure.preview_worker._command", return_value=[
            sys.executable, "-c", code
        ]):
            job = PreviewJob(request())
            assert job.done.wait(3)
            assert job.result[0] == "error"
            if expected != "error":
                assert job.result[1] == expected


def test_render_failure_closes_figure():
    with patch("ktfigure.PlotRenderer._render_to_ax", side_effect=ValueError("broken")), \
         patch("matplotlib.pyplot.close") as close:
        import pytest
        with pytest.raises(ValueError, match="broken"):
            render_thumbnail(request())
        close.assert_called_once()


def test_frozen_command_and_stream_fallback():
    with patch.object(sys, "frozen", True, create=True):
        assert _command() == [sys.executable, "--preview-worker"]
    stream = object()
    with patch("sys.stdin", None), patch("ktfigure.preview_worker.os.name", "posix"), \
         patch("os.fdopen", return_value=stream) as fdopen:
        assert _binary_stream("stdin", 0, "rb") is stream
        fdopen.assert_called_once_with(0, "rb", closefd=False)


def test_cancel_while_process_is_starting():
    from ktfigure import preview_worker

    entered, release = threading.Event(), threading.Event()
    popen = preview_worker.subprocess.Popen

    def start(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return popen(*args, **kwargs)

    with patch("ktfigure.preview_worker.subprocess.Popen", side_effect=start):
        job = PreviewJob(request())
        try:
            assert entered.wait(3)
            job.cancel()
        finally:
            release.set()
        assert job.done.wait(3)
    assert job._process.poll() is not None


def test_communication_failure_kills_worker():
    from ktfigure import preview_worker

    popen = preview_worker.subprocess.Popen

    def start(*args, **kwargs):
        process = popen(*args, **kwargs)
        read = process.stdout.read
        def fail_once(*args, **kwargs):
            process.stdout.read = read
            raise RuntimeError("pipe failed")
        process.stdout.read = fail_once
        return process

    with patch("ktfigure.preview_worker.subprocess.Popen", side_effect=start):
        job = PreviewJob(request())
        assert job.done.wait(3)
    assert job.result == ("error", "pipe failed")
    assert job._process.poll() is not None


def test_slow_startup_does_not_consume_render_budget():
    code = (
        "import time\n"
        "time.sleep(2.3)\n"
        "from ktfigure.preview_worker import main\n"
        "main()\n"
    )
    started = time.monotonic()
    with patch("ktfigure.preview_worker._command", return_value=[sys.executable, "-c", code]):
        job = PreviewJob(request(), startup_timeout=10)
        assert job.done.wait(10)
    assert time.monotonic() - started > 2
    assert job.result[0] == "ok"
    assert job.result[1].startswith(b"\x89PNG")
    assert job._process.poll() == 0


def test_slow_worker_shutdown_does_not_consume_render_budget():
    code = (
        "import time\n"
        "from ktfigure.preview_worker import main\n"
        "main()\n"
        "time.sleep(2.3)\n"
    )
    with patch("ktfigure.preview_worker._command", return_value=[sys.executable, "-c", code]):
        job = PreviewJob(request())
        assert job.done.wait(10)
    assert job.result[0] == "ok"
    assert job._process.poll() == 0


def test_startup_watchdog_kills_hung_worker():
    with patch("ktfigure.preview_worker._command", return_value=[
        sys.executable, "-c", "import time; time.sleep(30)"
    ]):
        job = PreviewJob(request(), startup_timeout=0.5)
        assert job.done.wait(4)
    assert job.result == ("startup_timeout", None)
    assert job._process.poll() is not None


def test_cancel_during_worker_startup():
    with patch("ktfigure.preview_worker._command", return_value=[
        sys.executable, "-c", "import time; time.sleep(30)"
    ]):
        job = PreviewJob(request())
        deadline = time.monotonic() + 3
        while job._process is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert job._process is not None
        job.cancel()
        assert job.done.wait(3)
    assert job._process.poll() is not None
    job._thread.join(1)
    assert not job._thread.is_alive()


def test_finishing_watchdog_kills_hung_worker():
    code = (
        "import sys, time, struct\n"
        f"sys.stdout.buffer.write({_READY!r}); sys.stdout.buffer.flush()\n"
        "sys.stdin.buffer.read()\n"
        f"sys.stdout.buffer.write({_RENDERING!r} + struct.pack('!d', time.monotonic()))\n"
        f"sys.stdout.buffer.write({_FINISHED!r} + struct.pack('!d', time.monotonic()))\n"
        "sys.stdout.buffer.flush()\n"
        "time.sleep(30)\n"
    )
    with patch("ktfigure.preview_worker._command", return_value=[sys.executable, "-c", code]), \
         patch("ktfigure.preview_worker.PREVIEW_FINISH_TIMEOUT", 0.5):
        job = PreviewJob(request())
        assert job.done.wait(4)
    assert job.result == ("finish_timeout", None)
    assert job._process.poll() is not None
