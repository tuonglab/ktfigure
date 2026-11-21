"""Isolated thumbnail rendering and its cancellable subprocess controller."""

import io
import os
import pickle
import struct
import subprocess
import sys
import threading
import time


PREVIEW_TIMEOUT = 2.0
PREVIEW_STARTUP_TIMEOUT = 45.0
PREVIEW_FINISH_TIMEOUT = 10.0
_READY = b"KTFREADY\n"
_RENDERING = b"KTFRENDER"
_FINISHED = b"KTFFINISH"


def _command():
    if getattr(sys, "frozen", False):
        return [sys.executable, "--preview-worker"]
    return [sys.executable, "-m", "ktfigure.preview_worker"]


class PreviewJob:
    """Run one preview without blocking Tk; cancellation kills its renderer."""

    def __init__(self, request, timeout=PREVIEW_TIMEOUT,
                 startup_timeout=PREVIEW_STARTUP_TIMEOUT):
        self.timing = ("startup", time.monotonic() + startup_timeout)
        self._timeout = timeout
        self.result = None
        self.done = threading.Event()
        self._cancelled = False
        self._process = None
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, args=(request,), daemon=True)
        self._thread.start()

    def cancel(self):
        with self._lock:
            self._cancelled = True
            if self._process is not None and self._process.poll() is None:
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass

    def _run(self, request):
        process = None
        try:
            if request["plot_type"] == "scatter" and len(request["df"]) > 20000:
                request = dict(request)
                request["df"] = request["df"].sample(n=20000, random_state=0)
            payload = pickle.dumps(request, protocol=pickle.HIGHEST_PROTOCOL)
            if self._cancelled:
                return
            if time.monotonic() >= self.timing[1]:
                self.result = ("startup_timeout", None)
                return
            env = os.environ.copy()
            if not getattr(sys, "frozen", False):
                package_root = os.path.dirname(os.path.dirname(__file__))
                env["PYTHONPATH"] = os.pathsep.join(
                    [package_root, env.get("PYTHONPATH", "")]
                )
            process = subprocess.Popen(
                _command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                self._process = process
                if self._cancelled:
                    process.kill()
            exchange_done = threading.Event()
            response = {}
            errors = bytearray()

            def read_errors():
                for chunk in iter(lambda: process.stderr.read(4096), b""):
                    if len(errors) < 65536:
                        errors.extend(chunk[:65536 - len(errors)])

            def exchange():
                try:
                    if process.stdout.read(len(_READY)) != _READY:
                        raise RuntimeError("Preview worker did not signal readiness.")
                    process.stdin.write(payload)
                    process.stdin.close()
                    header = process.stdout.read(len(_RENDERING) + 8)
                    if len(header) != len(_RENDERING) + 8 or not header.startswith(_RENDERING):
                        raise RuntimeError("Preview worker did not start rendering.")
                    started = struct.unpack("!d", header[len(_RENDERING):])[0]
                    self.timing = ("render", started + self._timeout)
                    header = process.stdout.read(len(_FINISHED) + 8)
                    if len(header) != len(_FINISHED) + 8 or not header.startswith(_FINISHED):
                        raise RuntimeError("Preview worker did not finish rendering.")
                    finished = struct.unpack("!d", header[len(_FINISHED):])[0]
                    response["render_finished"] = finished
                    if finished <= started + self._timeout:
                        self.timing = ("finishing", time.monotonic() + PREVIEW_FINISH_TIMEOUT)
                    response["output"] = process.stdout.read()
                    process.wait()
                except Exception as exc:
                    response["error"] = exc
                finally:
                    exchange_done.set()

            stderr_thread = threading.Thread(target=read_errors, daemon=True)
            io_thread = threading.Thread(target=exchange, daemon=True)
            stderr_thread.start()
            io_thread.start()
            expired = None
            while not exchange_done.wait(0.02):
                phase, deadline = self.timing
                if time.monotonic() >= deadline:
                    expired = {
                        "render": "timeout", "startup": "startup_timeout",
                        "finishing": "finish_timeout",
                    }[phase]
                    process.kill()
                    break
            killed_for_error = process.poll() is None and "error" in response
            if process.poll() is None and (expired or killed_for_error):
                process.kill()
            process.wait()
            io_thread.join()
            stderr_thread.join()
            if expired:
                self.result = (expired, None)
                return
            if self._cancelled:
                return
            if (self.timing[0] == "render"
                    and response.get("render_finished", 0) > self.timing[1]):
                self.result = ("timeout", None)
            elif killed_for_error:
                self.result = ("error", str(response["error"]))
            elif process.returncode:
                detail = errors.decode("utf-8", errors="replace").strip()
                self.result = ("error", detail or "Preview worker exited unexpectedly.")
            elif "error" in response:
                self.result = ("error", str(response["error"]))
            else:
                self.result = pickle.loads(response["output"])
        except Exception as exc:
            if not self._cancelled:
                self.result = ("error", str(exc))
        finally:
            try:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()
                if process is not None:
                    for stream in (process.stdin, process.stdout, process.stderr):
                        if stream is not None and not stream.closed:
                            stream.close()
            finally:
                self.done.set()


def render_thumbnail(request):
    """Render the regular Matplotlib thumbnail and return PNG bytes."""
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    from ktfigure import PlotBlock, PlotRenderer

    width, height, dpi = request["width"], request["height"], request["dpi"]
    block = PlotBlock(0, 0, width, height)
    block.df = request["df"]
    block.plot_type = request["plot_type"]
    if block.plot_type == "scatter" and len(block.df) > 20000:
        block.df = block.df.sample(n=20000, random_state=0)
    block.col_x = request["col_x"]
    block.col_y = request["col_y"]
    block.col_hue = request["col_hue"]
    block.col_size = request["col_size"]
    fig = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    try:
        ax = fig.add_subplot(111)
        PlotRenderer._render_to_ax(block, ax, fig, raise_errors=True)
        output = io.BytesIO()
        fig.savefig(output, format="png", dpi=dpi)
        return output.getvalue()
    finally:
        plt.close(fig)


def _binary_stream(name, fd, mode):
    stream = getattr(sys, name)
    if stream is not None:
        return stream.buffer
    # Windowed PyInstaller builds can replace Python's standard streams with
    # None even when the subprocess inherited redirected Windows handles.
    if os.name == "nt":
        import ctypes
        import msvcrt

        get_handle = ctypes.windll.kernel32.GetStdHandle
        get_handle.restype = ctypes.c_void_p
        handle = get_handle(-10 if fd == 0 else -11)
        flags = os.O_BINARY | (os.O_RDONLY if fd == 0 else os.O_WRONLY)
        fd = msvcrt.open_osfhandle(handle, flags)
    return os.fdopen(fd, mode, closefd=False)


def main():
    # Imports are complete before readiness; input transfer and unpickling are
    # covered by the startup watchdog, not the rendering budget.
    output = _binary_stream("stdout", 1, "wb")
    output.write(_READY)
    output.flush()
    try:
        request = pickle.load(_binary_stream("stdin", 0, "rb"))
        output.write(_RENDERING + struct.pack("!d", time.monotonic()))
        output.flush()
        result = ("ok", render_thumbnail(request))
    except Exception as exc:
        if "request" not in locals():
            output.write(_RENDERING + struct.pack("!d", time.monotonic()))
        result = ("error", str(exc))
    output.write(_FINISHED + struct.pack("!d", time.monotonic()))
    pickle.dump(result, output)
    output.flush()


if __name__ == "__main__":
    main()
