"""Entry point for the standalone desktop builds."""
import io
import sys
import tkinter as tk

import pandas as pd
from PIL import Image, ImageTk

from ktfigure import KTFigure, PlotBlock, PlotRenderer, main
from ktfigure.gpu_preview import run_file, show_preview


def smoke_test():
    root = tk.Tk()
    try:
        app = KTFigure(root)
        root.update()
        icon = ImageTk.PhotoImage(Image.new("RGB", (1, 1)))
        if not str(icon):
            raise RuntimeError("Tk image support did not initialize")
        block = PlotBlock(0, 0, 384, 288)
        block.df = pd.read_csv(io.StringIO("x,y\n1,2\n2,3\n"))
        block.plot_type = "scatter"
        block.col_x = "x"
        block.col_y = "y"
        figure = PlotRenderer.render(block)
        output = io.BytesIO()
        figure.savefig(output, format="png")
        if not output.getvalue().startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Plot export did not produce a PNG")
        if root.title() != "ktfigure" or app.root != root:
            raise RuntimeError("Application window did not initialize")
    finally:
        root.destroy()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--gpu-preview":
        run_file(sys.argv[2])
    elif sys.argv[1:] == ["--gpu-import-test"]:
        from vispy import app

        app.use_app("glfw")
    elif len(sys.argv) == 3 and sys.argv[1] == "--gpu-smoke-test":
        import contextlib
        import traceback

        with open(sys.argv[2], "w", encoding="utf-8", buffering=1) as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                try:
                    import numpy as np
                    from vispy import app

                    app.use_app("glfw")
                    timer = app.Timer(interval=1, connect=lambda event: app.quit(), start=True)
                    show_preview(np.array([[0.0, 0.0], [1.0, 1.0]]), "x", "y", 0)
                except Exception:
                    traceback.print_exc()
                    sys.exit(1)
    elif sys.argv[1:] == ["--smoke-test"]:
        smoke_test()
    else:
        main()
