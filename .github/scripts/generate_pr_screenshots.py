"""Capture KTFigure GUI screenshots for the automated PR comment.

Opens the KTFigure application once, draws a few shapes and plot blocks,
then takes two screenshots inside the same Tk session — one with the grid
hidden and one with the dot-grid overlay visible.

Run under xvfb-run on Linux:
    xvfb-run --auto-servernum python .github/scripts/generate_pr_screenshots.py

Screenshots are written to SCREENSHOT_DIR (default /tmp/pr_screenshots).
"""
import json
import os
import subprocess
import sys
import time
import traceback

OUT = os.environ.get("SCREENSHOT_DIR", "/tmp/pr_screenshots")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# Import tkinter and ktfigure
# ---------------------------------------------------------------------------
try:
    import tkinter as tk
except ImportError as exc:
    print(f"tkinter not available: {exc}", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
from ktfigure import KTFigure, PlotBlock, Shape  # noqa: E402


def _pump(root: "tk.Tk", n: int = 30) -> None:
    for _ in range(n):
        root.update()


def _scrot(output_path: str) -> bool:
    """Take a full-screen screenshot with scrot."""
    try:
        subprocess.run(
            ["scrot", "--quality", "90", output_path],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  ⚠ scrot failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Open one Tk session and take both screenshots inside it
# ---------------------------------------------------------------------------
manifest = []
failures = []

try:
    root = tk.Tk()
except tk.TclError as exc:
    print(f"Could not open display: {exc}", file=sys.stderr)
    sys.exit(1)

try:
    root.geometry("1280x860")
    app = KTFigure(root)

    # draw a couple of plot-block placeholders
    for coords in [(40, 60, 420, 360), (460, 60, 840, 360)]:
        b = PlotBlock(*coords)
        app._blocks.append(b)
        app._draw_empty_block(b)

    # draw some shapes so the canvas looks interesting
    for x1, y1, x2, y2, stype in [
        (100, 420, 380, 600, "rectangle"),
        (420, 420, 700, 600, "circle"),
        (740, 420, 1000, 600, "line"),
    ]:
        s = Shape(x1, y1, x2, y2, stype)
        app._shapes.append(s)
        app._draw_shape(s)

    # raise the window and paint everything
    _pump(root, 50)
    root.deiconify()
    root.lift()
    root.focus_force()
    _pump(root, 30)
    time.sleep(0.3)
    _pump(root, 10)

    # ── screenshot 1: grid hidden ──────────────────────────────────────────
    path1 = os.path.join(OUT, "gui_grid_hidden.png")
    if _scrot(path1):
        manifest.append({"file": "gui_grid_hidden.png", "path": path1, "label": "KTFigure – snap ON, grid hidden"})
        print(f"  ✓ {path1}")
    else:
        failures.append("gui_grid_hidden.png")

    # ── screenshot 2: grid visible ─────────────────────────────────────────
    app._toggle_grid_visible()
    _pump(root, 20)
    time.sleep(0.2)
    _pump(root, 10)

    path2 = os.path.join(OUT, "gui_grid_visible.png")
    if _scrot(path2):
        manifest.append({"file": "gui_grid_visible.png", "path": path2, "label": "KTFigure – snap ON, grid visible"})
        print(f"  ✓ {path2}")
    else:
        failures.append("gui_grid_visible.png")

except Exception:
    traceback.print_exc(file=sys.stderr)
    failures.append("unexpected error")
finally:
    try:
        root.destroy()
    except Exception:
        pass

manifest_path = os.path.join(OUT, "manifest.json")
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"  ✓ manifest → {manifest_path}")

if failures:
    print(f"\n{len(failures)} screenshot(s) failed.", file=sys.stderr)
    sys.exit(1)

print(f"\nAll screenshots saved to {OUT}/")
