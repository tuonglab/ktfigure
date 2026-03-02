"""Capture KTFigure GUI screenshots for the automated PR comment.

Opens the KTFigure application, draws a few shapes and plot blocks on the
canvas, then takes two screenshots — one with the grid hidden and one with
the dot-grid overlay visible.

Run under xvfb-run on Linux:
    xvfb-run --auto-servernum python .github/scripts/generate_pr_screenshots.py

Screenshots are written to SCREENSHOT_DIR (default /tmp/pr_screenshots).
"""
import json
import os
import subprocess
import sys
import time
import tkinter as tk
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from ktfigure import KTFigure, PlotBlock, Shape  # noqa: E402

OUT = os.environ.get("SCREENSHOT_DIR", "/tmp/pr_screenshots")
os.makedirs(OUT, exist_ok=True)


def capture_gui(output_path: str, *, show_grid: bool = False) -> bool:
    """Open KTFigure, populate the canvas, take a screenshot with scrot."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"  ⚠ No display: {exc}", file=sys.stderr)
        return False

    root.geometry("1280x860")
    app = KTFigure(root)

    # --- draw a couple of plot-block placeholders ---
    for coords in [(40, 60, 420, 360), (460, 60, 840, 360)]:
        b = PlotBlock(*coords)
        app._blocks.append(b)
        app._draw_empty_block(b)

    # --- draw some shapes so the canvas looks interesting ---
    shapes = [
        (100, 420, 380, 600, "rectangle"),
        (420, 420, 700, 600, "circle"),
        (740, 420, 1000, 600, "line"),
    ]
    for x1, y1, x2, y2, stype in shapes:
        s = Shape(x1, y1, x2, y2, stype)
        app._shapes.append(s)
        app._draw_shape(s)

    if show_grid:
        app._toggle_grid_visible()

    # pump events so everything is painted
    for _ in range(50):
        root.update()
    root.deiconify()
    root.lift()
    root.focus_force()
    for _ in range(30):
        root.update()
    time.sleep(0.3)
    for _ in range(10):
        root.update()

    try:
        subprocess.run(
            ["scrot", "--quality", "90", output_path],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  ⚠ scrot failed: {exc}", file=sys.stderr)
        root.destroy()
        return False

    root.destroy()
    return True


SCENARIOS = [
    ("gui_grid_hidden.png", "KTFigure – snap ON, grid hidden", False),
    ("gui_grid_visible.png", "KTFigure – snap ON, grid visible", True),
]

manifest = []
failures = []

for fname, label, show_grid in SCENARIOS:
    out_path = os.path.join(OUT, fname)
    try:
        ok = capture_gui(out_path, show_grid=show_grid)
        if ok:
            manifest.append({"file": fname, "path": out_path, "label": label})
            print(f"  ✓ {out_path}")
        else:
            failures.append(fname)
    except Exception:
        print(f"  ✗ {fname}:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        failures.append(fname)

manifest_path = os.path.join(OUT, "manifest.json")
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"  ✓ manifest → {manifest_path}")

if failures:
    print(f"\n{len(failures)} screenshot(s) failed.", file=sys.stderr)
    sys.exit(1)

print(f"\nAll screenshots saved to {OUT}/")
