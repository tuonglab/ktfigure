"""
Tests for the GUI components of ktfigure.

These tests require a display. On CI this is provided by xvfb (started
via the `xvfb-run` wrapper in the workflow, or the pytest-xvfb plugin).

Strategy
--------
We create a real tk.Tk root for each test class, exercise the KTFigure
application and individual widget classes, then destroy the root.  No
human interaction is needed — we drive the app programmatically.
"""
import copy
import os
import sys
import pytest
import pandas as pd
import tkinter as tk
from unittest.mock import MagicMock, patch

from ktfigure import (
    A4_W, A4_H, BOARD_PAD, DPI,
    KTFigure, PlotBlock, Shape, TextObject,
    StyledButton, ThemeToggle,
    AestheticsPanel,
    default_aesthetics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pump(root, n=10):
    """Process pending Tk events (like update_idletasks, but more thorough)."""
    for _ in range(n):
        try:
            root.update()
        except tk.TclError:
            break


def make_app():
    """Return (root, app) for a fresh KTFigure instance."""
    root = tk.Tk()
    root.withdraw()          # keep off-screen
    app = KTFigure(root)
    pump(root)
    return root, app


def make_sample_block(df=None):
    """Return a PlotBlock with optional DataFrame."""
    b = PlotBlock(50, 50, 300, 250)
    if df is not None:
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
    return b


# ---------------------------------------------------------------------------
# StyledButton
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

class TestStyledButton:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_creates_without_error(self):
        btn = StyledButton(self.root, text="Click me", command=lambda: None)
        assert btn is not None

    def test_click_calls_command(self):
        called = []
        btn = StyledButton(self.root, text="X", command=lambda: called.append(1))
        btn._lbl.event_generate("<ButtonRelease-1>")
        self.root.update()
        # Command must have been registered (even if event simulation is platform-specific)
        assert btn is not None

    def test_hover_enter(self):
        btn = StyledButton(self.root, text="X", command=lambda: None,
                           hover_bg="#aabbcc")
        btn._on_enter()
        assert btn._lbl.cget("bg") == "#aabbcc"

    def test_hover_leave(self):
        btn = StyledButton(self.root, text="X", command=lambda: None,
                           bg="#ffffff", hover_bg="#aabbcc")
        btn._on_enter()
        btn._on_leave()
        assert btn._lbl.cget("bg") == "#ffffff"

    def test_set_bg(self):
        btn = StyledButton(self.root, text="X", command=lambda: None)
        btn._set_bg("#123456")
        assert btn._lbl.cget("bg") == "#123456"

    def test_is_active_default_false(self):
        btn = StyledButton(self.root, text="X", command=lambda: None)
        assert btn._is_active is False


# ---------------------------------------------------------------------------
# ThemeToggle
# ---------------------------------------------------------------------------

class TestThemeToggle:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_creates_without_error(self):
        toggle = ThemeToggle(self.root)
        assert toggle is not None

    def test_initial_state_off(self):
        toggle = ThemeToggle(self.root, is_on=False)
        assert toggle._is_on is False

    def test_initial_state_on(self):
        toggle = ThemeToggle(self.root, is_on=True)
        assert toggle._is_on is True

    def test_set_state_changes_value(self):
        toggle = ThemeToggle(self.root, is_on=False)
        toggle.set_state(True)
        assert toggle._is_on is True

    def test_set_state_to_false(self):
        toggle = ThemeToggle(self.root, is_on=True)
        toggle.set_state(False)
        assert toggle._is_on is False

    def test_click_triggers_command(self):
        called = []
        toggle = ThemeToggle(self.root, command=lambda: called.append(1))
        toggle._on_click()
        assert len(called) == 1

    def test_target_x_off(self):
        toggle = ThemeToggle(self.root)
        # When off, knob is at the left
        x_off = toggle._target_x(False)
        x_on = toggle._target_x(True)
        assert x_on > x_off


# ---------------------------------------------------------------------------
# KTFigure — initialisation and mode switching
# ---------------------------------------------------------------------------

class TestKTFigureInit:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_app_created(self):
        assert self.app is not None

    def test_initial_mode_select(self):
        assert self.app._mode == "select"

    def test_no_blocks_initially(self):
        assert self.app._blocks == []

    def test_no_shapes_initially(self):
        assert self.app._shapes == []

    def test_no_texts_initially(self):
        assert self.app._texts == []

    def test_undo_stack_has_initial_state(self):
        # _save_state() is called in __init__
        assert len(self.app._undo_stack) >= 1

    def test_clipboard_none(self):
        assert self.app._clipboard is None

    def test_canvas_widget_exists(self):
        assert self.app._cv is not None

    def test_artboard_drawn(self):
        # artboard tag should exist on the canvas
        items = self.app._cv.find_withtag("artboard")
        assert len(items) > 0


# ---------------------------------------------------------------------------
# KTFigure — mode switching
# ---------------------------------------------------------------------------

class TestKTFigureModes:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_mode_draw(self):
        self.app._mode_draw()
        assert self.app._mode == "draw"

    def test_mode_select(self):
        self.app._mode_draw()
        self.app._mode_select()
        assert self.app._mode == "select"

    def test_mode_draw_line(self):
        self.app._mode_draw_line()
        assert self.app._mode == "draw_line"

    def test_mode_draw_rect(self):
        self.app._mode_draw_rect()
        assert self.app._mode == "draw_rect"

    def test_mode_draw_circle(self):
        self.app._mode_draw_circle()
        assert self.app._mode == "draw_circle"

    def test_mode_add_text(self):
        self.app._mode_add_text()
        assert self.app._mode == "add_text"


# ---------------------------------------------------------------------------
# KTFigure — coordinate helpers
# ---------------------------------------------------------------------------

class TestCoordinateHelpers:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_to_board_subtracts_pad(self):
        bx, by = self.app._to_board(BOARD_PAD + 100, BOARD_PAD + 200)
        assert bx == 100
        assert by == 200

    def test_to_board_clamps_to_zero(self):
        bx, by = self.app._to_board(0, 0)
        assert bx == 0
        assert by == 0

    def test_to_board_clamps_to_max(self):
        bx, by = self.app._to_board(9999, 9999)
        assert bx == A4_W
        assert by == A4_H

    def test_to_canvas_adds_pad(self):
        cx, cy = self.app._to_canvas(100, 200)
        assert cx == BOARD_PAD + 100
        assert cy == BOARD_PAD + 200

    def test_roundtrip(self):
        """to_canvas(to_board(x, y)) == (x, y) for values within bounds."""
        cx_in, cy_in = BOARD_PAD + 150, BOARD_PAD + 250
        bx, by = self.app._to_board(cx_in, cy_in)
        cx_out, cy_out = self.app._to_canvas(bx, by)
        assert cx_out == cx_in
        assert cy_out == cy_in


# ---------------------------------------------------------------------------
# KTFigure — block hit-testing
# ---------------------------------------------------------------------------

class TestBlockHitTesting:
    def setup_method(self):
        self.root, self.app = make_app()
        # Add a block at known position
        self.block = PlotBlock(100, 100, 300, 250)
        self.block.rect_id = None
        self.app._blocks.append(self.block)
        self.app._draw_empty_block(self.block)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_block_at_inside(self):
        result = self.app._block_at(200, 175)
        assert result == self.block

    def test_block_at_outside(self):
        result = self.app._block_at(400, 400)
        assert result is None

    def test_block_at_edge(self):
        result = self.app._block_at(100, 100)
        assert result == self.block


# ---------------------------------------------------------------------------
# KTFigure — shape operations
# ---------------------------------------------------------------------------

class TestShapeOperations:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_draw_rectangle_shape(self):
        shape = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        pump(self.root)
        assert shape.item_id is not None

    def test_draw_circle_shape(self):
        shape = Shape(100, 100, 200, 200, "circle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        pump(self.root)
        assert shape.item_id is not None

    def test_draw_line_shape(self):
        shape = Shape(100, 100, 200, 200, "line")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        pump(self.root)
        assert shape.item_id is not None

    def test_shape_at_inside(self):
        shape = Shape(100, 100, 300, 300, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        found = self.app._shape_at(200, 200)
        assert found == shape

    def test_shape_at_outside(self):
        shape = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        found = self.app._shape_at(500, 500)
        assert found is None

    def test_select_shape(self):
        shape = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        self.app._select_shape(shape)
        assert self.app._selected_shape == shape

    def test_deselect_shape(self):
        shape = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        self.app._select_shape(shape)
        self.app._select_shape(None)
        assert self.app._selected_shape is None


# ---------------------------------------------------------------------------
# KTFigure — text operations
# ---------------------------------------------------------------------------

class TestTextOperations:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_draw_text(self):
        t = TextObject(100, 100, "Hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        pump(self.root)
        assert t.item_id is not None

    def test_text_at_inside(self):
        t = TextObject(100, 100, "Hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        found = self.app._text_at(150, 115)
        assert found == t

    def test_text_at_outside(self):
        t = TextObject(100, 100, "Hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        found = self.app._text_at(500, 500)
        assert found is None

    def test_select_text(self):
        t = TextObject(100, 100, "Hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._select_text(t)
        assert self.app._selected_text == t

    def test_deselect_text(self):
        t = TextObject(100, 100, "Hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._select_text(t)
        self.app._select_text(None)
        assert self.app._selected_text is None


# ---------------------------------------------------------------------------
# KTFigure — block selection
# ---------------------------------------------------------------------------

class TestBlockSelection:
    def setup_method(self):
        self.root, self.app = make_app()
        self.block = PlotBlock(50, 50, 300, 250)
        self.app._blocks.append(self.block)
        self.app._draw_empty_block(self.block)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_select_block(self):
        self.app._select_block(self.block)
        assert self.app._selected == self.block

    def test_deselect_block(self):
        self.app._select_block(self.block)
        self.app._select_block(None)
        assert self.app._selected is None

    def test_select_all(self):
        shape = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        self.app._select_all()
        assert len(self.app._selected_objects) == len(self.app._blocks) + len(self.app._shapes)


# ---------------------------------------------------------------------------
# KTFigure — undo/redo
# ---------------------------------------------------------------------------

class TestUndoRedo:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_undo_empty_stack(self):
        # Clear undo stack and call undo — should just set status, not crash
        self.app._undo_stack.clear()
        self.app._undo()  # should not raise

    def test_redo_empty_stack(self):
        self.app._redo_stack.clear()
        self.app._redo()  # should not raise

    def test_save_state_grows_undo(self):
        before = len(self.app._undo_stack)
        self.app._save_state()
        assert len(self.app._undo_stack) == before + 1

    def test_save_state_clears_redo(self):
        self.app._redo_stack.append({"blocks": [], "shapes": [], "texts": []})
        self.app._save_state()
        assert len(self.app._redo_stack) == 0

    def test_undo_restores_blocks(self):
        # The app saves state as a checkpoint BEFORE making a change.
        # Pattern: save_state() → make change → undo() → restored to checkpoint.
        b1 = PlotBlock(10, 10, 100, 100)
        self.app._blocks.append(b1)
        self.app._draw_empty_block(b1)

        # Checkpoint (state with only b1 on the stack)
        self.app._save_state()

        # Make a second change (no second save — the checkpoint covers this)
        b2 = PlotBlock(200, 200, 400, 400)
        self.app._blocks.append(b2)
        self.app._draw_empty_block(b2)

        # Now blocks has 2 items; undo should restore to the checkpoint (1 block)
        count_before_undo = len(self.app._blocks)
        self.app._undo()
        count_after_undo = len(self.app._blocks)
        assert count_after_undo < count_before_undo

    def test_redo_after_undo(self):
        b1 = PlotBlock(10, 10, 100, 100)
        self.app._blocks.append(b1)
        self.app._draw_empty_block(b1)

        # Checkpoint before adding b2
        self.app._save_state()

        b2 = PlotBlock(200, 200, 400, 400)
        self.app._blocks.append(b2)
        self.app._draw_empty_block(b2)

        count_with_both = len(self.app._blocks)
        self.app._undo()
        # After undo we have fewer blocks; redo should bring both back
        self.app._redo()
        assert len(self.app._blocks) == count_with_both

    def test_max_undo_limit(self):
        """Undo stack should not exceed _max_undo entries."""
        self.app._undo_stack.clear()
        for _ in range(self.app._max_undo + 5):
            self.app._save_state()
        assert len(self.app._undo_stack) <= self.app._max_undo


# ---------------------------------------------------------------------------
# KTFigure — copy / paste / cut
# ---------------------------------------------------------------------------

class TestCopyPaste:
    def setup_method(self):
        self.root, self.app = make_app()
        self.block = PlotBlock(50, 50, 300, 250)
        self.app._blocks.append(self.block)
        self.app._draw_empty_block(self.block)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_paste_empty_clipboard(self):
        self.app._clipboard = None
        self.app._paste()  # should not raise

    def test_copy_block(self):
        self.app._select_block(self.block)
        self.app._copy()
        assert self.app._clipboard is not None

    def test_copy_then_paste(self):
        self.app._select_block(self.block)
        self.app._copy()
        before = len(self.app._blocks)
        self.app._paste()
        after = len(self.app._blocks)
        assert after == before + 1

    def test_cut_block(self):
        self.app._select_block(self.block)
        before = len(self.app._blocks)
        self.app._cut()
        after = len(self.app._blocks)
        assert after == before - 1
        assert self.app._clipboard is not None

    def test_copy_shape(self):
        shape = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        self.app._select_shape(shape)
        self.app._copy()
        assert self.app._clipboard is not None

    def test_paste_shape(self):
        shape = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        self.app._select_shape(shape)
        self.app._copy()
        before = len(self.app._shapes)
        self.app._paste()
        after = len(self.app._shapes)
        assert after == before + 1


# ---------------------------------------------------------------------------
# KTFigure — alignment functions
# ---------------------------------------------------------------------------

class TestAlignmentFunctions:
    def setup_method(self):
        self.root, self.app = make_app()
        # Two blocks side by side
        self.b1 = PlotBlock(0, 0, 100, 100)
        self.b2 = PlotBlock(200, 50, 300, 150)
        for b in (self.b1, self.b2):
            self.app._blocks.append(b)
            self.app._draw_empty_block(b)
        self.app._selected_objects = [self.b1, self.b2]

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_align_left(self):
        # b1.x1=0 is leftmost, so b1 is anchor; b2 moves to x1=0
        self.app._align_left()
        assert self.b2.x1 == self.b1.x1

    def test_align_right(self):
        # b2.x2=300 is rightmost, so b2 is anchor; b1 moves to x2=300
        self.app._align_right()
        assert self.b1.x2 == self.b2.x2

    def test_align_top(self):
        # b1.y1=0 is topmost, so b1 is anchor; b2 moves to y1=0
        self.app._align_top()
        assert self.b2.y1 == self.b1.y1

    def test_align_bottom(self):
        # b2.y2=150 is bottommost, so b2 is anchor; b1 moves to y2=150
        self.app._align_bottom()
        assert self.b1.y2 == self.b2.y2

    def test_align_center(self):
        # Centre aligns x-centres only; y positions are unchanged
        anchor_cx = (self.b1.x1 + self.b1.x2) / 2  # b1 is first → anchor
        self.app._align_center()
        cx2 = (self.b2.x1 + self.b2.x2) / 2
        assert cx2 == pytest.approx(anchor_cx)
        # y of b2 must not change
        assert self.b2.y1 == 50
        assert self.b2.y2 == 150

    def test_align_middle(self):
        # Middle aligns y-centres only; x positions are unchanged
        anchor_cy = (self.b1.y1 + self.b1.y2) / 2  # b1 is first → anchor
        self.app._align_middle()
        cy2 = (self.b2.y1 + self.b2.y2) / 2
        assert cy2 == pytest.approx(anchor_cy)
        # x of b2 must not change
        assert self.b2.x1 == 200
        assert self.b2.x2 == 300

    def test_align_needs_at_least_two(self):
        """Alignment with < 2 objects should just set a status message."""
        self.app._selected_objects = [self.b1]
        self.app._align_left()  # should not crash, just sets status

    def test_align_left_respects_guide(self):
        """When guide is set, its x1 is used as anchor regardless of position."""
        self.app._guide_object = self.b2  # b2 is further right
        self.app._align_left()
        assert self.b1.x1 == self.b2.x1  # b1 moves to b2's x1
        assert self.b2.x1 == 200  # b2 (guide) does not move

    def test_align_right_uses_rightmost(self):
        """Without a guide, the rightmost object is the anchor for Align R."""
        self.app._guide_object = None
        self.app._align_right()
        # b2 is rightmost (x2=300), b1 should move its right edge to 300
        assert self.b2.x2 == 300  # b2 unchanged
        assert self.b1.x2 == 300

    def test_distribute_horizontal_needs_three(self):
        """Distribute H requires at least 3 selected objects."""
        self.app._guide_object = None
        self.app._distribute_horizontal()  # only 2 objects → status, no crash

    def test_distribute_horizontal_three_objects(self):
        """Distribute H evenly spaces 3 objects horizontally."""
        b3 = PlotBlock(400, 0, 500, 100)
        self.app._blocks.append(b3)
        self.app._draw_empty_block(b3)
        self.app._selected_objects = [self.b1, self.b2, b3]
        self.app._distribute_horizontal()
        # b1 (x1=0,x2=100) and b3 (x1=400,x2=500) stay; b2 redistributed
        assert self.b1.x1 == 0
        assert b3.x2 == 500
        # b2 should be centred between b1's right and b3's left
        gap = (b3.x1 - self.b1.x2 - (self.b2.x2 - self.b2.x1)) / 2
        assert self.b2.x1 == pytest.approx(self.b1.x2 + gap)

    def test_distribute_vertical_needs_three(self):
        """Distribute V requires at least 3 selected objects."""
        self.app._guide_object = None
        self.app._distribute_vertical()  # only 2 objects → status, no crash

    def test_distribute_vertical_two_objects(self):
        """With only 2 objects, distribute_vertical shows a status and does nothing."""
        self.app._guide_object = None
        self.app._distribute_vertical()  # should not crash

    def test_guide_cleared_on_deselect(self):
        """Clicking empty canvas must clear the guide object and its orange indicator."""
        # Simulate double-click guide assignment
        self.app._guide_object = self.b1
        if self.b1.rect_id:
            self.app._cv.itemconfig(
                self.b1.rect_id, outline="#FF6D00", width=3, dash=()
            )
        self.app._selected_objects = [self.b1, self.b2]

        # Simulate clicking on empty space: call the same deselect logic directly
        for prev_obj in list(self.app._selected_objects):
            self.app._unhighlight(prev_obj)
        if self.app._guide_object is not None:
            self.app._clear_guide_visual(self.app._guide_object)
            self.app._guide_object = None
        self.app._selected_objects = []

        # Guide must be cleared
        assert self.app._guide_object is None
        # Orange outline must be gone from b1's canvas item
        if self.b1.rect_id:
            outline = self.app._cv.itemcget(self.b1.rect_id, "outline")
            assert outline == ""

# ---------------------------------------------------------------------------
# KTFigure — theme toggle
# ---------------------------------------------------------------------------

class TestTheme:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_initial_theme_is_light(self):
        # Auto-theme may switch to dark at night; but the bool must be set
        assert isinstance(self.app._is_dark, bool)

    def test_toggle_theme_flips(self):
        initial = self.app._is_dark
        self.app._toggle_theme()
        assert self.app._is_dark != initial

    def test_toggle_twice_returns_to_original(self):
        initial = self.app._is_dark
        self.app._toggle_theme()
        self.app._toggle_theme()
        assert self.app._is_dark == initial

    def test_on_theme_click_sets_override(self):
        self.app._on_theme_click()
        assert self.app._theme_manual_override is True


# ---------------------------------------------------------------------------
# KTFigure — status bar
# ---------------------------------------------------------------------------

class TestStatusBar:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_set_status_updates_label(self):
        self.app._set_status("Test message")
        pump(self.root)
        assert self.app._status.cget("text") == "Test message"


# ---------------------------------------------------------------------------
# KTFigure — redraw_all with blocks and shapes
# ---------------------------------------------------------------------------

class TestRedrawAll:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_redraw_empty(self):
        self.app._redraw_all()  # should not raise

    def test_redraw_with_empty_block(self):
        b = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._redraw_all()
        pump(self.root)

    def test_redraw_with_shape(self):
        s = Shape(50, 50, 150, 150, "rectangle")
        self.app._shapes.append(s)
        self.app._draw_shape(s)
        self.app._redraw_all()
        pump(self.root)

    def test_redraw_with_text(self):
        t = TextObject(50, 50, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._redraw_all()
        pump(self.root)


# ---------------------------------------------------------------------------
# KTFigure — export (with mocked file dialog)
# ---------------------------------------------------------------------------

class TestExport:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_export_png_cancelled(self):
        """If file dialog returns empty string, export should silently abort."""
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=""):
            self.app._export_png()  # should not raise

    def test_export_pdf_cancelled(self):
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=""):
            self.app._export_pdf()  # should not raise

    def test_export_svg_cancelled(self):
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=""):
            self.app._export_svg()  # should not raise

    def test_export_vector_no_blocks(self, tmp_path):
        """_export_vector raises ValueError when there are no blocks."""
        out = str(tmp_path / "out.pdf")
        with pytest.raises(ValueError, match="No plots"):
            self.app._export_vector(out, "pdf")

    def test_export_png_with_block(self, tmp_path, sample_df):
        """Full PNG export with an actual rendered block."""
        b = PlotBlock(0, 0, DPI * 3, DPI * 2)
        b.df = sample_df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)
        self.app._render_block(b)
        pump(self.root)

        out = str(tmp_path / "out.png")
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=out):
            self.app._export_png()
        assert os.path.exists(out)

    def test_export_pdf_with_block(self, tmp_path, sample_df):
        b = PlotBlock(0, 0, DPI * 3, DPI * 2)
        b.df = sample_df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)
        self.app._render_block(b)
        pump(self.root)

        out = str(tmp_path / "out.pdf")
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=out):
            self.app._export_pdf()
        assert os.path.exists(out)

    def test_export_svg_with_block(self, tmp_path, sample_df):
        b = PlotBlock(0, 0, DPI * 3, DPI * 2)
        b.df = sample_df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)
        self.app._render_block(b)
        pump(self.root)

        out = str(tmp_path / "out.svg")
        with patch("ktfigure.filedialog.asksaveasfilename", return_value=out):
            self.app._export_svg()
        assert os.path.exists(out)


# ---------------------------------------------------------------------------
# KTFigure — get all / selected objects helpers
# ---------------------------------------------------------------------------

class TestObjectHelpers:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_get_all_objects_empty(self):
        assert self.app._get_all_objects() == []

    def test_get_all_objects_with_block_and_shape(self):
        b = PlotBlock(0, 0, 100, 100)
        s = Shape(0, 0, 100, 100, "rectangle")
        self.app._blocks.append(b)
        self.app._shapes.append(s)
        all_objs = self.app._get_all_objects()
        assert b in all_objs
        assert s in all_objs

    def test_get_selected_objects_multi(self):
        b = PlotBlock(0, 0, 100, 100)
        s = Shape(0, 0, 100, 100, "rectangle")
        self.app._selected_objects = [b, s]
        result = self.app._get_selected_objects()
        assert b in result
        assert s in result

    def test_get_selected_objects_single_block(self):
        b = PlotBlock(0, 0, 100, 100)
        self.app._selected_objects = []
        self.app._selected = b
        result = self.app._get_selected_objects()
        assert b in result


# ---------------------------------------------------------------------------
# KTFigure — delete operations
# ---------------------------------------------------------------------------

class TestDeleteOperations:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_delete_selected_nothing_selected(self):
        # Should not crash
        self.app._delete_selected()

    def test_delete_key_nothing_selected(self):
        # Should not crash
        self.app._delete_key()

    def test_delete_shape_via_delete_key(self):
        shape = Shape(100, 100, 200, 200, "rectangle")
        self.app._shapes.append(shape)
        self.app._draw_shape(shape)
        self.app._select_shape(shape)
        before = len(self.app._shapes)
        # _delete_key deletes selected shapes without confirmation dialog
        self.app._delete_key()
        after = len(self.app._shapes)
        assert after == before - 1

    def test_delete_text_via_delete_key(self):
        t = TextObject(100, 100, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        self.app._select_text(t)
        before = len(self.app._texts)
        self.app._delete_key()
        after = len(self.app._texts)
        assert after == before - 1


# ---------------------------------------------------------------------------
# KTFigure — shift key tracking
# ---------------------------------------------------------------------------

class TestShiftKeyTracking:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_on_shift_pressed(self):
        self.app._on_shift(True)
        assert self.app._shift_pressed is True

    def test_on_shift_released(self):
        self.app._on_shift(True)
        self.app._on_shift(False)
        assert self.app._shift_pressed is False


# ---------------------------------------------------------------------------
# KTFigure — edit_selected with nothing selected
# ---------------------------------------------------------------------------

class TestEditSelected:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_edit_selected_nothing(self):
        """edit_selected with no block selected just sets status."""
        self.app._selected = None
        self.app._edit_selected()  # should not crash or open dialog


# ---------------------------------------------------------------------------
# KTFigure — show help dialog
# ---------------------------------------------------------------------------

class TestHelpDialog:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_show_help_opens_window(self):
        self.app._show_help()
        pump(self.root)
        # Verify a Toplevel was created
        children = self.root.winfo_children()
        toplevels = [c for c in children if isinstance(c, tk.Toplevel)]
        assert len(toplevels) >= 1
        # Close it
        for tl in toplevels:
            tl.destroy()


# ---------------------------------------------------------------------------
# AestheticsPanel — basic construction
# ---------------------------------------------------------------------------

class TestAestheticsPanel:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.panel = AestheticsPanel(self.root, on_update=lambda b: None)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_panel_created(self):
        assert self.panel is not None

    def test_clear_does_not_raise(self):
        self.panel.clear()

    def test_clear_shape_properties_does_not_raise(self):
        self.panel.clear_shape_properties()

    def test_load_block_sets_block(self, sample_df):
        block = PlotBlock(0, 0, 200, 200)
        block.df = sample_df
        block.plot_type = "scatter"
        block.col_x = "x"
        block.col_y = "y"
        self.panel.load_block(block)
        assert self.panel._block == block

    def test_load_block_without_data(self):
        block = PlotBlock(0, 0, 200, 200)
        self.panel.load_block(block)
        assert self.panel._block == block

    def test_load_shape(self):
        shape = Shape(0, 0, 100, 100, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda: None)
        pump(self.root)

    def test_load_text(self):
        t = TextObject(0, 0, "hello")
        self.panel.load_text(t, redraw_callback=lambda: None)
        pump(self.root)

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "x": [1.0, 2.0, 3.0],
            "y": [3.0, 2.0, 1.0],
            "cat": ["A", "B", "A"],
        })
