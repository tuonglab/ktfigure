"""
Tests for the canvas zoom feature.

These tests require a display (xvfb on Linux CI).
"""
import sys
import tkinter as tk
import pytest

from ktfigure import A4_W, A4_H, BOARD_PAD, KTFigure, PlotBlock, Shape


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pump(root, n=20):
    for _ in range(n):
        try:
            root.update()
        except tk.TclError:
            break


def make_app():
    root = tk.Tk()
    root.withdraw()
    app = KTFigure(root)
    pump(root)
    return root, app


# ---------------------------------------------------------------------------
# Default zoom state
# ---------------------------------------------------------------------------

class TestZoomDefaults:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_zoom_default_is_1(self):
        assert self.app._zoom == 1.0

    def test_zoom_entry_default_is_100(self):
        assert self.app._zoom_var.get() == "100%"

    def test_zoom_buttons_exist(self):
        # The old separate buttons are gone; alias attributes remain for compat
        assert self.app._btn_zoom_in is None
        assert self.app._btn_zoom_out is None

    def test_zoom_combo_exists(self):
        assert self.app._zoom_combo is not None

    def test_zoom_entry_exists(self):
        # _zoom_entry is an alias for _zoom_combo
        assert self.app._zoom_entry is not None


# ---------------------------------------------------------------------------
# _to_canvas and _to_board with zoom
# ---------------------------------------------------------------------------

class TestZoomCoordinates:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_to_canvas_at_100pct(self):
        app = self.app
        cx, cy = app._to_canvas(0, 0)
        assert cx == BOARD_PAD
        assert cy == BOARD_PAD

    def test_to_canvas_at_200pct(self):
        app = self.app
        app._zoom = 2.0
        cx, cy = app._to_canvas(0, 0)
        assert cx == BOARD_PAD * 2
        assert cy == BOARD_PAD * 2

    def test_to_canvas_at_50pct(self):
        app = self.app
        app._zoom = 0.5
        cx, cy = app._to_canvas(100, 100)
        assert cx == (100 + BOARD_PAD) * 0.5
        assert cy == (100 + BOARD_PAD) * 0.5

    def test_to_board_at_100pct(self):
        app = self.app
        bx, by = app._to_board(BOARD_PAD, BOARD_PAD)
        assert bx == 0
        assert by == 0

    def test_to_board_at_200pct(self):
        app = self.app
        app._zoom = 2.0
        cx, cy = app._to_canvas(50, 100)
        bx, by = app._to_board(cx, cy)
        assert abs(bx - 50) < 1e-9
        assert abs(by - 100) < 1e-9

    def test_round_trip_at_zoom_150pct(self):
        """_to_board(_to_canvas(bx, by)) == (bx, by) for any zoom."""
        app = self.app
        app._zoom = 1.5
        bx_orig, by_orig = 200, 300
        cx, cy = app._to_canvas(bx_orig, by_orig)
        bx_back, by_back = app._to_board(cx, cy)
        assert abs(bx_back - bx_orig) < 1e-9
        assert abs(by_back - by_orig) < 1e-9


# ---------------------------------------------------------------------------
# _set_zoom
# ---------------------------------------------------------------------------

class TestSetZoom:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_set_zoom_updates_factor(self):
        self.app._set_zoom(2.0)
        assert self.app._zoom == 2.0

    def test_set_zoom_updates_entry(self):
        self.app._set_zoom(1.5)
        assert self.app._zoom_var.get() == "150%"

    def test_set_zoom_clamps_min(self):
        self.app._set_zoom(0.0)
        assert self.app._zoom >= 0.1

    def test_set_zoom_clamps_max(self):
        self.app._set_zoom(999.0)
        assert self.app._zoom <= 10.0

    def test_set_zoom_updates_scrollregion(self):
        app = self.app
        app._set_zoom(2.0)
        pump(self.root)
        sr = app._cv.cget("scrollregion")
        # scrollregion should be larger at 2× zoom
        expected_w = (A4_W + 2 * BOARD_PAD) * 2.0
        expected_h = (A4_H + 2 * BOARD_PAD) * 2.0
        parts = str(sr).split()
        assert len(parts) == 4
        assert abs(float(parts[2]) - expected_w) < 1
        assert abs(float(parts[3]) - expected_h) < 1

    def test_set_zoom_artboard_redrawn(self):
        """After set_zoom, artboard items must still exist on the canvas."""
        app = self.app
        app._set_zoom(1.5)
        pump(self.root)
        assert len(app._cv.find_withtag("artboard")) > 0

    def test_set_zoom_bg_redrawn(self):
        app = self.app
        app._set_zoom(0.75)
        pump(self.root)
        assert len(app._cv.find_withtag("bg")) > 0


# ---------------------------------------------------------------------------
# _zoom_in / _zoom_out
# ---------------------------------------------------------------------------

class TestZoomInOut:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_zoom_in_increases_factor(self):
        app = self.app
        before = app._zoom
        app._zoom_in()
        assert app._zoom > before

    def test_zoom_out_decreases_factor(self):
        app = self.app
        app._zoom_in()  # step up first so there's room to zoom out
        before = app._zoom
        app._zoom_out()
        assert app._zoom < before

    def test_zoom_in_steps_through_presets(self):
        app = self.app
        app._set_zoom(1.0)
        app._zoom_in()
        assert app._zoom == 1.25

    def test_zoom_out_steps_through_presets(self):
        app = self.app
        app._set_zoom(1.0)
        app._zoom_out()
        assert app._zoom == 0.75

    def test_zoom_in_clamps_at_maximum(self):
        app = self.app
        app._set_zoom(KTFigure._ZOOM_STEPS[-1])
        app._zoom_in()
        assert app._zoom == KTFigure._ZOOM_STEPS[-1]

    def test_zoom_out_clamps_at_minimum(self):
        app = self.app
        app._set_zoom(KTFigure._ZOOM_STEPS[0])
        app._zoom_out()
        assert app._zoom == KTFigure._ZOOM_STEPS[0]


# ---------------------------------------------------------------------------
# _apply_zoom_entry (no crash on empty/invalid input)
# ---------------------------------------------------------------------------

class TestApplyZoomEntry:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_valid_entry_applies_zoom(self):
        app = self.app
        app._zoom_var.set("150%")
        app._apply_zoom_entry()
        assert abs(app._zoom - 1.5) < 1e-9

    def test_valid_entry_no_percent_applies_zoom(self):
        app = self.app
        app._zoom_var.set("150")
        app._apply_zoom_entry()
        assert abs(app._zoom - 1.5) < 1e-9

    def test_empty_entry_does_not_crash(self):
        app = self.app
        app._zoom_var.set("")
        app._apply_zoom_entry()  # must not raise
        # Zoom unchanged; entry restored
        assert app._zoom == 1.0
        assert app._zoom_var.get() == "100%"

    def test_non_numeric_entry_does_not_crash(self):
        app = self.app
        app._zoom_var.set("abc")
        app._apply_zoom_entry()  # must not raise
        assert app._zoom == 1.0

    def test_zero_entry_does_not_crash(self):
        app = self.app
        app._zoom_var.set("0")
        app._apply_zoom_entry()  # must not raise
        assert app._zoom == 1.0

    def test_negative_entry_does_not_crash(self):
        app = self.app
        app._zoom_var.set("-50")
        app._apply_zoom_entry()  # must not raise
        assert app._zoom == 1.0


# ---------------------------------------------------------------------------
# Theme interaction
# ---------------------------------------------------------------------------

class TestZoomTheme:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_zoom_controls_survive_theme_switch(self):
        """Switching theme must not remove the zoom controls."""
        app = self.app
        app._on_theme_click()
        pump(self.root)
        assert app._zoom_combo is not None
        assert app._zoom_entry is not None  # alias

    def test_zoom_preserved_after_theme_switch(self):
        app = self.app
        app._set_zoom(1.5)
        app._on_theme_click()
        pump(self.root)
        assert app._zoom == 1.5


# ---------------------------------------------------------------------------
# macOS trackpad pinch-to-zoom (<Magnify> event)
# ---------------------------------------------------------------------------

class TestMagnifyZoom:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    @pytest.mark.skipif(
        sys.platform != "darwin",
        reason="<Magnify> handler is only set up on macOS",
    )
    def test_magnify_handler_zoom_in_after_threshold(self):
        """Accumulated float deltas ≥ 0.1 via the _on_magnify handler zoom in."""
        app = self.app
        before = app._zoom
        # Two typical macOS <Magnify> delta strings (float, not int)
        app._on_magnify("0.06")
        app._on_magnify("0.06")  # cumulative = 0.12 ≥ 0.1
        pump(self.root)
        assert app._zoom > before

    @pytest.mark.skipif(
        sys.platform != "darwin",
        reason="<Magnify> handler is only set up on macOS",
    )
    def test_magnify_handler_zoom_out_after_threshold(self):
        """Accumulated float deltas ≤ -0.1 via the _on_magnify handler zoom out."""
        app = self.app
        app._set_zoom(1.25)  # step up so there's room to zoom out
        before = app._zoom
        app._on_magnify("-0.06")
        app._on_magnify("-0.06")  # cumulative = -0.12 ≤ -0.1
        pump(self.root)
        assert app._zoom < before

    @pytest.mark.skipif(
        sys.platform != "darwin",
        reason="<Magnify> handler is only set up on macOS",
    )
    def test_magnify_handler_below_threshold_no_zoom(self):
        """A single small delta that doesn't reach the threshold must not zoom."""
        app = self.app
        before = app._zoom
        app._on_magnify("0.03")  # below 0.1 threshold → no zoom yet
        pump(self.root)
        assert app._zoom == before

    @pytest.mark.skipif(
        sys.platform != "darwin",
        reason="<Magnify> handler is only set up on macOS",
    )
    def test_magnify_handler_invalid_delta_no_crash(self):
        """A non-numeric delta string must not crash."""
        app = self.app
        before = app._zoom
        app._on_magnify("not_a_number")
        pump(self.root)
        assert app._zoom == before

    @pytest.mark.skipif(
        sys.platform != "darwin",
        reason="<Magnify> event is macOS-only",
    )
    def test_magnify_binding_exists_on_macos(self):
        """On macOS the canvas must have a <Magnify> binding registered."""
        bindings = self.app._cv.bind()
        assert "<Magnify>" in bindings

    @pytest.mark.skipif(
        sys.platform != "darwin",
        reason="<Magnify> event is macOS-only",
    )
    def test_magnify_binding_uses_uppercase_D_substitution(self):
        """The <Magnify> Tcl bind script must pass %D (float data field), not
        %d (integer detail field).  Using %d was the bug that caused the handler
        to always receive '0' instead of the actual magnification float."""
        bind_script = self.app._cv.tk.call(
            "bind", self.app._cv._w, "<Magnify>"
        )
        assert "%D" in bind_script, (
            "<Magnify> bind script does not contain '%D'; "
            "pinch-to-zoom will silently receive 0 instead of the "
            "actual magnification delta"
        )


# ---------------------------------------------------------------------------
# Windows precision-touchpad pinch-to-zoom via <MouseWheel> + Ctrl state bit
# ---------------------------------------------------------------------------

class MockWheelEvent:
    """Synthetic <MouseWheel> event with configurable state and delta."""
    def __init__(self, delta=120, state=0, num=0):
        self.delta = delta
        self.state = state
        self.num = num


class TestWindowsTouchpadZoom:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_ctrl_state_wheel_zooms_in(self):
        """<MouseWheel> with Ctrl state bit should zoom in (positive delta)."""
        app = self.app
        before = app._zoom
        evt = MockWheelEvent(delta=120, state=0x0004)  # Ctrl bit set
        app._on_canvas_wheel(evt)
        pump(self.root)
        assert app._zoom > before

    def test_ctrl_state_wheel_zooms_out(self):
        """<MouseWheel> with Ctrl state bit should zoom out (negative delta)."""
        app = self.app
        app._set_zoom(1.25)
        before = app._zoom
        evt = MockWheelEvent(delta=-120, state=0x0004)  # Ctrl bit set
        app._on_canvas_wheel(evt)
        pump(self.root)
        assert app._zoom < before

    def test_plain_wheel_does_not_zoom(self):
        """<MouseWheel> without Ctrl state must not change zoom."""
        app = self.app
        before = app._zoom
        evt = MockWheelEvent(delta=-120, state=0)  # no Ctrl
        app._on_canvas_wheel(evt)
        pump(self.root)
        assert app._zoom == before  # zoom unchanged

    def test_canvas_wheel_handler_attribute_exists(self):
        """_on_canvas_wheel must be stored on the instance for testability."""
        assert callable(self.app._on_canvas_wheel)
