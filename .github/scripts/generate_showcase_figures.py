"""Generate illustrative showcase figures from the tutorial's synthetic data.

Run after installing ktfigure: python .github/scripts/generate_showcase_figures.py
The annotations represent the finishing step performed in a vector editor.
"""

from pathlib import Path

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle

from ktfigure import PlotBlock, PlotRenderer


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "data"
OUTPUT = ROOT / "docs" / "images"


def plot(ax, fig, file, kind, x, y, hue, xlabel, ylabel):
    block = PlotBlock(0, 0, 300, 240)
    block.df = pd.read_csv(DATA / file)
    block.plot_type, block.col_x, block.col_y, block.col_hue = kind, x, y, hue
    block.aesthetics.update(
        style="white", palette="colorblind", font_family="DejaVu Sans",
        font_size=8, xlabel=xlabel, ylabel=ylabel, legend=bool(hue),
        legend_outside=False, legend_loc="best", grid=False,
    )
    PlotRenderer.render_to_ax(block, ax, fig)
    for text in ax.texts:
        if text.get_text().startswith("Render error:"):
            raise RuntimeError(text.get_text())
    ax.tick_params(labelsize=7)
    legend = ax.get_legend()
    if legend:
        legend.set_title(None)
        for text in legend.get_texts():
            text.set_fontsize(7)


def design(ax, kind):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    if kind == "timecourse":
        ax.text(.05, .85, "Control", fontsize=8)
        ax.text(.05, .62, "Treatment", fontsize=8)
        ax.annotate("", xy=(.93, .3), xytext=(.15, .3),
                    arrowprops={"arrowstyle": "->", "lw": 1})
        for x, label in ((.22, "0"), (.52, "24"), (.82, "48 h")):
            ax.plot([x, x], [.27, .33], color="black", lw=1)
            ax.text(x, .18, label, fontsize=8, ha="center")
            ax.plot([x, x], [.62, .85], "o", color="#0173b2", markersize=3)
        ax.text(.05, .03, "Response measured at each time", fontsize=7)
    else:
        boxes = [
            (.03, .41, .25, .20, "Input\n datasets"),
            (.38, .68, .25, .20, "Method A"),
            (.38, .14, .25, .20, "Method B"),
            (.73, .41, .25, .20, "Evaluation"),
        ]
        for x, y, w, h, label in boxes:
            ax.add_patch(Rectangle((x, y), w, h, fill=False, lw=1))
            ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=7)
        for start, end in (((.28, .51), (.38, .78)), ((.28, .51), (.38, .24)),
                           ((.63, .78), (.73, .51)), ((.63, .24), (.73, .51))):
            ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "lw": 1})


def make_figure(kind, cases):
    fig, axes = plt.subplots(2, 3, figsize=(7.09, 5.1))
    fig.subplots_adjust(left=.09, right=.97, bottom=.10, top=.92, wspace=.55, hspace=.65)
    design(axes.flat[0], kind)
    for ax, case in zip(axes.flat[1:], cases):
        plot(ax, fig, *case)
    for label, ax in zip("ABCDEF", axes.flat):
        ax.text(-.16, 1.10, label, transform=ax.transAxes,
                fontsize=10, fontweight="bold", va="top", clip_on=False)
    path = OUTPUT / f"showcase-{kind}.svg"
    fig.savefig(path, format="svg")
    path.write_text(
        "\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n"
    )
    plt.close(fig)


def main():
    np.random.seed(42)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    make_figure("timecourse", [
        ("timecourse.csv", "line", "time_h", "response", "group", "Time (h)", "Response (a.u.)"),
        ("timecourse-endpoints.csv", "strip", "group", "endpoint", None, "", "48 h response (a.u.)"),
        ("timecourse-endpoints.csv", "scatter", "baseline", "endpoint", "group", "Baseline (a.u.)", "48 h response (a.u.)"),
        ("timecourse-endpoints.csv", "scatter", "biomarker", "change", "group", "Biomarker (a.u.)", "Change (a.u.)"),
        ("timecourse-endpoints.csv", "histogram", "change", None, "group", "Change (a.u.)", "Count"),
    ])
    make_figure("methods", [
        ("methods-benchmark.csv", "strip", "method", "accuracy", None, "", "Accuracy (fraction)"),
        ("methods-benchmark.csv", "scatter", "runtime_min", "accuracy", "method", "Runtime (min)", "Accuracy (fraction)"),
        ("methods-benchmark.csv", "box", "method", "runtime_min", None, "", "Runtime (min)"),
        ("methods-benchmark.csv", "scatter", "agreement", "accuracy", "method", "Agreement (fraction)", "Accuracy (fraction)"),
        ("methods-benchmark.csv", "histogram", "accuracy", None, "method", "Accuracy (fraction)", "Count"),
    ])


if __name__ == "__main__":
    main()
