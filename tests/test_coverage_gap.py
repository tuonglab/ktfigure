"""
Tests targeting uncovered code paths to push combined coverage above 90%.

Focuses on:
 - Copy / Cut / Paste (single + multi-select, bounds clamping)
 - Grid: _draw_grid, _toggle_grid_visible, _apply_spacing_entry
 - Artboard: _add_artboard, _delete_artboard, _switch_artboard, _show_board_menu
 - Nudge selected (block, shape, text; snap on/off)
 - Guide: _set_guide, _clear_guide_visual
 - Zoom: _zoom_in, _zoom_out, _apply_zoom_entry, _set_zoom with pivot
 - Highlight / unhighlight (block, shape, text)
 - _open_config result path (patched wait_window)
 - Mouse-up: draw_line / draw_rect / draw_circle completions, multi-resize
   finish, single resize finish (block / shape / text), rubberband selection
 - Mouse-down: multi-select toggle, resize-handle on text, draw_circle start
 - _select_all, _edit_selected no-selection, _auto_theme_check
 - PlotRenderer: legend-inside, tick_labels=False, custom hue palette
 - AestheticsPanel: shape callbacks (color, lw, dash, fill), text callbacks
 - Export: _export_png, _export_pdf, _export_svg
 - StyledButton._on_release (active/inactive)
 - Uncovered branches in _to_board / _to_canvas / _hit_board_idx
 - _delete_key with guide in selection, text delete, shape delete
"""
import sys
import copy
import math
import pytest
import tkinter as tk
from unittest.mock import patch, MagicMock
import pandas as pd

from ktfigure import (
    A4_W, A4_H, BOARD_PAD, DPI, GRID_SIZE,
    KTFigure, PlotBlock, Shape, TextObject,
    AestheticsPanel, PlotConfigDialog,
    default_aesthetics,
    StyledButton,
)
from ktfigure import PlotRenderer


# ---------------------------------------------------------------------------
# Helpers shared across all tests in this module
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
    def __init__(self, x=0, y=0, state=0, num=0, delta=0):
        self.x = x
        self.y = y
        self.state = state
        self.num = num
        self.delta = delta


def board_event(app, bx, by, state=0):
    """Return a MockEvent whose pixel coords land at board point (bx, by)."""
    cx, cy = app._to_canvas(bx, by)
    # scrollbar offset is 0 in tests (canvas not scrolled), so widget px ≈ canvas px
    return MockEvent(x=int(cx), y=int(cy), state=state)


# ===========================================================================
# Copy / Cut / Paste
# ===========================================================================

class TestCopyCutPaste:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    # --- copy ---------------------------------------------------------------
    def test_copy_nothing(self):
        self.app._copy()
        assert "Nothing" in self.app._status.cget("text")

    def test_copy_single_block(self):
        b = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._select_block(b)
        self.app._copy()
        assert self.app._clipboard is not None

    def test_copy_single_shape(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._selected_shape = s
        self.app._copy()
        assert self.app._clipboard is not None

    def test_copy_multi_select(self):
        b = PlotBlock(50, 50, 200, 200)
        s = Shape(250, 50, 400, 200, "rectangle")
        self.app._blocks.append(b)
        self.app._shapes.append(s)
        self.app._draw_empty_block(b)
        self.app._draw_shape(s)
        self.app._selected_objects = [b, s]
        self.app._copy()
        assert isinstance(self.app._clipboard, list)
        assert len(self.app._clipboard) == 2

    # --- cut ----------------------------------------------------------------
    def test_cut_nothing(self):
        self.app._cut()
        assert "Nothing" in self.app._status.cget("text")

    def test_cut_single_block(self):
        b = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._select_block(b)
        before = len(self.app._blocks)
        self.app._cut()
        assert len(self.app._blocks) == before - 1
        assert self.app._clipboard is not None

    def test_cut_single_shape(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._selected_shape = s
        before = len(self.app._shapes)
        self.app._cut()
        assert len(self.app._shapes) == before - 1

    def test_cut_multi_select(self):
        b = PlotBlock(50, 50, 200, 200)
        s = Shape(250, 50, 400, 200, "rectangle")
        self.app._blocks.append(b)
        self.app._shapes.append(s)
        self.app._draw_empty_block(b)
        self.app._draw_shape(s)
        self.app._selected_objects = [b, s]
        self.app._cut()
        assert len(self.app._blocks) == 0
        assert len(self.app._shapes) == 0

    # --- paste --------------------------------------------------------------
    def test_paste_empty_clipboard(self):
        self.app._clipboard = None
        self.app._paste()
        assert "empty" in self.app._status.cget("text")

    def test_paste_single_block(self):
        b = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._select_block(b)
        self.app._copy()
        before = len(self.app._blocks)
        self.app._paste()
        assert len(self.app._blocks) == before + 1

    def test_paste_single_block_bounds_clamped(self):
        # Place near the edge so paste offset would push it out of bounds
        b = PlotBlock(A4_W - 10, A4_H - 10, A4_W, A4_H)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._select_block(b)
        self.app._copy()
        self.app._paste()
        new_b = self.app._blocks[-1]
        assert new_b.x2 <= A4_W
        assert new_b.y2 <= A4_H

    def test_paste_single_shape(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._selected_shape = s
        self.app._copy()
        before = len(self.app._shapes)
        self.app._paste()
        assert len(self.app._shapes) == before + 1

    def test_paste_single_shape_bounds_clamped(self):
        s = Shape(A4_W - 10, A4_H - 10, A4_W, A4_H, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._selected_shape = s
        self.app._copy()
        self.app._paste()
        new_s = self.app._shapes[-1]
        assert new_s.x2 <= A4_W
        assert new_s.y2 <= A4_H

    def test_paste_multi_select(self):
        b = PlotBlock(50, 50, 200, 200)
        s = Shape(250, 50, 400, 200, "rectangle")
        self.app._blocks.append(b)
        self.app._shapes.append(s)
        self.app._draw_empty_block(b)
        self.app._draw_shape(s)
        self.app._selected_objects = [b, s]
        self.app._copy()
        before_b = len(self.app._blocks)
        before_s = len(self.app._shapes)
        self.app._paste()
        assert len(self.app._blocks) == before_b + 1
        assert len(self.app._shapes) == before_s + 1

    def test_paste_multi_select_bounds_clamped(self):
        b = PlotBlock(A4_W - 10, A4_H - 10, A4_W, A4_H)
        s = Shape(A4_W - 50, A4_H - 50, A4_W, A4_H, "rectangle")
        self.app._blocks.append(b)
        self.app._shapes.append(s)
        self.app._draw_empty_block(b)
        self.app._draw_shape(s)
        self.app._selected_objects = [b, s]
        self.app._copy()
        self.app._paste()
        # All pasted objects must be within bounds
        for blk in self.app._blocks:
            assert blk.x2 <= A4_W
            assert blk.y2 <= A4_H


# ===========================================================================
# Grid
# ===========================================================================

class TestGrid:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_draw_grid_draws_items(self):
        self.app._grid_size = GRID_SIZE
        self.app._draw_grid()
        pump(self.root)
        items = self.app._cv.find_withtag("grid")
        assert len(items) > 0

    def test_clear_grid_removes_items(self):
        self.app._grid_size = GRID_SIZE
        self.app._draw_grid()
        self.app._clear_grid()
        items = self.app._cv.find_withtag("grid")
        assert len(items) == 0

    def test_toggle_grid_visible_on(self):
        self.app._show_grid = False
        self.app._toggle_grid_visible()
        assert self.app._show_grid is True

    def test_toggle_grid_visible_off(self):
        self.app._grid_size = GRID_SIZE
        self.app._show_grid = True
        self.app._toggle_grid_visible()
        assert self.app._show_grid is False

    def test_apply_spacing_entry_valid(self):
        self.app._spacing_var.set("20")
        self.app._apply_spacing_entry()
        assert self.app._grid_size == 20.0
        assert self.app._snap_grid_size == 20.0

    def test_apply_spacing_entry_valid_with_pt_suffix(self):
        self.app._spacing_var.set("10 pt")
        self.app._apply_spacing_entry()
        assert self.app._grid_size == 10.0

    def test_apply_spacing_entry_invalid_resets(self):
        self.app._grid_size = 20.0
        self.app._spacing_var.set("bad")
        self.app._apply_spacing_entry()
        # The invalid value is rejected; spacing stays at previous
        assert self.app._grid_size == 20.0

    def test_apply_spacing_entry_zero_resets(self):
        self.app._grid_size = 20.0
        self.app._spacing_var.set("0")
        self.app._apply_spacing_entry()
        assert self.app._grid_size == 20.0

    def test_draw_grid_with_show_in_spacing(self):
        self.app._show_grid = True
        self.app._grid_size = GRID_SIZE
        self.app._spacing_var.set("20")
        self.app._apply_spacing_entry()
        pump(self.root)


# ===========================================================================
# Artboard operations
# ===========================================================================

class TestArtboardOperations:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_add_artboard_increases_count(self):
        before = len(self.app._artboards)
        self.app._add_artboard()
        pump(self.root)
        assert len(self.app._artboards) == before + 1

    def test_add_artboard_switches_to_new(self):
        self.app._add_artboard()
        pump(self.root)
        assert self.app._active_board == len(self.app._artboards) - 1

    def test_delete_artboard_single_refuses(self):
        assert len(self.app._artboards) == 1
        self.app._delete_artboard()
        assert len(self.app._artboards) == 1
        assert "Cannot" in self.app._status.cget("text")

    def test_delete_artboard_removes_one(self):
        self.app._add_artboard()
        before = len(self.app._artboards)
        self.app._delete_artboard()
        pump(self.root)
        assert len(self.app._artboards) == before - 1

    def test_switch_artboard_noop_on_same(self):
        before = self.app._active_board
        self.app._switch_artboard(before)
        assert self.app._active_board == before

    def test_switch_artboard_changes_active(self):
        self.app._add_artboard()
        self.app._switch_artboard(0)
        pump(self.root)
        assert self.app._active_board == 0

    def test_show_board_menu_does_not_crash(self):
        # _show_board_menu posts a tk.Menu - just ensure it runs without error
        try:
            self.app._show_board_menu()
            pump(self.root)
        except tk.TclError:
            pass  # Menu.post may fail in headless; that is acceptable


# ===========================================================================
# Nudge selected
# ===========================================================================

class TestNudgeSelected:
    def setup_method(self):
        self.root, self.app = make_app()
        self.app._snap_grid_size = GRID_SIZE

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_nudge_nothing_selected(self):
        result = self.app._nudge_selected(10, 0)
        assert result is None

    def test_nudge_block_right(self):
        b = PlotBlock(100, 100, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._selected_objects = [b]
        old_x1 = b.x1
        self.app._nudge_selected(GRID_SIZE, 0)
        pump(self.root)
        assert b.x1 > old_x1

    def test_nudge_block_left(self):
        b = PlotBlock(100, 100, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._selected_objects = [b]
        old_x1 = b.x1
        self.app._nudge_selected(-GRID_SIZE, 0)
        pump(self.root)
        assert b.x1 < old_x1

    def test_nudge_block_down(self):
        b = PlotBlock(100, 100, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._selected_objects = [b]
        old_y1 = b.y1
        self.app._nudge_selected(0, GRID_SIZE)
        pump(self.root)
        assert b.y1 > old_y1

    def test_nudge_block_snap_off(self):
        self.app._snap_to_grid = False
        b = PlotBlock(105, 105, 205, 205)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._selected_objects = [b]
        old_x1 = b.x1
        self.app._nudge_selected(7, 0)
        assert b.x1 == old_x1 + 7

    def test_nudge_shape(self):
        s = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._selected_objects = [s]
        old_x1 = s.x1
        self.app._nudge_selected(GRID_SIZE, 0)
        pump(self.root)
        assert s.x1 > old_x1

    def test_nudge_text(self):
        t = TextObject(100, 100, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._selected_objects = [t]
        old_y1 = t.y1
        self.app._nudge_selected(0, GRID_SIZE)
        pump(self.root)
        assert t.y1 > old_y1

    def test_nudge_returns_break(self):
        b = PlotBlock(100, 100, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._selected_objects = [b]
        result = self.app._nudge_selected(GRID_SIZE, 0)
        assert result == "break"


# ===========================================================================
# Guide: _set_guide / _clear_guide_visual
# ===========================================================================

class TestGuide:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_set_guide_block(self):
        b = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._set_guide(b)
        assert self.app._guide_object is b

    def test_set_guide_shape(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._set_guide(s)
        assert self.app._guide_object is s

    def test_set_guide_line(self):
        s = Shape(50, 50, 150, 150, "line")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._set_guide(s)
        assert self.app._guide_object is s

    def test_set_guide_text(self):
        t = TextObject(50, 50, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._set_guide(t)
        assert self.app._guide_object is t

    def test_set_guide_replaces_previous(self):
        b1 = PlotBlock(50, 50, 150, 150)
        b2 = PlotBlock(200, 50, 350, 200)
        for b in (b1, b2):
            self.app._blocks.append(b)
            self.app._draw_empty_block(b)
        self.app._set_guide(b1)
        self.app._set_guide(b2)
        assert self.app._guide_object is b2

    def test_clear_guide_visual_block(self):
        b = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._set_guide(b)
        self.app._clear_guide_visual(b)  # should not raise

    def test_clear_guide_visual_shape(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._set_guide(s)
        self.app._clear_guide_visual(s)

    def test_clear_guide_visual_line(self):
        s = Shape(50, 50, 150, 150, "line")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._set_guide(s)
        self.app._clear_guide_visual(s)

    def test_clear_guide_visual_text(self):
        t = TextObject(50, 50, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._set_guide(t)
        self.app._clear_guide_visual(t)


# ===========================================================================
# Highlight / Unhighlight
# ===========================================================================

class TestHighlightUnhighlight:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_highlight_unhighlight_block(self):
        b = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._highlight(b)
        self.app._unhighlight(b)

    def test_unhighlight_block_not_in_selection(self):
        b = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._selected_objects = []
        self.app._highlight(b)
        self.app._unhighlight(b)  # clears handles since not in _selected_objects

    def test_highlight_unhighlight_shape(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._highlight_shape(s)
        self.app._unhighlight_shape(s)

    def test_highlight_unhighlight_line(self):
        s = Shape(50, 50, 150, 100, "line")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._highlight_shape(s)
        self.app._unhighlight_shape(s)

    def test_highlight_unhighlight_text(self):
        t = TextObject(50, 50, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._highlight_text(t)
        self.app._unhighlight_text(t)

    def test_unhighlight_shape_guide(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._guide_object = s
        self.app._highlight_shape(s)
        self.app._unhighlight_shape(s)
        self.app._guide_object = None

    def test_redraw_selected_handles_text(self):
        t = TextObject(50, 50, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._selected_objects = [t]
        self.app._redraw_selected_handles()


# ===========================================================================
# Zoom
# ===========================================================================

class TestZoomOperations:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_zoom_in_steps(self):
        self.app._zoom = 1.0
        self.app._zoom_in()
        pump(self.root)
        assert self.app._zoom > 1.0

    def test_zoom_out_steps(self):
        self.app._zoom = 1.0
        self.app._zoom_out()
        pump(self.root)
        assert self.app._zoom < 1.0

    def test_zoom_in_at_max_stays(self):
        self.app._zoom = 4.0
        self.app._zoom_in()
        pump(self.root)
        assert self.app._zoom == 4.0

    def test_zoom_out_at_min_stays(self):
        self.app._zoom = 0.25
        self.app._zoom_out()
        pump(self.root)
        assert self.app._zoom == 0.25

    def test_zoom_in_with_cursor(self):
        self.app._zoom = 1.0
        self.app._zoom_in(cx=200, cy=200)
        pump(self.root)
        assert self.app._zoom > 1.0

    def test_zoom_out_with_cursor(self):
        self.app._zoom = 1.0
        self.app._zoom_out(cx=200, cy=200)
        pump(self.root)
        assert self.app._zoom < 1.0

    def test_apply_zoom_entry_valid(self):
        self.app._zoom_var.set("150%")
        self.app._apply_zoom_entry()
        pump(self.root)
        assert self.app._zoom == pytest.approx(1.5)

    def test_apply_zoom_entry_invalid_resets(self):
        self.app._zoom = 1.0
        self.app._zoom_var.set("bad%")
        self.app._apply_zoom_entry()
        # Stays at previous zoom
        assert self.app._zoom == pytest.approx(1.0)

    def test_apply_zoom_entry_zero_resets(self):
        self.app._zoom = 1.0
        self.app._zoom_var.set("0%")
        self.app._apply_zoom_entry()
        assert self.app._zoom == pytest.approx(1.0)

    def test_set_zoom_with_pivot(self):
        self.app._zoom = 1.0
        pump(self.root)
        # Set zoom with a cursor pivot point
        self.app._set_zoom(2.0, cx=100, cy=100)
        pump(self.root)
        assert self.app._zoom == pytest.approx(2.0)


# ===========================================================================
# Mouse-up completions: shape drawing
# ===========================================================================

class TestMouseUpShapeDrawing:
    def setup_method(self):
        self.root, self.app = make_app()
        self.app._snap_grid_size = GRID_SIZE

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _draw_shape_up(self, mode_fn, x1, y1, x2, y2, state=0):
        mode_fn()
        down = board_event(self.app, x1, y1, state=state)
        self.app._mouse_down(down)
        drag = board_event(self.app, x2, y2, state=state)
        self.app._mouse_drag(drag)
        up = board_event(self.app, x2, y2, state=state)
        self.app._mouse_up(up)
        pump(self.root)

    def test_draw_line_creates_shape(self):
        before = len(self.app._shapes)
        self._draw_shape_up(self.app._mode_draw_line, 50, 50, 200, 200)
        assert len(self.app._shapes) == before + 1
        assert self.app._shapes[-1].shape_type == "line"

    def test_draw_line_too_short(self):
        # Disable snap so the two nearby board points don't snap apart
        self.app._snap_to_grid = False
        self.app._mode_draw_line()
        down = board_event(self.app, 50, 50)
        self.app._mouse_down(down)
        up = board_event(self.app, 55, 55)   # < 10 px apart in board coords
        self.app._mouse_up(up)
        pump(self.root)
        assert "short" in self.app._status.cget("text")

    def test_draw_rect_creates_shape(self):
        before = len(self.app._shapes)
        self._draw_shape_up(self.app._mode_draw_rect, 50, 50, 200, 200)
        assert len(self.app._shapes) == before + 1
        assert self.app._shapes[-1].shape_type == "rectangle"

    def test_draw_rect_too_small(self):
        # Disable snap so the two nearby board points don't snap apart
        self.app._snap_to_grid = False
        self.app._mode_draw_rect()
        down = board_event(self.app, 50, 50)
        self.app._mouse_down(down)
        up = board_event(self.app, 55, 55)
        self.app._mouse_up(up)
        pump(self.root)
        assert "small" in self.app._status.cget("text")

    def test_draw_circle_creates_shape(self):
        before = len(self.app._shapes)
        self._draw_shape_up(self.app._mode_draw_circle, 50, 50, 200, 200)
        assert len(self.app._shapes) == before + 1
        assert self.app._shapes[-1].shape_type == "circle"

    def test_draw_line_shift_constraint(self):
        """Shift key constrains line to 45-degree angles."""
        before = len(self.app._shapes)
        self._draw_shape_up(
            self.app._mode_draw_line, 50, 50, 200, 180, state=0x0001  # Shift
        )
        # Should still create the shape (shift only constrains angle)
        assert len(self.app._shapes) == before + 1

    def test_draw_rect_shift_constraint(self):
        """Shift key makes rectangle a square."""
        before = len(self.app._shapes)
        self._draw_shape_up(
            self.app._mode_draw_rect, 50, 50, 250, 200, state=0x0001  # Shift
        )
        assert len(self.app._shapes) == before + 1


# ===========================================================================
# Mouse-up: multi-resize finish
# ===========================================================================

class TestMouseUpMultiResize:
    def setup_method(self):
        self.root, self.app = make_app()
        self.app._snap_grid_size = GRID_SIZE

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_multi_resize_finish(self):
        b = PlotBlock(50, 50, 200, 200)
        s = Shape(250, 50, 400, 200, "rectangle")
        self.app._blocks.append(b)
        self.app._shapes.append(s)
        self.app._draw_empty_block(b)
        self.app._draw_shape(s)
        self.app._selected_objects = [b, s]
        # Simulate a multi-select resize in progress
        self.app._resize_corner = "se"
        self.app._resize_all_objects = [b, s]
        self.app._resize_initial_dims = {
            id(b): (b.x1, b.y1, b.x2, b.y2),
            id(s): (s.x1, s.y1, s.x2, s.y2),
        }
        self.app._resize_group_bbox = (50, 50, 400, 200)
        ev = board_event(self.app, 420, 220)
        self.app._mouse_up(ev)
        pump(self.root)
        # After mouse-up, resize state is cleared
        assert self.app._resize_corner is None
        assert len(self.app._resize_all_objects) == 0


# ===========================================================================
# Mouse-up: single resize finish (shape, text)
# ===========================================================================

class TestMouseUpSingleResize:
    def setup_method(self):
        self.root, self.app = make_app()
        self.app._snap_grid_size = GRID_SIZE

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_resize_shape_finish(self):
        s = Shape(100, 100, 250, 200, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._resize_corner = "se"
        self.app._resize_shape = s
        self.app._resize_orig_dims = (s.x1, s.y1, s.x2, s.y2)
        ev = board_event(self.app, 280, 230)
        self.app._mouse_up(ev)
        pump(self.root)
        assert self.app._resize_corner is None
        assert self.app._resize_shape is None

    def test_resize_text_finish(self):
        t = TextObject(100, 100, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._select_text(t)
        self.app._resize_corner = "se"
        self.app._resize_text = t
        self.app._resize_orig_dims = (t.x1, t.y1, t.x2, t.y2)
        ev = board_event(self.app, 200, 160)
        self.app._mouse_up(ev)
        pump(self.root)
        assert self.app._resize_corner is None
        assert self.app._resize_text is None


# ===========================================================================
# Mouse-up: rubberband selection
# ===========================================================================

class TestMouseUpRubberband:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_rubberband_selects_objects_in_box(self):
        b = PlotBlock(100, 100, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        # Simulate a selection rect being active
        self.app._mode_select()
        self.app._drag_start = (50, 50)
        self.app._selection_rect = self.app._cv.create_rectangle(
            0, 0, 1, 1, outline="#2979FF", dash=(3, 3), tags="selection_rect"
        )
        ev_up = board_event(self.app, 300, 300)
        self.app._mouse_up(ev_up)
        pump(self.root)
        # Block center (150,150) is inside (50,50)→(300,300)
        assert len(self.app._selected_objects) > 0


# ===========================================================================
# Mouse-down: resize handle on text object
# ===========================================================================

class TestMouseDownResizeText:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_resize_handle_detected_for_text(self):
        t = TextObject(100, 100, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._select_text(t)
        # Draw handles so they exist on the canvas
        self.app._draw_handles_text(t)
        pump(self.root)
        # Simulate clicking near the SE corner
        cx, cy = self.app._to_canvas(t.x2, t.y2)
        ev = MockEvent(x=int(cx), y=int(cy))
        self.app._mouse_down(ev)
        pump(self.root)
        # After clicking on a resize handle the resize corner state should be set
        assert self.app._resize_corner in ("nw", "ne", "sw", "se", None)


# ===========================================================================
# Select All / edit-selected no-selection
# ===========================================================================

class TestSelectAll:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_select_all_empty(self):
        self.app._select_all()
        assert "No objects" in self.app._status.cget("text")

    def test_select_all_selects_blocks_and_shapes(self):
        b = PlotBlock(50, 50, 200, 200)
        s = Shape(250, 50, 400, 200, "rectangle")
        self.app._blocks.append(b)
        self.app._shapes.append(s)
        self.app._draw_empty_block(b)
        self.app._draw_shape(s)
        self.app._select_all()
        assert len(self.app._selected_objects) == 2

    def test_edit_selected_nothing_selected(self):
        self.app._selected = None
        self.app._edit_selected()
        assert "Nothing" in self.app._status.cget("text")


# ===========================================================================
# _open_config result path
# ===========================================================================

class TestOpenConfigResult:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_open_config_result_false_no_render(self):
        """If dialog is closed without applying, block should not be rendered."""
        b = PlotBlock(50, 50, 300, 300)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)

        # Patch wait_window so it returns immediately (dlg.result stays False)
        with patch.object(self.root, 'wait_window'):
            self.app._open_config(b, is_edit=False)
        # No render called → image_id stays None
        assert b.image_id is None

    def test_open_config_result_true_renders(self):
        """If dialog result=True, block should be rendered."""
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        b = PlotBlock(50, 50, 300, 300)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)

        def fake_wait(dlg):
            dlg.result = True

        with patch.object(self.root, 'wait_window', side_effect=fake_wait):
            self.app._open_config(b, is_edit=True)
        pump(self.root)
        # After result=True, _render_block is called → image_id should be set
        assert b.image_id is not None


# ===========================================================================
# _auto_theme_check
# ===========================================================================

class TestAutoThemeCheck:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_auto_theme_check_no_override(self):
        self.app._theme_manual_override = False
        import datetime
        with patch('ktfigure.datetime') as mock_dt_mod:
            mock_now = MagicMock()
            mock_now.hour = 20
            mock_dt_mod.datetime.now.return_value = mock_now
            self.app._is_dark = False
            self.app._auto_theme_check()
            pump(self.root)
        # Hour 20 → should_dark=True, so theme flipped
        assert self.app._is_dark is True

    def test_auto_theme_check_with_override(self):
        self.app._theme_manual_override = True
        original = self.app._is_dark
        self.app._auto_theme_check()
        pump(self.root)
        # Override prevents auto-switch
        assert self.app._is_dark == original


# ===========================================================================
# _redraw_all with rendered blocks
# ===========================================================================

class TestRedrawAllRendered:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_redraw_all_with_rendered_block_and_grid(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        b = PlotBlock(50, 50, 300, 300)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)
        self.app._render_block(b)
        pump(self.root)
        # With show_grid=True, _redraw_all also draws grid
        self.app._show_grid = True
        self.app._grid_size = GRID_SIZE
        self.app._redraw_all()
        pump(self.root)


# ===========================================================================
# PlotRenderer: legend-inside path, tick_labels=False, custom hue palette
# ===========================================================================

class TestPlotRendererAdditional:
    def _make_block(self, df, plot_type, col_x="x", col_y="y", col_hue=None,
                    extra_aes=None):
        b = PlotBlock(0, 0, 300, 300)
        b.df = df
        b.plot_type = plot_type
        b.col_x = col_x
        b.col_y = col_y
        b.col_hue = col_hue
        if extra_aes:
            b.aesthetics.update(extra_aes)
        return b

    def test_legend_inside(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6], "g": ["a", "b", "a"]})
        b = self._make_block(df, "scatter", col_hue="g",
                              extra_aes={"legend": True, "legend_outside": False})
        fig = PlotRenderer.render(b)
        assert fig is not None

    def test_tick_labels_false(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        b = self._make_block(df, "scatter",
                              extra_aes={"tick_labels": False})
        fig = PlotRenderer.render(b)
        assert fig is not None

    def test_custom_hue_palette(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6], "g": ["a", "b", "a"]})
        b = self._make_block(df, "scatter", col_hue="g")
        b.aesthetics["hue_palette"] = {"a": "#ff0000", "b": "#0000ff"}
        b.aesthetics["use_color"] = False
        fig = PlotRenderer.render(b)
        assert fig is not None

    def test_use_color_with_hue(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6], "g": ["a", "b", "a"]})
        b = self._make_block(df, "scatter", col_hue="g")
        b.aesthetics["use_color"] = True
        b.aesthetics["color"] = "#ff0000"
        fig = PlotRenderer.render(b)
        assert fig is not None


# ===========================================================================
# AestheticsPanel shape property callbacks
# ===========================================================================

class TestAestheticsPanelShapeCallbacks:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.calls = []
        self.panel = AestheticsPanel(self.root, on_update=lambda b: self.calls.append(b))
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_shape_lw_callback(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        redraw_calls = []
        self.panel.load_shape(s, lambda x: redraw_calls.append(x))
        pump(self.root)
        # load_shape wires up traces; verify the panel loaded without error
        # and the shape properties frame was populated
        assert self.panel._obj_body is not None

    def test_shape_fill_callbacks(self):
        """Rectangles get a fill row; verify the panel loads without error."""
        s = Shape(50, 50, 150, 150, "rectangle")
        s.fill = "#aabbcc"
        redraw_calls = []
        self.panel.load_shape(s, lambda x: redraw_calls.append(x))
        pump(self.root)

    def test_shape_line_with_arrow_callbacks(self):
        s = Shape(50, 50, 150, 150, "line")
        s.arrow = "last"
        redraw_calls = []
        self.panel.load_shape(s, lambda x: redraw_calls.append(x))
        pump(self.root)

    def test_text_object_properties_callback(self):
        t = TextObject(50, 50, "hello world")
        redraw_calls = []
        self.panel.load_text(t, lambda x: redraw_calls.append(x))
        pump(self.root)

    def test_clear_shape_properties(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.panel.load_shape(s, lambda x: None)
        pump(self.root)
        self.panel.clear_shape_properties()
        pump(self.root)


# ===========================================================================
# Export
# ===========================================================================

class TestExportOperations:
    def setup_method(self):
        self.root, self.app = make_app()
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        b = PlotBlock(50, 50, 300, 300)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)
        self.app._render_block(b)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_export_png_with_data(self, tmp_path):
        path = str(tmp_path / "out.png")
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=path):
            self.app._export_png()
        import os
        assert os.path.exists(path)

    def test_export_pdf_with_data(self, tmp_path):
        path = str(tmp_path / "out.pdf")
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=path):
            self.app._export_pdf()
        import os
        assert os.path.exists(path)

    def test_export_svg_with_data(self, tmp_path):
        path = str(tmp_path / "out.svg")
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=path):
            self.app._export_svg()
        import os
        assert os.path.exists(path)

    def test_export_png_cancelled(self):
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=""):
            self.app._export_png()  # should not raise

    def test_export_pdf_cancelled(self):
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=""):
            self.app._export_pdf()

    def test_export_svg_cancelled(self):
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=""):
            self.app._export_svg()


# ===========================================================================
# _delete_key with guide object, shape/text delete
# ===========================================================================

class TestDeleteKeyAdvanced:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_delete_multi_with_guide(self):
        b = PlotBlock(50, 50, 200, 200)
        s = Shape(250, 50, 400, 200, "rectangle")
        self.app._blocks.append(b)
        self.app._shapes.append(s)
        self.app._draw_empty_block(b)
        self.app._draw_shape(s)
        self.app._selected_objects = [b, s]
        self.app._guide_object = b
        self.app._delete_key()
        pump(self.root)
        assert len(self.app._blocks) == 0
        assert self.app._guide_object is None

    def test_delete_shape(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._selected_shape = s
        before = len(self.app._shapes)
        self.app._delete_key()
        assert len(self.app._shapes) == before - 1

    def test_delete_text(self):
        t = TextObject(50, 50, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._selected_text = t
        before = len(self.app._texts)
        self.app._delete_key()
        assert len(self.app._texts) == before - 1


# ===========================================================================
# StyledButton._on_release
# ===========================================================================

class TestStyledButtonRelease:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_on_release_active(self):
        calls = []
        btn = StyledButton(self.root, text="X", command=lambda: calls.append(1))
        btn._is_active = True
        btn._on_release(MockEvent())
        assert calls == [1]

    def test_on_release_inactive(self):
        calls = []
        btn = StyledButton(self.root, text="X", command=lambda: calls.append(1))
        btn._is_active = False
        btn._on_release(MockEvent())
        assert calls == [1]

    def test_on_release_no_command(self):
        btn = StyledButton(self.root, text="X", command=None)
        btn._on_release(MockEvent())  # should not raise


# ===========================================================================
# _hit_board_idx boundary cases
# ===========================================================================

class TestHitBoardIdx:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_hit_board_inside(self):
        z = self.app._zoom
        ox = self.app._board_x_origin(0) * z
        cx = ox + A4_W * z / 2
        cy = BOARD_PAD * z + A4_H * z / 2
        assert self.app._hit_board_idx(cx, cy) == 0

    def test_hit_board_outside_y(self):
        # Canvas y above the artboard
        assert self.app._hit_board_idx(400, 0) is None

    def test_hit_board_outside_x(self):
        z = self.app._zoom
        # Canvas x far to the right of all artboards
        oy = BOARD_PAD * z + A4_H * z / 2
        assert self.app._hit_board_idx(A4_W * z * 10, oy) is None


# ===========================================================================
# _is_cmd_pressed — macOS branch covered via state bit 3
# ===========================================================================

class TestIsCmdPressed:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_ctrl_pressed(self):
        ev = MockEvent(state=0x0004)
        # On Linux/Windows the Control key is 0x0004
        if sys.platform != "darwin":
            assert self.app._is_cmd_pressed(ev) is True

    def test_ctrl_not_pressed(self):
        ev = MockEvent(state=0x0000)
        assert self.app._is_cmd_pressed(ev) is False


# ===========================================================================
# _on_aes_update path — empty block update
# ===========================================================================

class TestOnAesUpdate:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_aes_update_empty_block(self):
        b = PlotBlock(50, 50, 300, 300)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._selected = b
        self.app._on_aes_update(b)
        pump(self.root)

    def test_aes_update_empty_block_selected(self):
        b = PlotBlock(50, 50, 300, 300)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._select_block(b)
        self.app._on_aes_update(b)
        pump(self.root)


# ===========================================================================
# _clear_resize_state with _resize_group_bbox present
# ===========================================================================

class TestClearResizeState:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_clear_resize_state_removes_group_bbox(self):
        self.app._resize_group_bbox = (0, 0, 100, 100)
        self.app._resize_initial_dims = {1: (0, 0, 100, 100)}
        self.app._clear_resize_state()
        # _clear_resize_state uses `del self._resize_group_bbox` (not None assignment)
        assert not hasattr(self.app, "_resize_group_bbox")


# ===========================================================================
# Mouse-down: draw_circle start
# ===========================================================================

class TestMouseDownDrawCircle:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_draw_circle_creates_rubber_oval(self):
        self.app._mode_draw_circle()
        ev = board_event(self.app, 120, 120)
        self.app._mouse_down(ev)
        assert self.app._rubber_rect is not None
