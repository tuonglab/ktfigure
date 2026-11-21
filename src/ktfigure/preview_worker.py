"""Isolated thumbnail rendering and its cancellable subprocess controller."""

import io
import os
import pickle
import subprocess
import sys
import threading
import time


PREVIEW_TIMEOUT = 2.0


def _command():
    if getattr(sys, "frozen", False):
        return [sys.executable, "--preview-worker"]
    return [sys.executable, "-m", "ktfigure.preview_worker"]


class PreviewJob:
    """Run one preview without blocking Tk; cancellation kills its renderer."""

    def __init__(self, request, timeout=PREVIEW_TIMEOUT):
        self.deadline = time.monotonic() + timeout
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
            if time.monotonic() >= self.deadline:
                self.result = ("timeout", None)
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
            try:
                output, errors = process.communicate(
                    payload, timeout=max(0, self.deadline - time.monotonic())
                )
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                self.result = ("timeout", None)
                return
            if self._cancelled:
                return
            if time.monotonic() >= self.deadline:
                self.result = ("timeout", None)
            elif process.returncode:
                detail = errors.decode("utf-8", errors="replace").strip()
                self.result = ("error", detail or "Preview worker exited unexpectedly.")
            else:
                self.result = pickle.loads(output)
        except Exception as exc:
            if not self._cancelled:
                self.result = ("error", str(exc))
        finally:
            try:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.communicate()
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
    try:
        request = pickle.load(_binary_stream("stdin", 0, "rb"))
        result = ("ok", render_thumbnail(request))
    except Exception as exc:
        result = ("error", str(exc))
    output = _binary_stream("stdout", 1, "wb")
    pickle.dump(result, output)
    output.flush()


if __name__ == "__main__":
    main()
