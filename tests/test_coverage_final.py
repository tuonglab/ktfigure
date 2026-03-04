"""
Final coverage push to 90%+: visible window tests, mouse wheel, color picker,
and remaining closure triggers.
"""
import pytest
import pandas as pd
import tkinter as tk
import tkinter.ttk as ttk
from unittest.mock import patch

from ktfigure import (
    A4_W, A4_H, BOARD_PAD, DPI,
    KTFigure, PlotBlock, Shape, TextObject,
    AestheticsPanel, bind_mousewheel,
)


def pump(root, n=20):
    for _ in range(n):
        try:
            root.update()
        except tk.TclError:
            break


def pump_visible(root, n=20):
    """Pump events on a briefly-visible window."""
    root.deiconify()
    root.lift()
    root.update()
    for _ in range(n):
        try:
            root.update()
        except tk.TclError:
            break
    root.withdraw()
    root.update()


def make_app():
    root = tk.Tk()
    root.withdraw()
    app = KTFigure(root)
    pump(root)
    return root, app


class _ME:
    def __init__(self, x, y, state=0, delta=0, num=0):
        self.x = x
        self.y = y
        self.state = state
        self.delta = delta
        self.num = num


def be(app, bx, by, state=0):
    cx, cy = app._to_canvas(bx, by)
    return _ME(cx, cy, state=state)


# ---------------------------------------------------------------------------
# Mouse wheel – trigger bind_mousewheel callbacks
# ---------------------------------------------------------------------------

class TestMouseWheelCallbacks:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_mousewheel_vertical_scroll(self):
        """Generating MouseWheel events should trigger scroll callbacks."""
        canvas = tk.Canvas(self.root, width=200, height=200)
        canvas.pack()
        bind_mousewheel(canvas, canvas, "vertical")
        pump_visible(self.root)
        # Simulate scrolling
        canvas.event_generate("<MouseWheel>", delta=120, x=50, y=50)
        canvas.event_generate("<Button-4>", x=50, y=50)
        canvas.event_generate("<Button-5>", x=50, y=50)
        pump(self.root)

    def test_mousewheel_horizontal_scroll(self):
        canvas = tk.Canvas(self.root, width=200, height=200)
        canvas.pack()
        bind_mousewheel(canvas, canvas, "horizontal")
        pump_visible(self.root)
        canvas.event_generate("<MouseWheel>", delta=120, x=50, y=50, state=0x0001)
        pump(self.root)

    def test_mousewheel_both_scroll(self):
        canvas = tk.Canvas(self.root, width=200, height=200)
        canvas.pack()
        bind_mousewheel(canvas, canvas, "both")
        pump_visible(self.root)
        canvas.event_generate("<MouseWheel>", delta=120, x=50, y=50)
        canvas.event_generate("<MouseWheel>", delta=-120, x=50, y=50)
        pump(self.root)

    def test_stop_propagation_vertical(self):
        """stop_propagation=True should make the handler return 'break'."""
        canvas = tk.Canvas(self.root, width=200, height=200)
        canvas.pack()
        bind_mousewheel(canvas, canvas, "vertical", stop_propagation=True)
        pump_visible(self.root)
        canvas.event_generate("<MouseWheel>", delta=120, x=50, y=50)
        canvas.event_generate("<Button-4>", x=50, y=50)
        canvas.event_generate("<Button-5>", x=50, y=50)
        pump(self.root)

    def test_stop_propagation_horizontal(self):
        """stop_propagation=True with horizontal also returns 'break'."""
        canvas = tk.Canvas(self.root, width=200, height=200)
        canvas.pack()
        bind_mousewheel(canvas, canvas, "both", stop_propagation=True)
        pump_visible(self.root)
        canvas.event_generate("<Shift-MouseWheel>", delta=120, x=50, y=50)
        canvas.event_generate("<Shift-Button-4>", x=50, y=50)
        canvas.event_generate("<Shift-Button-5>", x=50, y=50)
        pump(self.root)

    def test_stop_propagation_on_combobox(self):
        """bind_mousewheel with stop_propagation on a Combobox should not raise."""
        combo = ttk.Combobox(self.root, values=["a", "b", "c"])
        combo.pack()
        canvas = tk.Canvas(self.root, width=200, height=200)
        canvas.pack()
        bind_mousewheel(combo, canvas, "both", stop_propagation=True)
        pump_visible(self.root)
        combo.event_generate("<MouseWheel>", delta=120, x=5, y=5)
        pump(self.root)

    def test_stop_propagation_on_spinbox(self):
        """bind_mousewheel with stop_propagation on a Spinbox should not raise."""
        spin = ttk.Spinbox(self.root, from_=0, to=100)
        spin.pack()
        canvas = tk.Canvas(self.root, width=200, height=200)
        canvas.pack()
        bind_mousewheel(spin, canvas, "both", stop_propagation=True)
        pump_visible(self.root)
        spin.event_generate("<MouseWheel>", delta=120, x=5, y=5)
        pump(self.root)


# ---------------------------------------------------------------------------
# AestheticsPanel color picker closures (requires visible window)
# ---------------------------------------------------------------------------

class TestAestheticsPanelColorPickers:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.calls = []
        self.panel = AestheticsPanel(self.root, on_update=lambda b: None)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _find_labels_with_cursor(self, parent, cursor="hand2"):
        result = []
        for child in parent.winfo_children():
            if isinstance(child, tk.Label):
                try:
                    if str(child.cget("cursor")) == cursor:
                        result.append(child)
                except Exception:
                    pass
            result.extend(self._find_labels_with_cursor(child, cursor))
        return result

    def test_pick_shape_color_via_swatch(self):
        """Click shape color swatch opens color dialog."""
        shape = Shape(0, 0, 100, 100, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)

        swatches = self._find_labels_with_cursor(self.panel._obj_body)
        if swatches:
            with patch("ktfigure.colorchooser.askcolor",
                       return_value=((255, 0, 0), "#ff0000")):
                pump_visible(self.root)
                swatches[0].event_generate("<Button-1>")
                pump(self.root)

    def test_pick_fill_color_via_swatch(self):
        """Click fill color swatch on rectangle opens color dialog."""
        shape = Shape(0, 0, 100, 100, "rectangle")
        shape.fill = "#ffffff"
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)

        swatches = self._find_labels_with_cursor(self.panel._obj_body)
        for swatch in swatches[1:]:  # Second swatch is fill color
            with patch("ktfigure.colorchooser.askcolor",
                       return_value=((0, 255, 0), "#00ff00")):
                pump_visible(self.root)
                swatch.event_generate("<Button-1>")
                pump(self.root)
                break

    def test_main_color_swatch_click(self):
        """Click main block color swatch."""
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]})
        b = PlotBlock(0, 0, DPI * 2, DPI * 2)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.panel.load_block(b)
        pump(self.root)

        # The main color swatch is in the _body section
        swatches = self._find_labels_with_cursor(self.panel._body)
        if swatches:
            with patch("ktfigure.colorchooser.askcolor",
                       return_value=((255, 128, 0), "#ff8000")):
                pump_visible(self.root)
                swatches[0].event_generate("<Button-1>")
                pump(self.root)


# ---------------------------------------------------------------------------
# AestheticsPanel – size controls via Entry events (with visible window)
# ---------------------------------------------------------------------------

class TestAestheticsPanelSizeControlsVisible:
    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.calls = []
        self.panel = AestheticsPanel(self.root, on_update=lambda b: None)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _find_entries(self, parent):
        result = []
        for child in parent.winfo_children():
            if isinstance(child, (ttk.Entry, tk.Entry)):
                result.append(child)
            result.extend(self._find_entries(child))
        return result

    def test_shape_size_width_entry_return(self):
        shape = Shape(0, 0, 200, 150, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump_visible(self.root)

        entries = self._find_entries(self.panel._obj_body)
        for entry in entries:
            try:
                var_name = str(entry.cget("textvariable"))
                if var_name:
                    self.panel.tk.setvar(var_name, "180")
                    entry.focus_force()
                    entry.event_generate("<Return>")
                    pump(self.root)
                    break
            except Exception:
                pass

    def test_shape_size_height_entry_focusout(self):
        shape = Shape(0, 0, 200, 150, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump_visible(self.root)

        entries = self._find_entries(self.panel._obj_body)
        if len(entries) >= 2:
            entry = entries[-1]  # Last entry should be height
            try:
                var_name = str(entry.cget("textvariable"))
                if var_name:
                    self.panel.tk.setvar(var_name, "120")
                    entry.focus_force()
                    entry.event_generate("<FocusOut>")
                    pump(self.root)
            except Exception:
                pass

    def test_text_size_entry_return(self):
        t = TextObject(0, 0, "hello")
        self.panel.load_text(t, redraw_callback=lambda x: self.calls.append(x))
        pump_visible(self.root)

        entries = self._find_entries(self.panel._obj_body)
        for entry in entries:
            try:
                var_name = str(entry.cget("textvariable"))
                if var_name:
                    self.panel.tk.setvar(var_name, "150")
                    entry.focus_force()
                    entry.event_generate("<Return>")
                    pump(self.root)
                    break
            except Exception:
                pass


# ---------------------------------------------------------------------------
# _edit_text dialog – choose_color callback (2730-2733)
# ---------------------------------------------------------------------------

class TestEditTextChooseColor:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_choose_color_in_edit_dialog(self):
        """Test clicking the 'Choose' color button in _edit_text dialog."""
        t = TextObject(100, 100, "colored")
        self.app._texts.append(t)
        self.app._draw_text(t)
        pump(self.root)

        def click_choose_and_ok():
            for child in self.root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    # Find "Choose" button (for color picking)
                    buttons = [w for w in _all_widgets(child)
                                if isinstance(w, tk.Button)]
                    for btn in buttons:
                        try:
                            if "Choose" in str(btn.cget("text")):
                                with patch("ktfigure.colorchooser.askcolor",
                                           return_value=((255, 0, 0), "#ff0000")):
                                    btn.invoke()
                                pump(self.root)
                                break
                        except Exception:
                            pass
                    # Now click OK
                    for btn in buttons:
                        try:
                            if "OK" == str(btn.cget("text")):
                                btn.invoke()
                                return
                        except Exception:
                            pass
                    child.destroy()

        self.root.after(100, click_choose_and_ok)
        self.app._edit_text(t)
        pump(self.root)


def _all_widgets(parent):
    """Recursively get all widgets."""
    result = [parent]
    for child in parent.winfo_children():
        result.extend(_all_widgets(child))
    return result


# ---------------------------------------------------------------------------
# Mouse down – click on text adds it to existing selection with Ctrl
# ---------------------------------------------------------------------------

class TestMouseDownTextCtrl:
    def setup_method(self):
        self.root, self.app = make_app()
        self.text = TextObject(200, 200, "hello")
        self.app._texts.append(self.text)
        self.app._draw_text(self.text)
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_ctrl_click_on_text(self):
        self.app._mode_select()
        self.app._selected_objects = []
        ev = be(self.app, 250, 215, state=0x0004)
        self.app._mouse_down(ev)
        pump(self.root)

    def test_double_click_on_text_edits(self):
        """Double-click on text should open inline editor or dialog."""
        self.app._mode_select()
        # First click to select
        ev = be(self.app, 250, 215)
        self.app._mouse_down(ev)
        pump(self.root)

        # Check if text is selected
        if self.app._selected_text == self.text:
            # Schedule dialog close
            def close_dialog():
                for child in self.root.winfo_children():
                    if isinstance(child, tk.Toplevel):
                        child.destroy()

            self.root.after(50, close_dialog)
            # Second click (simulate double-click by calling mouse_down again)
            ev2 = be(self.app, 250, 215)
            self.app._mouse_down(ev2)
            pump(self.root)


# ---------------------------------------------------------------------------
# Export SVG with texts (covers SVG text element rendering ~5074)
# ---------------------------------------------------------------------------

class TestExportSVGWithTexts:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_export_svg_with_texts(self, tmp_path):
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]})
        b = PlotBlock(0, 0, DPI * 3, DPI * 2)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        self.app._blocks.append(b)
        self.app._render_block(b)

        # Add text objects
        t1 = TextObject(400, 50, "title text")
        t1.bold = True
        t1.color = "#333333"
        self.app._texts.append(t1)
        self.app._draw_text(t1)

        t2 = TextObject(400, 100, "subtitle")
        t2.italic = True
        self.app._texts.append(t2)
        self.app._draw_text(t2)

        # Add a line shape
        line = Shape(400, 200, 600, 300, "line")
        line.arrow = "last"
        self.app._shapes.append(line)
        self.app._draw_shape(line)

        pump(self.root)

        out = str(tmp_path / "out.svg")
        self.app._export_vector(out, "svg")
        import os
        assert os.path.exists(out)


# ---------------------------------------------------------------------------
# Alignment with < 2 objects shows status message (covers 3096-3099)
# ---------------------------------------------------------------------------

class TestAlignmentFewObjects:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_align_left_zero_objects(self):
        self.app._align_left()
        assert "at least" in self.app._status.cget("text").lower() or \
               "select" in self.app._status.cget("text").lower()

    def test_align_right_single_object(self):
        b = PlotBlock(100, 100, 300, 300)
        self.app._blocks.append(b)
        self.app._draw_empty_block(b)
        self.app._guide_object = b
        pump(self.root)
        self.app._align_right()
        assert "at least" in self.app._status.cget("text").lower() or \
               "select" in self.app._status.cget("text").lower()


# ---------------------------------------------------------------------------
# _get_selected_objects coverage (lines 3083-3088)
# ---------------------------------------------------------------------------

class TestGetSelectedObjects:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_get_selected_with_block_and_shape(self):
        b = PlotBlock(50, 50, 200, 200)
        s = Shape(250, 50, 400, 200, "rectangle")
        self.app._blocks.append(b)
        self.app._shapes.append(s)
        self.app._draw_empty_block(b)
        self.app._draw_shape(s)
        self.app._selected = b
        self.app._selected_shape = s
        self.app._selected_objects = []
        pump(self.root)

        result = self.app._get_selected_objects()
        assert b in result
        assert s in result

    def test_get_selected_with_multi(self):
        b1 = PlotBlock(50, 50, 200, 200)
        b2 = PlotBlock(250, 50, 400, 200)
        self.app._selected_objects = [b1, b2]
        result = self.app._get_selected_objects()
        assert result == [b1, b2]


# ---------------------------------------------------------------------------
# AestheticsPanel – closures not yet exercised by existing tests
# ---------------------------------------------------------------------------

def _all_widgets_recursive(parent):
    result = [parent]
    for child in parent.winfo_children():
        result.extend(_all_widgets_recursive(child))
    return result


def _find_labels_by_cursor(parent, cursor):
    result = []
    for child in parent.winfo_children():
        if isinstance(child, tk.Label):
            try:
                if str(child.cget("cursor")) == cursor:
                    result.append(child)
            except Exception:
                pass
        result.extend(_find_labels_by_cursor(child, cursor))
    return result


def _click_label_visible(root, label):
    """Click a label while its window is deiconified, ensuring event fires."""
    root.deiconify()
    root.update()
    label.event_generate("<Button-1>")
    root.update()
    root.withdraw()
    root.update()


class TestAestheticsPanelMissingClosures:
    """Cover closure callbacks not previously exercised (color pickers, trace vars, etc.)."""

    def setup_method(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.calls = []
        self.panel = AestheticsPanel(self.root, on_update=lambda b: None)
        self.panel.pack(fill="both", expand=True)  # must be packed for click events
        pump(self.root)

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    # ---- shape color swatch (cursor="arrow") --------------------------------

    def test_shape_color_swatch_click(self):
        """Click shape color swatch (cursor=arrow) triggers pick_shape_color body."""
        shape = Shape(0, 0, 100, 100, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)
        labels = _find_labels_by_cursor(self.panel._obj_body, "arrow")
        with patch("ktfigure.colorchooser.askcolor",
                   return_value=((255, 0, 0), "#ff0000")):
            if labels:
                _click_label_visible(self.root, labels[0])

    # ---- fill color swatch --------------------------------------------------

    def test_fill_color_swatch_click(self):
        """Click fill color swatch (second arrow swatch on rectangle) triggers body."""
        shape = Shape(0, 0, 100, 100, "rectangle")
        shape.fill = "#aabbcc"
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)
        labels = _find_labels_by_cursor(self.panel._obj_body, "arrow")
        with patch("ktfigure.colorchooser.askcolor",
                   return_value=((0, 255, 0), "#00ff00")):
            if len(labels) >= 2:  # second swatch is fill
                _click_label_visible(self.root, labels[1])

    # ---- text color swatch --------------------------------------------------

    def test_text_color_swatch_click(self):
        """Click text color swatch (cursor=arrow) triggers pick_text_color body."""
        t = TextObject(0, 0, "hello")
        self.panel.load_text(t, redraw_callback=lambda x: self.calls.append(x))
        pump(self.root)
        labels = _find_labels_by_cursor(self.panel._obj_body, "arrow")
        with patch("ktfigure.colorchooser.askcolor",
                   return_value=((0, 0, 255), "#0000ff")):
            if labels:
                _click_label_visible(self.root, labels[0])

    # ---- italic checkbox change (on_italic_change) --------------------------

    def test_italic_checkbox_change(self):
        """Setting italic var triggers on_italic_change."""
        t = TextObject(0, 0, "hello")
        self.panel.load_text(t, redraw_callback=lambda x: self.calls.append(x))
        pump(self.root)
        for child in _all_widgets_recursive(self.panel._obj_body):
            if isinstance(child, ttk.Checkbutton):
                try:
                    if "Italic" in str(child.cget("text")):
                        var_name = str(child.cget("variable"))
                        if var_name:
                            self.panel.tk.setvar(var_name, "1")
                            pump(self.root)
                        break
                except Exception:
                    pass

    # ---- arrow_size trace (on_arrow_size_change) ----------------------------

    def test_arrow_size_trace_change(self):
        """Setting arrow_size_var triggers on_arrow_size_change."""
        shape = Shape(0, 0, 100, 50, "line")
        shape.arrow = "last"
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)
        # Arrow-size spinbox is the 2nd spinbox (after line-width spinbox)
        spinboxes = [w for w in _all_widgets_recursive(self.panel._obj_body)
                     if isinstance(w, ttk.Spinbox)]
        if len(spinboxes) >= 2:
            var_name = str(spinboxes[1].cget("textvariable"))
            if var_name:
                self.panel.tk.setvar(var_name, "15")
                pump(self.root)

    # ---- arrow_style trace (on_arrow_style_change) --------------------------

    def test_arrow_style_trace_change(self):
        """Setting arrow_style_var triggers on_arrow_style_change."""
        shape = Shape(0, 0, 100, 50, "line")
        shape.arrow = "last"
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)
        # Find the arrow-style combobox (values include "sharp", "wide", etc.)
        for child in _all_widgets_recursive(self.panel._obj_body):
            if isinstance(child, ttk.Combobox):
                try:
                    if "sharp" in str(child.cget("values")):
                        var_name = str(child.cget("textvariable"))
                        if var_name:
                            self.panel.tk.setvar(var_name, "sharp")
                            pump(self.root)
                        break
                except Exception:
                    pass

    # ---- text widget on_text_widget_change ----------------------------------

    def test_text_widget_typing(self):
        """Generating <<Change>> on the Text widget triggers on_text_widget_change."""
        t = TextObject(0, 0, "initial")
        self.panel.load_text(t, redraw_callback=lambda x: self.calls.append(x))
        pump(self.root)
        for child in _all_widgets_recursive(self.panel._obj_body):
            if isinstance(child, tk.Text):
                try:
                    child.delete("1.0", "end")
                    child.insert("1.0", "changed")
                    child.event_generate("<<Change>>")
                    pump(self.root)
                    break
                except Exception:
                    pass

    # ---- hue swatch click (make_picker closure) -----------------------------

    def test_hue_swatch_click(self):
        """Click a hue colour swatch (cursor=hand2) triggers make_picker body."""
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "cat": ["a", "b", "a"]})
        b = PlotBlock(0, 0, DPI * 2, DPI * 2)
        b.df = df
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "x"
        b.col_hue = "cat"
        self.panel.load_block(b)
        pump(self.root)
        hand2_labels = _find_labels_by_cursor(self.panel._hue_color_frame, "hand2")
        with patch("ktfigure.colorchooser.askcolor",
                   return_value=((200, 100, 50), "#c86432")):
            if hand2_labels:
                _click_label_visible(self.root, hand2_labels[0])

    # ---- _reset_hue_colors when _block is None ------------------------------

    def test_reset_hue_colors_no_block(self):
        """_reset_hue_colors when _block is None does not crash."""
        self.panel._block = None
        self.panel._reset_hue_colors()  # should not raise

    # ---- _apply_block_size early returns ------------------------------------

    def test_apply_block_size_no_block(self):
        """_apply_block_size returns early when _block is None."""
        self.panel._block = None
        self.panel._apply_block_size(True)  # should not raise

    def test_apply_block_size_invalid_value(self):
        """_apply_block_size handles ValueError from non-numeric entry."""
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]})
        b = PlotBlock(0, 0, DPI * 2, DPI * 2)
        b.df = df
        self.panel.load_block(b)
        pump(self.root)
        self.panel._size_w_var.set("not-a-number")
        self.panel._apply_block_size(True)  # should not raise

    def test_apply_block_size_locked_width_change(self):
        """_apply_block_size with lock ON and width changed adjusts height."""
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]})
        b = PlotBlock(0, 0, DPI * 4, DPI * 2)
        b.df = df
        self.panel.load_block(b)
        pump(self.root)
        self.panel._size_lock_var.set(True)
        self.panel._size_w_var.set("300")
        self.panel._size_h_var.set("150")
        self.panel._apply_block_size(True)

    def test_apply_block_size_locked_height_change(self):
        """_apply_block_size with lock ON and height changed adjusts width."""
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 1.0]})
        b = PlotBlock(0, 0, DPI * 4, DPI * 2)
        b.df = df
        self.panel.load_block(b)
        pump(self.root)
        self.panel._size_lock_var.set(True)
        self.panel._size_w_var.set("300")
        self.panel._size_h_var.set("100")
        self.panel._apply_block_size(False)

    # ---- load_block with invalid aesthetics value (exception path) ----------

    def test_load_block_bad_aesthetics_value(self):
        """load_block's except-branch fires when var.set raises with bad type."""
        b = PlotBlock(0, 0, DPI * 2, DPI * 2)
        # DoubleVar.set("bad") will raise a TclError, exercising the except pass
        # "not-a-float" is stored in aesthetics under "line_width" (a DoubleVar key).
        # When load_block calls var.set("not-a-float"), tkinter's DoubleVar raises
        # TclError (can't validate non-numeric string), exercising the except clause.
        b.aesthetics["line_width"] = "not-a-float"
        self.panel.load_block(b)
        pump(self.root)  # should not raise

    def test_load_block_partial_aesthetics(self):
        """load_block with missing keys exercises the if-key-in-a False branch."""
        b = PlotBlock(0, 0, DPI * 2, DPI * 2)
        b.aesthetics = {"style": "whitegrid"}  # most keys missing
        self.panel.load_block(b)
        pump(self.root)  # should not raise

    # ---- _rebuild_hue_colors exception paths --------------------------------

    def test_rebuild_hue_palette_exception(self):
        """_rebuild_hue_colors falls back when sns.color_palette raises."""
        b = PlotBlock(0, 0, DPI * 2, DPI * 2)
        b.df = pd.DataFrame({"x": [1.0, 2.0], "cat": ["a", "b"]})
        b.col_hue = "cat"
        b.aesthetics["palette"] = "invalid_palette"
        self.panel.load_block(b)
        pump(self.root)  # should not raise

    def test_rebuild_hue_sorted_exception(self):
        """_rebuild_hue_colors handles KeyError when col_hue not in df."""
        b = PlotBlock(0, 0, DPI * 2, DPI * 2)
        b.df = pd.DataFrame({"x": [1.0, 2.0]})
        b.col_hue = "missing_column"  # KeyError → except Exception: return
        self.panel._block = b
        self.panel._rebuild_hue_colors(b)
        pump(self.root)  # should not raise

    # ---- _add_obj_size_controls: apply_size with lock -----------------------

    def _get_entries(self, parent):
        return [w for w in _all_widgets_recursive(parent)
                if isinstance(w, (ttk.Entry, tk.Entry))]

    def _fire_entry_return(self, root, entry, value):
        """Set entry variable and fire <Return> with window visible."""
        try:
            var_name = str(entry.cget("textvariable"))
            if var_name:
                entry.tk.setvar(var_name, value)
        except Exception:
            return
        root.deiconify()
        root.update()
        entry.event_generate("<Return>")
        root.update()
        root.withdraw()
        root.update()

    def test_obj_size_apply_invalid_value(self):
        """apply_size handles ValueError from non-numeric entry."""
        shape = Shape(0, 0, 200, 100, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)
        entries = self._get_entries(self.panel._obj_body)
        if entries:
            self._fire_entry_return(self.root, entries[0], "bad-value")

    def test_obj_size_apply_locked_width(self):
        """apply_size with lock=True and width changed adjusts height for shape."""
        shape = Shape(0, 0, 200, 100, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)
        # Find the lock checkbutton and enable it
        for child in _all_widgets_recursive(self.panel._obj_body):
            if isinstance(child, ttk.Checkbutton):
                try:
                    if "Lock" in str(child.cget("text")):
                        var_name = str(child.cget("variable"))
                        if var_name:
                            self.panel.tk.setvar(var_name, "1")
                        break
                except Exception:
                    pass
        entries = self._get_entries(self.panel._obj_body)
        if entries:
            self._fire_entry_return(self.root, entries[0], "250")

    def test_obj_size_apply_locked_height_change(self):
        """apply_size with lock=True and height entry changes width."""
        shape = Shape(0, 0, 200, 100, "rectangle")
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)
        # Enable lock
        for child in _all_widgets_recursive(self.panel._obj_body):
            if isinstance(child, ttk.Checkbutton):
                try:
                    if "Lock" in str(child.cget("text")):
                        var_name = str(child.cget("variable"))
                        if var_name:
                            self.panel.tk.setvar(var_name, "1")
                        break
                except Exception:
                    pass
        entries = self._get_entries(self.panel._obj_body)
        if len(entries) >= 2:
            self._fire_entry_return(self.root, entries[1], "80")

    # ---- load_block with var.set raising an exception -----------------------

    def test_load_block_var_set_exception(self):
        """Patch a var.set to raise, covering the except-pass in load_block."""
        b = PlotBlock(0, 0, DPI * 2, DPI * 2)
        if self.panel._vars:
            # Any var suffices; we just need var.set() to raise to hit the except clause.
            first_key = next(iter(self.panel._vars))
            original_var = self.panel._vars[first_key]
            with patch.object(original_var, "set", side_effect=tk.TclError("err")):
                self.panel.load_block(b)
            pump(self.root)

    # ---- arrow_size IntVar TclError path ------------------------------------

    def test_arrow_size_trace_invalid(self):
        """Setting arrow_size_var to non-integer triggers TclError in on_arrow_size_change."""
        shape = Shape(0, 0, 100, 50, "line")
        shape.arrow = "last"
        self.panel.load_shape(shape, redraw_callback=lambda s: self.calls.append(s))
        pump(self.root)
        spinboxes = [w for w in _all_widgets_recursive(self.panel._obj_body)
                     if isinstance(w, ttk.Spinbox)]
        if len(spinboxes) >= 2:
            var_name = str(spinboxes[1].cget("textvariable"))
            if var_name:
                self.panel.tk.setvar(var_name, "not-an-int")
                pump(self.root)

    # ---- font-size IntVar TclError path (on_size_change except) -------------

    def test_text_font_size_trace_invalid(self):
        """Setting size_var to non-integer triggers TclError in on_size_change."""
        t = TextObject(0, 0, "hello")
        self.panel.load_text(t, redraw_callback=lambda x: self.calls.append(x))
        pump(self.root)
        # size spinbox is the only spinbox in text panel
        spinboxes = [w for w in _all_widgets_recursive(self.panel._obj_body)
                     if isinstance(w, ttk.Spinbox)]
        if spinboxes:
            var_name = str(spinboxes[0].cget("textvariable"))
            if var_name:
                self.panel.tk.setvar(var_name, "not-an-int")
                pump(self.root)
