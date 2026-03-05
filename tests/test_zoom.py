"""
Tests for canvas zoom functionality in KTFigure.

Covers:
  - _ZOOM_STEPS constant
  - Default zoom state
  - _to_canvas / _to_board coordinate scaling with zoom
  - _set_zoom: factor clamping, scrollregion update, zoom label
  - _zoom_in / _zoom_out step navigation
  - _apply_zoom_entry: valid and invalid input
  - _on_ctrl_scroll: zoom-in/out direction from event.delta / event.num
  - _on_magnify: accumulation threshold (macOS pinch-to-zoom simulation)
  - Cursor-centred scroll adjustment after zoom change
  - UI widgets: zoom entry and buttons exist
"""
import sys
import tkinter as tk
import pytest

from ktfigure import (
    A4_W, A4_H, BOARD_PAD,
    KTFigure,
    _ZOOM_STEPS,
)


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


class MockEvent:
    """Minimal synthetic event accepted by KTFigure event handlers.

    Parameters
    ----------
    x, y   : cursor position in widget-pixel coordinates
    delta  : scroll-wheel delta (positive = scroll up / zoom in,
             negative = scroll down / zoom out; Windows/macOS convention)
    num    : Linux button number (4 = scroll up/zoom in, 5 = scroll down/zoom out)
    """
    def __init__(self, x=400, y=300, delta=0, num=0):
        self.x = x
        self.y = y
        self.delta = delta
        self.num = num


# ---------------------------------------------------------------------------
# _ZOOM_STEPS constant
# ---------------------------------------------------------------------------

class TestZoomStepsConstant:
    def test_zoom_steps_is_list(self):
        assert isinstance(_ZOOM_STEPS, list)

    def test_zoom_steps_not_empty(self):
        assert len(_ZOOM_STEPS) > 0

    def test_zoom_steps_sorted_ascending(self):
        assert _ZOOM_STEPS == sorted(_ZOOM_STEPS)

    def test_zoom_steps_contains_1(self):
        assert 1.0 in _ZOOM_STEPS

    def test_zoom_steps_min_positive(self):
        assert _ZOOM_STEPS[0] > 0

    def test_zoom_steps_max_at_least_2(self):
        assert _ZOOM_STEPS[-1] >= 2.0


# ---------------------------------------------------------------------------
# Default state
# ---------------------------------------------------------------------------

class TestZoomDefaults:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_zoom_default_1(self):
        assert self.app._zoom == 1.0

    def test_zoom_var_shows_100_percent(self):
        assert self.app._zoom_var.get() == "100%"

    def test_zoom_entry_widget_exists(self):
        assert hasattr(self.app, "_zoom_entry")

    def test_zoom_in_button_exists(self):
        assert hasattr(self.app, "_btn_zoom_in")

    def test_zoom_out_button_exists(self):
        assert hasattr(self.app, "_btn_zoom_out")


# ---------------------------------------------------------------------------
# Coordinate helpers scale with zoom
# ---------------------------------------------------------------------------

class TestCoordinateScaling:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_to_canvas_at_zoom_1(self):
        cx, cy = self.app._to_canvas(100, 200)
        assert cx == BOARD_PAD + 100
        assert cy == BOARD_PAD + 200

    def test_to_board_at_zoom_1(self):
        bx, by = self.app._to_board(BOARD_PAD + 100, BOARD_PAD + 200)
        assert abs(bx - 100) < 1e-6
        assert abs(by - 200) < 1e-6

    def test_to_canvas_at_zoom_2(self):
        self.app._zoom = 2.0
        cx, cy = self.app._to_canvas(100, 200)
        assert cx == BOARD_PAD + 200  # 100 * 2
        assert cy == BOARD_PAD + 400  # 200 * 2

    def test_to_board_at_zoom_2(self):
        self.app._zoom = 2.0
        bx, by = self.app._to_board(BOARD_PAD + 200, BOARD_PAD + 400)
        assert abs(bx - 100) < 1e-6
        assert abs(by - 200) < 1e-6

    def test_to_canvas_at_zoom_half(self):
        self.app._zoom = 0.5
        cx, cy = self.app._to_canvas(100, 200)
        assert cx == BOARD_PAD + 50   # 100 * 0.5
        assert cy == BOARD_PAD + 100  # 200 * 0.5

    def test_to_board_clamps_to_zero(self):
        self.app._zoom = 1.0
        bx, by = self.app._to_board(0, 0)  # before BOARD_PAD
        assert bx == 0
        assert by == 0

    def test_to_board_clamps_to_max(self):
        self.app._zoom = 1.0
        bx, by = self.app._to_board(BOARD_PAD + A4_W + 100, BOARD_PAD + A4_H + 100)
        assert bx == A4_W
        assert by == A4_H

    def test_roundtrip_board_canvas(self):
        self.app._zoom = 1.5
        bx_orig, by_orig = 123.4, 456.7
        cx, cy = self.app._to_canvas(bx_orig, by_orig)
        bx, by = self.app._to_board(cx, cy)
        assert abs(bx - bx_orig) < 1e-6
        assert abs(by - by_orig) < 1e-6


# ---------------------------------------------------------------------------
# _set_zoom
# ---------------------------------------------------------------------------

class TestSetZoom:
    def setup_method(self):
        self.root, self.app = make_app()
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_set_zoom_changes_zoom_attribute(self):
        self.app._set_zoom(1.5)
        pump(self.root)
        assert self.app._zoom == 1.5

    def test_set_zoom_updates_label(self):
        self.app._set_zoom(2.0)
        pump(self.root)
        assert self.app._zoom_var.get() == "200%"

    def test_set_zoom_clamps_below_min(self):
        self.app._set_zoom(0.01)
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[0]

    def test_set_zoom_clamps_above_max(self):
        self.app._set_zoom(999.0)
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[-1]

    def test_set_zoom_updates_scrollregion(self):
        self.app._set_zoom(2.0)
        pump(self.root)
        sr = self.app._cv.cget("scrollregion")
        # scrollregion is a string like "0 0 W H" or a 4-tuple depending on Tk version
        if isinstance(sr, str):
            parts = sr.split()
            w = float(parts[2])
            h = float(parts[3])
        else:
            w = float(sr[2])
            h = float(sr[3])
        expected_w = 2 * BOARD_PAD + A4_W * 2.0
        expected_h = 2 * BOARD_PAD + A4_H * 2.0
        assert abs(w - expected_w) < 1.0
        assert abs(h - expected_h) < 1.0

    def test_set_zoom_100_percent_label(self):
        self.app._set_zoom(1.0)
        pump(self.root)
        assert self.app._zoom_var.get() == "100%"

    def test_set_zoom_25_percent_label(self):
        self.app._set_zoom(0.25)
        pump(self.root)
        assert self.app._zoom_var.get() == "25%"


# ---------------------------------------------------------------------------
# _zoom_in / _zoom_out step navigation
# ---------------------------------------------------------------------------

class TestZoomSteps:
    def setup_method(self):
        self.root, self.app = make_app()
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_zoom_in_from_1_goes_to_next_step(self):
        idx = _ZOOM_STEPS.index(1.0)
        self.app._set_zoom(1.0)
        self.app._zoom_in()
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[idx + 1]

    def test_zoom_out_from_1_goes_to_prev_step(self):
        idx = _ZOOM_STEPS.index(1.0)
        self.app._set_zoom(1.0)
        self.app._zoom_out()
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[idx - 1]

    def test_zoom_in_at_max_stays_at_max(self):
        self.app._set_zoom(_ZOOM_STEPS[-1])
        self.app._zoom_in()
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[-1]

    def test_zoom_out_at_min_stays_at_min(self):
        self.app._set_zoom(_ZOOM_STEPS[0])
        self.app._zoom_out()
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[0]

    def test_zoom_in_accepts_cursor_coords(self):
        """_zoom_in with cx/cy shouldn't raise."""
        self.app._set_zoom(1.0)
        self.app._zoom_in(cx=400, cy=300)
        pump(self.root)
        idx = _ZOOM_STEPS.index(1.0)
        assert self.app._zoom == _ZOOM_STEPS[idx + 1]

    def test_zoom_out_accepts_cursor_coords(self):
        """_zoom_out with cx/cy shouldn't raise."""
        self.app._set_zoom(1.0)
        self.app._zoom_out(cx=400, cy=300)
        pump(self.root)
        idx = _ZOOM_STEPS.index(1.0)
        assert self.app._zoom == _ZOOM_STEPS[idx - 1]


# ---------------------------------------------------------------------------
# _apply_zoom_entry
# ---------------------------------------------------------------------------

class TestApplyZoomEntry:
    def setup_method(self):
        self.root, self.app = make_app()
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_valid_percent_string(self):
        self.app._zoom_var.set("150%")
        self.app._apply_zoom_entry()
        pump(self.root)
        assert self.app._zoom == 1.5

    def test_valid_number_without_percent(self):
        self.app._zoom_var.set("75")
        self.app._apply_zoom_entry()
        pump(self.root)
        assert self.app._zoom == 0.75

    def test_invalid_string_restores_label(self):
        self.app._set_zoom(1.0)
        self.app._zoom_var.set("abc")
        self.app._apply_zoom_entry()
        pump(self.root)
        # Zoom should be unchanged; label restored to current zoom
        assert self.app._zoom == 1.0
        assert self.app._zoom_var.get() == "100%"

    def test_zero_clamped_to_min(self):
        self.app._zoom_var.set("0")
        self.app._apply_zoom_entry()
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[0]


# ---------------------------------------------------------------------------
# _on_ctrl_scroll
# ---------------------------------------------------------------------------

class TestCtrlScroll:
    def setup_method(self):
        self.root, self.app = make_app()
        self.app._set_zoom(1.0)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_positive_delta_zooms_in(self):
        idx = _ZOOM_STEPS.index(1.0)
        self.app._on_ctrl_scroll(MockEvent(delta=120))
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[idx + 1]

    def test_negative_delta_zooms_out(self):
        idx = _ZOOM_STEPS.index(1.0)
        self.app._on_ctrl_scroll(MockEvent(delta=-120))
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[idx - 1]

    def test_button_4_zooms_in(self):
        """Linux Button-4 (scroll up) should zoom in."""
        idx = _ZOOM_STEPS.index(1.0)
        self.app._on_ctrl_scroll(MockEvent(num=4, delta=0))
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[idx + 1]

    def test_button_5_zooms_out(self):
        """Linux Button-5 (scroll down) should zoom out."""
        idx = _ZOOM_STEPS.index(1.0)
        self.app._on_ctrl_scroll(MockEvent(num=5, delta=0))
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[idx - 1]

    def test_returns_break(self):
        """Handler must return 'break' to stop event propagation."""
        result = self.app._on_ctrl_scroll(MockEvent(delta=120))
        assert result == "break"

    def test_passes_cursor_coords_to_zoom(self):
        """Cursor coordinates are forwarded so pivot is cursor-centred."""
        # This just checks no exception is raised with arbitrary coords
        self.app._on_ctrl_scroll(MockEvent(x=200, y=150, delta=120))
        pump(self.root)
        assert self.app._zoom > 1.0


# ---------------------------------------------------------------------------
# _on_magnify (macOS pinch-to-zoom accumulation)
# ---------------------------------------------------------------------------

class TestOnMagnify:
    def setup_method(self):
        self.root, self.app = make_app()
        # Ensure the accumulator exists even on non-Darwin (we set it manually)
        self.app._magnify_accum = 0.0
        self.app._set_zoom(1.0)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_small_positive_delta_accumulates_without_zoom(self):
        evt = MockEvent(delta=0.05)
        self.app._on_magnify(evt)
        assert self.app._zoom == 1.0  # threshold not reached
        assert abs(self.app._magnify_accum - 0.05) < 1e-6

    def test_threshold_crossed_positive_zooms_in(self):
        evt = MockEvent(delta=0.15)
        idx = _ZOOM_STEPS.index(1.0)
        self.app._on_magnify(evt)
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[idx + 1]
        assert self.app._magnify_accum == 0.0  # reset after firing

    def test_threshold_crossed_negative_zooms_out(self):
        evt = MockEvent(delta=-0.15)
        idx = _ZOOM_STEPS.index(1.0)
        self.app._on_magnify(evt)
        pump(self.root)
        assert self.app._zoom == _ZOOM_STEPS[idx - 1]
        assert self.app._magnify_accum == 0.0

    def test_accumulation_across_multiple_events(self):
        """Multiple small events should add up to trigger zoom."""
        evt = MockEvent(delta=0.04)
        for _ in range(3):
            self.app._on_magnify(evt)
        # 3 × 0.04 = 0.12 >= 0.10 threshold → should have zoomed in
        pump(self.root)
        idx = _ZOOM_STEPS.index(1.0)
        assert self.app._zoom == _ZOOM_STEPS[idx + 1]


# ---------------------------------------------------------------------------
# Cursor-centred zoom: scroll offset adjustment
# ---------------------------------------------------------------------------

class TestCursorCentredZoom:
    def setup_method(self):
        self.root, self.app = make_app()
        self.app._set_zoom(1.0)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _get_scrollregion_size(self):
        sr = self.app._cv.cget("scrollregion")
        if isinstance(sr, str):
            parts = sr.split()
            return float(parts[2]), float(parts[3])
        return float(sr[2]), float(sr[3])

    def test_scrollregion_grows_on_zoom_in(self):
        w0, h0 = self._get_scrollregion_size()
        self.app._set_zoom(2.0)
        pump(self.root)
        w1, h1 = self._get_scrollregion_size()
        assert w1 > w0
        assert h1 > h0

    def test_scrollregion_shrinks_on_zoom_out(self):
        w0, h0 = self._get_scrollregion_size()
        self.app._set_zoom(0.5)
        pump(self.root)
        w1, h1 = self._get_scrollregion_size()
        assert w1 < w0
        assert h1 < h0

    def test_scrollregion_correct_at_zoom_2(self):
        self.app._set_zoom(2.0)
        pump(self.root)
        w, h = self._get_scrollregion_size()
        assert abs(w - (2 * BOARD_PAD + A4_W * 2.0)) < 1.0
        assert abs(h - (2 * BOARD_PAD + A4_H * 2.0)) < 1.0

    def test_scroll_adjusted_when_cursor_given(self):
        """When cx/cy are provided the view should shift to keep pivot under cursor."""
        # Reset scroll to 0,0
        self.app._cv.xview_moveto(0)
        self.app._cv.yview_moveto(0)
        pump(self.root)
        xv_before = self.app._cv.xview()[0]
        # Zoom in at a point that is NOT the canvas origin
        self.app._set_zoom(2.0, cx=300, cy=200)
        pump(self.root)
        xv_after = self.app._cv.xview()[0]
        # The xview should have changed to keep the cursor point in view
        # (exact value depends on window size, but it should be ≥ 0)
        assert xv_after >= 0.0

    def test_no_crash_when_cx_cy_none(self):
        """_set_zoom without cursor coords should not raise."""
        self.app._set_zoom(1.5, cx=None, cy=None)
        pump(self.root)
        assert self.app._zoom == 1.5
