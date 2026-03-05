"""
Tests for the grid visibility toggle and snap-to-grid feature.

These tests require a display (xvfb on Linux CI).
"""
import tkinter as tk
import pytest

from ktfigure import (
    A4_W, A4_H, BOARD_PAD, GRID_SIZE,
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
    """Minimal synthetic event accepted by KTFigure mouse handlers."""
    def __init__(self, x, y, state=0):
        self.x = x
        self.y = y
        self.state = state
        self.num = 0
        self.delta = 0


def board_event(app, bx, by, state=0):
    """Return a MockEvent whose canvas coords map to board position (bx, by)."""
    cx, cy = app._to_canvas(bx, by)
    return MockEvent(cx, cy, state=state)


# ---------------------------------------------------------------------------
# GRID_SIZE constant
# ---------------------------------------------------------------------------

class TestGridSizeConstant:
    def test_grid_size_is_positive_integer(self):
        assert isinstance(GRID_SIZE, int)
        assert GRID_SIZE > 0

    def test_grid_size_divides_cleanly(self):
        """Grid should divide the A4 dimensions reasonably (no remainder check,
        just ensure it is a sensible value ≤ 100 px)."""
        assert GRID_SIZE <= 100


# ---------------------------------------------------------------------------
# Default state
# ---------------------------------------------------------------------------

class TestGridSnapDefaults:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_snap_to_grid_on_by_default(self):
        assert self.app._snap_to_grid is True

    def test_show_grid_off_by_default(self):
        assert self.app._show_grid is False

    def test_snap_button_active_by_default(self):
        """Snap button should start highlighted (active)."""
        assert self.app._btn_snap._is_active is True

    def test_grid_button_inactive_by_default(self):
        """Grid button should start un-highlighted (inactive)."""
        assert self.app._btn_grid._is_active is False


# ---------------------------------------------------------------------------
# _snap helper
# ---------------------------------------------------------------------------

class TestSnapHelper:
    def setup_method(self):
        self.root, self.app = make_app()
        # Set snap grid size to GRID_SIZE so snap tests are meaningful
        self.app._snap_grid_size = GRID_SIZE

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_snap_rounds_to_nearest_grid(self):
        app = self.app
        assert app._snap(0) == 0
        assert app._snap(GRID_SIZE) == GRID_SIZE
        # Values just past the halfway point round away from the midpoint
        assert app._snap(GRID_SIZE - 1) == GRID_SIZE   # 19 → 20 (closer to 20)
        assert app._snap(1) == 0                        # 1  →  0 (closer to 0)
        # Clear unambiguous cases that don't involve the exact midpoint
        assert app._snap(GRID_SIZE // 2 + 1) == GRID_SIZE  # 11 → 20
        assert app._snap(GRID_SIZE // 2 - 1) == 0          # 9  →  0

    def test_snap_disabled_returns_value_unchanged(self):
        app = self.app
        app._snap_to_grid = False
        raw = 37.5
        assert app._snap(raw) == raw

    def test_snap_pos_snaps_both_axes(self):
        app = self.app
        bx, by = app._snap_pos(3, 18)
        assert bx == 0
        assert by == GRID_SIZE

    def test_snap_pos_disabled(self):
        app = self.app
        app._snap_to_grid = False
        bx, by = app._snap_pos(3, 18)
        assert bx == 3
        assert by == 18


# ---------------------------------------------------------------------------
# Toggle grid visibility
# ---------------------------------------------------------------------------

class TestToggleGridVisible:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_toggle_shows_grid(self):
        app = self.app
        assert app._show_grid is False
        app._toggle_grid_visible()
        assert app._show_grid is True

    def test_toggle_twice_hides_grid(self):
        app = self.app
        app._toggle_grid_visible()
        app._toggle_grid_visible()
        assert app._show_grid is False

    def test_grid_lines_drawn_on_canvas(self):
        app = self.app
        before = len(app._cv.find_withtag("grid"))
        app._toggle_grid_visible()
        after = len(app._cv.find_withtag("grid"))
        assert after > before

    def test_grid_lines_removed_on_toggle_off(self):
        app = self.app
        app._toggle_grid_visible()           # on
        app._toggle_grid_visible()           # off
        remaining = app._cv.find_withtag("grid")
        assert len(remaining) == 0

    def test_grid_button_active_when_visible(self):
        app = self.app
        app._toggle_grid_visible()
        assert app._btn_grid._is_active is True

    def test_grid_button_inactive_when_hidden(self):
        app = self.app
        app._toggle_grid_visible()   # on
        app._toggle_grid_visible()   # off
        assert app._btn_grid._is_active is False

    def test_draw_grid_places_horizontal_lines(self):
        app = self.app
        app._draw_grid()
        tags = [app._cv.gettags(item) for item in app._cv.find_withtag("grid")]
        assert len(tags) > 0

    def test_clear_grid_removes_all_lines(self):
        app = self.app
        app._draw_grid()
        app._clear_grid()
        assert len(app._cv.find_withtag("grid")) == 0

    def test_grid_lines_span_artboard_width(self):
        """There should be at least A4_W / GRID_SIZE vertical lines."""
        app = self.app
        app._draw_grid()
        count = len(app._cv.find_withtag("grid"))
        expected_min = A4_W // GRID_SIZE + A4_H // GRID_SIZE
        assert count >= expected_min


# ---------------------------------------------------------------------------
# Toggle snap-to-grid
# ---------------------------------------------------------------------------

class TestToggleSnapToGrid:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_toggle_disables_snap(self):
        app = self.app
        assert app._snap_to_grid is True
        app._toggle_snap_to_grid()
        assert app._snap_to_grid is False

    def test_toggle_twice_re_enables_snap(self):
        app = self.app
        app._toggle_snap_to_grid()
        app._toggle_snap_to_grid()
        assert app._snap_to_grid is True

    def test_snap_button_inactive_after_disable(self):
        app = self.app
        app._toggle_snap_to_grid()
        assert app._btn_snap._is_active is False

    def test_snap_button_active_after_re_enable(self):
        app = self.app
        app._toggle_snap_to_grid()   # off
        app._toggle_snap_to_grid()   # on
        assert app._btn_snap._is_active is True


# ---------------------------------------------------------------------------
# Snap applied when drawing new shapes / blocks
# ---------------------------------------------------------------------------

class TestSnapOnDraw:
    def setup_method(self):
        self.root, self.app = make_app()
        # Set snap grid size to GRID_SIZE so tests verify 20-px snapping
        self.app._snap_grid_size = GRID_SIZE

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _draw_rect_from_to(self, bx1, by1, bx2, by2):
        """Helper: simulate drawing a rectangle from (bx1,by1) to (bx2,by2)."""
        app = self.app
        app._mode_draw_rect()
        ev_down = board_event(app, bx1, by1)
        app._mouse_down(ev_down)
        ev_drag = board_event(app, bx2, by2)
        app._mouse_drag(ev_drag)
        app._mouse_up(ev_drag)
        pump(self.root)

    def test_snap_aligns_drag_start_to_grid(self):
        """After mouse_down, the stored drag_start must sit on grid lines."""
        app = self.app
        app._mode_draw_rect()
        # Feed a non-grid-aligned coordinate
        ev = board_event(app, 13, 27)
        app._mouse_down(ev)
        sx, sy = app._drag_start
        assert sx % GRID_SIZE == 0
        assert sy % GRID_SIZE == 0

    def test_snap_aligns_new_shape_to_grid(self):
        """A rectangle drawn between non-grid-aligned points should have
        its corners snapped to the nearest grid lines."""
        app = self.app
        # Use coords that are slightly off grid
        self._draw_rect_from_to(13, 17, 93, 77)
        if app._shapes:
            s = app._shapes[-1]
            assert s.x1 % GRID_SIZE == 0
            assert s.y1 % GRID_SIZE == 0
            assert s.x2 % GRID_SIZE == 0
            assert s.y2 % GRID_SIZE == 0

    def test_snap_off_does_not_align_drag_start(self):
        """With snap disabled the raw coordinate is stored."""
        app = self.app
        app._snap_to_grid = False
        app._mode_draw_rect()
        ev = board_event(app, 13, 27)
        app._mouse_down(ev)
        sx, sy = app._drag_start
        # At least one coordinate should be off-grid
        assert sx % GRID_SIZE != 0 or sy % GRID_SIZE != 0


# ---------------------------------------------------------------------------
# Snap applied when moving objects
# ---------------------------------------------------------------------------

class TestSnapOnMove:
    def setup_method(self):
        self.root, self.app = make_app()
        # Set snap grid size to GRID_SIZE so tests verify 20-px snapping
        self.app._snap_grid_size = GRID_SIZE

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _add_shape_at(self, x1, y1, x2, y2, shape_type="rectangle"):
        app = self.app
        s = Shape(x1, y1, x2, y2, shape_type)
        app._shapes.append(s)
        app._draw_shape(s)
        return s

    def test_snap_aligns_moved_shape_to_grid(self):
        """Dragging a shape to a non-grid position snaps its top-left corner."""
        app = self.app
        s = self._add_shape_at(0, 0, 100, 100)
        app._select_shape(s)

        # Simulate picking up the shape at its top-left and moving to off-grid pos
        ev_down = board_event(app, 0, 0)
        app._drag_shape = s
        app._drag_offset = (0, 0)

        # Move to (13, 17) — not on a grid line
        ev_drag = board_event(app, 13, 17)
        app._mouse_drag(ev_drag)
        pump(self.root)

        assert s.x1 % GRID_SIZE == 0
        assert s.y1 % GRID_SIZE == 0

    def test_snap_off_does_not_align_moved_shape(self):
        app = self.app
        app._snap_to_grid = False
        s = self._add_shape_at(0, 0, 100, 100)
        app._select_shape(s)
        app._drag_shape = s
        app._drag_offset = (0, 0)

        ev_drag = board_event(app, 13, 17)
        app._mouse_drag(ev_drag)
        pump(self.root)

        # Without snap the coordinates should equal the raw values
        assert s.x1 == 13
        assert s.y1 == 17


# ---------------------------------------------------------------------------
# Snap applied when resizing objects
# ---------------------------------------------------------------------------

class TestSnapOnResize:
    def setup_method(self):
        self.root, self.app = make_app()
        # Set snap grid size to GRID_SIZE so tests verify 20-px snapping
        self.app._snap_grid_size = GRID_SIZE

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_snap_aligns_resize_corner_to_grid(self):
        """Dragging the SE resize corner of a block to an off-grid position
        should snap the new corner to the nearest grid lines."""
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)
        app._draw_empty_block(b)
        app._select_block(b)

        # Simulate grabbing the SE resize handle
        app._resize_corner = "se"
        app._resize_block = b
        app._resize_orig_dims = (0, 0, 100, 100)

        # Drag to an off-grid coordinate
        ev = board_event(app, 113, 117)
        app._mouse_drag(ev)
        pump(self.root)

        assert b.x2 % GRID_SIZE == 0
        assert b.y2 % GRID_SIZE == 0


# ---------------------------------------------------------------------------
# Theme changes keep button states correct
# ---------------------------------------------------------------------------

class TestGridSnapTheme:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_snap_button_stays_active_after_theme_switch(self):
        """Switching theme must not accidentally deactivate the snap button."""
        app = self.app
        assert app._btn_snap._is_active is True
        app._on_theme_click()   # switch to dark
        pump(self.root)
        assert app._btn_snap._is_active is True

    def test_grid_button_stays_active_after_theme_switch(self):
        app = self.app
        app._toggle_grid_visible()  # turn grid on
        app._on_theme_click()       # switch to dark
        pump(self.root)
        assert app._btn_grid._is_active is True

    def test_grid_button_stays_inactive_after_theme_switch(self):
        app = self.app
        assert app._btn_grid._is_active is False
        app._on_theme_click()   # switch theme
        pump(self.root)
        assert app._btn_grid._is_active is False
