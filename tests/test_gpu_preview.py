import numpy as np
import pandas as pd
import pytest
import runpy

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


def test_preview_renders_all_points_with_precise_normalization(monkeypatch):
    pytest.importorskip("vispy")
    pytest.importorskip("glfw")
    from vispy import app, scene

    app.use_app("glfw")
    timer = app.Timer(interval=1, connect=lambda event: app.quit(), start=True)
    original = scene.visuals.Markers.set_data
    drawn = {}

    def capture(self, positions, *args, **kwargs):
        drawn["positions"] = positions.copy()
        return original(self, positions, *args, **kwargs)

    monkeypatch.setattr(scene.visuals.Markers, "set_data", capture)
    x = 1_000_000_000 + np.arange(1_000_000, dtype=np.float64) / 1_000_000
    points = np.column_stack((x, np.arange(len(x), dtype=np.float64)))
    show_preview(points, "x", "y", 0)
    assert drawn["positions"].shape == (1_000_000, 2)
    np.testing.assert_array_equal(drawn["positions"][[0, -1]], [[0, 0], [1, 1]])


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
