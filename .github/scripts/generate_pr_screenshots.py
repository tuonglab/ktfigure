"""Generate representative plot screenshots for the automated PR comment.

Run this script under xvfb-run on Linux (ktfigure imports tkinter at the
module level, so a virtual display is required even when only using the
non-interactive Agg matplotlib backend for rendering).

Usage:
    xvfb-run --auto-servernum python .github/scripts/generate_pr_screenshots.py
"""
import os
import sys

# Force the non-interactive Agg backend BEFORE any other matplotlib import.
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib  # noqa: E402
matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# Allow running from the repo root without an installed package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from ktfigure import PlotBlock, PlotRenderer, default_aesthetics  # noqa: E402

# ── sample data ──────────────────────────────────────────────────────────────
DPI = 96
OUT = os.environ.get("SCREENSHOT_DIR", "/tmp/pr_screenshots")
os.makedirs(OUT, exist_ok=True)

rng = np.random.default_rng(42)
n = 80
df = pd.DataFrame(
    {
        "x": rng.uniform(0, 10, n),
        "y": rng.uniform(0, 10, n) + rng.normal(0, 1, n),
        "category": rng.choice(["Group A", "Group B", "Group C"], n),
    }
)


# ── helper ────────────────────────────────────────────────────────────────────
def make_block(plot_type, col_x, col_y=None, col_hue=None, **aesthetics):
    b = PlotBlock(0, 0, DPI * 5, DPI * 4)
    b.df = df
    b.plot_type = plot_type
    b.col_x = col_x
    b.col_y = col_y
    b.col_hue = col_hue
    # Start from defaults so required keys like 'style' are always present.
    aes = default_aesthetics()
    aes.update(aesthetics)
    b.aesthetics = aes
    return b


# ── screenshots ───────────────────────────────────────────────────────────────
SCREENSHOTS = [
    (
        "legend_inside.png",
        "Scatter – legend **inside** axes (legend re-render fix)",
        make_block(
            "scatter", "x", "y", col_hue="category",
            title="Scatter – legend inside",
            legend=True, legend_outside=False,
            xlabel="X", ylabel="Y",
        ),
    ),
    (
        "legend_outside.png",
        "Scatter – legend **outside** axes",
        make_block(
            "scatter", "x", "y", col_hue="category",
            title="Scatter – legend outside",
            legend=True, legend_outside=True,
            xlabel="X", ylabel="Y",
        ),
    ),
    (
        "box_plot.png",
        "Box plot",
        make_block(
            "box", "category", "y",
            title="Box plot", xlabel="Category", ylabel="Y",
        ),
    ),
    (
        "violin_plot.png",
        "Violin plot",
        make_block(
            "violin", "category", "y",
            title="Violin plot", xlabel="Category", ylabel="Y",
        ),
    ),
]

failures = []
for fname, caption, block in SCREENSHOTS:
    try:
        fig = PlotRenderer.render(block)
        out_path = os.path.join(OUT, fname)
        fig.savefig(out_path, dpi=120, bbox_inches="tight")
        print(f"  ✓ {out_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ {fname}: {exc}", file=sys.stderr)
        failures.append(fname)

if failures:
    print(f"\n{len(failures)} screenshot(s) failed to generate.", file=sys.stderr)
    sys.exit(1)

print(f"\nAll {len(SCREENSHOTS)} screenshots saved to {OUT}/")
