"""Entry point for the standalone desktop builds."""
import io
import sys
import tkinter as tk

import pandas as pd
from PIL import Image, ImageTk

from ktfigure import KTFigure, PlotBlock, PlotRenderer, main


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
    if sys.argv[1:] == ["--smoke-test"]:
        smoke_test()
    else:
        main()
