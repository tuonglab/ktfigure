"""Generate matplotlib plot screenshots for the automated PR comment.

Run this script under xvfb-run on Linux (ktfigure imports tkinter at the
module level, so a virtual display is required even when only using the
non-interactive Agg matplotlib backend for rendering).

Usage:
    xvfb-run --auto-servernum python .github/scripts/generate_pr_screenshots.py

Note: KTFigure application window screenshots (showing the grid/snap feature)
are committed directly to the repository under docs/screenshots/ and are
referenced in the PR comment via raw.githubusercontent.com URLs — no dynamic
upload is needed for those images.  This script only generates the matplotlib
plot renders (scatter, box, violin, etc.).
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

import json  # noqa: E402 – stdlib, placed here to keep imports together
import traceback  # noqa: E402

manifest = []
failures = []
for fname, caption, block in SCREENSHOTS:
    out_path = os.path.join(OUT, fname)
    try:
        fig = PlotRenderer.render(block)
        fig.savefig(out_path, dpi=120, bbox_inches="tight")
        manifest.append({"file": fname, "path": out_path, "label": caption})
        print(f"  ✓ {out_path}")
    except Exception:  # noqa: BLE001
        print(f"  ✗ {fname} ({caption}):", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        failures.append(fname)

manifest_path = os.path.join(OUT, "manifest.json")
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"  ✓ manifest written to {manifest_path}")

if failures:
    print(f"\n{len(failures)} screenshot(s) failed to generate.", file=sys.stderr)
    sys.exit(1)

print(f"\nAll {len(SCREENSHOTS)} matplotlib plot screenshots saved to {OUT}/")
