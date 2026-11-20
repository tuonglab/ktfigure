import numpy as np
import pandas as pd
import pytest
import runpy
import sys

from ktfigure.gpu_preview import prepare_points, run_file, show_preview


def test_python_module_launches_main(monkeypatch):
    calls = []
    monkeypatch.setattr("ktfigure.main", lambda: calls.append(True))
    runpy.run_module("ktfigure", run_name="__main__")
    assert calls == [True]


def test_prepare_points_keeps_finite_pairs_and_original_precision():
    points, dropped = prepare_points(
        pd.Series([1_000_000_000.0, 1_000_000_000.25, None, np.inf]),
        pd.Series([1.0, 2.0, 3.0, 4.0]),
    )
    np.testing.assert_array_equal(
        points, [[1_000_000_000.0, 1.0], [1_000_000_000.25, 2.0]]
    )
    assert dropped == 2


def test_prepare_points_rejects_non_numeric_or_empty_data():
    with pytest.raises(ValueError):
        prepare_points(pd.Series(["invalid"]), pd.Series([1]))
    with pytest.raises(ValueError, match="no finite numeric pairs"):
        prepare_points(pd.Series([None]), pd.Series([1]))


def test_preview_explains_missing_optional_dependencies(monkeypatch):
    monkeypatch.setitem(sys.modules, "vispy", None)
    with pytest.raises(RuntimeError, match="requires VisPy and GLFW"):
        show_preview(np.array([[1.0, 2.0]]), "x", "y", 0)


def test_preview_rejects_unrepresentable_numeric_range():
    pytest.importorskip("vispy")
    pytest.importorskip("glfw")
    with np.errstate(over="ignore"), pytest.raises(ValueError, match="too wide"):
        show_preview(np.array([[-1e308, 0.0], [1e308, 1.0]]), "x", "y", 0)


def test_preview_renders_all_points_with_precise_normalization(monkeypatch):
    pytest.importorskip("vispy")
    pytest.importorskip("glfw")
    from vispy import app, scene
    from vispy.gloo import gl

    app.use_app("glfw")
    timer = app.Timer(interval=1, connect=lambda event: app.quit(), start=True)
    original = scene.visuals.Markers.set_data
    original_get = gl.glGetParameter
    drawn = {}

    def capture(self, positions, *args, **kwargs):
        drawn["positions"] = positions.copy()
        return original(self, positions, *args, **kwargs)

    monkeypatch.setattr(scene.visuals.Markers, "set_data", capture)
    def renderer_as_bytes(parameter):
        value = original_get(parameter)
        if parameter == gl.GL_RENDERER and isinstance(value, str):
            return value.encode()
        return value

    monkeypatch.setattr(gl, "glGetParameter", renderer_as_bytes)
    x = 1_000_000_000 + np.arange(1_000_000, dtype=np.float64) / 1_000_000
    points = np.column_stack((x, np.arange(len(x), dtype=np.float64)))
    show_preview(points, "x", "y", 0)
    assert drawn["positions"].shape == (1_000_000, 2)
    np.testing.assert_array_equal(drawn["positions"][[0, -1]], [[0, 0], [1, 1]])


def test_preview_handles_constant_axis_and_text_renderer(monkeypatch):
    pytest.importorskip("vispy")
    pytest.importorskip("glfw")
    from vispy import app, scene
    from vispy.gloo import gl

    app.use_app("glfw")
    timer = app.Timer(interval=0.5, connect=lambda event: app.quit(), start=True)
    original = scene.visuals.Markers.set_data
    original_get = gl.glGetParameter
    drawn = {}

    def capture(self, positions, *args, **kwargs):
        drawn["positions"] = positions.copy()
        return original(self, positions, *args, **kwargs)

    def renderer_as_text(parameter):
        value = original_get(parameter)
        if parameter == gl.GL_RENDERER and isinstance(value, bytes):
            return value.decode(errors="replace")
        return value

    monkeypatch.setattr(scene.visuals.Markers, "set_data", capture)
    monkeypatch.setattr(gl, "glGetParameter", renderer_as_text)
    show_preview(np.array([[7.0, 1.0], [7.0, 2.0]]), "x", "y", 0)
    np.testing.assert_array_equal(drawn["positions"], [[0, 0], [0, 1]])


def test_run_file_passes_data_and_removes_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / "preview.npz"
    np.savez(path, points=[[1, 2]], x="x", y="y", dropped=3)
    received = []
    monkeypatch.setattr(
        "ktfigure.gpu_preview.show_preview",
        lambda *args: received.append(args),
    )
    run_file(path)
    assert not path.exists()
    np.testing.assert_array_equal(received[0][0], [[1, 2]])
    assert received[0][1:] == ("x", "y", 3)


def test_run_file_reports_error_and_removes_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / "preview.npz"
    path.write_bytes(b"invalid")
    errors = []
    monkeypatch.setattr(
        "ktfigure.gpu_preview.messagebox.showerror",
        lambda title, message, **kwargs: errors.append((title, message)),
    )
    with pytest.raises(ValueError):
        run_file(path)
    assert not path.exists()
    assert errors and errors[0][0] == "GPU preview unavailable"
