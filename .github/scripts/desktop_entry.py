"""Entry point for the standalone desktop builds."""
import io
import sys
import time
import tkinter as tk

if __name__ == "__main__" and sys.argv[1:] == ["--preview-worker"]:
    from ktfigure.preview_worker import main as preview_worker_main

    preview_worker_main()
    sys.exit(0)

import pandas as pd
from PIL import Image, ImageTk

from ktfigure import KTFigure, PlotBlock, PlotConfigDialog, PlotRenderer, main


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
        dialog = PlotConfigDialog(root, block)
        try:
            dialog._update_preview()
            deadline = time.monotonic() + 5
            while dialog._preview_job is not None and time.monotonic() < deadline:
                root.update()
                time.sleep(0.01)
            if dialog._preview_photo is None:
                raise RuntimeError(
                    "Isolated thumbnail failed: " + dialog._preview_lbl.cget("text")
                )
        finally:
            dialog.destroy()
        if root.title() != "ktfigure" or app.root != root:
            raise RuntimeError("Application window did not initialize")
    finally:
        root.destroy()


if __name__ == "__main__":
    if sys.argv[1:] == ["--smoke-test"]:
        smoke_test()
    else:
        main()
