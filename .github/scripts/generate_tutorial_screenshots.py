"""Generate the tutorial screenshots from the example data.

On Linux, run with a virtual display:
    xvfb-run -a -s "-screen 0 1600x1000x24" python .github/scripts/generate_tutorial_screenshots.py
"""

from pathlib import Path
import tkinter as tk

import pandas as pd
from PIL import ImageGrab

from ktfigure import KTFigure, PlotBlock, PlotConfigDialog


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "images"


def capture(widget, name):
    widget.update()
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    box = (x, y, x + widget.winfo_width(), y + widget.winfo_height())
    ImageGrab.grab(bbox=box).save(OUTPUT / name)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = KTFigure(root)
    root.geometry("1280x900+0+0")
    if app._is_dark:
        app._on_theme_click()
    app._theme_manual_override = True
    root.update()

    block = PlotBlock(50, 50, 710, 480)
    block.df = pd.read_csv(ROOT / "example_data.csv")
    block.plot_type = "scatter"
    block.col_x = "temperature"
    block.col_y = "sales"
    block.col_hue = "season"

    dialog = PlotConfigDialog(root, block)
    dialog._filename.set("example_data.csv  (16 rows × 4 cols)")
    dialog._nb.select(1)
    dialog._update_preview()
    capture(dialog, "configure-scatter.png")
    dialog.destroy()

    block.aesthetics.update(
        title="Sales and temperature",
        xlabel="Temperature (°C)",
        ylabel="Sales",
        palette="colorblind",
        style="whitegrid",
    )
    app._blocks.append(block)
    app._draw_empty_block(block)
    app._render_block(block)
    app._select_block(block)
    capture(root, "styled-scatter.png")

    block.plot_type = "box"
    block.col_x = "season"
    block.col_hue = None
    block.aesthetics.update(
        title="Sales by season",
        xlabel="Season",
        ylabel="Sales",
    )
    app._render_block(block)
    app._select_block(block)
    capture(root, "season-box.png")
    root.destroy()


if __name__ == "__main__":
    main()
