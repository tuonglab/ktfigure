"""Generate GUI screenshots for the automated PR comment.

Run this script under xvfb-run on Linux (ktfigure imports tkinter at the
module level, so a virtual display is required even when only using the
non-interactive Agg matplotlib backend for rendering).

Usage:
    xvfb-run --auto-servernum python .github/scripts/generate_pr_screenshots.py

Generated files are written to SCREENSHOT_DIR (default /tmp/pr_screenshots)
and are uploaded directly to the GitHub PR comment — no files are committed
to the repository.
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

from ktfigure import KTFigure, PlotBlock, PlotRenderer, Shape, default_aesthetics  # noqa: E402

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


# ── Tk GUI screenshots ────────────────────────────────────────────────────────

def _capture_tk_gui(output_path, show_grid=True):
    """Launch KTFigure, optionally show the grid, and capture a screenshot.

    Requires a running X display (xvfb) and ``scrot`` to be installed.
    Returns True on success, False if the display or scrot is unavailable.
    """
    import subprocess
    import time
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"  ⚠ No display available for Tk GUI screenshot: {exc}", file=sys.stderr)
        return False

    root.geometry("1280x860")
    app = KTFigure(root)

    # Add a placeholder plot block
    b = PlotBlock(40, 40, 380, 300)
    app._blocks.append(b)
    app._draw_empty_block(b)

    # Add a couple of shapes so the canvas looks interesting
    for args in [
        (420, 60, 680, 220, "rectangle"),
        (60, 340, 380, 540, "circle"),
    ]:
        s = Shape(*args)
        app._shapes.append(s)
        app._draw_shape(s)

    # Enable / disable grid according to the scenario
    if show_grid:
        app._toggle_grid_visible()

    # Pump events so the window is fully painted
    for _ in range(40):
        root.update()
    root.deiconify()
    root.lift()
    root.focus_force()
    for _ in range(30):
        root.update()
    time.sleep(0.4)
    for _ in range(10):
        root.update()

    # Capture the full virtual display (= the KTFigure window on xvfb)
    try:
        subprocess.run(
            ["scrot", "--quality", "90", output_path],
            check=True, capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  ⚠ scrot unavailable, skipping GUI screenshot: {exc}", file=sys.stderr)
        root.destroy()
        return False

    root.destroy()
    return True


GUI_SCREENSHOTS = [
    (
        "gui_grid_off.png",
        "KTFigure GUI – default state (snap ON, grid hidden)",
        False,
    ),
    (
        "gui_grid_on.png",
        "KTFigure GUI – grid overlay visible + snap ON",
        True,
    ),
]

for fname, caption, show_grid in GUI_SCREENSHOTS:
    out_path = os.path.join(OUT, fname)
    try:
        ok = _capture_tk_gui(out_path, show_grid=show_grid)
        if ok:
            manifest.append({"file": fname, "path": out_path, "label": caption})
            print(f"  ✓ {out_path}")
        else:
            print(f"  ⚠ {fname} skipped (no display / scrot missing)", file=sys.stderr)
    except Exception:  # noqa: BLE001
        print(f"  ✗ {fname} ({caption}):", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        # GUI screenshot failures are non-blocking


manifest_path = os.path.join(OUT, "manifest.json")
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"  ✓ manifest written to {manifest_path}")

if failures:
    print(f"\n{len(failures)} screenshot(s) failed to generate.", file=sys.stderr)
    sys.exit(1)

print(f"\nAll screenshots saved to {OUT}/")
