"""Capture KTFigure GUI screenshots for the automated PR comment.

Opens the KTFigure application, loads example_data.csv, renders a randomly
chosen plot (boxplot, violinplot, or scatterplot) inside a PlotBlock, adds
one small circle, one large circle, and one rectangle in different parts of
the artboard, then captures everything in a single screenshot.

Run under xvfb-run on Linux:
    xvfb-run --auto-servernum python .github/scripts/generate_pr_screenshots.py

Screenshots are written to SCREENSHOT_DIR (default /tmp/pr_screenshots).
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import time
import traceback

OUT = os.environ.get("SCREENSHOT_DIR", "/tmp/pr_screenshots")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# Locate repo root (two levels above this script)
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CSV_PATH = os.path.join(REPO_ROOT, "example_data.csv")

# ---------------------------------------------------------------------------
# Import tkinter and ktfigure
# ---------------------------------------------------------------------------
try:
    import tkinter as tk
except ImportError as exc:
    print(f"tkinter not available: {exc}", file=sys.stderr)
    sys.exit(1)

try:
    import pandas as pd
except ImportError as exc:
    print(f"pandas not available: {exc}", file=sys.stderr)
    sys.exit(1)

try:
    from PIL import Image as _PILImage
except ImportError as exc:
    print(f"Pillow not available: {exc}", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
from ktfigure import KTFigure, PlotBlock, Shape  # noqa: E402


def _pump(root: "tk.Tk", n: int = 30) -> None:
    for _ in range(n):
        root.update()


def _scrot(output_path: str, root: "tk.Tk") -> bool:
    """Take a screenshot cropped to the Tk window bounds."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(tmp_fd)
    os.remove(tmp_path)  # scrot won't overwrite an existing file
    try:
        subprocess.run(
            ["scrot", "--quality", "90", tmp_path],
            check=True,
            capture_output=True,
        )
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        w = root.winfo_width()
        h = root.winfo_height()
        _PILImage.open(tmp_path).crop((x, y, x + w, y + h)).save(output_path)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  ⚠ scrot failed: {exc}", file=sys.stderr)
        return False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ---------------------------------------------------------------------------
# Open one Tk session, build scene, take one screenshot
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

    # ── load data ──────────────────────────────────────────────────────────
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"example_data.csv not found at {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)

    # ── randomly choose plot type (intentionally non-deterministic so each
    # PR run demonstrates a different chart style) ─────────────────────────
    # box / violin use categorical x; scatter uses two numeric columns
    plot_type = random.choice(["box", "violin", "scatter"])
    if plot_type in ("box", "violin"):
        col_x, col_y, col_hue = "season", "sales", "region"
    else:  # scatter
        col_x, col_y, col_hue = "temperature", "sales", "region"

    print(f"  ℹ plot type chosen: {plot_type} (x={col_x}, y={col_y}, hue={col_hue})")

    # ── PlotBlock — left portion of artboard ──────────────────────────────
    block = PlotBlock(30, 30, 470, 380)
    block.df = df
    block.plot_type = plot_type
    block.col_x = col_x
    block.col_y = col_y
    block.col_hue = col_hue
    app._blocks.append(block)
    app._draw_empty_block(block)   # draw placeholder first (required for rect_id)
    _pump(root, 10)
    app._render_block(block)       # replace with actual rendered plot

    # ── shapes: small circle (top-right), big circle (mid-right), rectangle (bottom) ──
    small_circle = Shape(510, 30, 600, 120, "circle")   # 90×90 px
    small_circle.color = "#e74c3c"
    small_circle.line_width = 2
    app._shapes.append(small_circle)
    app._draw_shape(small_circle)

    big_circle = Shape(510, 160, 720, 370, "circle")    # 210×210 px
    big_circle.color = "#2980b9"
    big_circle.line_width = 3
    app._shapes.append(big_circle)
    app._draw_shape(big_circle)

    rectangle = Shape(30, 420, 430, 520, "rectangle")   # 400×100 px
    rectangle.color = "#27ae60"
    rectangle.line_width = 2
    app._shapes.append(rectangle)
    app._draw_shape(rectangle)

    # ── raise window and let everything render ─────────────────────────────
    _pump(root, 50)
    root.deiconify()
    root.lift()
    root.focus_force()
    _pump(root, 40)
    time.sleep(0.5)
    _pump(root, 20)

    # ── single screenshot capturing the full scene ─────────────────────────
    fname = "gui_screenshot.png"
    path = os.path.join(OUT, fname)
    label = "KTFigure GUI screenshot"
    if _scrot(path, root):
        manifest.append({"file": fname, "path": path, "label": label})
        print(f"  ✓ {path}")
    else:
        failures.append(fname)

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
