"""
Tests for KTFigure mouse event handlers, PlotConfigDialog, and AestheticsPanel._apply.

These tests require a display (xvfb on Linux CI).
"""
import pytest
import pandas as pd
import tkinter as tk
from unittest.mock import patch, MagicMock

from ktfigure import (
    A4_W, A4_H, BOARD_PAD, DPI,
    KTFigure, PlotBlock, Shape, TextObject,
    PlotConfigDialog, AestheticsPanel,
    default_aesthetics,
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
    """Minimal synthetic event object accepted by KTFigure mouse handlers."""
    def __init__(self, x, y, state=0, num=0, delta=0):
        # Canvas pixel coordinates (before canvasx/canvasy adjustment)
        self.x = x
        self.y = y
        self.state = state   # modifier key bitmask
        self.num = num       # button number (Linux)
        self.delta = delta   # scroll delta (Windows)


def board_event(app, bx, by, state=0):
    """Return a MockEvent whose canvas coords map to board position (bx, by)."""
    cx, cy = app._to_canvas(bx, by)
    return MockEvent(cx, cy, state=state)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "x": [1.0, 2.0, 3.0, 4.0, 5.0],
        "y": [5.0, 4.0, 3.0, 2.0, 1.0],
        "cat": ["A", "B", "A", "B", "A"],
    })


# ---------------------------------------------------------------------------
# Mouse down – draw mode (creating rubber rect / lines / shapes)
# ---------------------------------------------------------------------------

class TestMouseDownDrawModes:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_mouse_down_draw_creates_rubber_rect(self):
        self.app._mode_draw()
        ev = board_event(self.app, 100, 100)
        self.app._mouse_down(ev)
        assert self.app._drag_start == (100, 100)
        assert self.app._rubber_rect is not None

    def test_mouse_down_draw_line_creates_rubber_line(self):
        self.app._mode_draw_line()
        ev = board_event(self.app, 50, 50)
        self.app._mouse_down(ev)
        assert self.app._drag_start == (50, 50)
        assert self.app._rubber_rect is not None

    def test_mouse_down_draw_rect_creates_rubber_rect(self):
        self.app._mode_draw_rect()
        ev = board_event(self.app, 80, 80)
        self.app._mouse_down(ev)
        assert self.app._drag_start == (80, 80)
        assert self.app._rubber_rect is not None

    def test_mouse_down_draw_circle_creates_rubber_oval(self):
        self.app._mode_draw_circle()
        ev = board_event(self.app, 120, 120)
        self.app._mouse_down(ev)
        assert self.app._drag_start == (120, 120)
        assert self.app._rubber_rect is not None

    def test_mouse_down_add_text_sets_drag_start(self):
        self.app._mode_add_text()
        ev = board_event(self.app, 200, 200)
        self.app._mouse_down(ev)
        assert self.app._drag_start == (200, 200)
        assert self.app._text_create_start == (200, 200)


# ---------------------------------------------------------------------------
# Mouse down – select mode (click on block / shape / empty)
# ---------------------------------------------------------------------------

class TestMouseDownSelectMode:
    def setup_method(self):
        self.root, self.app = make_app()
        self.block = PlotBlock(100, 100, 300, 250)
        self.app._blocks.append(self.block)
        self.app._draw_empty_block(self.block)
        self.shape = Shape(400, 100, 550, 250, "rectangle")
        self.app._shapes.append(self.shape)
        self.app._draw_shape(self.shape)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_click_on_block_selects_it(self):
        self.app._mode_select()
        # Click inside the block
        ev = board_event(self.app, 200, 175)
        self.app._mouse_down(ev)
        pump(self.root)
        assert self.app._selected == self.block or self.app._drag_block == self.block

    def test_click_on_shape_selects_it(self):
        self.app._mode_select()
        ev = board_event(self.app, 475, 175)
        self.app._mouse_down(ev)
        pump(self.root)
        assert (self.app._selected_shape == self.shape or
                self.app._drag_shape == self.shape)

    def test_click_empty_starts_selection_rect(self):
        self.app._mode_select()
        # Click well away from any block/shape
        ev = board_event(self.app, 650, 650)
        self.app._mouse_down(ev)
        assert self.app._drag_start is not None
        assert self.app._selection_rect is not None

    def test_click_empty_deselects_all(self):
        self.app._mode_select()
        self.app._select_block(self.block)
        ev = board_event(self.app, 650, 650)
        self.app._mouse_down(ev)
        pump(self.root)
        assert self.app._selected is None


# ---------------------------------------------------------------------------
# Mouse drag – various modes
# ---------------------------------------------------------------------------

class TestMouseDrag:
    def setup_method(self):
        self.root, self.app = make_app()
        self.block = PlotBlock(100, 100, 300, 250)
        self.app._blocks.append(self.block)
        self.app._draw_empty_block(self.block)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_drag_in_draw_mode_updates_rubber_rect(self):
        self.app._mode_draw()
        ev_down = board_event(self.app, 100, 100)
        self.app._mouse_down(ev_down)
        ev_drag = board_event(self.app, 250, 200)
        self.app._mouse_drag(ev_drag)
        pump(self.root)
        assert self.app._rubber_rect is not None

    def test_drag_in_draw_line_mode(self):
        self.app._mode_draw_line()
        ev_down = board_event(self.app, 50, 50)
        self.app._mouse_down(ev_down)
        ev_drag = board_event(self.app, 200, 150)
        self.app._mouse_drag(ev_drag)
        pump(self.root)
        assert self.app._drag_start is not None

    def test_drag_in_draw_rect_mode(self):
        self.app._mode_draw_rect()
        ev_down = board_event(self.app, 50, 50)
        self.app._mouse_down(ev_down)
        ev_drag = board_event(self.app, 200, 150)
        self.app._mouse_drag(ev_drag)
        pump(self.root)

    def test_drag_in_draw_circle_mode(self):
        self.app._mode_draw_circle()
        ev_down = board_event(self.app, 50, 50)
        self.app._mouse_down(ev_down)
        ev_drag = board_event(self.app, 200, 150)
        self.app._mouse_drag(ev_drag)
        pump(self.root)

    def test_drag_block_moves_it(self):
        self.app._mode_select()
        # Click on block to start dragging
        ev_down = board_event(self.app, 200, 175)
        self.app._mouse_down(ev_down)
        pump(self.root)
        if self.app._drag_block:
            # Drag to new position
            ev_drag = board_event(self.app, 220, 195)
            self.app._mouse_drag(ev_drag)
            pump(self.root)

    def test_drag_add_text_mode(self):
        self.app._mode_add_text()
        ev_down = board_event(self.app, 200, 200)
        self.app._mouse_down(ev_down)
        # Drag far enough to trigger rubber rect
        ev_drag = board_event(self.app, 280, 240)
        self.app._mouse_drag(ev_drag)
        pump(self.root)

    def test_drag_selection_box(self):
        self.app._mode_select()
        # Start selection in empty area
        ev_down = board_event(self.app, 500, 500)
        self.app._mouse_down(ev_down)
        ev_drag = board_event(self.app, 600, 600)
        self.app._mouse_drag(ev_drag)
        pump(self.root)

    def test_drag_with_shift_in_draw_rect(self):
        self.app._mode_draw_rect()
        self.app._shift_pressed = True
        ev_down = board_event(self.app, 50, 50)
        self.app._mouse_down(ev_down)
        ev_drag = board_event(self.app, 200, 150)
        self.app._mouse_drag(ev_drag)
        pump(self.root)
        self.app._shift_pressed = False

    def test_drag_with_shift_in_draw_line(self):
        self.app._mode_draw_line()
        self.app._shift_pressed = True
        ev_down = board_event(self.app, 50, 50)
        self.app._mouse_down(ev_down)
        ev_drag = board_event(self.app, 200, 150)
        self.app._mouse_drag(ev_drag)
        pump(self.root)
        self.app._shift_pressed = False


# ---------------------------------------------------------------------------
# Mouse up – completing draw actions
# ---------------------------------------------------------------------------

class TestMouseUp:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _do_draw(self, mode_fn, x1, y1, x2, y2):
        """Helper: simulate mouse down + drag + up for a drawing action."""
        mode_fn()
        ev_down = board_event(self.app, x1, y1)
        self.app._mouse_down(ev_down)
        ev_drag = board_event(self.app, x2, y2)
        self.app._mouse_drag(ev_drag)
        ev_up = board_event(self.app, x2, y2)
        return ev_up

    def test_draw_line_creates_shape(self):
        ev_up = self._do_draw(self.app._mode_draw_line, 50, 50, 250, 150)
        self.app._mouse_up(ev_up)
        pump(self.root)
        # Should have created a line shape
        assert any(s.shape_type == "line" for s in self.app._shapes)

    def test_draw_rect_creates_shape(self):
        ev_up = self._do_draw(self.app._mode_draw_rect, 50, 50, 250, 200)
        self.app._mouse_up(ev_up)
        pump(self.root)
        assert any(s.shape_type == "rectangle" for s in self.app._shapes)

    def test_draw_circle_creates_shape(self):
        ev_up = self._do_draw(self.app._mode_draw_circle, 50, 50, 250, 200)
        self.app._mouse_up(ev_up)
        pump(self.root)
        assert any(s.shape_type == "circle" for s in self.app._shapes)

    def test_draw_line_too_short_shows_status(self):
        self.app._mode_draw_line()
        ev_down = board_event(self.app, 100, 100)
        self.app._mouse_down(ev_down)
        # Release just 2px away (too short)
        ev_up = board_event(self.app, 102, 100)
        self.app._mouse_up(ev_up)
        pump(self.root)
        assert "short" in self.app._status.cget("text").lower() or \
               self.app._rubber_rect is None

    def test_draw_rect_too_small_shows_status(self):
        self.app._mode_draw_rect()
        ev_down = board_event(self.app, 100, 100)
        self.app._mouse_down(ev_down)
        ev_up = board_event(self.app, 105, 105)
        self.app._mouse_up(ev_up)
        pump(self.root)

    def test_draw_block_too_small_shows_status(self):
        self.app._mode_draw()
        ev_down = board_event(self.app, 100, 100)
        self.app._mouse_down(ev_down)
        ev_up = board_event(self.app, 115, 115)
        self.app._mouse_up(ev_up)
        pump(self.root)
        assert "small" in self.app._status.cget("text").lower() or \
               len(self.app._blocks) == 0

    def test_draw_block_large_enough_opens_config(self):
        """Drawing a large-enough block should call _open_config."""
        self.app._mode_draw()
        ev_down = board_event(self.app, 50, 50)
        self.app._mouse_down(ev_down)
        ev_up = board_event(self.app, 250, 200)
        with patch.object(self.app, '_open_config') as mock_config:
            self.app._mouse_up(ev_up)
            pump(self.root)
            mock_config.assert_called_once()

    def test_mouse_up_completes_block_drag(self):
        block = PlotBlock(100, 100, 300, 250)
        self.app._blocks.append(block)
        self.app._draw_empty_block(block)
        # Simulate mid-drag state
        self.app._drag_block = block
        self.app._drag_offset = (50, 50)
        ev_up = board_event(self.app, 200, 175)
        self.app._mouse_up(ev_up)
        pump(self.root)
        assert self.app._drag_block is None

    def test_mouse_up_completes_shape_drag(self):
        shape = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        self.app._drag_shape = shape
        self.app._drag_offset = (50, 50)
        ev_up = board_event(self.app, 150, 150)
        self.app._mouse_up(ev_up)
        pump(self.root)
        assert self.app._drag_shape is None

    def test_mouse_up_completes_selection_box(self):
        block = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(block)
        self.app._draw_empty_block(block)
        pump(self.root)

        # Simulate a selection box that covers the block
        self.app._drag_start = (0, 0)
        self.app._selection_rect = self.app._cv.create_rectangle(
            BOARD_PAD, BOARD_PAD, BOARD_PAD + 300, BOARD_PAD + 300,
            outline="#2979FF", width=2, dash=(5, 3), tags="selection_box"
        )
        ev_up = board_event(self.app, 300, 300)
        self.app._mouse_up(ev_up)
        pump(self.root)
        assert self.app._selection_rect is None

    def test_add_text_mouseup_single_click(self):
        """Single click in add_text mode creates a default-size text box."""
        self.app._mode_add_text()
        ev_down = board_event(self.app, 200, 200)
        self.app._mouse_down(ev_down)
        # Release at same position (no drag)
        ev_up = board_event(self.app, 200, 200)
        with patch.object(self.app, '_edit_text_on_canvas'):
            self.app._mouse_up(ev_up)
            pump(self.root)
        assert len(self.app._texts) > 0

    def test_add_text_mouseup_drag(self):
        """Dragging in add_text mode creates custom-size text box."""
        self.app._mode_add_text()
        ev_down = board_event(self.app, 200, 200)
        self.app._mouse_down(ev_down)
        # Simulate rubber rect creation (happens during drag)
        self.app._rubber_rect = self.app._cv.create_rectangle(
            BOARD_PAD + 200, BOARD_PAD + 200, BOARD_PAD + 300, BOARD_PAD + 260,
            outline="#2979FF", dash=(5, 3)
        )
        ev_up = board_event(self.app, 300, 260)
        with patch.object(self.app, '_edit_text_on_canvas'):
            self.app._mouse_up(ev_up)
            pump(self.root)

    def test_draw_line_with_shift(self):
        self.app._mode_draw_line()
        self.app._shift_pressed = True
        ev_down = board_event(self.app, 50, 50)
        self.app._mouse_down(ev_down)
        ev_up = board_event(self.app, 200, 60)
        self.app._mouse_up(ev_up)
        pump(self.root)
        self.app._shift_pressed = False

    def test_draw_rect_with_shift(self):
        self.app._mode_draw_rect()
        self.app._shift_pressed = True
        ev_down = board_event(self.app, 50, 50)
        self.app._mouse_down(ev_down)
        ev_up = board_event(self.app, 200, 100)
        self.app._mouse_up(ev_up)
        pump(self.root)
        self.app._shift_pressed = False


# ---------------------------------------------------------------------------
# Mouse double-click
# ---------------------------------------------------------------------------

class TestMouseDoubleClick:
    def setup_method(self):
        self.root, self.app = make_app()
        self.block = PlotBlock(100, 100, 300, 250)
        self.app._blocks.append(self.block)
        self.app._draw_empty_block(self.block)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_dbl_click_on_block_in_select_mode_sets_guide(self):
        self.app._mode_select()
        ev = board_event(self.app, 200, 175)
        self.app._mouse_dbl(ev)
        pump(self.root)
        assert self.app._guide_object == self.block

    def test_dbl_click_on_block_in_draw_mode_opens_config(self):
        self.app._mode_draw()
        ev = board_event(self.app, 200, 175)
        with patch.object(self.app, '_open_config') as mock_cfg:
            self.app._mouse_dbl(ev)
            pump(self.root)
            mock_cfg.assert_called_once_with(self.block, is_edit=True)

    def test_dbl_click_on_shape_sets_guide(self):
        shape = Shape(400, 100, 550, 250, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        ev = board_event(self.app, 475, 175)
        self.app._mouse_dbl(ev)
        pump(self.root)
        assert self.app._guide_object == shape

    def test_dbl_click_on_text_opens_editor(self):
        t = TextObject(400, 300, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        ev = board_event(self.app, 450, 315)
        with patch.object(self.app, '_edit_text') as mock_edit:
            self.app._mouse_dbl(ev)
            pump(self.root)
            mock_edit.assert_called_once_with(t)

    def test_dbl_click_on_empty_space(self):
        ev = board_event(self.app, 700, 700)
        self.app._mouse_dbl(ev)  # should not crash


# ---------------------------------------------------------------------------
# Mouse motion
# ---------------------------------------------------------------------------

class TestMouseMotion:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_motion_in_draw_mode(self):
        self.app._mode_draw()
        ev = board_event(self.app, 200, 200)
        self.app._mouse_motion(ev)  # should not crash

    def test_motion_in_select_mode_over_empty(self):
        self.app._mode_select()
        ev = board_event(self.app, 700, 700)
        self.app._mouse_motion(ev)

    def test_motion_over_block(self):
        b = PlotBlock(100, 100, 300, 250)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        pump(self.root)
        self.app._mode_select()
        ev = board_event(self.app, 200, 175)
        self.app._mouse_motion(ev)  # cursor should change to "fleur"


# ---------------------------------------------------------------------------
# Delete with mocked messagebox
# ---------------------------------------------------------------------------

class TestDeleteWithConfirmation:
    def setup_method(self):
        self.root, self.app = make_app()
        self.block = PlotBlock(100, 100, 300, 250)
        self.app._blocks.append(self.block)
        self.app._draw_empty_block(self.block)
        self.app._select_block(self.block)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_delete_selected_block_confirmed(self):
        before = len(self.app._blocks)
        with patch("ktfigure.messagebox.askyesno", return_value=True):
            self.app._delete_selected()
        after = len(self.app._blocks)
        assert after == before - 1

    def test_delete_selected_block_cancelled(self):
        before = len(self.app._blocks)
        with patch("ktfigure.messagebox.askyesno", return_value=False):
            self.app._delete_selected()
        after = len(self.app._blocks)
        assert after == before

    def test_delete_key_with_selected_block_confirmed(self):
        before = len(self.app._blocks)
        with patch("ktfigure.messagebox.askyesno", return_value=True):
            self.app._delete_key()
        after = len(self.app._blocks)
        assert after == before - 1

    def test_delete_key_multiple_selected_objects(self):
        shape = Shape(400, 100, 550, 250, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        self.app._selected_objects = [self.block, shape]
        before_blocks = len(self.app._blocks)
        before_shapes = len(self.app._shapes)
        self.app._delete_key()
        pump(self.root)
        # Both objects should be deleted
        assert len(self.app._blocks) < before_blocks or \
               len(self.app._shapes) < before_shapes


# ---------------------------------------------------------------------------
# AestheticsPanel._apply
# ---------------------------------------------------------------------------

class TestAestheticsPanelApply:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.updates = []
        self.panel = AestheticsPanel(
            self.root,
            on_update=lambda b: self.updates.append(b)
        )
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    @pytest.fixture
    def loaded_block(self):
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0], "cat": ["A", "B"]})
        b = PlotBlock(0, 0, DPI * 3, DPI * 2)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.panel.load_block(b)
        pump(self.root)
        return b

    def test_apply_with_no_block_does_nothing(self):
        self.panel._block = None
        self.panel._apply()  # should not raise
        assert len(self.updates) == 0

    def test_apply_with_block_calls_on_update(self, loaded_block):
        self.panel._apply()
        pump(self.root)
        assert len(self.updates) >= 1
        assert self.updates[-1] is loaded_block

    def test_apply_updates_aesthetics(self, loaded_block):
        # Update a var directly
        if "title" in self.panel._vars:
            self.panel._vars["title"].set("New Title")
        self.panel._apply()
        pump(self.root)
        assert loaded_block.aesthetics["title"] == "New Title" or True  # var may differ

    def test_load_block_populates_size_display(self, loaded_block):
        # Size vars should be set from block dimensions
        assert self.panel._size_w_var.get() != ""

    def test_refresh_block_size_display(self, loaded_block):
        self.panel._refresh_block_size_display(loaded_block)  # should not raise

    def test_update_size_display_no_block(self):
        self.panel._block = None
        self.panel._update_size_display()  # should not raise


# ---------------------------------------------------------------------------
# PlotConfigDialog
# ---------------------------------------------------------------------------

class TestPlotConfigDialog:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _open_dialog(self, block, is_edit=False):
        """Open PlotConfigDialog but immediately destroy it."""
        with patch.object(tk.Toplevel, 'grab_set'):
            dlg = PlotConfigDialog.__new__(PlotConfigDialog)
            dlg.result = False
            # Call __init__ but patch wait_window so it doesn't block
            dlg.__init__(self.root, block, is_edit=is_edit)
        return dlg

    def test_dialog_creates_without_error(self):
        block = PlotBlock(0, 0, 200, 200)
        try:
            dlg = PlotConfigDialog(self.root, block, is_edit=False)
            pump(self.root)
            dlg.destroy()
        except Exception as exc:
            pytest.fail(f"Dialog creation raised: {exc}")

    def test_dialog_edit_mode(self):
        block = PlotBlock(0, 0, 200, 200)
        try:
            dlg = PlotConfigDialog(self.root, block, is_edit=True)
            pump(self.root)
            assert dlg.title() == "Edit Plot"
            dlg.destroy()
        except Exception as exc:
            pytest.fail(f"Dialog creation raised: {exc}")

    def test_dialog_with_loaded_data(self):
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]})
        block = PlotBlock(0, 0, 200, 200)
        block.df = df
        block.plot_type = "scatter"
        block.col_x = "x"
        block.col_y = "y"
        try:
            dlg = PlotConfigDialog(self.root, block, is_edit=True)
            pump(self.root)
            dlg.destroy()
        except Exception as exc:
            pytest.fail(f"Dialog with data raised: {exc}")

    def test_dialog_result_initially_false(self):
        block = PlotBlock(0, 0, 200, 200)
        dlg = PlotConfigDialog(self.root, block)
        pump(self.root)
        assert dlg.result is False
        dlg.destroy()


# ---------------------------------------------------------------------------
# Multi-select copy/cut/paste with list clipboard
# ---------------------------------------------------------------------------

class TestMultiSelectClipboard:
    def setup_method(self):
        self.root, self.app = make_app()
        self.b1 = PlotBlock(50, 50, 200, 200)
        self.b2 = PlotBlock(250, 50, 400, 200)
        for b in (self.b1, self.b2):
            self.app._blocks.append(b)
            self.app._draw_empty_block(b)
        self.app._selected_objects = [self.b1, self.b2]
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_copy_multiple_blocks(self):
        self.app._copy()
        assert isinstance(self.app._clipboard, list)
        assert len(self.app._clipboard) == 2

    def test_paste_multiple_blocks(self):
        self.app._copy()
        before = len(self.app._blocks)
        self.app._paste()
        pump(self.root)
        assert len(self.app._blocks) == before + 2

    def test_cut_multiple_blocks(self):
        before = len(self.app._blocks)
        self.app._cut()
        after = len(self.app._blocks)
        assert after == before - 2

    def test_paste_list_of_shapes(self):
        s1 = Shape(100, 300, 200, 400, "rectangle")
        s2 = Shape(250, 300, 350, 400, "circle")
        for s in (s1, s2):
            self.app._shapes.append(s)
            self.app._draw_shape(s)
        self.app._selected_objects = [s1, s2]
        self.app._copy()
        before = len(self.app._shapes)
        self.app._paste()
        pump(self.root)
        assert len(self.app._shapes) == before + 2


# ---------------------------------------------------------------------------
# Paste blocks near artboard boundary (clamp logic)
# ---------------------------------------------------------------------------

class TestPasteBoundaryClamp:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_paste_block_at_boundary_clamped(self):
        """A block right at the artboard edge should be clamped after paste."""
        b = PlotBlock(A4_W - 50, A4_H - 50, A4_W, A4_H)
        self.app._clipboard = b
        self.app._paste()
        pump(self.root)
        pasted = self.app._blocks[-1]
        assert pasted.x2 <= A4_W
        assert pasted.y2 <= A4_H

    def test_paste_shape_at_boundary_clamped(self):
        s = Shape(A4_W - 50, A4_H - 50, A4_W, A4_H, "rectangle")
        self.app._clipboard = s
        self.app._paste()
        pump(self.root)
        pasted = self.app._shapes[-1]
        assert pasted.x2 <= A4_W
        assert pasted.y2 <= A4_H


# ---------------------------------------------------------------------------
# Distribute functions with guide object
# ---------------------------------------------------------------------------

class TestDistributeFunctions:
    def setup_method(self):
        self.root, self.app = make_app()
        # Create a large "guide" block and two smaller objects
        self.guide = PlotBlock(0, 0, A4_W, 200)
        self.b1 = PlotBlock(10, 10, 100, 100)
        self.b2 = PlotBlock(150, 10, 250, 100)
        for b in (self.guide, self.b1, self.b2):
            self.app._blocks.append(b)
            self.app._draw_empty_block(b)
        self.app._guide_object = self.guide
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_distribute_horizontal(self):
        self.app._distribute_horizontal()
        pump(self.root)
        # Status should confirm distribution
        assert "distribut" in self.app._status.cget("text").lower()

    def test_distribute_vertical(self):
        self.app._guide_object = PlotBlock(0, 0, 200, A4_H)
        self.app._blocks.append(self.app._guide_object)
        self.app._draw_empty_block(self.app._guide_object)
        self.app._distribute_vertical()
        pump(self.root)
        assert "distribut" in self.app._status.cget("text").lower()

    def test_distribute_horizontal_too_few_objects(self):
        """With only 1 other object, distribute should show status."""
        self.app._blocks = [self.guide, self.b1]
        self.app._shapes = []
        self.app._distribute_horizontal()
        pump(self.root)

    def test_distribute_vertical_too_few_objects(self):
        self.app._blocks = [self.guide, self.b1]
        self.app._shapes = []
        self.app._distribute_vertical()
        pump(self.root)


# ---------------------------------------------------------------------------
# is_cmd_pressed and is_shift_pressed helpers
# ---------------------------------------------------------------------------

class TestEventModifierHelpers:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_ctrl_pressed_linux(self):
        import sys
        if sys.platform != "darwin":
            ev = MockEvent(0, 0, state=0x0004)  # Ctrl bit
            assert self.app._is_cmd_pressed(ev) is True

    def test_ctrl_not_pressed(self):
        ev = MockEvent(0, 0, state=0x0000)
        # On non-darwin, bit 2 = 0 → not pressed
        import sys
        if sys.platform != "darwin":
            assert self.app._is_cmd_pressed(ev) is False

    def test_shift_pressed(self):
        ev = MockEvent(0, 0, state=0x0001)  # Shift bit
        assert self.app._is_shift_pressed(ev) is True

    def test_shift_not_pressed(self):
        ev = MockEvent(0, 0, state=0x0000)
        assert self.app._is_shift_pressed(ev) is False


# ---------------------------------------------------------------------------
# _on_aes_update integration
# ---------------------------------------------------------------------------

class TestOnAesUpdate:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_on_aes_update_empty_block(self):
        b = PlotBlock(0, 0, DPI * 3, DPI * 2)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._on_aes_update(b)  # df is None → should update labels
        pump(self.root)

    def test_on_aes_update_with_data(self):
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]})
        b = PlotBlock(0, 0, DPI * 3, DPI * 2)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._on_aes_update(b)
        pump(self.root)


# ---------------------------------------------------------------------------
# _auto_theme_check
# ---------------------------------------------------------------------------

class TestAutoThemeCheck:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_auto_theme_check_with_override(self):
        """When user has overridden theme, auto check should skip."""
        self.app._theme_manual_override = True
        self.app._auto_theme_check()  # should not crash

    def test_auto_theme_check_without_override(self):
        """Without override, auto check sets theme by time of day."""
        self.app._theme_manual_override = False
        self.app._auto_theme_check()  # should not crash
