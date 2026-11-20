"""Separate OpenGL scatter preview; the canvas and exports use Matplotlib."""
import os
import sys
import tkinter as tk
from tkinter import messagebox

import numpy as np
import pandas as pd


def prepare_points(x, y):
    """Return finite numeric coordinates in their original precision."""
    xs = pd.to_numeric(x, errors="raise").to_numpy(dtype=np.float64, na_value=np.nan)
    ys = pd.to_numeric(y, errors="raise").to_numpy(dtype=np.float64, na_value=np.nan)
    valid = np.isfinite(xs) & np.isfinite(ys)
    points = np.column_stack((xs[valid], ys[valid]))
    if not len(points):
        raise ValueError("The selected columns have no finite numeric pairs.")
    return points, int(len(xs) - len(points))


def show_preview(points, x_label, y_label, dropped):
    try:
        from vispy import app, scene
        from vispy.gloo import gl
    except ImportError as exc:
        raise RuntimeError(
            "GPU preview requires VisPy and GLFW. Install ktfigure with the "
            "'gpu' extra: pip install 'ktfigure[gpu]'."
        ) from exc

    app.use_app("glfw")
    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    span = maximum - minimum
    if not np.all(np.isfinite(span)):
        raise ValueError("The selected values span too wide a range to preview.")
    scale = np.where(span == 0, 1, span)
    normalized = ((points - minimum) / scale).astype(np.float32)

    canvas = scene.SceneCanvas(keys="interactive", size=(900, 700), show=True, bgcolor="white")
    grid = canvas.central_widget.add_grid(spacing=0)
    info = scene.Label(
        f"{x_label}: {minimum[0]:.6g} to {maximum[0]:.6g}    "
        f"{y_label}: {minimum[1]:.6g} to {maximum[1]:.6g}\n"
        f"{len(points):,} points; {dropped:,} non-finite pairs omitted. "
        "Single-colour preview; styling and exports are unchanged.",
        color="black", font_size=10,
    )
    info.height_max = 60
    grid.add_widget(info, row=0, col=1)
    view = grid.add_view(row=1, col=1, bgcolor="white")
    view.camera = scene.PanZoomCamera(aspect=None)
    view.camera.set_range(x=(-0.05, 1.05), y=(-0.05, 1.05))
    markers = scene.visuals.Markers(parent=view.scene)
    markers.set_data(normalized, face_color=(0.15, 0.4, 0.8, 0.6), edge_width=0, size=3)
    bottom = scene.AxisWidget(orientation="bottom", axis_label=f"{x_label} (normalized)")
    left = scene.AxisWidget(orientation="left", axis_label=f"{y_label} (normalized)")
    grid.add_widget(bottom, row=2, col=1)
    grid.add_widget(left, row=1, col=0)
    bottom.link_view(view)
    left.link_view(view)
    renderer = gl.glGetParameter(gl.GL_RENDERER)
    if isinstance(renderer, bytes):
        renderer = renderer.decode(errors="replace")
    canvas.title = f"Scatter preview | OpenGL: {renderer}"
    app.run()


def run_file(path):
    try:
        try:
            with np.load(path, allow_pickle=False) as data:
                points = data["points"]
                x = str(data["x"])
                y = str(data["y"])
                dropped = int(data["dropped"])
        finally:
            os.unlink(path)
        show_preview(points, x, y, dropped)
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror("GPU preview unavailable", str(exc), parent=root)
        finally:
            root.destroy()
        raise


if __name__ == "__main__":
    run_file(sys.argv[1])
