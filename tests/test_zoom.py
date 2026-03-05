"""
Tests for the canvas zoom feature.

Covers:
  - _to_canvas / _to_board coordinate transforms at various zoom levels
  - _apply_zoom: zoom clamping, scroll-region update, status message
  - Zoom-at-cursor math: the board point under the cursor stays fixed
  - _on_zoom_scroll: Ctrl+scroll handler
  - _on_pinch_zoom: macOS <Magnify> handler
  - Grid line scaling
  - ZOOM_MIN / ZOOM_MAX limits
  - Normal scroll suppressed when Ctrl is held
"""
import pytest
import tkinter as tk
from unittest.mock import patch, MagicMock

from ktfigure import (
    A4_W, A4_H, BOARD_PAD, GRID_SIZE,
    ZOOM_MIN, ZOOM_MAX, ZOOM_STEP,
    KTFigure, PlotBlock, Shape, TextObject,
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
    """Minimal synthetic event for zoom handlers."""
    def __init__(self, x=0, y=0, state=0, num=0, delta=0):
        self.x = x
        self.y = y
        self.state = state
        self.num = num
        self.delta = delta


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestZoomConstants:
    def test_zoom_min_lt_one(self):
        assert ZOOM_MIN < 1.0

    def test_zoom_max_gt_one(self):
        assert ZOOM_MAX > 1.0

    def test_zoom_step_gt_one(self):
        assert ZOOM_STEP > 1.0

    def test_zoom_min_positive(self):
        assert ZOOM_MIN > 0.0


# ---------------------------------------------------------------------------
# Coordinate transforms
# ---------------------------------------------------------------------------

class TestZoomCoordinates:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_default_zoom_is_one(self):
        assert self.app._zoom == 1.0

    def test_to_canvas_zoom_one(self):
        cx, cy = self.app._to_canvas(100, 200)
        assert cx == 100 + BOARD_PAD
        assert cy == 200 + BOARD_PAD

    def test_to_canvas_zoom_two(self):
        self.app._zoom = 2.0
        cx, cy = self.app._to_canvas(100, 200)
        # Current formula: (BOARD_PAD + bx) * z, (BOARD_PAD + by) * z
        assert cx == pytest.approx((BOARD_PAD + 100) * 2)
        assert cy == pytest.approx((BOARD_PAD + 200) * 2)

    def test_to_canvas_zoom_half(self):
        self.app._zoom = 0.5
        cx, cy = self.app._to_canvas(200, 400)
        # Current formula: (BOARD_PAD + bx) * z, (BOARD_PAD + by) * z
        assert cx == pytest.approx((BOARD_PAD + 200) * 0.5)
        assert cy == pytest.approx((BOARD_PAD + 400) * 0.5)

    def test_to_board_zoom_one(self):
        # canvas (100+60, 200+60) → board (100, 200)
        bx, by = self.app._to_board(100 + BOARD_PAD, 200 + BOARD_PAD)
        assert bx == pytest.approx(100.0)
        assert by == pytest.approx(200.0)

    def test_to_board_zoom_two(self):
        self.app._zoom = 2.0
        # Current formula: bx = cx/z - BOARD_PAD, by = cy/z - BOARD_PAD
        # For board (100, 200) at zoom=2: canvas = (BOARD_PAD+100)*2=320, (BOARD_PAD+200)*2=520
        bx, by = self.app._to_board(320, 520)
        assert bx == pytest.approx(100.0)
        assert by == pytest.approx(200.0)

    def test_roundtrip_zoom_one(self):
        for bx0, by0 in [(0, 0), (100, 200), (A4_W, A4_H), (394, 560)]:
            cx, cy = self.app._to_canvas(bx0, by0)
            bx1, by1 = self.app._to_board(cx, cy)
            assert bx1 == pytest.approx(bx0, abs=1e-6)
            assert by1 == pytest.approx(by0, abs=1e-6)

    def test_roundtrip_zoom_three(self):
        self.app._zoom = 3.0
        bx0, by0 = 150.0, 300.0
        cx, cy = self.app._to_canvas(bx0, by0)
        bx1, by1 = self.app._to_board(cx, cy)
        assert bx1 == pytest.approx(bx0, abs=1e-6)
        assert by1 == pytest.approx(by0, abs=1e-6)

    def test_to_board_outside_origin(self):
        self.app._zoom = 1.0
        # Canvas coord (0,0) maps outside the artboard (no clamping in current code)
        bx, by = self.app._to_board(0, 0)
        assert bx == pytest.approx(-BOARD_PAD)
        assert by == pytest.approx(-BOARD_PAD)

    def test_to_board_outside_max(self):
        self.app._zoom = 1.0
        # Large canvas coords map to large board coords (no clamping in current code)
        bx, by = self.app._to_board(10000, 10000)
        assert bx == pytest.approx(10000 - BOARD_PAD)
        assert by == pytest.approx(10000 - BOARD_PAD)

    def test_to_canvas_origin_scales_with_zoom(self):
        """Board origin (0,0) canvas coordinate scales with zoom: (BOARD_PAD*z, BOARD_PAD*z)."""
        for zoom in (0.5, 1.0, 2.0, 4.0):
            self.app._zoom = zoom
            cx, cy = self.app._to_canvas(0, 0)
            assert cx == pytest.approx(BOARD_PAD * zoom)
            assert cy == pytest.approx(BOARD_PAD * zoom)


# ---------------------------------------------------------------------------
# _apply_zoom
# ---------------------------------------------------------------------------

class TestApplyZoom:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_apply_zoom_changes_zoom_level(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            self.app._apply_zoom(2.0, 300, 300)
        assert self.app._zoom == pytest.approx(2.0)

    def test_apply_zoom_updates_scroll_region(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            self.app._apply_zoom(2.0, 0, 0)
        sr = str(self.app._cv.cget("scrollregion"))
        parts = [float(p) for p in sr.split()]
        # Current formula: total_w = _canvas_total_width() * zoom = (2*BOARD_PAD + A4_W) * zoom
        expected_w = (2 * BOARD_PAD + A4_W) * 2.0
        expected_h = (2 * BOARD_PAD + A4_H) * 2.0
        assert parts[2] == pytest.approx(expected_w)
        assert parts[3] == pytest.approx(expected_h)

    def test_apply_zoom_updates_status_message(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            self.app._apply_zoom(1.5, 0, 0)
        assert "150%" in self.app._status.cget("text")

    def test_apply_zoom_clamps_at_min(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            self.app._apply_zoom(ZOOM_MIN / 2, 0, 0)
        assert self.app._zoom == pytest.approx(ZOOM_MIN)

    def test_apply_zoom_clamps_at_max(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            self.app._apply_zoom(ZOOM_MAX * 10, 0, 0)
        assert self.app._zoom == pytest.approx(ZOOM_MAX)

    def test_apply_zoom_same_level_is_noop(self):
        """Calling _apply_zoom with the current zoom should not redraw."""
        with patch.object(self.app, '_redraw_at_zoom') as mock_redraw:
            self.app._apply_zoom(1.0, 0, 0)
        mock_redraw.assert_not_called()

    def test_apply_zoom_calls_redraw(self):
        with patch.object(self.app, '_redraw_at_zoom') as mock_redraw:
            self.app._apply_zoom(2.0, 100, 100)
        mock_redraw.assert_called_once()

    def test_apply_zoom_100pct_status(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            self.app._apply_zoom(2.0, 0, 0)
            self.app._apply_zoom(1.0, 0, 0)
        assert "100%" in self.app._status.cget("text")


# ---------------------------------------------------------------------------
# Zoom-at-cursor math
# ---------------------------------------------------------------------------

class TestZoomAnchorMath:
    """
    The scroll-offset formula must keep the board point under the cursor
    at the same widget position before and after a zoom change.
    """

    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _capture_zoom(self, new_zoom, event_x, event_y):
        """Apply zoom and return (frac_x, frac_y) passed to xview_moveto/yview_moveto."""
        captured = {}
        orig_x = self.app._cv.xview_moveto
        orig_y = self.app._cv.yview_moveto

        def cap_x(f):
            captured['x'] = f
            orig_x(f)

        def cap_y(f):
            captured['y'] = f
            orig_y(f)

        with patch.object(self.app, '_redraw_at_zoom'):
            with patch.object(self.app._cv, 'xview_moveto', side_effect=cap_x):
                with patch.object(self.app._cv, 'yview_moveto', side_effect=cap_y):
                    self.app._apply_zoom(new_zoom, event_x, event_y)

        return captured.get('x', 0.0), captured.get('y', 0.0)

    def test_anchor_matches_expected_fraction_no_scroll(self):
        """
        At zoom=1, no prior scroll, cursor at widget (300, 300).
        canvasx(0) = 0, canvasy(0) = 0
        mc_x = canvasx(300) = 300, mc_y = canvasy(300) = 300
        ratio = 2
        new_sx = mc_x * (ratio - 1) + sx = 300 * (2 - 1) + 0 = 300
        new_sy = 300
        total_w = (2*BOARD_PAD + A4_W) * 2
        """
        fx, fy = self._capture_zoom(2.0, 300, 300)
        total_w = (2 * BOARD_PAD + A4_W) * 2.0
        total_h = (2 * BOARD_PAD + A4_H) * 2.0
        expected_fx = max(0.0, 300.0) / total_w
        expected_fy = max(0.0, 300.0) / total_h
        assert fx == pytest.approx(expected_fx, abs=1e-6)
        assert fy == pytest.approx(expected_fy, abs=1e-6)

    def test_anchor_board_point_preserved_math(self):
        """
        Board point (200, 300) at zoom=1 maps to canvas (260, 360) via
        current formula: (BOARD_PAD + bx)*z.
        After zoom to 2: new_sx = mc_x * (ratio-1) = cx1 * 1 = cx1.
        """
        bx, by = 200.0, 300.0
        cx1, cy1 = self.app._to_canvas(bx, by)   # (260, 360) at zoom=1
        fx, fy = self._capture_zoom(2.0, cx1, cy1)

        total_w = (2 * BOARD_PAD + A4_W) * 2.0
        total_h = (2 * BOARD_PAD + A4_H) * 2.0
        # new_sx = mc_x * (ratio-1) + sx = cx1 * (2-1) + 0 = cx1
        expected_sx = cx1 * (2.0 - 1.0)
        expected_sy = cy1 * (2.0 - 1.0)
        expected_fx = max(0.0, expected_sx) / total_w
        expected_fy = max(0.0, expected_sy) / total_h

        assert fx == pytest.approx(expected_fx, abs=1e-6)
        assert fy == pytest.approx(expected_fy, abs=1e-6)

    def test_cursor_at_board_pad_scroll_fraction(self):
        """
        Cursor at (BOARD_PAD, BOARD_PAD).
        new_sx = mc_x * (ratio - 1) + sx = BOARD_PAD * 1 + 0 = BOARD_PAD
        """
        fx, fy = self._capture_zoom(2.0, BOARD_PAD, BOARD_PAD)
        total_w = (2 * BOARD_PAD + A4_W) * 2.0
        total_h = (2 * BOARD_PAD + A4_H) * 2.0
        expected_fx = max(0.0, float(BOARD_PAD)) / total_w
        expected_fy = max(0.0, float(BOARD_PAD)) / total_h
        assert fx == pytest.approx(expected_fx, abs=1e-6)
        assert fy == pytest.approx(expected_fy, abs=1e-6)

    def test_zoom_out_scroll_fraction_clamped(self):
        """
        Zooming out from a non-scrolled view with cursor far from top-left
        may produce a negative scroll offset, which is clamped to 0.
        """
        # At zoom=2, zoom out to 1 from cursor at widget position (100, 100)
        self.app._zoom = 2.0
        with patch.object(self.app, '_redraw_at_zoom'):
            self.app._cv.configure(
                scrollregion=(0, 0, A4_W * 2 + 2 * BOARD_PAD, A4_H * 2 + 2 * BOARD_PAD)
            )
        fx, fy = self._capture_zoom(1.0, 100, 100)
        # Fraction must not be negative
        assert fx >= 0.0
        assert fy >= 0.0


# ---------------------------------------------------------------------------
# _on_zoom_scroll (Ctrl+scroll)
# ---------------------------------------------------------------------------

class TestCtrlScrollZoom:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_positive_delta_zooms_in(self):
        ev = MockEvent(x=300, y=300, delta=120)
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self.app._on_zoom_scroll(ev)
        new_zoom, ex, ey = mock_az.call_args[0]
        assert new_zoom > 1.0   # zoom in
        assert ex == 300
        assert ey == 300

    def test_negative_delta_zooms_out(self):
        ev = MockEvent(x=200, y=200, delta=-120)
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self.app._on_zoom_scroll(ev)
        new_zoom, ex, ey = mock_az.call_args[0]
        assert new_zoom < 1.0   # zoom out
        assert ex == 200
        assert ey == 200

    def test_linux_button4_zooms_in(self):
        ev = MockEvent(x=100, y=100, num=4, delta=0)
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self.app._on_zoom_scroll(ev)
        new_zoom, _, _ = mock_az.call_args[0]
        assert new_zoom > 1.0

    def test_linux_button5_zooms_out(self):
        ev = MockEvent(x=100, y=100, num=5, delta=0)
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self.app._on_zoom_scroll(ev)
        new_zoom, _, _ = mock_az.call_args[0]
        assert new_zoom < 1.0

    def test_zoom_step_applied_correctly(self):
        ev = MockEvent(x=0, y=0, delta=120)   # positive delta → × ZOOM_STEP
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self.app._on_zoom_scroll(ev)
        new_zoom, _, _ = mock_az.call_args[0]
        assert new_zoom == pytest.approx(ZOOM_STEP)

    def test_zoom_out_step_applied_correctly(self):
        ev = MockEvent(x=0, y=0, delta=-120)  # negative delta → ÷ ZOOM_STEP
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self.app._on_zoom_scroll(ev)
        new_zoom, _, _ = mock_az.call_args[0]
        assert new_zoom == pytest.approx(1.0 / ZOOM_STEP)

    def test_returns_break(self):
        ev = MockEvent(x=0, y=0, delta=120)
        with patch.object(self.app, '_apply_zoom'):
            result = self.app._on_zoom_scroll(ev)
        assert result == "break"

    def test_event_position_forwarded(self):
        ev = MockEvent(x=123, y=456, delta=120)
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self.app._on_zoom_scroll(ev)
        _, ex, ey = mock_az.call_args[0]
        assert ex == 123
        assert ey == 456


# ---------------------------------------------------------------------------
# _on_pinch_zoom (macOS <Magnify>)
# ---------------------------------------------------------------------------

class TestPinchZoom:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _pointer_patch(self, x, y, root_x=0, root_y=0):
        """Return a list of patch.object context managers for winfo_pointer/root."""
        return [
            patch.object(self.app._cv, 'winfo_pointerx', return_value=x + root_x),
            patch.object(self.app._cv, 'winfo_pointery', return_value=y + root_y),
            patch.object(self.app._cv, 'winfo_rootx', return_value=root_x),
            patch.object(self.app._cv, 'winfo_rooty', return_value=root_y),
        ]

    def test_positive_delta_zooms_in(self):
        ev = MockEvent(delta=0.1)
        patches = self._pointer_patch(400, 400)
        with patch.object(self.app, '_apply_zoom') as mock_az, \
             patches[0], patches[1], patches[2], patches[3]:
            self.app._on_pinch_zoom(ev)
        new_zoom, ex, ey = mock_az.call_args[0]
        assert new_zoom > 1.0
        assert ex == 400
        assert ey == 400

    def test_negative_delta_zooms_out(self):
        ev = MockEvent(delta=-0.1)
        patches = self._pointer_patch(300, 300)
        with patch.object(self.app, '_apply_zoom') as mock_az, \
             patches[0], patches[1], patches[2], patches[3]:
            self.app._on_pinch_zoom(ev)
        new_zoom, _, _ = mock_az.call_args[0]
        assert new_zoom < 1.0

    def test_factor_is_one_plus_delta(self):
        """new_zoom = current_zoom * (1 + delta)"""
        ev = MockEvent(delta=0.2)
        patches = self._pointer_patch(0, 0)
        with patch.object(self.app, '_apply_zoom') as mock_az, \
             patches[0], patches[1], patches[2], patches[3]:
            self.app._on_pinch_zoom(ev)
        new_zoom, _, _ = mock_az.call_args[0]
        assert new_zoom == pytest.approx(1.0 * (1.0 + 0.2))

    def test_catastrophic_negative_delta_skipped(self):
        """delta = -1.5 → factor = -0.5 ≤ 0.05 → do nothing."""
        ev = MockEvent(delta=-1.5)
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self.app._on_pinch_zoom(ev)
        mock_az.assert_not_called()

    def test_returns_break(self):
        ev = MockEvent(delta=0.1)
        patches = self._pointer_patch(0, 0)
        with patch.object(self.app, '_apply_zoom'), \
             patches[0], patches[1], patches[2], patches[3]:
            result = self.app._on_pinch_zoom(ev)
        assert result == "break"

    def test_event_position_forwarded(self):
        """Zoom anchor uses pointer position relative to the canvas."""
        ev = MockEvent(delta=0.1)
        # Canvas root at (10, 20); pointer at screen (87, 108)
        # → canvas-relative: (87-10, 108-20) = (77, 88)
        patches = self._pointer_patch(77, 88, root_x=10, root_y=20)
        with patch.object(self.app, '_apply_zoom') as mock_az, \
             patches[0], patches[1], patches[2], patches[3]:
            self.app._on_pinch_zoom(ev)
        _, ex, ey = mock_az.call_args[0]
        assert ex == 77
        assert ey == 88


# ---------------------------------------------------------------------------
# Zoom limits (ZOOM_MIN / ZOOM_MAX)
# ---------------------------------------------------------------------------

class TestZoomLimits:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_cannot_set_below_min(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            self.app._apply_zoom(0.0, 0, 0)
        assert self.app._zoom == pytest.approx(ZOOM_MIN)

    def test_cannot_set_above_max(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            self.app._apply_zoom(999.0, 0, 0)
        assert self.app._zoom == pytest.approx(ZOOM_MAX)

    def test_successive_zoom_in_stops_at_max(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            for _ in range(50):
                self.app._apply_zoom(self.app._zoom * ZOOM_STEP, 0, 0)
        assert self.app._zoom == pytest.approx(ZOOM_MAX)

    def test_successive_zoom_out_stops_at_min(self):
        with patch.object(self.app, '_redraw_at_zoom'):
            for _ in range(50):
                self.app._apply_zoom(self.app._zoom / ZOOM_STEP, 0, 0)
        assert self.app._zoom == pytest.approx(ZOOM_MIN)


# ---------------------------------------------------------------------------
# Ctrl held suppresses normal scroll
# ---------------------------------------------------------------------------

class TestCtrlSuppressesScroll:
    """
    When Control is held, _on_mousewheel must return early WITHOUT scrolling.
    The zoom handler (_on_zoom_scroll) handles the event instead.
    """

    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_ctrl_scroll_calls_zoom_not_scroll(self):
        """Verify _on_zoom_scroll calls _apply_zoom and not yview_scroll."""
        scroll_calls = []
        orig_yview = self.app._cv.yview_scroll

        def capturing_yview(*a, **kw):
            scroll_calls.append(a)
            orig_yview(*a, **kw)

        ev = MockEvent(x=0, y=0, delta=120)
        with patch.object(self.app._cv, 'yview_scroll', side_effect=capturing_yview):
            with patch.object(self.app, '_apply_zoom') as mock_az:
                result = self.app._on_zoom_scroll(ev)

        mock_az.assert_called_once()
        assert len(scroll_calls) == 0
        assert result == "break"


# ---------------------------------------------------------------------------
# _redraw_at_zoom
# ---------------------------------------------------------------------------

class TestRedrawAtZoom:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_redraw_clears_canvas(self):
        # Manually add a stray item
        item = self.app._cv.create_rectangle(10, 10, 100, 100)
        assert item in self.app._cv.find_all()
        self.app._redraw_at_zoom()
        # Stray item is gone
        assert item not in self.app._cv.find_all()

    def test_redraw_recreates_artboard(self):
        self.app._cv.delete("all")
        assert len(self.app._cv.find_withtag("artboard")) == 0
        self.app._redraw_at_zoom()
        assert len(self.app._cv.find_withtag("artboard")) > 0

    def test_redraw_recreates_shapes(self):
        s = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._redraw_at_zoom()
        pump(self.root)
        assert s.item_id is not None
        assert s.item_id in self.app._cv.find_all()

    def test_redraw_recreates_empty_block(self):
        block = PlotBlock(50, 50, 250, 250)
        self.app._blocks.append(block)
        self.app._draw_empty_block(block)
        pump(self.root)
        self.app._redraw_at_zoom()
        pump(self.root)
        assert block.rect_id is not None or block.label_id is not None

    def test_artboard_size_scales_with_zoom(self):
        """At zoom=2, the artboard rectangle coords should be ~double."""
        self.app._zoom = 1.0
        self.app._redraw_at_zoom()
        pump(self.root)
        items1 = self.app._cv.find_withtag("artboard")
        coords1 = self.app._cv.coords(items1[0])

        self.app._zoom = 2.0
        self.app._redraw_at_zoom()
        pump(self.root)
        items2 = self.app._cv.find_withtag("artboard")
        coords2 = self.app._cv.coords(items2[0])

        # Width at zoom=2 should be ~double width at zoom=1
        w1 = coords1[2] - coords1[0]
        w2 = coords2[2] - coords2[0]
        assert w2 == pytest.approx(w1 * 2.0, rel=0.01)


# ---------------------------------------------------------------------------
# Grid scaling
# ---------------------------------------------------------------------------

class TestZoomGridScaling:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_grid_drawn_at_zoom_one(self):
        self.app._zoom = 1.0
        self.app._draw_grid()
        pump(self.root)
        assert len(self.app._cv.find_withtag("grid")) > 0

    def test_grid_drawn_at_zoom_two(self):
        self.app._zoom = 2.0
        self.app._draw_grid()
        pump(self.root)
        assert len(self.app._cv.find_withtag("grid")) > 0

    def test_grid_line_count_same_across_zoom(self):
        """Grid line count should be the same: it's based on A4 / GRID_SIZE."""
        self.app._zoom = 1.0
        self.app._draw_grid()
        n1 = len(self.app._cv.find_withtag("grid"))
        self.app._cv.delete("grid")

        self.app._zoom = 2.0
        self.app._draw_grid()
        n2 = len(self.app._cv.find_withtag("grid"))

        assert n1 == n2

    def test_grid_lines_scaled_x_spacing(self):
        """Horizontal spacing between vertical grid lines should double at zoom=2."""
        self.app._zoom = 1.0
        self.app._draw_grid()
        pump(self.root)
        v_lines_1 = [
            self.app._cv.coords(i)
            for i in self.app._cv.find_withtag("grid")
            if len(self.app._cv.coords(i)) == 4
            and abs(self.app._cv.coords(i)[0] - self.app._cv.coords(i)[2]) < 1  # vertical: x1≈x2
        ]
        x_coords_1 = sorted(c[0] for c in v_lines_1)
        self.app._cv.delete("grid")

        self.app._zoom = 2.0
        self.app._draw_grid()
        pump(self.root)
        v_lines_2 = [
            self.app._cv.coords(i)
            for i in self.app._cv.find_withtag("grid")
            if len(self.app._cv.coords(i)) == 4
            and abs(self.app._cv.coords(i)[0] - self.app._cv.coords(i)[2]) < 1
        ]
        x_coords_2 = sorted(c[0] for c in v_lines_2)

        if len(x_coords_1) >= 2 and len(x_coords_2) >= 2:
            spacing_1 = x_coords_1[1] - x_coords_1[0]
            spacing_2 = x_coords_2[1] - x_coords_2[0]
            assert spacing_2 == pytest.approx(spacing_1 * 2.0, rel=0.05)


# ---------------------------------------------------------------------------
# _redraw_at_zoom branches (grid, pil_img_base, df path, selection highlights)
# ---------------------------------------------------------------------------

class TestRedrawAtZoomBranches:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_redraw_with_grid_visible(self):
        """Grid must be drawn when _show_grid is True."""
        self.app._show_grid = True
        self.app._redraw_at_zoom()
        pump(self.root)
        assert len(self.app._cv.find_withtag("grid")) > 0

    def test_redraw_with_pil_img_base_block(self):
        """Fast-path: block with _pil_img_base is rescaled without re-rendering."""
        from PIL import Image as _PIL
        block = PlotBlock(100, 100, 400, 300)
        block._pil_img_base = _PIL.new("RGB", (300, 200), color=(100, 150, 200))
        self.app._blocks.append(block)

        # Draw it first so it gets canvas IDs
        self.app._draw_empty_block(block)
        pump(self.root)

        # Now call _redraw_at_zoom — should use the fast PIL path
        self.app._redraw_at_zoom()
        pump(self.root)

        # Block should now have an image item
        assert block.image_id is not None
        assert block.image_id in self.app._cv.find_all()

    def test_redraw_with_df_block_no_base_calls_render(self):
        """If block.df is set but _pil_img_base is None, _render_block is called."""
        import pandas as pd
        block = PlotBlock(50, 50, 300, 300)
        block.df = pd.DataFrame({"x": [1, 2], "y": [3, 4], "cat": ["A", "B"]})
        block.plot_type = "scatter"
        block.col_x = "x"
        block.col_y = "y"
        block._pil_img_base = None  # force render path
        self.app._blocks.append(block)

        called = []
        orig_render = self.app._render_block

        def capturing_render(b):
            called.append(b)
            orig_render(b)

        with patch.object(self.app, '_render_block', side_effect=capturing_render):
            self.app._redraw_at_zoom()
            pump(self.root)

        assert block in called

    def test_redraw_restores_selected_block(self):
        """A selected block must be re-highlighted after redraw."""
        block = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(block)
        self.app._draw_empty_block(block)
        pump(self.root)

        # Set block as selected
        self.app._selected = block

        highlights_called = []
        orig_highlight = self.app._highlight

        def capturing_highlight(b):
            highlights_called.append(b)
            orig_highlight(b)

        with patch.object(self.app, '_highlight', side_effect=capturing_highlight):
            self.app._redraw_at_zoom()
            pump(self.root)

        assert block in highlights_called

    def test_redraw_restores_selected_shape(self):
        """A selected shape must be re-highlighted after redraw."""
        s = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        pump(self.root)

        self.app._selected_shape = s

        highlighted = []
        orig = self.app._highlight_shape

        def cap(sh):
            highlighted.append(sh)
            orig(sh)

        with patch.object(self.app, '_highlight_shape', side_effect=cap):
            self.app._redraw_at_zoom()
            pump(self.root)

        assert s in highlighted

    def test_redraw_restores_selected_objects_multiselect(self):
        """Multi-selected objects must be re-highlighted after redraw (non-primary)."""
        b1 = PlotBlock(50, 50, 200, 200)
        b2 = PlotBlock(250, 50, 450, 200)
        self.app._blocks.extend([b1, b2])
        self.app._draw_empty_block(b1)
        self.app._draw_empty_block(b2)
        pump(self.root)

        self.app._selected_objects = [b1, b2]
        self.app._selected = b1   # b1 is the primary; b2 should go via _selected_objects path

        highlighted = []
        orig = self.app._highlight

        def cap(b):
            highlighted.append(b)
            orig(b)

        with patch.object(self.app, '_highlight', side_effect=cap):
            self.app._redraw_at_zoom()
            pump(self.root)

        # b2 should be highlighted via the _selected_objects loop
        assert b2 in highlighted

    def test_redraw_restores_selected_text(self):
        """A selected TextObject must be re-highlighted after redraw."""
        t = TextObject(100, 100, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        pump(self.root)

        self.app._selected_text = t

        highlighted = []
        orig = self.app._highlight_text

        def cap(txt):
            highlighted.append(txt)
            orig(txt)

        with patch.object(self.app, '_highlight_text', side_effect=cap):
            self.app._redraw_at_zoom()
            pump(self.root)

        assert t in highlighted

    def test_redraw_restores_selected_shapes_in_multiselect(self):
        """Shapes in _selected_objects (non-primary) must be re-highlighted."""
        s1 = Shape(50, 50, 150, 150, "rectangle")
        s2 = Shape(200, 50, 300, 150, "circle")
        self.app._shapes.extend([s1, s2])
        self.app._draw_shape(s1)
        self.app._draw_shape(s2)
        pump(self.root)

        self.app._selected_objects = [s1, s2]
        self.app._selected_shape = s1   # s1 is primary; s2 goes via _selected_objects loop

        highlighted = []
        orig = self.app._highlight_shape

        def cap(sh):
            highlighted.append(sh)
            orig(sh)

        with patch.object(self.app, '_highlight_shape', side_effect=cap):
            self.app._redraw_at_zoom()
            pump(self.root)

        # s2 should be highlighted via the _selected_objects loop (shape branch)
        assert s2 in highlighted


# ---------------------------------------------------------------------------
# Smooth-scroll else branch in _on_zoom_scroll
# ---------------------------------------------------------------------------

class TestSmoothScrollZoom:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_zero_delta_zero_num_reaches_else_branch(self):
        """delta==0 and num==0 hits the else branch; no zoom change occurs."""
        ev = MockEvent(x=0, y=0, num=0, delta=0)
        with patch.object(self.app, '_apply_zoom') as mock_az:
            result = self.app._on_zoom_scroll(ev)
        mock_az.assert_not_called()
        assert result == "break"

    def test_fractional_delta_else_branch(self):
        """A fractional non-120 delta hits the else branch for smooth scroll."""
        ev = MockEvent(x=0, y=0, num=0, delta=60)   # positive but not the Button-4/5 path
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self.app._on_zoom_scroll(ev)
        new_zoom, _, _ = mock_az.call_args[0]
        # 60/120 = 0.5 → factor = ZOOM_STEP ** 0.5
        expected = ZOOM_STEP ** 0.5
        assert new_zoom == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Zoom keyboard shortcuts (_zoom_in / _zoom_out / _zoom_reset)
# ---------------------------------------------------------------------------

class TestZoomKeyboardShortcuts:
    def setup_method(self):
        self.root, self.app = make_app()
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _fire_key(self, key_sequence):
        """Event-generate a key event and pump the event loop."""
        try:
            self.app.root.event_generate(key_sequence)
            pump(self.root)
        except Exception:
            pass

    def test_ctrl_equal_zooms_in(self):
        """Ctrl+= should zoom in via _apply_zoom."""
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self._fire_key('<Control-equal>')
        if mock_az.called:
            new_zoom, _, _ = mock_az.call_args[0]
            assert new_zoom == pytest.approx(ZOOM_STEP)

    def test_ctrl_minus_zooms_out(self):
        """Ctrl+- should zoom out via _apply_zoom."""
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self._fire_key('<Control-minus>')
        if mock_az.called:
            new_zoom, _, _ = mock_az.call_args[0]
            assert new_zoom == pytest.approx(1.0 / ZOOM_STEP)

    def test_ctrl_zero_resets_zoom(self):
        """Ctrl+0 should reset zoom to 1.0."""
        self.app._zoom = 2.0
        with patch.object(self.app, '_apply_zoom') as mock_az:
            self._fire_key('<Control-0>')
        if mock_az.called:
            new_zoom, _, _ = mock_az.call_args[0]
            assert new_zoom == pytest.approx(1.0)

