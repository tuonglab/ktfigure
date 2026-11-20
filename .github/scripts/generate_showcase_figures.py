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
        ax.text(.5, .96, "Cohort and sampling", fontsize=6.5, ha="center", va="top")
        lane_colors = ("#0173b2", "#de8f05")
        lane_centers = (.70, .31)
        sample_x = (.34, .55, .76)
        sample_w, sample_h = .17, .20
        group_x, group_w, group_h = .02, .22, .20

        for color, center, group in zip(
            lane_colors, lane_centers, ("Control\nvehicle", "Treatment\nagent")
        ):
            group_y = center - group_h / 2
            nodes = [(group_x, group_y, group_w, group_h, group, color)]
            for x, time in zip(sample_x, ("0 h\nsample", "24 h\nsample", "48 h\nsample")):
                nodes.append((x, center - sample_h / 2, sample_w, sample_h, time, color))

            for left, right in zip(nodes, nodes[1:]):
                start = (left[0] + left[2], center)
                end = (right[0], center)
                ax.annotate(
                    "", xy=end, xytext=start,
                    arrowprops={"arrowstyle": "->", "lw": 1, "color": "#25383d"},
                    zorder=1,
                )

            for x, y, width, height, label, edge in nodes:
                ax.add_patch(Rectangle(
                    (x, y), width, height, facecolor="white", edgecolor=edge,
                    linewidth=1.1, zorder=2,
                ))
                ax.text(
                    x + width / 2, y + height / 2, label, ha="center", va="center",
                    fontsize=6.2, color="#172d35", linespacing=1.15, zorder=3,
                )
    else:
        ax.text(.5, .96, "Analysis pipeline", fontsize=6.5, ha="center", va="top")
        boxes = [
            (.02, .39, .14, .22, "Matched\ndatasets"),
            (.21, .39, .17, .22, "QC +\nprocessing"),
            (.42, .67, .15, .20, "Method A"),
            (.42, .13, .15, .20, "Method B"),
            (.63, .67, .15, .20, "Score\nruns"),
            (.63, .13, .15, .20, "Score\nruns"),
            (.84, .34, .15, .32, "Compare\nmatched runs"),
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
        arrow((.16, .50), (.21, .50))
        ax.plot([.38, .40], [.50, .50], color=color, lw=1, zorder=1)
        ax.plot([.40, .40], [.23, .77], color=color, lw=1, zorder=1)
        arrow((.40, .77), (.42, .77))
        arrow((.40, .23), (.42, .23))
        arrow((.57, .77), (.63, .77))
        arrow((.57, .23), (.63, .23))
        ax.plot([.78, .80], [.77, .77], color=color, lw=1, zorder=1)
        ax.plot([.78, .80], [.23, .23], color=color, lw=1, zorder=1)
        ax.plot([.80, .80], [.23, .77], color=color, lw=1, zorder=1)
        arrow((.80, .50), (.84, .50))

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
    grid = fig.add_gridspec(3, 4)
    axes = [
        fig.add_subplot(grid[0, :]),
        fig.add_subplot(grid[1, 0]),
        fig.add_subplot(grid[1, 1]),
        fig.add_subplot(grid[1, 2]),
        fig.add_subplot(grid[2, :2]),
        fig.add_subplot(grid[2, 2:]),
    ]
    fig.subplots_adjust(left=.09, right=.97, bottom=.07, top=.94, wspace=.75, hspace=.8)
    design(axes[0], kind)
    for ax, case in zip(axes[1:], cases):
        plot(ax, fig, *case)
    for label, ax in zip("ABCDEF", axes):
        label_x = -.01 if label == "A" else -.16
        ax.text(label_x, 1.10, label, transform=ax.transAxes,
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
