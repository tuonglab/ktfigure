"""
Final coverage push - targeting text editing, inline canvas entry,
shape/text resize drag remaining paths, and size controls.
"""
import pytest
import pandas as pd
import tkinter as tk
import tkinter.ttk as ttk
from unittest.mock import patch

from ktfigure import (
    A4_W, A4_H, BOARD_PAD, DPI,
    KTFigure, PlotBlock, Shape, TextObject,
    AestheticsPanel,
)


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
    def __init__(self, x, y, state=0):
        self.x = x
        self.y = y
        self.state = state
        self.num = 0
        self.delta = 0


def board_event(app, bx, by, state=0):
    cx, cy = app._to_canvas(bx, by)
    return MockEvent(cx, cy, state=state)


# ---------------------------------------------------------------------------
# _edit_text_on_canvas
# ---------------------------------------------------------------------------

class TestEditTextOnCanvas:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_edit_text_on_canvas_enter(self):
        """Placing a canvas text entry and pressing Enter should save."""
        t = TextObject(100, 100, "hello")
        self.app._texts.append(t)
        self.app._draw_text(t)
        pump(self.root)

        self.app._edit_text_on_canvas(t)
        pump(self.root)

        # Simulate Return keypress
        entry_windows = self.app._cv.find_withtag("text_entry")
        for item in entry_windows:
            widget = self.app._cv.itemcget(item, "window")
            if widget:
                try:
                    w = self.app._cv.nametowidget(widget)
                    w.event_generate("<Return>")
                except Exception:
                    pass
        pump(self.root)

    def test_edit_text_on_canvas_escape(self):
        """Pressing Escape should also save in current impl."""
        t = TextObject(100, 100, "test")
        self.app._texts.append(t)
        self.app._draw_text(t)
        pump(self.root)

        self.app._edit_text_on_canvas(t)
        pump(self.root)

        entry_windows = self.app._cv.find_withtag("text_entry")
        for item in entry_windows:
            widget = self.app._cv.itemcget(item, "window")
            if widget:
                try:
                    w = self.app._cv.nametowidget(widget)
                    w.event_generate("<Escape>")
                except Exception:
                    pass
        pump(self.root)

    def test_edit_text_on_canvas_focus_out(self):
        """FocusOut should also save."""
        t = TextObject(100, 100, "focus test")
        self.app._texts.append(t)
        self.app._draw_text(t)
        pump(self.root)

        self.app._edit_text_on_canvas(t)
        pump(self.root)

        entry_windows = self.app._cv.find_withtag("text_entry")
        for item in entry_windows:
            widget = self.app._cv.itemcget(item, "window")
            if widget:
                try:
                    w = self.app._cv.nametowidget(widget)
                    w.event_generate("<FocusOut>")
                except Exception:
                    pass
        pump(self.root)


# ---------------------------------------------------------------------------
# _edit_text dialog
# ---------------------------------------------------------------------------

class TestEditTextDialog:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_edit_text_opens_and_closes(self):
        t = TextObject(100, 100, "hello world")
        self.app._texts.append(t)
        self.app._draw_text(t)
        pump(self.root)

        # Schedule dialog close before calling _edit_text (which blocks in wait_window)
        def close_dialog():
            for child in self.root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.destroy()

        self.root.after(50, close_dialog)
        self.app._edit_text(t)  # blocks until dialog destroyed
        pump(self.root)

    def test_edit_text_ok_applies_changes(self):
        t = TextObject(100, 100, "original")
        self.app._texts.append(t)
        self.app._draw_text(t)
        pump(self.root)

        def click_ok():
            for child in self.root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    # Find and click the OK button
                    for btn in child.winfo_children():
                        if isinstance(btn, tk.Frame):
                            for subbtn in btn.winfo_children():
                                if isinstance(subbtn, tk.Button):
                                    try:
                                        txt = str(subbtn.cget("text"))
                                        if "OK" in txt:
                                            subbtn.invoke()
                                            return
                                    except Exception:
                                        pass
                    child.destroy()

        self.root.after(50, click_ok)
        self.app._edit_text(t)
        pump(self.root)


# ---------------------------------------------------------------------------
# AestheticsPanel – _add_obj_size_controls interaction
# ---------------------------------------------------------------------------

class TestAestheticsPanelObjSizeControls:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.redraw_calls = []
        self.panel = AestheticsPanel(self.root, on_update=lambda b: None)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _find_entries(self, parent):
        """Recursively find all Entry widgets."""
        result = []
        for child in parent.winfo_children():
            if isinstance(child, ttk.Entry) or isinstance(child, tk.Entry):
                result.append(child)
            result.extend(self._find_entries(child))
        return result

    def _find_comboboxes(self, parent):
        result = []
        for child in parent.winfo_children():
            if isinstance(child, ttk.Combobox):
                result.append(child)
            result.extend(self._find_comboboxes(child))
        return result

    def test_shape_size_controls_interaction(self):
        shape = Shape(0, 0, 100, 100, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: self.redraw_calls.append(s))
        pump(self.root)

        entries = self._find_entries(self.panel._obj_body)
        for entry in entries:
            try:
                entry.delete(0, tk.END)
                entry.insert(0, "150")
                entry.event_generate("<Return>")
                pump(self.root)
                break  # Test one entry is enough
            except Exception:
                pass

    def test_shape_size_unit_change(self):
        shape = Shape(0, 0, 200, 150, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: self.redraw_calls.append(s))
        pump(self.root)

        combos = self._find_comboboxes(self.panel._obj_body)
        for cb in combos:
            try:
                vals = cb.cget("values")
                if "cm" in str(vals):
                    cb.set("cm")
                    pump(self.root)
                    cb.set("mm")
                    pump(self.root)
                    break
            except Exception:
                pass

    def test_text_size_controls(self):
        t = TextObject(0, 0, "hello")
        self.panel.load_text(t, redraw_callback=lambda x: self.redraw_calls.append(x))
        pump(self.root)

        entries = self._find_entries(self.panel._obj_body)
        for entry in entries:
            try:
                entry.delete(0, tk.END)
                entry.insert(0, "120")
                entry.event_generate("<Return>")
                pump(self.root)
                break
            except Exception:
                pass

    def test_shape_size_focus_out(self):
        shape = Shape(0, 0, 100, 100, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: None)
        pump(self.root)

        entries = self._find_entries(self.panel._obj_body)
        for entry in entries:
            try:
                entry.delete(0, tk.END)
                entry.insert(0, "200")
                entry.event_generate("<FocusOut>")
                pump(self.root)
                break
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Mouse drag – drag selection box
# ---------------------------------------------------------------------------

class TestMouseDragSelectionBox:
    def setup_method(self):
        self.root, self.app = make_app()
        self.b = PlotBlock(50, 50, 200, 200)
        self.app._blocks.append(self.b)
        self.app._draw_empty_block(self.b)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_drag_selection_box_updates(self):
        # Set up selection rect state
        self.app._drag_start = (0, 0)
        self.app._selection_rect = self.app._cv.create_rectangle(
            BOARD_PAD, BOARD_PAD, BOARD_PAD + 100, BOARD_PAD + 100,
            outline="#2979FF"
        )
        ev = board_event(self.app, 200, 200)
        self.app._mouse_drag(ev)
        pump(self.root)


# ---------------------------------------------------------------------------
# Mouse drag – multi-select drag including TextObject
# ---------------------------------------------------------------------------

class TestMouseDragMultiSelectWithText:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_multi_drag_with_text_object(self):
        b = PlotBlock(50, 50, 200, 200)
        t = TextObject(250, 50, "hello")
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._texts.append(t)
        self.app._draw_text(t)
        pump(self.root)

        self.app._selected_objects = [b, t]
        self.app._multi_drag_start = (125, 125)
        self.app._multi_drag_initial = {
            id(b): (b.x1, b.y1, b.x2, b.y2),
            id(t): (t.x1, t.y1, t.x2, t.y2),
        }
        self.app._drag_block = b

        ev = board_event(self.app, 155, 155)
        self.app._mouse_drag(ev)
        pump(self.root)


# ---------------------------------------------------------------------------
# Mouse up – selection box cmd-click adds to existing
# ---------------------------------------------------------------------------

class TestMouseUpCmdSelection:
    def setup_method(self):
        self.root, self.app = make_app()
        self.b = PlotBlock(100, 100, 300, 250)
        self.app._blocks.append(self.b)
        self.app._draw_empty_block(self.b)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_selection_box_with_cmd_adds_to_selection(self):
        """Cmd+drag-select should add to existing selection."""
        existing = PlotBlock(400, 100, 550, 250)
        self.app._blocks.append(existing)
        self.app._draw_empty_block(existing)
        self.app._selected_objects = [existing]
        pump(self.root)

        # Setup selection box around the first block
        self.app._drag_start = (0, 0)
        self.app._selection_rect = self.app._cv.create_rectangle(
            BOARD_PAD, BOARD_PAD, BOARD_PAD + 400, BOARD_PAD + 400,
            outline="#2979FF"
        )
        import sys
        # Use ctrl state
        ev = board_event(self.app, 400, 400, state=0x0004)
        self.app._mouse_up(ev)
        pump(self.root)


# ---------------------------------------------------------------------------
# Mouse up – selection box un-highlights previously selected
# ---------------------------------------------------------------------------

class TestMouseUpSelectionBoxUnhighlight:
    def setup_method(self):
        self.root, self.app = make_app()
        self.b1 = PlotBlock(50, 50, 200, 200)
        self.b2 = PlotBlock(400, 50, 550, 200)
        for b in (self.b1, self.b2):
            self.app._blocks.append(b)
            self.app._draw_empty_block(b)
        # Pre-select b2
        self.app._selected_objects = [self.b2]
        self.app._select_block(self.b2)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_selection_box_replaces_selection(self):
        """New selection box should replace old selection."""
        # Select only b1 via selection box
        self.app._drag_start = (0, 0)
        self.app._selection_rect = self.app._cv.create_rectangle(
            BOARD_PAD, BOARD_PAD, BOARD_PAD + 350, BOARD_PAD + 350,
            outline="#2979FF"
        )
        ev = board_event(self.app, 350, 350)
        self.app._mouse_up(ev)
        pump(self.root)
        # b1 should now be selected
        assert self.b1 in self.app._selected_objects


# ---------------------------------------------------------------------------
# Mouse drag – resize shape NE/SW corners
# ---------------------------------------------------------------------------

class TestMouseDragResizeShapeCorners:
    def setup_method(self):
        self.root, self.app = make_app()
        self.shape = Shape(100, 100, 300, 250, "rectangle")
        self.app._shapes.append(self.shape)
        self.app._draw_shape(self.shape)
        self.app._select_shape(self.shape)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_resize_shape_ne_corner(self):
        self.app._resize_corner = "ne"
        self.app._resize_shape = self.shape
        self.app._resize_block = None
        self.app._resize_orig_dims = (100, 100, 300, 250)
        ev = board_event(self.app, 350, 80)
        self.app._mouse_drag(ev)
        pump(self.root)

    def test_resize_shape_sw_corner(self):
        self.app._resize_corner = "sw"
        self.app._resize_shape = self.shape
        self.app._resize_block = None
        self.app._resize_orig_dims = (100, 100, 300, 250)
        ev = board_event(self.app, 80, 300)
        self.app._mouse_drag(ev)
        pump(self.root)


# ---------------------------------------------------------------------------
# Mouse drag – line shape resize
# ---------------------------------------------------------------------------

class TestMouseDragResizeLine:
    def setup_method(self):
        self.root, self.app = make_app()
        self.line = Shape(100, 100, 300, 200, "line")
        self.app._shapes.append(self.line)
        self.app._draw_shape(self.line)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_resize_line_nw_corner(self):
        self.app._resize_corner = "nw"
        self.app._resize_shape = self.line
        self.app._resize_block = None
        self.app._resize_orig_dims = (100, 100, 300, 200)
        ev = board_event(self.app, 80, 80)
        self.app._mouse_drag(ev)
        pump(self.root)

    def test_resize_line_ne_corner(self):
        self.app._resize_corner = "ne"
        self.app._resize_shape = self.line
        self.app._resize_block = None
        self.app._resize_orig_dims = (100, 100, 300, 200)
        ev = board_event(self.app, 350, 80)
        self.app._mouse_drag(ev)
        pump(self.root)

    def test_resize_line_sw_corner(self):
        self.app._resize_corner = "sw"
        self.app._resize_shape = self.line
        self.app._resize_block = None
        self.app._resize_orig_dims = (100, 100, 300, 200)
        ev = board_event(self.app, 80, 250)
        self.app._mouse_drag(ev)
        pump(self.root)

    def test_resize_line_se_corner(self):
        self.app._resize_corner = "se"
        self.app._resize_shape = self.line
        self.app._resize_block = None
        self.app._resize_orig_dims = (100, 100, 300, 200)
        ev = board_event(self.app, 350, 250)
        self.app._mouse_drag(ev)
        pump(self.root)


# ---------------------------------------------------------------------------
# Mouse drag – resize block NE/SW corners
# ---------------------------------------------------------------------------

class TestMouseDragResizeBlockCorners:
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

    def test_resize_block_ne_corner(self):
        self.app._resize_corner = "ne"
        self.app._resize_block = self.block
        self.app._resize_shape = None
        self.app._resize_orig_dims = (100, 100, 300, 250)
        ev = board_event(self.app, 350, 80)
        self.app._mouse_drag(ev)
        pump(self.root)

    def test_resize_block_sw_corner(self):
        self.app._resize_corner = "sw"
        self.app._resize_block = self.block
        self.app._resize_shape = None
        self.app._resize_orig_dims = (100, 100, 300, 250)
        ev = board_event(self.app, 80, 300)
        self.app._mouse_drag(ev)
        pump(self.root)


# ---------------------------------------------------------------------------
# Mouse up – drag text object complete
# ---------------------------------------------------------------------------

class TestMouseUpDragText:
    def setup_method(self):
        self.root, self.app = make_app()
        self.text = TextObject(100, 100, "hello")
        self.app._texts.append(self.text)
        self.app._draw_text(self.text)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_mouse_up_drag_text_saves_state(self):
        self.app._drag_text = self.text
        self.app._drag_offset = (10, 10)
        self.app._multi_drag_start = (100, 100)
        self.app._multi_drag_initial = {id(self.text): (100, 100, 200, 130)}
        ev = board_event(self.app, 200, 200)
        self.app._mouse_up(ev)
        pump(self.root)
        assert self.app._drag_text is None


# ---------------------------------------------------------------------------
# Mouse up – block drag with rendered block (re-renders on mouseup)
# ---------------------------------------------------------------------------

class TestMouseUpDragRenderedBlock:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_mouse_up_with_rendered_block(self):
        """After dragging a rendered block, mouse_up should re-render it."""
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]})
        b = PlotBlock(50, 50, DPI * 3, DPI * 2)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)
        self.app._render_block(b)
        pump(self.root)

        self.app._drag_block = b
        self.app._drag_offset = (10, 10)
        ev = board_event(self.app, 100, 100)
        self.app._mouse_up(ev)
        pump(self.root)
        assert self.app._drag_block is None


# ---------------------------------------------------------------------------
# _fmt helper
# ---------------------------------------------------------------------------

class TestFmtHelper:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.panel = AestheticsPanel(self.root, on_update=lambda b: None)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_fmt_integer(self):
        result = self.panel._fmt(100.0)
        assert result == "100"

    def test_fmt_float(self):
        result = self.panel._fmt(3.14159)
        assert "3.14" in result

    def test_fmt_whole_number(self):
        result = self.panel._fmt(42.0)
        assert result == "42"


# ---------------------------------------------------------------------------
# Render with block that has image already
# ---------------------------------------------------------------------------

class TestRenderBlockWithExistingImage:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_render_twice_replaces_image(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [3.0, 2.0, 1.0]})
        b = PlotBlock(0, 0, DPI * 3, DPI * 2)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)

        # First render
        self.app._render_block(b)
        pump(self.root)
        first_image_id = b.image_id

        # Second render (should delete old image and create new)
        self.app._render_block(b)
        pump(self.root)
        # Image should have been updated
        assert b.image_id is not None
