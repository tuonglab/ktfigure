"""Generate illustrative showcase figures from the tutorial's synthetic data.

Run after installing ktfigure: python .github/scripts/generate_showcase_figures.py
The annotations represent the finishing step performed in a vector editor.
"""

from pathlib import Path

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator

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
        font_size=8, xlabel=xlabel, ylabel=ylabel, legend=False, grid=False,
    )
    PlotRenderer.render_to_ax(block, ax, fig)
    for text in ax.texts:
        if text.get_text().startswith("Render error:"):
            raise RuntimeError(text.get_text())
    ax.tick_params(labelsize=7)
    if kind == "histogram":
        ax.xaxis.set_major_locator(MaxNLocator(nbins=3))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4, integer=(kind == "histogram")))


def design(ax, kind):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    if kind == "timecourse":
        lane_colors = ("#0173b2", "#de8f05")
        lane_centers = (.70, .30)
        sample_x = (.40, .60, .80)
        sample_w, sample_h = .16, .20
        group_x, group_w, group_h = .01, .30, .20

        for color, center, group in zip(
            lane_colors, lane_centers, ("Control", "Treatment")
        ):
            group_y = center - group_h / 2
            nodes = [(group_x, group_y, group_w, group_h, group, color)]
            for x, time in zip(sample_x, ("0 h", "24 h", "48 h")):
                nodes.append((x, center - sample_h / 2, sample_w, sample_h, time, color))

            for left, right in zip(nodes, nodes[1:]):
                start = (left[0] + left[2], center)
                end = (right[0], center)
                ax.annotate(
                    "", xy=end, xytext=start,
                    arrowprops={"arrowstyle": "->", "lw": 1, "color": "#25383d",
                                "shrinkA": 0, "shrinkB": 0},
                    zorder=1,
                )

            for x, y, width, height, label, edge in nodes:
                ax.add_patch(Rectangle(
                    (x, y), width, height, facecolor="white", edgecolor=edge,
                    linewidth=1.1, zorder=2,
                ))
                ax.text(
                    x + width / 2, y + height / 2, label, ha="center", va="center",
                    fontsize=6, color="#172d35", zorder=3,
                )
    else:
        boxes = [
            (.20, .79, .60, .16, "Matched datasets"),
            (.20, .56, .60, .16, "QC + processing"),
            (.04, .31, .40, .16, "Method A"),
            (.56, .31, .40, .16, "Method B"),
            (.20, .05, .60, .16, "Score and compare"),
        ]
        color = "#25383d"

        def arrow(start, end):
            ax.annotate(
                "", xy=end, xytext=start,
                arrowprops={
                    "arrowstyle": "->", "lw": 1, "color": color,
                    "shrinkA": 0, "shrinkB": 0,
                },
                zorder=1,
            )

        # A shared input branches into parallel methods, then rejoins for comparison.
        arrow((.50, .79), (.50, .72))
        ax.plot([.50, .50], [.56, .52], color=color, lw=1, zorder=1)
        ax.plot([.24, .76], [.52, .52], color=color, lw=1, zorder=1)
        arrow((.24, .52), (.24, .47))
        arrow((.76, .52), (.76, .47))
        ax.plot([.24, .24], [.31, .26], color=color, lw=1, zorder=1)
        ax.plot([.76, .76], [.31, .26], color=color, lw=1, zorder=1)
        ax.plot([.24, .76], [.26, .26], color=color, lw=1, zorder=1)
        arrow((.50, .26), (.50, .21))

        for x, y, width, height, label in boxes:
            ax.add_patch(Rectangle(
                (x, y), width, height, facecolor="white", edgecolor="#167465",
                linewidth=1.1, zorder=2,
            ))
            ax.text(
                x + width / 2, y + height / 2, label, ha="center", va="center",
                fontsize=6, color="#172d35", linespacing=1.15, zorder=3,
            )


def make_figure(kind, cases):
    fig = plt.figure(figsize=(7.09, 6.2))
    axes = [fig.add_axes([x, y, .22, .28])
            for y in (.60, .16) for x in (.12, .42, .72)]
    design(axes[0], kind)
    for ax, case in zip(axes[1:], cases):
        plot(ax, fig, *case)
    for label, ax in zip("ABCDEF", axes):
        ax.text(-.18, 1.09, label, transform=ax.transAxes,
                fontsize=10, fontweight="bold", va="top", clip_on=False)
    labels = ("Control", "Treatment") if kind == "timecourse" else ("Method A", "Method B")
    handles = [
        Line2D([], [], marker="o", linestyle="none", markersize=5, color=color, label=label)
        for color, label in zip(("#0173b2", "#de8f05"), labels)
    ]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(.94, .985),
               ncol=2, frameon=False, fontsize=7, handletextpad=.4, columnspacing=1.2)
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
        ("timecourse-endpoints.csv", "strip", "group", "endpoint", None, "Group", "48 h response (a.u.)"),
        ("timecourse-endpoints.csv", "scatter", "baseline", "endpoint", "group", "Baseline (a.u.)", "48 h response (a.u.)"),
        ("timecourse-endpoints.csv", "scatter", "biomarker", "change", "group", "Biomarker (a.u.)", "Change (a.u.)"),
        ("timecourse-endpoints.csv", "histogram", "change", None, "group", "Change (a.u.)", "Count"),
    ])
    make_figure("methods", [
        ("methods-benchmark.csv", "strip", "method", "accuracy", None, "Method", "Accuracy (fraction)"),
        ("methods-benchmark.csv", "scatter", "runtime_min", "accuracy", "method", "Runtime (min)", "Accuracy (fraction)"),
        ("methods-benchmark.csv", "box", "method", "runtime_min", None, "Method", "Runtime (min)"),
        ("methods-benchmark.csv", "scatter", "agreement", "accuracy", "method", "Agreement (fraction)", "Accuracy (fraction)"),
        ("methods-benchmark.csv", "histogram", "accuracy", None, "method", "Accuracy (fraction)", "Count"),
    ])


if __name__ == "__main__":
    main()
