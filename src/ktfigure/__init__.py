#!/usr/bin/env python
"""
ktfigure
A GUI tool for researchers to create seaborn/matplotlib plots
without any coding knowledge.

Requirements:
    pip install pandas matplotlib seaborn pillow

Usage:
    python ktfigure.py
"""
import copy
import ctypes
import datetime
import io
import math
import os
import sys

import matplotlib
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import tkinter as tk

from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse, Rectangle
from tkinter import ttk, filedialog, messagebox, colorchooser

FONTTYPE = 42

# set the font so no weird lines and boxes are made during export
matplotlib.rcParams["pdf.fonttype"] = FONTTYPE
matplotlib.rcParams["ps.fonttype"] = FONTTYPE
matplotlib.use("Agg")  # off-screen rendering; we paste images onto the canvas


try:
    from PIL import Image, ImageTk

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
A4_W = 794  # A4 width  at 96 DPI  (210 mm → 8.27 in → 794 px)
A4_H = 1123  # A4 height at 96 DPI  (297 mm → 11.69 in → 1123 px)
BOARD_PAD = 60  # grey padding around the white artboard
DPI = 96
GRID_SIZE = 20  # pixels between grid lines (used for snap-to-grid)
HOVER_PAD = 5  # pixel buffer around objects for hover/cursor detection

# Unit conversion: multiply px value by these to get the given unit
# (or divide px by these to convert FROM the unit)
_UNIT_TO_PX = {
    "px": 1.0,
    "cm": DPI / 2.54,
    "mm": DPI / 25.4,
    "pts": DPI / 72.0,
}

# Minimum pixel sizes enforced when typing values in the size panel
_MIN_BLOCK_SIZE_PX = 40  # plot blocks
_MIN_OBJ_SIZE_PX = 10  # shapes and text objects

PLOT_TYPES = [
    "scatter",
    "line",
    "bar",
    "barh",
    "box",
    "violin",
    "strip",
    "swarm",
    "histogram",
    "kde",
    "heatmap",
    "count",
    "regression",
]

SEABORN_STYLES = ["whitegrid", "darkgrid", "white", "dark", "ticks"]

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------
THEME_LIGHT = {
    "tb": "#f8fafc",
    "btn": "#f1f5f9",
    "btn_fg": "#334155",
    "btn_hover": "#e2e8f0",
    "btn_press": "#cbd5e1",
    "sep": "#e2e8f0",
    "canvas": "#525252",
    "accent": "#3b82f6",
    "status_fg": "#334155",
    "panel_bg": "#ffffff",
}
THEME_DARK = {
    "tb": "#2d2d2d",
    "btn": "#3c3c3c",
    "btn_fg": "#cccccc",
    "btn_hover": "#505050",
    "btn_press": "#3a3a3a",
    "sep": "#555555",
    "canvas": "#3c3c3c",
    "accent": "#4fc3f7",
    "status_fg": "#cccccc",
    "panel_bg": "#252526",
}
SEABORN_PALETTES = [
    "deep",
    "muted",
    "bright",
    "pastel",
    "dark",
    "colorblind",
    "Blues",
    "Reds",
    "Greens",
    "Purples",
    "Oranges",
    "viridis",
    "plasma",
    "magma",
    "cividis",
    "Set1",
    "Set2",
    "Set3",
    "tab10",
    "tab20",
]
LINE_STYLES = ["-", "--", "-.", ":"]
MARKER_TYPES = ["o", "s", "^", "D", "v", "*", "x", "+", "None"]
LEGEND_LOCS = [
    "best",
    "upper right",
    "upper left",
    "lower right",
    "lower left",
    "upper center",
    "lower center",
    "center left",
    "center right",
    "center",
]

FONT_FAMILIES = sorted({f.name for f in fm.fontManager.ttflist})
FONT_FAMILIES = [
    "DejaVu Sans",
    "Arial",
    "Times New Roman",
    "Courier New",
    "Helvetica",
] + [
    f
    for f in FONT_FAMILIES
    if f not in ("DejaVu Sans", "Arial", "Times New Roman", "Courier New", "Helvetica")
][
    :40
]


# ---------------------------------------------------------------------------
# Mouse wheel scrolling helper
# ---------------------------------------------------------------------------
def bind_mousewheel(widget, canvas_or_scrollable, orientation="vertical"):
    """Bind mouse wheel events to a widget for scrolling a canvas or scrollable widget.

    Args:
        widget: The widget to bind events to (e.g., frame, canvas)
        canvas_or_scrollable: The canvas or treeview to scroll
        orientation: "vertical", "horizontal", or "both"
    """

    def _on_mousewheel(event):
        # Determine scroll direction and amount
        if event.num == 4 or event.delta > 0:
            delta = -1
        elif event.num == 5 or event.delta < 0:
            delta = 1
        else:
            delta = -int(event.delta / 120)

        # Apply scroll based on orientation
        if orientation in ("vertical", "both"):
            if hasattr(canvas_or_scrollable, "yview_scroll"):
                canvas_or_scrollable.yview_scroll(delta, "units")
        if orientation in ("horizontal", "both") and event.state & 0x1:  # Shift key
            if hasattr(canvas_or_scrollable, "xview_scroll"):
                canvas_or_scrollable.xview_scroll(delta, "units")

    def _on_horizontal_scroll(event):
        # Horizontal scroll for touchpads/Shift+wheel
        if event.num == 4 or event.delta > 0:
            delta = -1
        elif event.num == 5 or event.delta < 0:
            delta = 1
        else:
            delta = -int(event.delta / 120)

        if hasattr(canvas_or_scrollable, "xview_scroll"):
            canvas_or_scrollable.xview_scroll(delta, "units")

    # Bind for different platforms
    widget.bind("<MouseWheel>", _on_mousewheel)  # Windows/macOS
    widget.bind("<Button-4>", _on_mousewheel)  # Linux scroll up
    widget.bind("<Button-5>", _on_mousewheel)  # Linux scroll down

    if orientation in ("horizontal", "both"):
        widget.bind("<Shift-MouseWheel>", _on_horizontal_scroll)
        widget.bind("<Shift-Button-4>", _on_horizontal_scroll)
        widget.bind("<Shift-Button-5>", _on_horizontal_scroll)


# ---------------------------------------------------------------------------
# StyledButton  –  flat Frame+Label button with hover/press colours
# ---------------------------------------------------------------------------
class StyledButton(tk.Frame):
    """A flat button built from tk.Frame + tk.Label — no Canvas, cross-platform."""

    def __init__(
        self,
        parent,
        text,
        command=None,
        bg="#f1f5f9",
        fg="#1e293b",
        hover_bg="#e2e8f0",
        press_bg="#cbd5e1",
        canvas_bg="#f8fafc",  # ignored – kept for API compat
        padx=13,
        pady=7,
        font=("", 9),
        **kw,
    ):
        super().__init__(
            parent,
            bg=bg,
            cursor="arrow",
            bd=0,
            highlightthickness=1,
            highlightbackground=bg,
            highlightcolor=bg,
            **kw,
        )
        self._bg = bg
        self._hover_bg = hover_bg
        self._press_bg = press_bg
        self._command = command
        self._is_active = False  # Track if button is in active mode

        self._lbl = tk.Label(
            self,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            padx=padx,
            pady=pady,
            cursor="arrow",
        )
        self._lbl.pack()

        for widget in (self, self._lbl):
            widget.bind("<Enter>", lambda _e: self._on_enter())
            widget.bind("<Leave>", lambda _e: self._on_leave())
            widget.bind(
                "<Button-1>",
                lambda _e: self._set_bg(press_bg) if not self._is_active else None,
            )
            widget.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self):
        """Hover: only change bg if not active."""
        if not self._is_active:
            self._set_bg(self._hover_bg)

    def _on_leave(self):
        """Leave: restore appropriate bg based on active state."""
        if self._is_active:
            self._set_bg("#3b82f6")  # Keep blue when active
        else:
            self._set_bg(self._bg)

    def _set_bg(self, color):
        self.configure(bg=color, highlightbackground=color, highlightcolor=color)
        self._lbl.configure(bg=color)

    def _on_release(self, _e):
        if not self._is_active:
            self._set_bg(self._hover_bg)
        if self._command:
            self._command()


# ---------------------------------------------------------------------------
# ThemeToggle – iOS-style sliding switch for light / dark theme
# ---------------------------------------------------------------------------
class ThemeToggle(tk.Canvas):
    """Sliding toggle switch styled like macOS System Preferences."""

    W = 52  # total width  (px)
    H = 28  # total height (px)
    PAD = 3  # padding inside track around the knob

    TRACK_ON = "#3b82f6"  # accent blue  – dark mode active
    TRACK_OFF = "#94a3b8"  # slate grey   – light mode
    KNOB = "#ffffff"

    def __init__(self, parent, command=None, is_on=False, bg="#f8fafc", **kwargs):
        super().__init__(
            parent,
            width=self.W,
            height=self.H,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="arrow",
            **kwargs,
        )
        self._command = command
        self._is_on = is_on
        self._knob_x = float(self._target_x(is_on))
        self._anim_id = None
        self._redraw()
        self.bind("<Button-1>", self._on_click)

    # ---- geometry helpers ------------------------------------------------

    def _target_x(self, is_on: bool) -> float:
        return float((self.W - self.H + self.PAD) if is_on else self.PAD)

    # ---- drawing ---------------------------------------------------------

    def _redraw(self):
        self.delete("all")
        color = self.TRACK_ON if self._is_on else self.TRACK_OFF
        r = self.H / 2
        # Pill: left cap + body + right cap
        self.create_oval(0, 0, self.H, self.H, fill=color, outline="")
        self.create_oval(self.W - self.H, 0, self.W, self.H, fill=color, outline="")
        self.create_rectangle(r, 0, self.W - r, self.H, fill=color, outline="")
        # Knob
        d = self.H - 2 * self.PAD
        x = round(self._knob_x)
        self.create_oval(x, self.PAD, x + d, self.PAD + d, fill=self.KNOB, outline="")

    # ---- animation -------------------------------------------------------

    def _animate_to(self, target_x: float, steps: int = 6):
        if self._anim_id is not None:
            self.after_cancel(self._anim_id)
        self._step(self._knob_x, target_x, steps)

    def _step(self, start: float, target: float, remaining: int):
        if remaining <= 0:
            self._knob_x = target
            self._redraw()
            return
        self._knob_x = start + (target - start) / remaining
        self._redraw()
        self._anim_id = self.after(
            16, lambda: self._step(self._knob_x, target, remaining - 1)
        )

    # ---- public API ------------------------------------------------------

    def set_state(self, is_on: bool):
        """Update toggle state (with animation) from outside."""
        if self._is_on == is_on:
            return
        self._is_on = is_on
        self._animate_to(self._target_x(is_on))

    # ---- user interaction ------------------------------------------------

    def _on_click(self, *_):
        self._is_on = not self._is_on
        self._animate_to(self._target_x(self._is_on))
        if self._command:
            self._command()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def fig_to_photoimage(fig):
    """Convert a matplotlib Figure to a PIL Image + Tkinter PhotoImage."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight")
    buf.seek(0)
    pil_img = Image.open(buf).copy()
    return ImageTk.PhotoImage(pil_img), pil_img.size, pil_img


def default_aesthetics():
    return {
        "style": "whitegrid",
        "palette": "deep",
        "font_family": "DejaVu Sans",
        "font_size": 11,
        "title": "",
        "xlabel": "",
        "ylabel": "",
        "line_style": "-",
        "line_width": 1.5,
        "marker": "o",
        "alpha": 0.8,
        "color": "#4C72B0",
        "use_color": False,
        "grid": True,
        "legend": True,
        "legend_outside": True,  # place legend outside right, vertically centred
        "legend_frameon": False,  # no box around legend
        "legend_loc": "center left",  # used when legend_outside is True
        "tick_labels": True,
        "hue_palette": {},  # {category_value: hex_color} – empty = use palette
    }


# ---------------------------------------------------------------------------
# PlotBlock  –  one plot region on the artboard
# ---------------------------------------------------------------------------
class PlotBlock:
    _id_counter = 0

    def __init__(self, x1, y1, x2, y2):
        PlotBlock._id_counter += 1
        self.bid = PlotBlock._id_counter

        # Artboard-relative pixel coordinates
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)

        self.df = None
        self.plot_type = None
        self.col_x = None
        self.col_y = None
        self.col_hue = None
        self.col_size = None
        self.aesthetics = default_aesthetics()

        # tkinter canvas item IDs
        self.rect_id = None
        self.image_id = None
        self.label_id = None
        self._photo = None  # keep reference so GC does not collect it
        self._pil_img = None  # PIL image for export

    def __deepcopy__(self, memo):
        """Custom deep-copy that skips tkinter PhotoImage (_photo), which
        cannot be pickled.  Canvas IDs are reset so the copy starts clean."""
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "_photo":
                # ImageTk.PhotoImage holds a tkinter reference — skip it
                setattr(result, k, None)
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        return result

    @property
    def width_px(self):
        return max(int(self.x2 - self.x1), 40)

    @property
    def height_px(self):
        return max(int(self.y2 - self.y1), 40)

    @property
    def width_in(self):
        return self.width_px / DPI

    @property
    def height_in(self):
        return self.height_px / DPI


# ---------------------------------------------------------------------------
# Arrowhead helpers
# ---------------------------------------------------------------------------
# Base arrowshape tuples (d1, d2, d3) for each style at size=10.
# d1: distance from tip to neck along line
# d2: distance from tip to trailing points along line
# d3: half-width of the arrowhead perpendicular to line
_ARROWSHAPE_BASES = {
    "default": (8, 10, 3),
    "sharp": (12, 15, 2),
    "wide": (8, 10, 6),
    "flat": (4, 6, 4),
    "triangle": (10, 10, 5),
}


def _compute_arrowshape(style, size):
    """Return an arrowshape tuple scaled by *size* (default 10)."""
    base = _ARROWSHAPE_BASES.get(style, _ARROWSHAPE_BASES["default"])
    scale = size / 10.0
    return tuple(max(1, round(v * scale)) for v in base)


# ---------------------------------------------------------------------------
# Shape classes for drawing
# ---------------------------------------------------------------------------
class Shape:
    """Base class for drawable shapes."""

    _id_counter = 0

    def __init__(self, x1, y1, x2, y2, shape_type):
        Shape._id_counter += 1
        self.sid = Shape._id_counter
        # For lines, preserve original direction; for rectangles and circles, normalize
        if shape_type == "line":
            self.x1 = x1
            self.y1 = y1
            self.x2 = x2
            self.y2 = y2
        else:
            self.x1 = min(x1, x2)
            self.y1 = min(y1, y2)
            self.x2 = max(x1, x2)
            self.y2 = max(y1, y2)
        self.shape_type = shape_type  # 'line', 'rectangle', 'circle'
        self.color = "#000000"
        self.line_width = 2
        self.fill = ""  # empty for no fill
        self.arrow = None  # None, 'first', 'last', 'both' for lines
        self.arrow_size = 10  # arrowhead size (controls scale of arrowshape)
        self.arrowshape_style = "default"  # 'default', 'sharp', 'wide', 'flat'
        self.dash = ()  # () for solid, (5, 5) for dashed

        # Canvas item ID
        self.item_id = None

    @property
    def width_px(self):
        return abs(self.x2 - self.x1)

    @property
    def height_px(self):
        return abs(self.y2 - self.y1)

    @property
    def center_x(self):
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self):
        return (self.y1 + self.y2) / 2


# ---------------------------------------------------------------------------
# Text class for text objects
# ---------------------------------------------------------------------------
class TextObject:
    """Text object with customizable font."""

    _id_counter = 0

    def __init__(self, x, y, text="Text"):
        TextObject._id_counter += 1
        self.tid = TextObject._id_counter
        self.x1 = x
        self.y1 = y
        self.x2 = x + 100  # default width
        self.y2 = y + 30  # default height
        self.text = text
        self.font_family = "DejaVu Sans"
        self.font_size = 14
        self.color = "#000000"
        self.bold = False
        self.italic = False

        # Canvas item ID
        self.item_id = None

    @property
    def center_x(self):
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self):
        return (self.y1 + self.y2) / 2


# ---------------------------------------------------------------------------
# PlotConfigDialog
# ---------------------------------------------------------------------------
class PlotConfigDialog(tk.Toplevel):
    def __init__(self, parent, block: PlotBlock, is_edit=False):
        super().__init__(parent)
        self.block = block
        self.is_edit = is_edit
        self.result = False

        self.title("Configure Plot" if not is_edit else "Edit Plot")
        self.resizable(True, True)
        self.grab_set()
        self.focus_set()

        self._df = copy.copy(block.df)
        self._plot_type = tk.StringVar(value=block.plot_type or "scatter")
        self._col_x = tk.StringVar(value=block.col_x or "")
        self._col_y = tk.StringVar(value=block.col_y or "")
        self._col_hue = tk.StringVar(value=block.col_hue or "(none)")
        self._col_size = tk.StringVar(value=block.col_size or "(none)")
        self._filename = tk.StringVar(value="No file loaded")

        self._preview_photo = None  # keep PhotoImage alive for preview

        self._build_ui()
        self.update_idletasks()
        w, h = 860, 600
        px = parent.winfo_rootx() + max(0, (parent.winfo_width() - w) // 2)
        py = parent.winfo_rooty() + max(0, (parent.winfo_height() - h) // 2)
        self.geometry(f"{w}x{h}+{px}+{py}")

    # -------------------------------------------------------------------------
    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._nb = nb

        f_data = ttk.Frame(nb, padding=12)
        nb.add(f_data, text="  1 · Data  ")
        self._build_data_tab(f_data)

        f_plot = ttk.Frame(nb, padding=12)
        nb.add(f_plot, text="  2 · Plot type  ")
        self._build_plot_tab(f_plot)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side="right", padx=4
        )
        ttk.Button(btn_frame, text="Apply  ▶", command=self._apply).pack(
            side="right", padx=4
        )

    def _build_data_tab(self, parent):
        ttk.Label(
            parent, text="Step 1 — Load your data file", font=("", 10, "bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Button(parent, text="Browse CSV / TSV…", command=self._load_file).grid(
            row=1, column=0, sticky="w"
        )
        ttk.Label(parent, textvariable=self._filename, foreground="#556").grid(
            row=1, column=1, columnspan=2, sticky="w", padx=10
        )

        ttk.Separator(parent, orient="horizontal").grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=10
        )

        ttk.Label(parent, text="Preview — first 5 rows:").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )

        frame_tbl = ttk.Frame(parent)
        frame_tbl.grid(row=4, column=0, columnspan=3, sticky="nsew")
        parent.rowconfigure(4, weight=1)
        parent.columnconfigure(2, weight=1)

        self._tree = ttk.Treeview(frame_tbl, height=7)
        vsb = ttk.Scrollbar(frame_tbl, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(frame_tbl, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree.pack(side="left", fill="both", expand=True)

        # Enable mouse wheel scrolling
        bind_mousewheel(self._tree, self._tree, "both")

        if self._df is not None:
            self._populate_preview(self._df)

    def _build_plot_tab(self, parent):
        # ── left side: configuration controls ──────────────────────────────
        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.columnconfigure(1, weight=1)

        def lrow(r, lbl, widget):
            ttk.Label(left, text=lbl).grid(
                row=r, column=0, sticky="w", pady=6, padx=(0, 12)
            )
            widget.grid(row=r, column=1, sticky="ew", pady=6)

        self._cb_type = ttk.Combobox(
            left,
            textvariable=self._plot_type,
            values=PLOT_TYPES,
            state="readonly",
            width=22,
        )
        lrow(0, "Plot type:", self._cb_type)
        self._cb_type.bind("<<ComboboxSelected>>", self._on_type_change)

        self._cb_x = ttk.Combobox(
            left, textvariable=self._col_x, values=[], state="readonly", width=22
        )
        lrow(1, "X axis / category:", self._cb_x)
        self._cb_x.bind("<<ComboboxSelected>>", self._update_preview)

        self._cb_y = ttk.Combobox(
            left, textvariable=self._col_y, values=[], state="readonly", width=22
        )
        lrow(2, "Y axis / value:", self._cb_y)
        self._cb_y.bind("<<ComboboxSelected>>", self._update_preview)

        self._cb_hue = ttk.Combobox(
            left,
            textvariable=self._col_hue,
            values=["(none)"],
            state="readonly",
            width=22,
        )
        lrow(3, "Hue / colour group:", self._cb_hue)
        self._cb_hue.bind("<<ComboboxSelected>>", self._update_preview)

        self._cb_size = ttk.Combobox(
            left,
            textvariable=self._col_size,
            values=["(none)"],
            state="readonly",
            width=22,
        )
        lrow(4, "Size column\n(scatter only):", self._cb_size)
        self._cb_size.bind("<<ComboboxSelected>>", self._update_preview)

        ttk.Separator(left, orient="horizontal").grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=8
        )

        self._type_hint = ttk.Label(
            left, text="", foreground="#556", wraplength=260, justify="left"
        )
        self._type_hint.grid(row=6, column=0, columnspan=2, sticky="w")
        self._update_hint()

        if self._df is not None:
            self._refresh_column_combos()

        # ── right side: live preview ────────────────────────────────────────
        right = ttk.Frame(parent)
        right.pack(side="left", fill="both", expand=True)

        hdr = ttk.Frame(right)
        hdr.pack(fill="x", pady=(0, 4))
        ttk.Label(hdr, text="Preview", font=("", 9, "bold")).pack(side="left")
        ttk.Button(hdr, text="↺  Refresh", command=self._update_preview).pack(
            side="right"
        )

        self._preview_lbl = tk.Label(
            right,
            text="Select columns then click Refresh to preview",
            bg="#cccccc",
            fg="#555555",
            relief="flat",
            anchor="center",
            wraplength=350,
        )
        self._preview_lbl.pack(fill="both", expand=True)

    # -------------------------------------------------------------------------
    def _populate_preview(self, df):
        self._tree.delete(*self._tree.get_children())
        self._tree["columns"] = list(df.columns)
        self._tree["show"] = "headings"
        for col in df.columns:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=95, anchor="center", stretch=True)
        for _, row_data in df.head(5).iterrows():
            self._tree.insert("", "end", values=list(row_data))

    def _refresh_column_combos(self):
        cols = list(self._df.columns)
        ncols = ["(none)"] + cols
        self._cb_x["values"] = cols
        self._cb_y["values"] = cols
        self._cb_hue["values"] = ncols
        self._cb_size["values"] = ncols
        if not self._col_x.get() or self._col_x.get() not in cols:
            self._col_x.set(cols[0] if cols else "")
        if not self._col_y.get() or self._col_y.get() not in cols:
            self._col_y.set(cols[1] if len(cols) > 1 else (cols[0] if cols else ""))

    HINTS = {
        "scatter": "Needs numeric X and Y.  Hue colours points by group.",
        "line": "Needs X and Y.  Useful for time-series data.",
        "bar": "Category on X, numeric on Y.  Seaborn averages Y per group.",
        "barh": "Horizontal bar chart (same as bar, axes swapped).",
        "box": "Category on X, numeric on Y.  Shows median / IQR / outliers.",
        "violin": "Like box plot but shows full distribution shape.",
        "strip": "Jitter-plots each data point.  Good for small datasets.",
        "swarm": "Like strip but avoids overlapping.  Slow on large data.",
        "histogram": "Only needs X (numeric).  Counts occurrences in bins.",
        "kde": "Smooth density curve.  Only needs X.",
        "heatmap": "Needs X (column) and Y (row) to pivot and colour by mean value.",
        "count": "Counts rows per category in X.  No Y needed.",
        "regression": "Needs numeric X and Y.  Draws a linear regression line.",
    }

    def _update_hint(self):
        t = self._plot_type.get()
        self._type_hint.configure(text=self.HINTS.get(t, ""))

    def _on_type_change(self, _=None):
        t = self._plot_type.get()
        no_y = {"histogram", "kde", "count"}
        self._cb_y.configure(state="disabled" if t in no_y else "readonly")
        self._update_hint()
        self._update_preview()

    # Fixed thumbnail dimensions and low DPI — keeps memory and render time small
    _PREVIEW_W = 240
    _PREVIEW_H = 180
    _PREVIEW_DPI = 48  # half normal DPI; adequate for a thumbnail

    def _update_preview(self, *_):
        """Render a low-res thumbnail of the current plot configuration."""
        if self._df is None or not self._col_x.get():
            return

        temp = PlotBlock(0, 0, self._PREVIEW_W, self._PREVIEW_H)
        temp.df = self._df
        temp.plot_type = self._plot_type.get()
        temp.col_x = self._col_x.get() or None
        col_y = self._col_y.get()
        temp.col_y = col_y if col_y not in ("", "(none)") else None
        col_hue = self._col_hue.get()
        temp.col_hue = col_hue if col_hue != "(none)" else None
        col_size = self._col_size.get()
        temp.col_size = col_size if col_size != "(none)" else None

        try:
            # Render directly at low DPI — far cheaper than full-res then downscale
            fig = Figure(
                figsize=(
                    self._PREVIEW_W / self._PREVIEW_DPI,
                    self._PREVIEW_H / self._PREVIEW_DPI,
                ),
                dpi=self._PREVIEW_DPI,
            )
            ax = fig.add_subplot(111)
            PlotRenderer._render_to_ax(temp, ax, fig)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=self._PREVIEW_DPI)
            plt.close(fig)
            buf.seek(0)
            pil_img = Image.open(buf).copy()
            buf.close()
            pil_img = pil_img.resize((self._PREVIEW_W, self._PREVIEW_H), Image.BILINEAR)
            self._preview_photo = ImageTk.PhotoImage(pil_img)
            self._preview_lbl.configure(image=self._preview_photo, text="")
        except Exception as exc:
            self._preview_lbl.configure(
                image="", text=f"Preview error:\n{exc}", bg="#ffe0e0"
            )

    # -------------------------------------------------------------------------
    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Open data file",
            filetypes=[("CSV / TSV files", "*.csv *.tsv *.txt"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return
        try:
            sep = "\t" if path.lower().endswith((".tsv", ".txt")) else ","
            df = pd.read_csv(path, sep=sep)
            if df.empty:
                raise ValueError("File loaded but contains no data rows.")
            self._df = df
            short = path.replace("\\", "/").rsplit("/", 1)[-1]
            self._filename.set(f"{short}  ({len(df):,} rows × {len(df.columns)} cols)")
            self._populate_preview(df)
            self._refresh_column_combos()
            self._nb.select(1)  # switch to "2 · Plot type" tab
            self.after(100, self._update_preview)  # auto-preview after layout
        except Exception as exc:
            messagebox.showerror("Load error", str(exc), parent=self)

    def _apply(self):
        if self._df is None:
            messagebox.showwarning(
                "No data", "Please load a data file first.", parent=self
            )
            return
        if not self._col_x.get():
            messagebox.showwarning(
                "Missing column", "Please select an X axis column.", parent=self
            )
            return

        self.block.df = self._df
        self.block.plot_type = self._plot_type.get()
        self.block.col_x = self._col_x.get() or None
        self.block.col_y = (
            self._col_y.get() if self._col_y.get() not in ("", "(none)") else None
        )
        self.block.col_hue = (
            self._col_hue.get() if self._col_hue.get() != "(none)" else None
        )
        self.block.col_size = (
            self._col_size.get() if self._col_size.get() != "(none)" else None
        )
        self.result = True
        self.destroy()


# ---------------------------------------------------------------------------
# AestheticsPanel
# ---------------------------------------------------------------------------
class AestheticsPanel(ttk.Frame):
    def __init__(self, parent, on_update):
        super().__init__(parent, padding=6)
        self._block = None
        self._on_update = on_update
        self._vars = {}
        self._color_val = "#4C72B0"
        self._loading = False
        # plot config vars – populated in load_block
        self._plot_type_var = tk.StringVar()
        self._col_x_var = tk.StringVar()
        self._col_y_var = tk.StringVar()
        self._col_hue_var = tk.StringVar()
        self._cb_col_x = None
        self._cb_col_y = None
        self._cb_col_hue = None
        # size controls for plot blocks
        self._size_unit_var = tk.StringVar(value="px")
        self._size_w_var = tk.StringVar(value="")
        self._size_h_var = tk.StringVar(value="")
        self._size_lock_var = tk.BooleanVar(value=True)
        self._size_updating = False
        self._build()

    # helper factories for tkinter variables
    def _sv(self, key, val=""):
        v = tk.StringVar(value=str(val))
        self._vars[key] = v
        return v

    def _bv(self, key, val=False):
        v = tk.BooleanVar(value=val)
        self._vars[key] = v
        return v

    def _dv(self, key, val=1.0):
        v = tk.DoubleVar(value=val)
        self._vars[key] = v
        return v

    def _iv(self, key, val=11):
        v = tk.IntVar(value=val)
        self._vars[key] = v
        return v

    def _build(self):
        ttk.Label(self, text="Properties", font=("", 11, "bold")).pack(
            anchor="w", pady=(0, 6)
        )

        self._placeholder = ttk.Label(
            self,
            text="← Select a plot block\nto edit its style",
            foreground="#999",
            justify="center",
        )
        self._placeholder.pack(expand=True)

        self._body = ttk.Frame(self)

        # Separate panel shown only when a shape or text object is selected
        self._obj_body = ttk.Frame(self)

        # scrollable body – vertical + horizontal
        canvas = tk.Canvas(self._body, highlightthickness=0)
        vsb = ttk.Scrollbar(self._body, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(self._body, orient="horizontal", command=canvas.xview)
        self._inner = ttk.Frame(canvas)
        self._inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        _win = canvas.create_window((0, 0), window=self._inner, anchor="nw")

        def _fit_inner(e):
            # Keep inner frame as wide as the visible canvas so rows fill the space
            canvas.itemconfig(_win, width=e.width)

        canvas.bind("<Configure>", _fit_inner)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        # Enable mouse wheel scrolling
        bind_mousewheel(canvas, canvas, "both")
        bind_mousewheel(self._inner, canvas, "both")

        def section(txt):
            ttk.Separator(self._inner, orient="horizontal").pack(fill="x", pady=(10, 0))
            ttk.Label(
                self._inner, text=txt.upper(), font=("", 8, "bold"), foreground="#888"
            ).pack(anchor="w", pady=(4, 2))

        def row(lbl, w_func):
            f = ttk.Frame(self._inner)
            f.pack(fill="x", pady=2)
            ttk.Label(f, text=lbl, width=15, anchor="w").pack(side="left")
            w = w_func(f)
            w.pack(side="left", fill="x", expand=True, padx=(4, 0))
            return w

        # ---- Data & Plot ----
        section("Data & Plot")
        row(
            "Plot type",
            lambda p: ttk.Combobox(
                p,
                textvariable=self._plot_type_var,
                values=PLOT_TYPES,
                state="readonly",
            ),
        )
        self._cb_col_x = row(
            "X axis",
            lambda p: ttk.Combobox(
                p, textvariable=self._col_x_var, values=[], state="disabled"
            ),
        )
        self._cb_col_y = row(
            "Y axis",
            lambda p: ttk.Combobox(
                p, textvariable=self._col_y_var, values=[], state="disabled"
            ),
        )
        self._cb_col_hue = row(
            "Hue",
            lambda p: ttk.Combobox(
                p, textvariable=self._col_hue_var, values=["(none)"], state="disabled"
            ),
        )

        # ---- Labels ----
        section("Labels")
        row("Title", lambda p: ttk.Entry(p, textvariable=self._sv("title")))
        row("X label", lambda p: ttk.Entry(p, textvariable=self._sv("xlabel")))
        row("Y label", lambda p: ttk.Entry(p, textvariable=self._sv("ylabel")))

        # ---- Size ----
        section("Size")
        sf_unit = ttk.Frame(self._inner)
        sf_unit.pack(fill="x", pady=2)
        ttk.Label(sf_unit, text="Unit", width=15, anchor="w").pack(side="left")
        ttk.Combobox(
            sf_unit,
            textvariable=self._size_unit_var,
            values=["px", "cm", "mm", "pts"],
            state="readonly",
            width=6,
        ).pack(side="left")
        sf_lock = ttk.Frame(self._inner)
        sf_lock.pack(fill="x", pady=2)
        ttk.Checkbutton(
            sf_lock, text="Lock aspect ratio", variable=self._size_lock_var
        ).pack(side="left")
        sf_w = ttk.Frame(self._inner)
        sf_w.pack(fill="x", pady=2)
        ttk.Label(sf_w, text="Width", width=15, anchor="w").pack(side="left")
        self._size_w_entry = ttk.Entry(sf_w, textvariable=self._size_w_var, width=8)
        self._size_w_entry.pack(side="left", padx=(4, 0))
        self._size_w_entry.bind("<FocusOut>", lambda e: self._apply_block_size(True))
        self._size_w_entry.bind("<Return>", lambda e: self._apply_block_size(True))
        sf_h = ttk.Frame(self._inner)
        sf_h.pack(fill="x", pady=2)
        ttk.Label(sf_h, text="Height", width=15, anchor="w").pack(side="left")
        self._size_h_entry = ttk.Entry(sf_h, textvariable=self._size_h_var, width=8)
        self._size_h_entry.pack(side="left", padx=(4, 0))
        self._size_h_entry.bind("<FocusOut>", lambda e: self._apply_block_size(False))
        self._size_h_entry.bind("<Return>", lambda e: self._apply_block_size(False))

        # ---- Theme ----
        section("Theme & Palette")
        row(
            "Style",
            lambda p: ttk.Combobox(
                p,
                textvariable=self._sv("style", "whitegrid"),
                values=SEABORN_STYLES,
                state="readonly",
            ),
        )

        row(
            "Palette",
            lambda p: ttk.Combobox(
                p,
                textvariable=self._sv("palette", "deep"),
                values=SEABORN_PALETTES,
                state="readonly",
            ),
        )

        # ---- Font ----
        section("Font")
        row(
            "Family",
            lambda p: ttk.Combobox(
                p,
                textvariable=self._sv("font_family", "DejaVu Sans"),
                values=FONT_FAMILIES,
                state="readonly",
            ),
        )
        row(
            "Size",
            lambda p: ttk.Spinbox(
                p, textvariable=self._iv("font_size", 11), from_=6, to=28, width=5
            ),
        )

        # ---- Line & Marker ----
        section("Line & Marker")
        row(
            "Line style",
            lambda p: ttk.Combobox(
                p,
                textvariable=self._sv("line_style", "-"),
                values=LINE_STYLES,
                state="readonly",
            ),
        )
        row(
            "Line width",
            lambda p: ttk.Spinbox(
                p,
                textvariable=self._dv("line_width", 1.5),
                from_=0.5,
                to=8.0,
                increment=0.5,
                width=5,
            ),
        )
        row(
            "Marker",
            lambda p: ttk.Combobox(
                p,
                textvariable=self._sv("marker", "o"),
                values=MARKER_TYPES,
                state="readonly",
            ),
        )
        row(
            "Alpha",
            lambda p: ttk.Spinbox(
                p,
                textvariable=self._dv("alpha", 0.8),
                from_=0.05,
                to=1.0,
                increment=0.05,
                width=5,
            ),
        )

        # ---- Colour override ----
        section("Colour Override")
        cf = ttk.Frame(self._inner)
        cf.pack(fill="x", pady=2)
        self._use_color_var = self._bv("use_color", False)
        ttk.Checkbutton(
            cf, text="Use single colour", variable=self._use_color_var
        ).pack(side="left")
        self._swatch = tk.Label(
            cf, bg="#4C72B0", width=4, relief="solid", borderwidth=1, cursor="arrow"
        )
        self._swatch.pack(side="left", padx=6)
        self._swatch.bind("<Button-1>", lambda _: self._pick_color())

        # ---- Grid / Legend ----
        section("Grid & Legend")
        gf = ttk.Frame(self._inner)
        gf.pack(fill="x", pady=2)
        ttk.Checkbutton(gf, text="Show grid", variable=self._bv("grid", True)).pack(
            side="left", padx=(0, 14)
        )
        ttk.Checkbutton(gf, text="Show legend", variable=self._bv("legend", True)).pack(
            side="left"
        )
        lf = ttk.Frame(self._inner)
        lf.pack(fill="x", pady=2)
        ttk.Checkbutton(
            lf, text="Outside right", variable=self._bv("legend_outside", True)
        ).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(
            lf, text="Frame on", variable=self._bv("legend_frameon", False)
        ).pack(side="left")
        row(
            "Legend loc\n(inside only)",
            lambda p: ttk.Combobox(
                p,
                textvariable=self._sv("legend_loc", "center left"),
                values=LEGEND_LOCS,
                state="readonly",
            ),
        )
        tf = ttk.Frame(self._inner)
        tf.pack(fill="x", pady=2)
        ttk.Checkbutton(
            tf, text="Show tick labels", variable=self._bv("tick_labels", True)
        ).pack(side="left")

        # ---- Shapes ----
        section("Shape Properties")
        self._shape_section = ttk.Frame(self._inner)
        self._shape_section.pack(fill="x", pady=2)
        ttk.Label(
            self._shape_section,
            text="(select a shape to edit)",
            foreground="#999",
        ).pack(anchor="w")

        # ---- Hue Colours ----
        section("Hue Colours")
        ttk.Label(self._inner, text="Custom colour per group:", foreground="#556").pack(
            anchor="w", pady=(0, 2)
        )
        self._hue_color_frame = ttk.Frame(self._inner)
        self._hue_color_frame.pack(fill="x", pady=2)
        ttk.Label(
            self._hue_color_frame,
            text="(no hue column selected)",
            foreground="#999",
        ).pack(anchor="w")
        self._hue_color_map: dict = {}  # {str(value): hex_color}

        self._bind_auto_apply()

    # ---- auto-apply wiring ----------------------------------------------
    def _bind_auto_apply(self):
        def on_change(*_):
            if not self._loading:
                self._apply()

        def on_hue_change(*_):
            if not self._loading and self._block:
                v = self._col_hue_var.get()
                self._block.col_hue = v if v != "(none)" else None
                self._rebuild_hue_colors(self._block)
                self._apply()

        for var in self._vars.values():
            var.trace_add("write", on_change)
        self._plot_type_var.trace_add("write", on_change)
        self._col_x_var.trace_add("write", on_change)
        self._col_y_var.trace_add("write", on_change)
        self._col_hue_var.trace_add("write", on_hue_change)
        self._size_unit_var.trace_add("write", self._update_size_display)

    # ---- public ---------------------------------------------------------
    def load_shape(self, shape, redraw_callback):
        """Load shape properties into the dedicated shape panel."""
        # Show shape panel only (hide plot body and placeholder)
        self._placeholder.pack_forget()
        self._body.pack_forget()
        for w in self._obj_body.winfo_children():
            w.destroy()
        ttk.Label(self._obj_body, text="Shape Properties", font=("", 10, "bold")).pack(
            anchor="w", pady=(0, 6)
        )
        self._obj_body.pack(fill="both", expand=True)

        # Create controls for shape properties
        def make_row(parent, label_text, widget_func):
            f = ttk.Frame(parent)
            f.pack(fill="x", pady=2)
            ttk.Label(f, text=label_text, width=12, anchor="w").pack(side="left")
            w = widget_func(f)
            w.pack(side="left", fill="x", expand=True, padx=(4, 0))
            return w

        # Color picker
        cf = ttk.Frame(self._obj_body)
        cf.pack(fill="x", pady=2)
        ttk.Label(cf, text="Color", width=12, anchor="w").pack(side="left")
        shape_swatch = tk.Label(
            cf, bg=shape.color, width=4, relief="solid", borderwidth=1, cursor="arrow"
        )
        shape_swatch.pack(side="left", padx=(4, 0))

        def pick_shape_color(*_):
            color = colorchooser.askcolor(initialcolor=shape.color, parent=self)[1]
            if color:
                shape.color = color
                shape_swatch.configure(bg=color)
                redraw_callback(shape)

        shape_swatch.bind("<Button-1>", pick_shape_color)

        # Line width
        lw_var = tk.IntVar(value=shape.line_width)

        def on_lw_change(*_):
            try:
                val = lw_var.get()
                if val:
                    shape.line_width = val
                    redraw_callback(shape)
            except (tk.TclError, ValueError):
                pass

        lw_var.trace_add("write", on_lw_change)
        make_row(
            self._obj_body,
            "Line width",
            lambda p: ttk.Spinbox(p, textvariable=lw_var, from_=1, to=20, width=5),
        )

        # Line style (solid/dashed) - for all shape types
        dash_var = tk.StringVar(value="solid" if not shape.dash else "dashed")

        def on_dash_change(*_):
            shape.dash = (5, 5) if dash_var.get() == "dashed" else ()
            redraw_callback(shape)

        dash_var.trace_add("write", on_dash_change)
        make_row(
            self._obj_body,
            "Line style",
            lambda p: ttk.Combobox(
                p,
                textvariable=dash_var,
                values=["solid", "dashed"],
                state="readonly",
            ),
        )

        # Fill color (only for rectangles and circles)
        if shape.shape_type in ("rectangle", "circle"):
            fill_var = tk.StringVar(value=shape.fill or "")
            ff = ttk.Frame(self._obj_body)
            ff.pack(fill="x", pady=2)
            ttk.Label(ff, text="Fill", width=12, anchor="w").pack(side="left")
            fill_swatch = tk.Label(
                ff,
                bg=shape.fill or "#ffffff",
                width=4,
                relief="solid",
                borderwidth=1,
                cursor="arrow",
            )
            fill_swatch.pack(side="left", padx=(4, 6))

            def pick_fill_color(*_):
                color = colorchooser.askcolor(
                    initialcolor=shape.fill or "#ffffff", parent=self
                )[1]
                if color:
                    shape.fill = color
                    fill_var.set(color)
                    fill_swatch.configure(bg=color)
                    redraw_callback(shape)

            fill_swatch.bind("<Button-1>", pick_fill_color)

            def clear_fill():
                shape.fill = ""
                fill_var.set("")
                fill_swatch.configure(bg="#ffffff")
                redraw_callback(shape)

            ttk.Button(ff, text="Clear", command=clear_fill).pack(side="left")

        # Arrow (only for lines)
        if shape.shape_type == "line":
            arrow_var = tk.StringVar(value=shape.arrow or "None")

            def on_arrow_change(*_):
                val = arrow_var.get()
                shape.arrow = None if val == "None" else val
                redraw_callback(shape)

            arrow_var.trace_add("write", on_arrow_change)
            make_row(
                self._obj_body,
                "Arrowhead",
                lambda p: ttk.Combobox(
                    p,
                    textvariable=arrow_var,
                    values=["None", "first", "last", "both"],
                    state="readonly",
                ),
            )

            # Arrowhead size
            arrow_size_var = tk.IntVar(value=shape.arrow_size)

            def on_arrow_size_change(*_):
                try:
                    val = arrow_size_var.get()
                    if val:
                        shape.arrow_size = val
                        redraw_callback(shape)
                except (tk.TclError, ValueError):
                    pass

            arrow_size_var.trace_add("write", on_arrow_size_change)
            make_row(
                self._obj_body,
                "Arrow size",
                lambda p: ttk.Spinbox(
                    p, textvariable=arrow_size_var, from_=5, to=30, width=5
                ),
            )

            # Arrowhead style
            arrow_style_var = tk.StringVar(value=shape.arrowshape_style)

            def on_arrow_style_change(*_):
                shape.arrowshape_style = arrow_style_var.get()
                redraw_callback(shape)

            arrow_style_var.trace_add("write", on_arrow_style_change)
            make_row(
                self._obj_body,
                "Arrow style",
                lambda p: ttk.Combobox(
                    p,
                    textvariable=arrow_style_var,
                    values=list(_ARROWSHAPE_BASES.keys()),
                    state="readonly",
                ),
            )

        # ---- Size controls ----
        self._add_obj_size_controls(self._obj_body, shape, redraw_callback)

    def clear_shape_properties(self):
        """Clear the shape/text properties panel."""
        self._obj_body.pack_forget()
        for w in self._obj_body.winfo_children():
            w.destroy()
        # Also reset the in-body shape section placeholder (used when block is shown)
        for w in self._shape_section.winfo_children():
            w.destroy()
        ttk.Label(
            self._shape_section,
            text="(select a shape to edit)",
            foreground="#999",
        ).pack(anchor="w")

    def load_text(self, text_obj, redraw_callback):
        """Load text properties into the dedicated text panel."""
        # Show text panel only (hide plot body and placeholder)
        self._placeholder.pack_forget()
        self._body.pack_forget()
        for w in self._obj_body.winfo_children():
            w.destroy()
        ttk.Label(self._obj_body, text="Text Properties", font=("", 10, "bold")).pack(
            anchor="w", pady=(0, 6)
        )
        self._obj_body.pack(fill="both", expand=True)

        # Create controls for text properties
        def make_row(parent, label_text, widget_func):
            f = ttk.Frame(parent)
            f.pack(fill="x", pady=2)
            ttk.Label(f, text=label_text, width=12, anchor="w").pack(side="left")
            w = widget_func(f)
            w.pack(side="left", fill="x", expand=True, padx=(4, 0))
            return w

        # Text content
        text_var = tk.StringVar(value=text_obj.text)

        def on_text_change(*_):
            text_obj.text = text_var.get()
            redraw_callback(text_obj)

        text_var.trace_add("write", on_text_change)
        text_entry = tk.Text(self._obj_body, height=3, width=30, wrap="word")
        text_entry.pack(fill="both", padx=2, pady=2)
        text_entry.delete("1.0", "end")
        text_entry.insert("1.0", text_obj.text)

        def on_text_widget_change(*_):
            text_obj.text = text_entry.get("1.0", "end-1c")
            redraw_callback(text_obj)

        text_entry.bind("<<Change>>", on_text_widget_change)
        text_entry.bind(
            "<Control-a>", lambda e: text_entry.tag_add(tk.SEL, "1.0", tk.END)
        )

        # Hook into text modifications
        def text_changed(event=None):
            text_obj.text = text_entry.get("1.0", "end-1c")
            redraw_callback(text_obj)

        # Use after to detect changes
        def watch_text():
            current = text_entry.get("1.0", "end-1c")
            if current != text_obj.text:
                text_obj.text = current
                redraw_callback(text_obj)
            text_entry.after(300, watch_text)

        watch_text()

        # Color picker
        cf = ttk.Frame(self._obj_body)
        cf.pack(fill="x", pady=2)
        ttk.Label(cf, text="Color", width=12, anchor="w").pack(side="left")
        text_swatch = tk.Label(
            cf,
            bg=text_obj.color,
            width=4,
            relief="solid",
            borderwidth=1,
            cursor="arrow",
        )
        text_swatch.pack(side="left", padx=(4, 0))

        def pick_text_color(*_):
            color = colorchooser.askcolor(initialcolor=text_obj.color, parent=self)[1]
            if color:
                text_obj.color = color
                text_swatch.configure(bg=color)
                redraw_callback(text_obj)

        text_swatch.bind("<Button-1>", pick_text_color)

        # Font family
        font_var = tk.StringVar(value=text_obj.font_family)

        def on_font_change(*_):
            text_obj.font_family = font_var.get()
            redraw_callback(text_obj)

        font_var.trace_add("write", on_font_change)
        make_row(
            self._obj_body,
            "Font",
            lambda p: ttk.Combobox(
                p,
                textvariable=font_var,
                values=FONT_FAMILIES,
                state="readonly",
            ),
        )

        # Font size
        size_var = tk.IntVar(value=text_obj.font_size)

        def on_size_change(*_):
            try:
                val = size_var.get()
                if val:
                    text_obj.font_size = val
                    redraw_callback(text_obj)
            except (tk.TclError, ValueError):
                pass

        size_var.trace_add("write", on_size_change)
        make_row(
            self._obj_body,
            "Size",
            lambda p: ttk.Spinbox(p, textvariable=size_var, from_=6, to=72, width=5),
        )

        # Bold/Italic
        style_frame = ttk.Frame(self._obj_body)
        style_frame.pack(fill="x", pady=2)
        bold_var = tk.BooleanVar(value=text_obj.bold)

        def on_bold_change(*_):
            text_obj.bold = bold_var.get()
            redraw_callback(text_obj)

        bold_var.trace_add("write", on_bold_change)
        ttk.Checkbutton(style_frame, text="Bold", variable=bold_var).pack(side="left")

        italic_var = tk.BooleanVar(value=text_obj.italic)

        def on_italic_change(*_):
            text_obj.italic = italic_var.get()
            redraw_callback(text_obj)

        italic_var.trace_add("write", on_italic_change)
        ttk.Checkbutton(style_frame, text="Italic", variable=italic_var).pack(
            side="left"
        )

        # ---- Size controls ----
        self._add_obj_size_controls(self._obj_body, text_obj, redraw_callback)

    def load_block(self, block: PlotBlock):
        self._loading = True
        try:
            self._block = block
            a = block.aesthetics
            self._placeholder.pack_forget()
            self._obj_body.pack_forget()
            self._body.pack(fill="both", expand=True)
            for key, var in self._vars.items():
                if key in a:
                    try:
                        var.set(a[key])
                    except Exception:
                        pass
            self._color_val = a.get("color", "#4C72B0")
            self._swatch.configure(bg=self._color_val)

            # populate plot type
            self._plot_type_var.set(block.plot_type or "scatter")

            # populate column dropdowns if data is loaded
            if block.df is not None:
                cols = list(block.df.columns)
                ncols = ["(none)"] + cols
                self._cb_col_x.configure(state="readonly", values=cols)
                self._cb_col_y.configure(state="readonly", values=cols)
                self._cb_col_hue.configure(state="readonly", values=ncols)
                self._col_x_var.set(block.col_x or (cols[0] if cols else ""))
                self._col_y_var.set(block.col_y or (cols[1] if len(cols) > 1 else ""))
                self._col_hue_var.set(block.col_hue or "(none)")
            else:
                self._cb_col_x.configure(state="disabled", values=[])
                self._cb_col_y.configure(state="disabled", values=[])
                self._cb_col_hue.configure(state="disabled", values=["(none)"])

            # seed hue colour map from block's stored palette
            self._hue_color_map = dict(a.get("hue_palette", {}))

            # populate size fields
            self._refresh_block_size_display(block)
        finally:
            self._loading = False

        self._rebuild_hue_colors(block)

    def clear(self):
        self._block = None
        self._obj_body.pack_forget()
        self._body.pack_forget()
        self._placeholder.pack(expand=True)

    # ---- internals -------------------------------------------------------
    def _rebuild_hue_colors(self, block):
        """Repopulate the Hue Colours frame based on the current hue column."""
        for w in self._hue_color_frame.winfo_children():
            w.destroy()

        if block is None or block.df is None or not block.col_hue:
            ttk.Label(
                self._hue_color_frame,
                text="(no hue column selected)",
                foreground="#999",
            ).pack(anchor="w")
            self._hue_color_map = {}
            return

        try:
            vals = sorted(block.df[block.col_hue].dropna().unique(), key=str)
        except Exception:
            return

        # Generate default colours from current palette name
        try:
            pal_name = block.aesthetics.get("palette", "deep")
            pal_colors = sns.color_palette(pal_name, len(vals))
            default_hexes = [mcolors.to_hex(c) for c in pal_colors]
        except Exception:
            default_hexes = ["#4C72B0"] * len(vals)

        # Preserve any previously picked colours; fill the rest from palette
        for i, val in enumerate(vals):
            k = str(val)
            if k not in self._hue_color_map:
                self._hue_color_map[k] = default_hexes[i % len(default_hexes)]

        # Remove stale keys
        valid_keys = {str(v) for v in vals}
        self._hue_color_map = {
            k: v for k, v in self._hue_color_map.items() if k in valid_keys
        }

        ttk.Button(
            self._hue_color_frame,
            text="Reset all to palette",
            command=self._reset_hue_colors,
        ).pack(anchor="w", pady=(0, 6))

        for val in vals:
            k = str(val)
            hex_c = self._hue_color_map[k]
            rf = ttk.Frame(self._hue_color_frame)
            rf.pack(fill="x", pady=1)
            ttk.Label(rf, text=k, width=14, anchor="w").pack(side="left")
            swatch = tk.Label(rf, bg=hex_c, width=3, relief="solid", borderwidth=1)
            swatch.pack(side="left", padx=4)

            def make_picker(v=k, sw=swatch):
                def pick():
                    res = colorchooser.askcolor(
                        color=self._hue_color_map.get(v, "#4C72B0"),
                        title=f'Colour for "{v}"',
                        parent=self,
                    )
                    if res and res[1]:
                        self._hue_color_map[v] = res[1]
                        sw.configure(bg=res[1])
                        self._apply()

                return pick

            ttk.Button(rf, text="Pick…", command=make_picker()).pack(side="left")

    def _reset_hue_colors(self):
        self._hue_color_map = {}
        if self._block:
            self._block.aesthetics["hue_palette"] = {}
            self._rebuild_hue_colors(self._block)
            self._on_update(self._block)

    def _pick_color(self):
        res = colorchooser.askcolor(
            color=self._color_val, title="Choose colour", parent=self
        )
        if res and res[1]:
            self._color_val = res[1]
            self._swatch.configure(bg=self._color_val)
            self._apply()

    # ---- size helpers (plot blocks) --------------------------------------

    @staticmethod
    def _fmt(v):
        """Format a float, stripping unnecessary trailing zeros."""
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s if s else "0"

    def _refresh_block_size_display(self, block):
        """Refresh width/height entries from the block's current pixel dimensions."""
        if self._size_updating:
            return
        self._size_updating = True
        try:
            scale = _UNIT_TO_PX.get(self._size_unit_var.get(), 1.0)
            self._size_w_var.set(self._fmt(block.width_px / scale))
            self._size_h_var.set(self._fmt(block.height_px / scale))
        finally:
            self._size_updating = False

    def _update_size_display(self, *_):
        """Called when the unit combobox changes – re-display current block size."""
        if self._loading or not self._block:
            return
        self._refresh_block_size_display(self._block)

    def _apply_block_size(self, is_width_changed: bool):
        """Apply a typed width or height to the current plot block."""
        if self._size_updating or not self._block:
            return
        self._size_updating = True
        try:
            scale = _UNIT_TO_PX.get(self._size_unit_var.get(), 1.0)
            try:
                w_val = float(self._size_w_var.get())
                h_val = float(self._size_h_var.get())
            except ValueError:
                return
            new_w_px = max(_MIN_BLOCK_SIZE_PX, round(w_val * scale))
            new_h_px = max(_MIN_BLOCK_SIZE_PX, round(h_val * scale))
            if self._size_lock_var.get():
                old_w = self._block.width_px
                old_h = self._block.height_px
                if old_w > 0 and old_h > 0:
                    if is_width_changed:
                        new_h_px = max(
                            _MIN_BLOCK_SIZE_PX, round(new_w_px * old_h / old_w)
                        )
                        self._size_h_var.set(self._fmt(new_h_px / scale))
                    else:
                        new_w_px = max(
                            _MIN_BLOCK_SIZE_PX, round(new_h_px * old_w / old_h)
                        )
                        self._size_w_var.set(self._fmt(new_w_px / scale))
            self._block.x2 = self._block.x1 + new_w_px
            self._block.y2 = self._block.y1 + new_h_px
            self._on_update(self._block)
        finally:
            self._size_updating = False

    # ---- size helpers (shapes & text objects) ----------------------------

    def _add_obj_size_controls(self, parent, obj, redraw_callback):
        """Append width/height/unit/lock controls to *parent* for a shape or text obj."""
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(10, 2))
        ttk.Label(parent, text="SIZE", font=("", 8, "bold"), foreground="#888").pack(
            anchor="w", pady=(0, 2)
        )

        size_unit_var = tk.StringVar(value="px")
        size_lock_var = tk.BooleanVar(value=True)
        size_w_var = tk.StringVar()
        size_h_var = tk.StringVar()
        updating = False

        def to_unit(px):
            return px / _UNIT_TO_PX.get(size_unit_var.get(), 1.0)

        def to_px(val):
            return val * _UNIT_TO_PX.get(size_unit_var.get(), 1.0)

        def refresh_display(*_):
            nonlocal updating
            if updating:
                return
            updating = True
            try:
                size_w_var.set(self._fmt(to_unit(abs(obj.x2 - obj.x1))))
                size_h_var.set(self._fmt(to_unit(abs(obj.y2 - obj.y1))))
            finally:
                updating = False

        def apply_size(is_width_changed):
            nonlocal updating
            if updating:
                return
            updating = True
            try:
                try:
                    w_val = float(size_w_var.get())
                    h_val = float(size_h_var.get())
                except ValueError:
                    return
                new_w_px = max(_MIN_OBJ_SIZE_PX, round(to_px(w_val)))
                new_h_px = max(_MIN_OBJ_SIZE_PX, round(to_px(h_val)))
                if size_lock_var.get():
                    old_w = abs(obj.x2 - obj.x1)
                    old_h = abs(obj.y2 - obj.y1)
                    if old_w > 0 and old_h > 0:
                        if is_width_changed:
                            new_h_px = max(
                                _MIN_OBJ_SIZE_PX, round(new_w_px * old_h / old_w)
                            )
                            size_h_var.set(self._fmt(to_unit(new_h_px)))
                        else:
                            new_w_px = max(
                                _MIN_OBJ_SIZE_PX, round(new_h_px * old_w / old_h)
                            )
                            size_w_var.set(self._fmt(to_unit(new_w_px)))
                # Keep top-left corner; change bottom-right
                obj.x2 = obj.x1 + new_w_px
                obj.y2 = obj.y1 + new_h_px
                redraw_callback(obj)
            finally:
                updating = False

        refresh_display()
        size_unit_var.trace_add("write", refresh_display)

        # Unit row
        uf = ttk.Frame(parent)
        uf.pack(fill="x", pady=2)
        ttk.Label(uf, text="Unit", width=12, anchor="w").pack(side="left")
        ttk.Combobox(
            uf,
            textvariable=size_unit_var,
            values=["px", "cm", "mm", "pts"],
            state="readonly",
            width=6,
        ).pack(side="left")

        # Lock row
        lf = ttk.Frame(parent)
        lf.pack(fill="x", pady=2)
        ttk.Checkbutton(lf, text="Lock aspect ratio", variable=size_lock_var).pack(
            side="left"
        )

        # Width row
        wf = ttk.Frame(parent)
        wf.pack(fill="x", pady=2)
        ttk.Label(wf, text="Width", width=12, anchor="w").pack(side="left")
        we = ttk.Entry(wf, textvariable=size_w_var, width=8)
        we.pack(side="left", padx=(4, 0))
        we.bind("<FocusOut>", lambda e: apply_size(True))
        we.bind("<Return>", lambda e: apply_size(True))

        # Height row
        hf = ttk.Frame(parent)
        hf.pack(fill="x", pady=2)
        ttk.Label(hf, text="Height", width=12, anchor="w").pack(side="left")
        he = ttk.Entry(hf, textvariable=size_h_var, width=8)
        he.pack(side="left", padx=(4, 0))
        he.bind("<FocusOut>", lambda e: apply_size(False))
        he.bind("<Return>", lambda e: apply_size(False))

    def _apply(self):
        if not self._block:
            return
        a = self._block.aesthetics
        for key, var in self._vars.items():
            try:
                a[key] = var.get()
            except Exception:
                pass
        a["color"] = self._color_val
        a["use_color"] = self._use_color_var.get()
        a["hue_palette"] = dict(self._hue_color_map)
        pt = self._plot_type_var.get()
        if pt:
            self._block.plot_type = pt
        for attr, var in (("col_x", self._col_x_var), ("col_y", self._col_y_var)):
            v = var.get()
            setattr(self._block, attr, v if v not in ("", "(none)") else None)
        v = self._col_hue_var.get()
        self._block.col_hue = v if v != "(none)" else None

        self._on_update(self._block)


# ---------------------------------------------------------------------------
# PlotRenderer
# ---------------------------------------------------------------------------
class PlotRenderer:
    @staticmethod
    def _render_to_ax(block: "PlotBlock", ax, fig):
        """Draw block's plot onto *ax*.  Handles all seaborn plot types."""
        a = block.aesthetics
        df = block.df

        sns.set_theme(
            style=a["style"], font=a["font_family"], font_scale=a["font_size"] / 10.0
        )

        color = a["color"] if a["use_color"] else None

        pt = block.plot_type
        x, y = block.col_x, block.col_y
        hue = block.col_hue
        size = block.col_size

        # Build palette: custom hue mapping > named palette > None (when color override)
        hue_pal = a.get("hue_palette", {})
        if a["use_color"]:
            palette = None
        elif hue_pal and hue:
            # Convert string keys back to original types to match dataframe values
            palette = {}
            try:
                hue_values = df[hue].dropna().unique()
                for val in hue_values:
                    str_key = str(val)
                    if str_key in hue_pal:
                        palette[val] = hue_pal[str_key]
            except Exception:
                palette = hue_pal  # fallback to original if conversion fails
        else:
            palette = a["palette"]
        kw = dict(data=df, ax=ax)

        try:
            if pt == "scatter":
                sns.scatterplot(
                    x=x,
                    y=y,
                    hue=hue,
                    size=size,
                    palette=palette,
                    color=color,
                    alpha=a["alpha"],
                    marker=a["marker"] if a["marker"] != "None" else "o",
                    **kw,
                )
            elif pt == "line":
                sns.lineplot(
                    x=x,
                    y=y,
                    hue=hue,
                    palette=palette,
                    color=color,
                    alpha=a["alpha"],
                    linestyle=a["line_style"],
                    linewidth=a["line_width"],
                    **kw,
                )
            elif pt == "bar":
                sns.barplot(
                    x=x,
                    y=y,
                    hue=hue,
                    palette=palette,
                    color=color,
                    alpha=a["alpha"],
                    **kw,
                )
            elif pt == "barh":
                sns.barplot(
                    x=y,
                    y=x,
                    hue=hue,
                    palette=palette,
                    color=color,
                    alpha=a["alpha"],
                    orient="h",
                    **kw,
                )
            elif pt == "box":
                sns.boxplot(x=x, y=y, hue=hue, palette=palette, color=color, **kw)
            elif pt == "violin":
                sns.violinplot(x=x, y=y, hue=hue, palette=palette, color=color, **kw)
            elif pt == "strip":
                sns.stripplot(
                    x=x,
                    y=y,
                    hue=hue,
                    palette=palette,
                    color=color,
                    alpha=a["alpha"],
                    **kw,
                )
            elif pt == "swarm":
                sns.swarmplot(x=x, y=y, hue=hue, palette=palette, color=color, **kw)
            elif pt == "histogram":
                sns.histplot(
                    data=df,
                    x=x,
                    hue=hue,
                    palette=palette,
                    color=color,
                    alpha=a["alpha"],
                    ax=ax,
                )
            elif pt == "kde":
                sns.kdeplot(
                    data=df,
                    x=x,
                    hue=hue,
                    palette=palette,
                    color=color,
                    fill=True,
                    alpha=a["alpha"],
                    ax=ax,
                )
            elif pt == "count":
                sns.countplot(data=df, x=x, hue=hue, palette=palette, color=color, **kw)
            elif pt == "regression":
                sns.regplot(
                    data=df,
                    x=x,
                    y=y,
                    ax=ax,
                    color=color or "#4C72B0",
                    scatter_kws={"alpha": a["alpha"]},
                    line_kws={
                        "linewidth": a["line_width"],
                        "linestyle": a["line_style"],
                    },
                )
            elif pt == "heatmap":
                pivot = df.pivot_table(index=y, columns=x, aggfunc="mean")
                sns.heatmap(
                    pivot,
                    ax=ax,
                    cmap=palette if isinstance(palette, str) else "viridis",
                )
            else:
                ax.text(
                    0.5,
                    0.5,
                    f"Plot type '{pt}' not supported.",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
        except Exception as exc:
            ax.clear()
            ax.text(
                0.5,
                0.5,
                f"Render error:\n{exc}",
                ha="center",
                va="center",
                transform=ax.transAxes,
                wrap=True,
                fontsize=9,
                color="red",
            )

        if a.get("title"):
            ax.set_title(a["title"], fontsize=a["font_size"] + 2)
        if a.get("xlabel"):
            ax.set_xlabel(a["xlabel"], fontsize=a["font_size"])
        if a.get("ylabel"):
            ax.set_ylabel(a["ylabel"], fontsize=a["font_size"])
        if not a.get("grid"):
            ax.grid(False)

        legend = ax.get_legend()
        if not a.get("legend"):
            if legend:
                legend.remove()
        elif legend:
            frameon = a.get("legend_frameon", False)
            if a.get("legend_outside", True):
                legend.remove()
                ax.legend(
                    loc="center left",
                    bbox_to_anchor=(1.02, 0.5),
                    borderaxespad=0,
                    frameon=frameon,
                )
            else:
                handles, labels = ax.get_legend_handles_labels()
                legend.remove()
                ax.legend(
                    handles,
                    labels,
                    loc=a.get("legend_loc", "best"),
                    frameon=frameon,
                )

        if not a.get("tick_labels", True):
            ax.set_xticklabels([])
            ax.set_yticklabels([])

    @staticmethod
    def render(block: "PlotBlock") -> Figure:
        """Return a new Figure with the plot rendered."""
        fig = Figure(figsize=(block.width_in, block.height_in), dpi=DPI)
        ax = fig.add_subplot(111)
        PlotRenderer._render_to_ax(block, ax, fig)
        fig.tight_layout()
        return fig

    @staticmethod
    def render_to_ax(block: "PlotBlock", ax, fig):
        """Render the plot onto an existing axes (used for vector export)."""
        PlotRenderer._render_to_ax(block, ax, fig)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
class KTFigure:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ktfigure")
        self.root.geometry("1260x880")
        self.root.minsize(960, 700)

        # Set window icon
        try:
            icon_path = os.path.join(
                os.path.dirname(__file__), "images", "ktfigure_logo.png"
            )
            if os.path.exists(icon_path):
                icon_img = Image.open(icon_path)
                icon_photo = ImageTk.PhotoImage(icon_img)
                self.root.iconphoto(True, icon_photo)
        except Exception as e:
            print(f"Warning: Could not load window icon: {e}")

        self._blocks: list[PlotBlock] = []
        self._selected: PlotBlock | None = None
        self._drag_start = None
        self._rubber_rect = None
        self._mode = "select"
        self._resize_handles: list = []
        self._resize_corner: str | None = None
        self._resize_block: PlotBlock | None = None
        self._resize_shape: Shape | None = None
        self._resize_all_objects: list = []  # For multi-object resizing
        self._resize_initial_dims: dict = {}  # Initial dims for multi-resize
        self._drag_block: PlotBlock | None = None
        self._drag_offset = (0, 0)

        # Shape drawing
        self._shapes: list[Shape] = []
        self._selected_shape: Shape | None = None
        self._drag_shape: Shape | None = None
        self._guide_object = None  # Can be PlotBlock or Shape
        self._shape_color = "#000000"
        self._shape_line_width = 2

        # Text objects
        self._texts: list[TextObject] = []
        self._selected_text: TextObject | None = None
        self._drag_text: TextObject | None = None
        self._text_create_start = (
            None  # Track initial click for single-click text creation
        )

        # Multi-select support
        self._selected_objects: list = []  # List of selected blocks/shapes
        self._selection_rect = None  # Selection rectangle ID

        # Shift key tracking
        self._shift_pressed = False

        # Resize tracking for shapes
        self._resize_shape: Shape | None = None
        self._resize_text: TextObject | None = None

        # Undo/Redo stacks
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._max_undo = 50

        # Grid / snap state
        self._snap_to_grid: bool = True  # snap is on by default
        self._show_grid: bool = False  # grid lines hidden by default

        # Clipboard
        self._clipboard = None

        # Theme
        self._is_dark = False
        self._theme_manual_override = False  # True once user has manually toggled
        self._theme_widgets: dict = {}  # refs collected during _build_ui

        self._build_ui()
        self._mode_select()  # Set default mode to select
        # Snap is on by default – reflect that in the button visual state
        self._btn_snap._is_active = True
        self._btn_snap._set_bg("#3b82f6")
        self._btn_snap._lbl.configure(fg="white")
        self._draw_artboard()
        self._save_state()  # Initial state
        self._auto_theme_check()  # Set theme by time of day, then schedule checks

    # -----------------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------------
    def _build_ui(self):
        # ── toolbar ────────────────────────────────────────────────────────
        TC = THEME_LIGHT  # shorthand — always start in light mode
        TB_BG = TC["tb"]

        _all_tbs: list[tk.Frame] = []  # toolbar row frames
        _all_seps: list[tk.Frame] = []  # separator frames
        _all_btns: list[StyledButton] = []  # every normal (non-coloured) tbtn

        def tbtn(
            parent,
            text,
            cmd,
            bg=None,
            fg=None,
            hover_bg=None,
            press_bg=None,
            _themed=True,  # False for coloured special buttons
        ):
            b = StyledButton(
                parent,
                text=text,
                command=cmd,
                bg=bg or TC["btn"],
                fg=fg or TC["btn_fg"],
                hover_bg=hover_bg or TC["btn_hover"],
                press_bg=press_bg or TC["btn_press"],
                canvas_bg=TB_BG,
                padx=13,
                pady=7,
                font=("", 9),
            )
            b.pack(side="left", padx=4, pady=8)
            if _themed:
                _all_btns.append(b)
            return b

        def sep(parent):
            f = tk.Frame(parent, bg=TC["sep"], width=1)
            f.pack(side="left", fill="y", padx=2, pady=12)
            _all_seps.append(f)

        # Row 1: Select, Plot | Edit, Delete | PNG, PDF, SVG, Help | Theme toggle
        tb1 = tk.Frame(self.root, bg=TB_BG, height=52)
        tb1.pack(side="top", fill="x")
        tb1.pack_propagate(False)
        _all_tbs.append(tb1)

        self._btn_select = tbtn(tb1, "⬚  Select", self._mode_select)
        self._btn_draw = tbtn(tb1, "✏  Plot", self._mode_draw)
        sep(tb1)
        tbtn(tb1, "📝  Edit plot", self._edit_selected)
        tbtn(
            tb1,
            "🗑  Delete",
            self._delete_selected,
            bg="#fee2e2",
            fg="#991b1b",
            hover_bg="#fecaca",
            press_bg="#fca5a5",
            _themed=False,
        )
        sep(tb1)
        tbtn(
            tb1,
            "💾  PNG",
            self._export_png,
            bg="#dcfce7",
            fg="#166534",
            hover_bg="#bbf7d0",
            press_bg="#86efac",
            _themed=False,
        )
        tbtn(
            tb1,
            "📄  PDF",
            self._export_pdf,
            bg="#dbeafe",
            fg="#1e40af",
            hover_bg="#bfdbfe",
            press_bg="#93c5fd",
            _themed=False,
        )
        tbtn(
            tb1,
            "📐  SVG",
            self._export_svg,
            bg="#fef3c7",
            fg="#92400e",
            hover_bg="#fde68a",
            press_bg="#fcd34d",
            _themed=False,
        )
        tbtn(tb1, "❓  Help", self._show_help)

        # Sliding theme toggle — always at the far right of row 1
        self._theme_toggle = ThemeToggle(tb1, command=self._on_theme_click, bg=TB_BG)
        self._theme_toggle.pack(side="right", padx=12, pady=12)

        # Mode label — just to the left of the toggle
        self._mode_lbl = tk.Label(
            tb1,
            text="Mode: Select  ⬚",
            bg=TB_BG,
            fg=TC["accent"],
            font=("", 9, "bold"),
            padx=14,
        )
        self._mode_lbl.pack(side="right")

        # Border between rows
        _b1 = tk.Frame(self.root, bg=TC["sep"], height=1)
        _b1.pack(side="top", fill="x")
        _all_seps.append(_b1)

        # Row 2: Edit commands, shapes, and text
        tb2 = tk.Frame(self.root, bg=TB_BG, height=52)
        tb2.pack(side="top", fill="x")
        tb2.pack_propagate(False)
        _all_tbs.append(tb2)

        tbtn(tb2, "↶  Undo", self._undo)
        tbtn(tb2, "↷  Redo", self._redo)
        sep(tb2)
        tbtn(tb2, "✂  Cut", self._cut)
        tbtn(tb2, "📋  Copy", self._copy)
        tbtn(tb2, "📄  Paste", self._paste)
        sep(tb2)
        self._btn_line = tbtn(tb2, "📏  Line", self._mode_draw_line)
        self._btn_rect = tbtn(tb2, "▭  Rectangle", self._mode_draw_rect)
        self._btn_circle = tbtn(tb2, "⬭  Circle", self._mode_draw_circle)
        self._btn_text = tbtn(tb2, "🅃 Text", self._mode_add_text)

        # Border between rows
        _b2 = tk.Frame(self.root, bg=TC["sep"], height=1)
        _b2.pack(side="top", fill="x")
        _all_seps.append(_b2)

        # Row 3: All 7 alignment buttons
        tb3 = tk.Frame(self.root, bg=TB_BG, height=52)
        tb3.pack(side="top", fill="x")
        tb3.pack_propagate(False)
        _all_tbs.append(tb3)

        tbtn(tb3, "⬅  Align L", self._align_left)
        tbtn(tb3, "➡  Align R", self._align_right)
        tbtn(tb3, "⬆  Align T", self._align_top)
        tbtn(tb3, "⬇  Align B", self._align_bottom)
        tbtn(tb3, "⊟  Align H", self._align_center)
        tbtn(tb3, "⎅  Align V", self._align_middle)
        tbtn(tb3, "↔  Distribute H", self._distribute_horizontal)
        tbtn(tb3, "↕  Distribute V", self._distribute_vertical)
        sep(tb3)
        self._btn_grid = tbtn(tb3, "⊞  Grid", self._toggle_grid_visible)
        self._btn_snap = tbtn(tb3, "⊡  Snap", self._toggle_snap_to_grid)

        # Final bottom border
        _b3 = tk.Frame(self.root, bg=TC["sep"], height=1)
        _b3.pack(side="top", fill="x")
        _all_seps.append(_b3)

        # ── main ───────────────────────────────────────────────────────────
        main = tk.Frame(self.root, bg=TC["canvas"])
        self._main_frame = main
        main.pack(fill="both", expand=True)

        paned = ttk.PanedWindow(main, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=4, pady=4)

        # canvas area (left pane)
        co = tk.Frame(paned, bg=TC["canvas"])
        self._canvas_outer = co
        paned.add(co, weight=4)

        # right panel (right pane) – resizable by dragging the sash
        right = ttk.Frame(paned, width=280)
        paned.add(right, weight=1)
        self._aes = AestheticsPanel(right, self._on_aes_update)
        self._aes.pack(fill="both", expand=True)

        hsb = ttk.Scrollbar(co, orient="horizontal")
        vsb = ttk.Scrollbar(co, orient="vertical")
        self._cv = tk.Canvas(
            co,
            bg=TC["canvas"],
            cursor="crosshair",
            xscrollcommand=hsb.set,
            yscrollcommand=vsb.set,
            highlightthickness=0,
        )
        hsb.config(command=self._cv.xview)
        vsb.config(command=self._cv.yview)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        self._cv.pack(side="left", fill="both", expand=True)

        # Enable mouse wheel scrolling
        bind_mousewheel(self._cv, self._cv, "both")

        self._cv.configure(
            scrollregion=(0, 0, A4_W + 2 * BOARD_PAD, A4_H + 2 * BOARD_PAD)
        )

        self._cv.bind("<Button-1>", self._mouse_down)
        self._cv.bind("<B1-Motion>", self._mouse_drag)
        self._cv.bind("<ButtonRelease-1>", self._mouse_up)
        self._cv.bind("<Double-Button-1>", self._mouse_dbl)
        self._cv.bind("<Motion>", self._mouse_motion)

        # Bind Shift key tracking
        self.root.bind("<KeyPress-Shift_L>", lambda e: self._on_shift(True))
        self.root.bind("<KeyPress-Shift_R>", lambda e: self._on_shift(True))
        self.root.bind("<KeyRelease-Shift_L>", lambda e: self._on_shift(False))
        self.root.bind("<KeyRelease-Shift_R>", lambda e: self._on_shift(False))

        # Keyboard shortcuts (platform-aware)
        cmd_key = "Command" if sys.platform == "darwin" else "Control"

        self.root.bind(f"<{cmd_key}-z>", lambda e: self._undo())
        self.root.bind(f"<{cmd_key}-Z>", lambda e: self._redo())  # Cmd+Shift+Z
        self.root.bind(f"<{cmd_key}-y>", lambda e: self._redo())  # Cmd+Y alternative
        self.root.bind(f"<{cmd_key}-x>", lambda e: self._cut())
        self.root.bind(f"<{cmd_key}-c>", lambda e: self._copy())
        self.root.bind(f"<{cmd_key}-v>", lambda e: self._paste())
        self.root.bind(f"<{cmd_key}-a>", lambda e: self._select_all())
        self.root.bind("<Delete>", lambda e: self._delete_key())
        self.root.bind("<BackSpace>", lambda e: self._delete_key())

        # status bar
        self._status_sep = tk.Frame(self.root, bg=TC["sep"], height=1)
        self._status_sep.pack(side="bottom", fill="x")
        self._status = tk.Label(
            self.root,
            text="Ready — drag on the white A4 board to draw a plot region.",
            bd=0,
            relief="flat",
            anchor="w",
            bg=TC["tb"],
            fg=TC["status_fg"],
            padx=12,
            pady=4,
            font=("", 9),
        )
        self._status.pack(side="bottom", fill="x")

        # Store all themeable widget refs for _apply_theme()
        self._theme_widgets = {
            "tbs": _all_tbs,
            "seps": _all_seps,
            "btns": _all_btns,
        }

        # Apply initial light-mode ttk styles so dialogs (PlotConfigDialog etc.)
        # render with proper readable colors from the start
        self._apply_theme()

    def _draw_artboard(self):
        ox, oy = BOARD_PAD, BOARD_PAD
        # drop shadow
        self._cv.create_rectangle(
            ox + 5,
            oy + 5,
            ox + A4_W + 5,
            oy + A4_H + 5,
            fill="#222",
            outline="",
            tags="bg",
        )
        # white sheet
        self._cv.create_rectangle(
            ox,
            oy,
            ox + A4_W,
            oy + A4_H,
            fill="white",
            outline="#bbb",
            width=1,
            tags="artboard",
        )
        # subtle rulers
        for x in range(0, A4_W + 1, 100):
            self._cv.create_line(ox + x, oy, ox + x, oy + 8, fill="#ccc", tags="ruler")
        for y in range(0, A4_H + 1, 100):
            self._cv.create_line(ox, oy + y, ox + 8, oy + y, fill="#ccc", tags="ruler")

    # -----------------------------------------------------------------------
    # Coordinate helpers
    # -----------------------------------------------------------------------
    def _to_board(self, cx, cy):
        bx = cx - BOARD_PAD
        by = cy - BOARD_PAD
        return max(0, min(bx, A4_W)), max(0, min(by, A4_H))

    def _to_canvas(self, bx, by):
        return bx + BOARD_PAD, by + BOARD_PAD

    def _ev_board(self, event):
        return self._to_board(self._cv.canvasx(event.x), self._cv.canvasy(event.y))

    # -----------------------------------------------------------------------
    # Grid / snap helpers
    # -----------------------------------------------------------------------
    def _snap(self, v: float) -> float:
        """Snap a single board coordinate to the nearest grid line."""
        if not self._snap_to_grid:
            return v
        return round(v / GRID_SIZE) * GRID_SIZE

    def _snap_pos(self, bx: float, by: float):
        """Return (bx, by) snapped to the grid (no-op when snap is off)."""
        return self._snap(bx), self._snap(by)

    def _draw_grid(self):
        """Draw grid lines across the artboard.

        The artboard is always rendered on a white background regardless of
        the UI theme, so a fixed light-grey colour is appropriate here.
        """
        ox, oy = BOARD_PAD, BOARD_PAD
        for x in range(0, A4_W + 1, GRID_SIZE):
            self._cv.create_line(
                ox + x,
                oy,
                ox + x,
                oy + A4_H,
                fill="#cccccc",
                dash=(1, GRID_SIZE - 1),
                tags="grid",
            )
        for y in range(0, A4_H + 1, GRID_SIZE):
            self._cv.create_line(
                ox,
                oy + y,
                ox + A4_W,
                oy + y,
                fill="#cccccc",
                dash=(1, GRID_SIZE - 1),
                tags="grid",
            )
        # Place grid above the artboard (white sheet) but below blocks/shapes
        self._cv.tag_raise("grid", "artboard")

    def _clear_grid(self):
        """Remove all grid lines from the canvas."""
        self._cv.delete("grid")

    def _toggle_grid_visible(self):
        """Toggle visibility of the grid overlay on the artboard."""
        self._show_grid = not self._show_grid
        TC = THEME_DARK if self._is_dark else THEME_LIGHT
        if self._show_grid:
            self._draw_grid()
            self._btn_grid._is_active = True
            self._btn_grid._set_bg("#3b82f6")
            self._btn_grid._lbl.configure(fg="white")
            self._set_status("Grid visible. Drag objects to snap to grid lines.")
        else:
            self._clear_grid()
            self._btn_grid._is_active = False
            self._btn_grid._set_bg(TC["btn"])
            self._btn_grid._lbl.configure(fg=TC["btn_fg"])
            self._set_status("Grid hidden.")

    def _toggle_snap_to_grid(self):
        """Toggle snap-to-grid behaviour when placing or resizing objects."""
        self._snap_to_grid = not self._snap_to_grid
        TC = THEME_DARK if self._is_dark else THEME_LIGHT
        if self._snap_to_grid:
            self._btn_snap._is_active = True
            self._btn_snap._set_bg("#3b82f6")
            self._btn_snap._lbl.configure(fg="white")
            self._set_status("Snap to grid ON.")
        else:
            self._btn_snap._is_active = False
            self._btn_snap._set_bg(TC["btn"])
            self._btn_snap._lbl.configure(fg=TC["btn_fg"])
            self._set_status("Snap to grid OFF.")

    def _block_at(self, bx, by, pad=0):
        for b in reversed(self._blocks):
            if b.x1 - pad <= bx <= b.x2 + pad and b.y1 - pad <= by <= b.y2 + pad:
                return b
        return None

    def _shape_at(self, bx, by, pad=0):
        """Find shape at given board coordinates."""
        for s in reversed(self._shapes):
            # Normalise coords so min <= max (lines preserve drawing direction so
            # x1/y1 are not guaranteed to be the smaller values).
            x_min, x_max = min(s.x1, s.x2), max(s.x1, s.x2)
            y_min, y_max = min(s.y1, s.y2), max(s.y1, s.y2)
            # Lines can be horizontal/vertical (zero height/width), so ensure a
            # minimum 6-pixel hit area so they stay clickable.
            eff_pad = max(pad, 6) if s.shape_type == "line" else pad
            if (
                x_min - eff_pad <= bx <= x_max + eff_pad
                and y_min - eff_pad <= by <= y_max + eff_pad
            ):
                return s
        return None

    def _on_shift(self, pressed):
        """Track Shift key state."""
        self._shift_pressed = pressed

    def _is_cmd_pressed(self, event):
        """Check if Cmd (macOS) or Ctrl (other) is pressed from event state."""
        # Bit 2 (0x0004) = Control key on all platforms
        # Bit 3 (0x0008) = Command key on macOS
        if sys.platform == "darwin":
            return (event.state & 0x0008) != 0  # Command key on macOS
        else:
            return (event.state & 0x0004) != 0  # Control key on Windows/Linux

    def _is_shift_pressed(self, event):
        """Check if Shift key is pressed from event state."""
        # Bit 0 (0x0001) = Shift key
        return (event.state & 0x0001) != 0

    # -----------------------------------------------------------------------
    # Shape operations
    # -----------------------------------------------------------------------
    def _draw_shape(self, shape: Shape):
        """Draw or redraw a shape on the canvas."""
        if shape.item_id:
            self._cv.delete(shape.item_id)

        cx1, cy1 = self._to_canvas(shape.x1, shape.y1)
        cx2, cy2 = self._to_canvas(shape.x2, shape.y2)

        if shape.shape_type == "line":
            line_kwargs = dict(
                fill=shape.color,
                width=shape.line_width,
                arrow=shape.arrow or None,
                dash=shape.dash,
                tags=(f"shape{shape.sid}", "shape"),
            )
            if shape.arrow:
                line_kwargs["arrowshape"] = _compute_arrowshape(
                    shape.arrowshape_style, shape.arrow_size
                )
            shape.item_id = self._cv.create_line(cx1, cy1, cx2, cy2, **line_kwargs)
        elif shape.shape_type == "rectangle":
            shape.item_id = self._cv.create_rectangle(
                cx1,
                cy1,
                cx2,
                cy2,
                outline=shape.color,
                width=shape.line_width,
                fill=shape.fill,
                dash=shape.dash,
                tags=(f"shape{shape.sid}", "shape"),
            )
        elif shape.shape_type == "circle":
            shape.item_id = self._cv.create_oval(
                cx1,
                cy1,
                cx2,
                cy2,
                outline=shape.color,
                width=shape.line_width,
                fill=shape.fill,
                dash=shape.dash,
                tags=(f"shape{shape.sid}", "shape"),
            )

        # If this shape is currently selected, refresh its selection handles so
        # they stay in sync with the new canvas item and remain functional.
        if shape is self._selected_shape or (
            self._selected_objects and shape in self._selected_objects
        ):
            self._draw_handles_shape(shape)

    def _draw_text(self, text_obj: TextObject):
        """Draw or redraw a text object on the canvas."""
        if text_obj.item_id:
            self._cv.delete(text_obj.item_id)

        cx, cy = self._to_canvas(text_obj.center_x, text_obj.center_y)

        # Build font tuple with bold and italic
        weight = "bold" if text_obj.bold else "normal"
        slant = "italic" if text_obj.italic else "roman"
        font_tuple = (text_obj.font_family, text_obj.font_size, f"{weight} {slant}")

        text_obj.item_id = self._cv.create_text(
            cx,
            cy,
            text=text_obj.text,
            font=font_tuple,
            fill=text_obj.color,
            tags=(f"text{text_obj.tid}", "text"),
        )

        # If this text object is currently selected, refresh its selection handles
        # so they stay in sync with the new canvas item and remain functional.
        if text_obj is self._selected_text or (
            self._selected_objects and text_obj in self._selected_objects
        ):
            self._draw_handles_text(text_obj)

    def _text_at(self, x, y):
        """Find a text object at the given board coordinates."""
        for text_obj in self._texts:
            if text_obj.x1 <= x <= text_obj.x2 and text_obj.y1 <= y <= text_obj.y2:
                return text_obj
        return None

    def _select_text(self, text_obj: TextObject | None):
        """Select a text object and show its properties."""
        if self._selected_text and self._selected_text != text_obj:
            self._unhighlight_text(self._selected_text)
        self._selected_text = text_obj
        if text_obj:
            self._highlight_text(text_obj)
            self._aes.load_text(text_obj, self._draw_text)
            self._set_status(
                f"Text {text_obj.tid} selected. Double-click to edit in detail."
            )
        else:
            self._aes.clear_shape_properties()

    def _highlight_text(self, text_obj: TextObject):
        """Highlight a selected text object; orange only for the guide."""
        if text_obj.item_id and text_obj is self._guide_object:
            try:
                self._cv.itemconfig(text_obj.item_id, fill="#FF6D00")
            except tk.TclError:
                pass
        # Draw handles for text box
        self._draw_handles_text(text_obj, clear_first=False)

    def _unhighlight_text(self, text_obj: TextObject):
        """Remove highlight from text object."""
        if text_obj.item_id:
            try:
                self._cv.itemconfig(text_obj.item_id, fill=text_obj.color)
            except tk.TclError:
                pass
        # Clear handles if not in selection
        if text_obj not in self._selected_objects:
            for h in self._resize_handles:
                try:
                    self._cv.delete(h)
                except:
                    pass

    def _draw_handles_text(self, text_obj: TextObject, clear_first=True):
        """Draw resize handles for a text object."""
        if clear_first:
            self._clear_handles()
        HS = 5
        corners = {
            "nw": (text_obj.x1, text_obj.y1),
            "ne": (text_obj.x2, text_obj.y1),
            "sw": (text_obj.x1, text_obj.y2),
            "se": (text_obj.x2, text_obj.y2),
        }
        for name, (bx, by) in corners.items():
            cx, cy = self._to_canvas(bx, by)
            h = self._cv.create_rectangle(
                cx - HS,
                cy - HS,
                cx + HS,
                cy + HS,
                fill="white",
                outline="#FF6D00",
                width=2,
                tags=("resize_handle", name),
            )
            self._resize_handles.append(h)

    def _edit_text_on_canvas(self, text_obj: TextObject):
        """Place an Entry widget on canvas for direct text editing."""
        # Convert board coords to canvas coords
        cx1, cy1 = self._to_canvas(text_obj.x1, text_obj.y1)
        cx2, cy2 = self._to_canvas(text_obj.x2, text_obj.y2)

        # Create Entry widget (no visible border box)
        entry = tk.Entry(
            self._cv,
            font=(text_obj.font_family, text_obj.font_size),
            fg=text_obj.color,
            bg="white",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
        )
        entry.insert(0, text_obj.text)
        entry.focus()
        entry.select_range(0, tk.END)

        # Calculate entry position and size
        width_px = cx2 - cx1
        height_px = cy2 - cy1
        font_height = text_obj.font_size + 5  # Rough estimate

        # Create window on canvas
        entry_window = self._cv.create_window(
            cx1 + width_px // 2,
            cy1 + height_px // 2,
            window=entry,
            width=max(width_px - 4, 50),
            height=max(height_px - 4, font_height),
            tags="text_entry",
        )

        def finish_edit(save=True):
            """Finish editing and update text object."""
            if save:
                new_text = entry.get().strip()
                text_obj.text = new_text if new_text else "Text"

            try:
                self._cv.delete(entry_window)
            except tk.TclError:
                pass

            # Redraw text and select it, then switch back to select mode
            self._draw_text(text_obj)
            self._select_text(text_obj)
            self._save_state()
            self._mode_select()
            self._set_status("Text added. You can edit it by double-clicking.")

        def on_return(event):
            finish_edit(save=True)

        def on_escape(event):
            finish_edit(save=True)

        entry.bind("<Return>", on_return)
        entry.bind("<Escape>", on_escape)
        entry.bind("<FocusOut>", lambda e: finish_edit(save=True))

    def _edit_text(self, text_obj: TextObject):
        """Open a dialog to edit text object properties."""
        # Create a custom dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Text {text_obj.tid}")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_set()

        # Text content
        frame1 = tk.Frame(dialog, padx=10, pady=10)
        frame1.pack(fill=tk.X)
        tk.Label(frame1, text="Text:").pack(side=tk.LEFT)
        text_entry = tk.Entry(frame1, width=30)
        text_entry.insert(0, text_obj.text)
        text_entry.pack(side=tk.LEFT, padx=5)

        # Font size
        frame2 = tk.Frame(dialog, padx=10, pady=5)
        frame2.pack(fill=tk.X)
        tk.Label(frame2, text="Font Size:").pack(side=tk.LEFT)
        size_var = tk.IntVar(value=text_obj.font_size)
        tk.Spinbox(frame2, from_=8, to=72, textvariable=size_var, width=5).pack(
            side=tk.LEFT, padx=5
        )

        # Font family
        frame3 = tk.Frame(dialog, padx=10, pady=5)
        frame3.pack(fill=tk.X)
        tk.Label(frame3, text="Font:").pack(side=tk.LEFT)
        font_var = tk.StringVar(value=text_obj.font_family)
        font_combo = ttk.Combobox(
            frame3,
            textvariable=font_var,
            width=20,
            values=["DejaVu Sans", "Arial", "Times New Roman", "Courier"],
        )
        font_combo.pack(side=tk.LEFT, padx=5)

        # Bold/Italic
        frame4 = tk.Frame(dialog, padx=10, pady=5)
        frame4.pack(fill=tk.X)
        bold_var = tk.BooleanVar(value=text_obj.bold)
        tk.Checkbutton(frame4, text="Bold", variable=bold_var).pack(side=tk.LEFT)
        italic_var = tk.BooleanVar(value=text_obj.italic)
        tk.Checkbutton(frame4, text="Italic", variable=italic_var).pack(
            side=tk.LEFT, padx=5
        )

        # Color
        frame5 = tk.Frame(dialog, padx=10, pady=5)
        frame5.pack(fill=tk.X)
        tk.Label(frame5, text="Color:").pack(side=tk.LEFT)
        color_label = tk.Label(
            frame5, text="   ", bg=text_obj.color, width=3, relief=tk.SUNKEN
        )
        color_label.pack(side=tk.LEFT, padx=5)
        selected_color = [text_obj.color]

        def choose_color():
            color = colorchooser.askcolor(color=text_obj.color, parent=dialog)
            if color[1]:
                selected_color[0] = color[1]
                color_label.config(bg=color[1])

        tk.Button(frame5, text="Choose", command=choose_color).pack(side=tk.LEFT)

        # Buttons
        frame_btn = tk.Frame(dialog, padx=10, pady=10)
        frame_btn.pack(fill=tk.X)

        result = [False]

        def ok_clicked():
            text_obj.text = text_entry.get()
            text_obj.font_size = size_var.get()
            text_obj.font_family = font_var.get()
            text_obj.bold = bold_var.get()
            text_obj.italic = italic_var.get()
            text_obj.color = selected_color[0]
            result[0] = True
            dialog.destroy()

        tk.Button(frame_btn, text="OK", command=ok_clicked, width=10).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(frame_btn, text="Cancel", command=dialog.destroy, width=10).pack(
            side=tk.LEFT
        )

        dialog.wait_window()

        if result[0]:
            self._draw_text(text_obj)
            self._save_state()
            self._set_status(f"Text {text_obj.tid} updated.")

    def _select_shape(self, shape: Shape | None):
        """Select a shape and show its properties."""
        if self._selected_shape and self._selected_shape != shape:
            self._unhighlight_shape(self._selected_shape)
        self._selected_shape = shape
        if shape:
            self._highlight_shape(shape)
            self._aes.load_shape(shape, self._draw_shape)
            self._set_status(f"Selected Shape {shape.sid}")
        else:
            self._aes.clear_shape_properties()

    def _highlight_shape(self, shape: Shape):
        """Highlight a selected shape with handles; orange only for the guide."""
        if shape.item_id and shape is self._guide_object:
            try:
                if shape.shape_type == "line":
                    self._cv.itemconfig(
                        shape.item_id, width=shape.line_width + 2, fill="#FF6D00"
                    )
                else:
                    self._cv.itemconfig(
                        shape.item_id, width=shape.line_width + 2, outline="#FF6D00"
                    )
            except tk.TclError:
                pass
        # Draw handles for all selected objects
        self._draw_handles_shape(shape, clear_first=False)

    def _unhighlight_shape(self, shape: Shape):
        """Remove highlight from shape by restoring normal line width and color."""
        if shape.item_id:
            try:
                # Restore original line width and color
                if shape.shape_type == "line":
                    # For lines, use fill property
                    self._cv.itemconfig(
                        shape.item_id, width=shape.line_width, fill=shape.color
                    )
                else:
                    # For rectangles and circles, use outline property
                    self._cv.itemconfig(
                        shape.item_id, width=shape.line_width, outline=shape.color
                    )
            except tk.TclError:
                # Shape item might have been deleted, ignore
                pass
        # Don't clear handles here if other objects are selected
        if shape not in self._selected_objects:
            for h in self._resize_handles:
                try:
                    self._cv.delete(h)
                except:
                    pass

    def _draw_handles_shape(self, shape: Shape, clear_first=True):
        """Draw resize handles for a shape."""
        if clear_first:
            self._clear_handles()
        HS = 5
        corners = {
            "nw": (shape.x1, shape.y1),
            "ne": (shape.x2, shape.y1),
            "sw": (shape.x1, shape.y2),
            "se": (shape.x2, shape.y2),
        }
        for name, (bx, by) in corners.items():
            cx, cy = self._to_canvas(bx, by)
            h = self._cv.create_rectangle(
                cx - HS,
                cy - HS,
                cx + HS,
                cy + HS,
                fill="white",
                outline="#FF6D00",
                width=2,
                tags=("resize_handle", name),
            )
            self._resize_handles.append(h)

    # -----------------------------------------------------------------------
    # Modes
    # -----------------------------------------------------------------------
    def _clear_resize_state(self):
        """Clear all resize/selection state when switching away from select mode."""
        self._resize_corner = None
        self._resize_shape = None
        self._resize_text = None
        self._resize_block = None
        self._resize_all_objects = []
        if hasattr(self, "_resize_group_bbox"):
            del self._resize_group_bbox
        if hasattr(self, "_resize_initial_dims"):
            self._resize_initial_dims = {}
        self._selected = None
        self._selected_shape = None
        self._selected_text = None
        self._selected_objects = []
        self._clear_handles()
        self._aes.clear()
        self._aes.clear_shape_properties()

    def _mode_draw(self):
        self._clear_resize_state()
        self._mode = "draw"
        self._cv.configure(cursor="crosshair")
        self._mode_lbl.configure(text="Mode: Plot  ✏")
        self._highlight_mode_button(self._btn_draw)
        self._set_status("Drag on the white artboard to draw a new plot region.")

    def _mode_select(self):
        self._mode = "select"
        self._cv.configure(cursor="arrow")
        self._mode_lbl.configure(text="Mode: Select  ⬚")
        self._highlight_mode_button(self._btn_select)
        self._set_status(
            "Click & drag to move a plot.  Drag corners to resize.  Double-click to edit."
        )

    def _mode_draw_line(self):
        self._clear_resize_state()
        self._mode = "draw_line"
        self._cv.configure(cursor="crosshair")
        self._mode_lbl.configure(text="Mode: Line  📏")
        self._highlight_mode_button(self._btn_line)
        self._set_status("Drag to draw a line.")

    def _mode_draw_rect(self):
        self._clear_resize_state()
        self._mode = "draw_rect"
        self._cv.configure(cursor="crosshair")
        self._mode_lbl.configure(text="Mode: Rectangle  ▭")
        self._highlight_mode_button(self._btn_rect)
        self._set_status("Drag to draw a rectangle.")

    def _mode_draw_circle(self):
        self._clear_resize_state()
        self._mode = "draw_circle"
        self._cv.configure(cursor="crosshair")
        self._mode_lbl.configure(text="Mode: Circle  ⬭")
        self._highlight_mode_button(self._btn_circle)
        self._set_status("Drag to draw a circle/ellipse.")

    def _mode_add_text(self):
        self._clear_resize_state()
        self._mode = "add_text"
        self._cv.configure(cursor="crosshair")
        self._mode_lbl.configure(text="Mode: Text  🔤")
        self._highlight_mode_button(self._btn_text)
        self._set_status(
            "Click to add text (default size), or drag to create custom size. Then type directly."
        )

    def _highlight_mode_button(self, active_btn):
        """Highlight the active mode button and dim others."""
        mode_buttons = [
            self._btn_draw,
            self._btn_select,
            self._btn_line,
            self._btn_rect,
            self._btn_circle,
            self._btn_text,
        ]
        for btn in mode_buttons:
            if btn == active_btn:
                # Highlight active button with blue background and white text
                btn._bg = "#3b82f6"
                btn._hover_bg = "#2563eb"
                btn._press_bg = "#1d4ed8"
                btn._is_active = True
                btn.configure(
                    bg="#3b82f6",
                    highlightbackground="#3b82f6",
                    highlightcolor="#3b82f6",
                )
                btn._lbl.configure(bg="#3b82f6", fg="white")
            else:
                # Reset to default appearance using current theme colors
                TC = THEME_DARK if self._is_dark else THEME_LIGHT
                btn._bg = TC["btn"]
                btn._hover_bg = TC["btn_hover"]
                btn._press_bg = TC["btn_press"]
                btn._is_active = False
                btn.configure(
                    bg=TC["btn"],
                    highlightbackground=TC["btn"],
                    highlightcolor=TC["btn"],
                )
                btn._lbl.configure(bg=TC["btn"], fg=TC["btn_fg"])

    def _on_theme_click(self):
        """Called when the user manually clicks the theme toggle."""
        self._theme_manual_override = True
        self._is_dark = not self._is_dark
        self._apply_theme()

    def _toggle_theme(self):
        """Programmatically switch theme (used by auto-scheduler)."""
        self._is_dark = not self._is_dark
        self._apply_theme()

    def _auto_theme_check(self):
        """Auto-switch light/dark by time of day unless user has overridden."""
        if not self._theme_manual_override:
            hour = datetime.datetime.now().hour
            should_dark = hour >= 19 or hour < 7
            if should_dark != self._is_dark:
                self._is_dark = should_dark
                self._apply_theme()
        # Re-schedule every 60 s
        self.root.after(60_000, self._auto_theme_check)

    def _apply_theme(self):
        """Apply the current theme to all stored widget refs."""
        TC = THEME_DARK if self._is_dark else THEME_LIGHT

        # Toolbar rows
        for f in self._theme_widgets.get("tbs", []):
            f.configure(bg=TC["tb"])

        # Separator frames
        for f in self._theme_widgets.get("seps", []):
            f.configure(bg=TC["sep"])

        # Normal themed buttons (non-coloured)
        for btn in self._theme_widgets.get("btns", []):
            if not btn._is_active:
                btn._bg = TC["btn"]
                btn._hover_bg = TC["btn_hover"]
                btn._press_bg = TC["btn_press"]
                btn._set_bg(TC["btn"])
                btn._lbl.configure(fg=TC["btn_fg"])

        # Mode label
        self._mode_lbl.configure(bg=TC["tb"], fg=TC["accent"])

        # Status bar
        self._status.configure(bg=TC["tb"], fg=TC["status_fg"])
        self._status_sep.configure(bg=TC["sep"])

        # Canvas outer frame and canvas itself
        self._canvas_outer.configure(bg=TC["canvas"])
        self._cv.configure(bg=TC["canvas"])

        # Main container frame
        self._main_frame.configure(bg=TC["canvas"])

        # ttk theme for panels
        style = ttk.Style()
        if self._is_dark:
            style.theme_use("clam")
            style.configure(".", background=TC["panel_bg"], foreground=TC["btn_fg"])
            style.configure("TFrame", background=TC["panel_bg"])
            style.configure(
                "TLabel", background=TC["panel_bg"], foreground=TC["btn_fg"]
            )
            style.configure(
                "TEntry", fieldbackground="#3c3c3c", foreground=TC["btn_fg"]
            )
            style.configure(
                "TCombobox", fieldbackground="#3c3c3c", foreground=TC["btn_fg"]
            )
            style.configure(
                "TSpinbox", fieldbackground="#3c3c3c", foreground=TC["btn_fg"]
            )
            style.configure(
                "TCheckbutton", background=TC["panel_bg"], foreground=TC["btn_fg"]
            )
            style.configure("TButton", background=TC["btn"], foreground=TC["btn_fg"])
            style.configure("TPanedwindow", background=TC["canvas"])
            style.configure("Horizontal.TScrollbar", background=TC["btn"])
            style.configure("Vertical.TScrollbar", background=TC["btn"])
            style.configure("TNotebook", background=TC["panel_bg"])
            style.configure(
                "TNotebook.Tab", background=TC["btn"], foreground=TC["btn_fg"]
            )
            style.map("TNotebook.Tab", background=[("selected", "#505050")])
        else:
            style.theme_use("clam")
            style.configure(".", background=TC["panel_bg"], foreground="#1e293b")
            style.configure("TFrame", background=TC["panel_bg"])
            style.configure("TLabel", background=TC["panel_bg"], foreground="#1e293b")
            style.configure("TEntry", fieldbackground="#ffffff", foreground="#1e293b")
            style.configure(
                "TCombobox", fieldbackground="#ffffff", foreground="#1e293b"
            )
            style.configure("TSpinbox", fieldbackground="#ffffff", foreground="#1e293b")
            style.configure(
                "TCheckbutton", background=TC["panel_bg"], foreground="#1e293b"
            )
            style.configure("TButton", background="#e2e8f0", foreground="#1e293b")
            style.configure("TPanedwindow", background=TC["canvas"])
            style.configure("Horizontal.TScrollbar", background="#cbd5e1")
            style.configure("Vertical.TScrollbar", background="#cbd5e1")
            style.configure("TNotebook", background="#f1f5f9")
            style.configure("TNotebook.Tab", background="#e2e8f0", foreground="#1e293b")
            style.map("TNotebook.Tab", background=[("selected", "#ffffff")])

        # Update theme toggle switch visual state and background
        self._theme_toggle.set_state(self._is_dark)
        self._theme_toggle.configure(bg=TC["tb"])

        # Re-highlight the active mode button so it stays correct
        self._highlight_mode_button(
            next(
                (
                    b
                    for b in [
                        self._btn_select,
                        self._btn_draw,
                        self._btn_line,
                        self._btn_rect,
                        self._btn_circle,
                        self._btn_text,
                    ]
                    if b._is_active
                ),
                self._btn_select,
            )
        )

        # Keep grid/snap buttons in sync with current toggle state.
        # Always update internal resting/hover/press colours so that mouse
        # leave/hover work correctly after a theme switch, regardless of
        # whether the button is currently active (blue).
        self._btn_grid._bg = TC["btn"]
        self._btn_grid._hover_bg = TC["btn_hover"]
        self._btn_grid._press_bg = TC["btn_press"]
        if not self._btn_grid._is_active:
            self._btn_grid._set_bg(TC["btn"])
            self._btn_grid._lbl.configure(fg=TC["btn_fg"])
        self._btn_snap._bg = TC["btn"]
        self._btn_snap._hover_bg = TC["btn_hover"]
        self._btn_snap._press_bg = TC["btn_press"]
        if not self._btn_snap._is_active:
            self._btn_snap._set_bg(TC["btn"])
            self._btn_snap._lbl.configure(fg=TC["btn_fg"])

    def _set_status(self, msg):
        self._status.configure(text=msg)

    # -----------------------------------------------------------------------
    # Alignment functions
    # -----------------------------------------------------------------------
    def _get_all_objects(self):
        """Return all blocks and shapes."""
        return self._blocks + self._shapes

    def _get_selected_objects(self):
        """Return list of selected objects."""
        if len(self._selected_objects) > 0:
            return self._selected_objects
        objs = []
        if self._selected:
            objs.append(self._selected)
        if self._selected_shape:
            objs.append(self._selected_shape)
        return objs

    def _redraw_selected_handles(self):
        """Redraw handles for all selected objects to sync with their positions."""
        self._clear_all_handles()
        for obj in self._selected_objects:
            if isinstance(obj, PlotBlock):
                self._draw_handles(obj, clear_first=False)
            elif isinstance(obj, Shape):
                self._draw_handles_shape(obj, clear_first=False)
            elif isinstance(obj, TextObject):
                self._draw_handles_text(obj, clear_first=False)

    def _align_left(self):
        objs = self._get_selected_objects()
        if len(objs) < 2:
            self._set_status("Select at least 2 objects to align.")
            return
        if self._guide_object and self._guide_object in objs:
            anchor_obj = self._guide_object
        else:
            anchor_obj = min(objs, key=lambda o: o.x1)
        anchor_x = anchor_obj.x1
        for obj in objs:
            if obj is anchor_obj:
                continue
            w = obj.x2 - obj.x1
            obj.x1 = anchor_x
            obj.x2 = anchor_x + w
            self._update_object(obj)
        # Redraw handles for all selected objects
        self._redraw_selected_handles()
        self._set_status("Aligned left.")

    def _align_right(self):
        objs = self._get_selected_objects()
        if len(objs) < 2:
            self._set_status("Select at least 2 objects to align.")
            return
        if self._guide_object and self._guide_object in objs:
            anchor_obj = self._guide_object
        else:
            anchor_obj = max(objs, key=lambda o: o.x2)
        anchor_x = anchor_obj.x2
        for obj in objs:
            if obj is anchor_obj:
                continue
            w = obj.x2 - obj.x1
            obj.x2 = anchor_x
            obj.x1 = anchor_x - w
            self._update_object(obj)
        # Redraw handles for all selected objects
        self._redraw_selected_handles()
        self._set_status("Aligned right.")

    def _align_top(self):
        objs = self._get_selected_objects()
        if len(objs) < 2:
            self._set_status("Select at least 2 objects to align.")
            return
        if self._guide_object and self._guide_object in objs:
            anchor_obj = self._guide_object
        else:
            anchor_obj = min(objs, key=lambda o: o.y1)
        anchor_y = anchor_obj.y1
        for obj in objs:
            if obj is anchor_obj:
                continue
            h = obj.y2 - obj.y1
            obj.y1 = anchor_y
            obj.y2 = anchor_y + h
            self._update_object(obj)
        # Redraw handles for all selected objects
        self._redraw_selected_handles()
        self._set_status("Aligned top.")

    def _align_bottom(self):
        objs = self._get_selected_objects()
        if len(objs) < 2:
            self._set_status("Select at least 2 objects to align.")
            return
        if self._guide_object and self._guide_object in objs:
            anchor_obj = self._guide_object
        else:
            anchor_obj = max(objs, key=lambda o: o.y2)
        anchor_y = anchor_obj.y2
        for obj in objs:
            if obj is anchor_obj:
                continue
            h = obj.y2 - obj.y1
            obj.y2 = anchor_y
            obj.y1 = anchor_y - h
            self._update_object(obj)
        # Redraw handles for all selected objects
        self._redraw_selected_handles()
        self._set_status("Aligned bottom.")

    def _align_center(self):
        """Align x-centres of all selected objects (vertical axis), keeping y."""
        objs = self._get_selected_objects()
        if len(objs) < 2:
            self._set_status("Select at least 2 objects to align.")
            return
        if self._guide_object and self._guide_object in objs:
            anchor_obj = self._guide_object
        else:
            anchor_obj = objs[0]
        anchor_cx = (anchor_obj.x1 + anchor_obj.x2) / 2
        for obj in objs:
            if obj is anchor_obj:
                continue
            w = obj.x2 - obj.x1
            obj.x1 = anchor_cx - w / 2
            obj.x2 = anchor_cx + w / 2
            self._update_object(obj)
        # Redraw handles for all selected objects
        self._redraw_selected_handles()
        self._set_status("Aligned H.")

    def _align_middle(self):
        """Align y-centres of all selected objects (horizontal axis), keeping x."""
        objs = self._get_selected_objects()
        if len(objs) < 2:
            self._set_status("Select at least 2 objects to align.")
            return
        if self._guide_object and self._guide_object in objs:
            anchor_obj = self._guide_object
        else:
            anchor_obj = objs[0]
        anchor_cy = (anchor_obj.y1 + anchor_obj.y2) / 2
        for obj in objs:
            if obj is anchor_obj:
                continue
            h = obj.y2 - obj.y1
            obj.y1 = anchor_cy - h / 2
            obj.y2 = anchor_cy + h / 2
            self._update_object(obj)
        # Redraw handles for all selected objects
        self._redraw_selected_handles()
        self._set_status("Aligned V.")

    def _distribute_horizontal(self):
        """Evenly space selected objects horizontally; outermost objects stay fixed."""
        objs = self._get_selected_objects()
        if len(objs) < 3:
            self._set_status("Select at least 3 objects to distribute.")
            return
        objs_sorted = sorted(objs, key=lambda o: (o.x1 + o.x2) / 2)
        leftmost = objs_sorted[0]
        rightmost = objs_sorted[-1]
        inner = objs_sorted[1:-1]
        total_inner_width = sum(o.x2 - o.x1 for o in inner)
        available = rightmost.x1 - leftmost.x2
        spacing = (available - total_inner_width) / (len(inner) + 1)
        x_pos = leftmost.x2 + spacing
        for obj in inner:
            w = obj.x2 - obj.x1
            obj.x1 = x_pos
            obj.x2 = x_pos + w
            x_pos += w + spacing
            self._update_object(obj)
        self._redraw_selected_handles()
        self._set_status("Distributed horizontally.")

    def _distribute_vertical(self):
        """Evenly space selected objects vertically; outermost objects stay fixed."""
        objs = self._get_selected_objects()
        if len(objs) < 3:
            self._set_status("Select at least 3 objects to distribute.")
            return
        objs_sorted = sorted(objs, key=lambda o: (o.y1 + o.y2) / 2)
        topmost = objs_sorted[0]
        bottommost = objs_sorted[-1]
        inner = objs_sorted[1:-1]
        total_inner_height = sum(o.y2 - o.y1 for o in inner)
        available = bottommost.y1 - topmost.y2
        spacing = (available - total_inner_height) / (len(inner) + 1)
        y_pos = topmost.y2 + spacing
        for obj in inner:
            h = obj.y2 - obj.y1
            obj.y1 = y_pos
            obj.y2 = y_pos + h
            y_pos += h + spacing
            self._update_object(obj)
        self._redraw_selected_handles()
        self._set_status("Distributed vertically.")

    def _update_object(self, obj):
        """Update canvas position for a block or shape."""
        if isinstance(obj, PlotBlock):
            cx1, cy1 = self._to_canvas(obj.x1, obj.y1)
            cx2, cy2 = self._to_canvas(obj.x2, obj.y2)
            if obj.rect_id:
                self._cv.coords(obj.rect_id, cx1, cy1, cx2, cy2)
            if obj.image_id:
                self._cv.coords(obj.image_id, cx1, cy1)
            if obj.label_id:
                self._cv.coords(obj.label_id, (cx1 + cx2) / 2, (cy1 + cy2) / 2)
            if obj.df is not None:
                self._render_block(obj)
        elif isinstance(obj, Shape):
            self._draw_shape(obj)

    # -----------------------------------------------------------------------
    # Mouse events
    # -----------------------------------------------------------------------
    def _mouse_down(self, event):
        bx, by = self._ev_board(event)

        # Handle text mode click
        if self._mode == "add_text":
            # Check if we're in a drag (will start with small movement) or just a click
            bx, by = self._snap_pos(bx, by)
            self._drag_start = (bx, by)
            self._text_create_start = (
                bx,
                by,
            )  # Track initial click for single-click detection
            return

        if self._mode in ("draw", "draw_line", "draw_rect", "draw_circle"):
            bx, by = self._snap_pos(bx, by)
            self._drag_start = (bx, by)
            cx, cy = self._to_canvas(bx, by)
            if self._mode == "draw":
                self._rubber_rect = self._cv.create_rectangle(
                    cx,
                    cy,
                    cx,
                    cy,
                    outline="#2979FF",
                    width=2,
                    dash=(5, 3),
                    tags="rubber",
                )
            elif self._mode == "draw_line":
                self._rubber_rect = self._cv.create_line(
                    cx,
                    cy,
                    cx,
                    cy,
                    fill=self._shape_color,
                    width=self._shape_line_width,
                    tags="rubber",
                )
            elif self._mode == "draw_rect":
                self._rubber_rect = self._cv.create_rectangle(
                    cx,
                    cy,
                    cx,
                    cy,
                    outline=self._shape_color,
                    width=self._shape_line_width,
                    tags="rubber",
                )
            elif self._mode == "draw_circle":
                self._rubber_rect = self._cv.create_oval(
                    cx,
                    cy,
                    cx,
                    cy,
                    outline=self._shape_color,
                    width=self._shape_line_width,
                    tags="rubber",
                )
        else:
            cx = self._cv.canvasx(event.x)
            cy = self._cv.canvasy(event.y)
            # Check if clicking on a resize handle
            for item in self._cv.find_overlapping(cx - 6, cy - 6, cx + 6, cy + 6):
                tags = self._cv.gettags(item)
                if "resize_handle" in tags:
                    for tag in tags:
                        if tag in ("nw", "ne", "sw", "se"):
                            self._resize_corner = tag
                            # Handle resizing multiple selected objects or single object
                            if len(self._selected_objects) > 1:
                                # Multi-select resize: store all objects + group bbox
                                self._resize_all_objects = self._selected_objects[:]
                                self._resize_initial_dims = {
                                    id(obj): (obj.x1, obj.y1, obj.x2, obj.y2)
                                    for obj in self._selected_objects
                                }
                                # Store the overall group bounding box as the scale reference
                                all_x1 = min(obj.x1 for obj in self._selected_objects)
                                all_y1 = min(obj.y1 for obj in self._selected_objects)
                                all_x2 = max(obj.x2 for obj in self._selected_objects)
                                all_y2 = max(obj.y2 for obj in self._selected_objects)
                                self._resize_group_bbox = (
                                    all_x1,
                                    all_y1,
                                    all_x2,
                                    all_y2,
                                )
                                self._resize_block = None
                                self._resize_shape = None
                            elif self._selected:
                                # Single block resize
                                self._resize_block = self._selected
                                self._resize_shape = None
                                self._resize_all_objects = []
                                self._resize_orig_dims = (
                                    self._selected.x1,
                                    self._selected.y1,
                                    self._selected.x2,
                                    self._selected.y2,
                                )
                            elif self._selected_shape:
                                # Single shape resize
                                self._resize_shape = self._selected_shape
                                self._resize_block = None
                                self._resize_all_objects = []
                                self._resize_orig_dims = (
                                    self._selected_shape.x1,
                                    self._selected_shape.y1,
                                    self._selected_shape.x2,
                                    self._selected_shape.y2,
                                )
                            elif self._selected_text:
                                # Single text resize
                                self._resize_text = self._selected_text
                                self._resize_block = None
                                self._resize_shape = None
                                self._resize_all_objects = []
                                self._resize_orig_dims = (
                                    self._selected_text.x1,
                                    self._selected_text.y1,
                                    self._selected_text.x2,
                                    self._selected_text.y2,
                                )
                                self._resize_text_orig_font = (
                                    self._selected_text.font_size
                                )
                            return

            # Check if clicking inside a block, shape, or text
            block = self._block_at(bx, by)
            shape = self._shape_at(bx, by)
            text = self._text_at(bx, by)

            if block or shape or text:
                obj = block or shape or text

                # Check for Cmd/Ctrl or Shift modifier for multi-select
                if self._is_cmd_pressed(event) or self._is_shift_pressed(event):
                    # Cmd+Click or Shift+Click: Toggle selection
                    if obj in self._selected_objects:
                        self._selected_objects.remove(obj)
                        if isinstance(obj, PlotBlock):
                            self._unhighlight(obj)
                        elif isinstance(obj, Shape):
                            self._unhighlight_shape(obj)
                        # If down to 1 object, draw handles for it
                        if len(self._selected_objects) == 1:
                            remaining = self._selected_objects[0]
                            if isinstance(remaining, PlotBlock):
                                self._highlight(remaining)
                            elif isinstance(remaining, Shape):
                                self._highlight_shape(remaining)
                    else:
                        # When adding to selection, just append and highlight
                        self._selected_objects.append(obj)
                        if isinstance(obj, PlotBlock):
                            self._highlight(obj)
                        elif isinstance(obj, Shape):
                            self._highlight_shape(obj)
                    # Update single selection for compatibility
                    if block:
                        self._selected = block
                        self._selected_shape = None
                    else:
                        self._selected_shape = shape
                        self._selected = None
                else:
                    # Regular click: Select single object (or start drag-to-move)
                    # If clicking on already selected objects, prepare to drag multiple
                    if (
                        obj in self._selected_objects
                        and len(self._selected_objects) > 1
                    ):
                        # Promote to guide if this object is not already the guide
                        if obj is not self._guide_object:
                            self._set_guide(obj)
                            if block:
                                self._set_status(
                                    f"Plot {block.bid} set as alignment guide."
                                )
                            elif shape:
                                self._set_status(
                                    f"Shape {shape.sid} set as alignment guide."
                                )
                            elif text:
                                self._set_status(
                                    f"Text {text.tid} set as alignment guide."
                                )
                        # Dragging multiple objects - store initial positions
                        self._multi_drag_start = (bx, by)
                        self._multi_drag_initial = {
                            id(o): (o.x1, o.y1, o.x2, o.y2)
                            for o in self._selected_objects
                        }
                        if block:
                            self._drag_block = block
                        elif shape:
                            self._drag_shape = shape
                        elif text:
                            self._drag_text = text
                    else:
                        # Check if object is already the sole selected one before
                        # clearing selection, so we can promote it to guide
                        already_selected = obj in self._selected_objects
                        # Select single object - unhighlight previous multi-selection
                        for prev_obj in self._selected_objects:
                            if isinstance(prev_obj, PlotBlock):
                                self._unhighlight(prev_obj)
                            elif isinstance(prev_obj, Shape):
                                self._unhighlight_shape(prev_obj)
                            elif isinstance(prev_obj, TextObject):
                                self._unhighlight_text(prev_obj)
                        self._selected_objects = [obj]
                        if block:
                            self._drag_block = block
                            self._drag_offset = (bx - block.x1, by - block.y1)
                            self._select_block(block)
                        elif shape:
                            self._drag_shape = shape
                            self._drag_offset = (bx - shape.x1, by - shape.y1)
                            self._select_shape(shape)
                        elif text:
                            self._drag_text = text
                            self._drag_offset = (bx - text.x1, by - text.y1)
                            self._select_text(text)
                        # Second click on already-selected object → promote to guide
                        if already_selected and obj is not self._guide_object:
                            self._set_guide(obj)
                            if block:
                                self._set_status(
                                    f"Plot {block.bid} set as alignment guide."
                                )
                            elif shape:
                                self._set_status(
                                    f"Shape {shape.sid} set as alignment guide."
                                )
                            elif text:
                                self._set_status(
                                    f"Text {text.tid} set as alignment guide."
                                )
            else:
                # Clicking on empty space: start drag-to-select
                if not self._is_cmd_pressed(event):
                    # Unhighlight all previously selected objects
                    for prev_obj in self._selected_objects:
                        if isinstance(prev_obj, PlotBlock):
                            self._unhighlight(prev_obj)
                        elif isinstance(prev_obj, Shape):
                            self._unhighlight_shape(prev_obj)
                        elif isinstance(prev_obj, TextObject):
                            self._unhighlight_text(prev_obj)
                    # Clear guide object and its orange indicator
                    if self._guide_object is not None:
                        self._clear_guide_visual(self._guide_object)
                        self._guide_object = None
                    self._select_block(None)
                    self._select_shape(None)
                    self._select_text(None)
                    self._selected_objects = []
                    self._clear_all_handles()
                # Start selection box
                self._drag_start = (bx, by)
                cx, cy = self._to_canvas(bx, by)
                self._selection_rect = self._cv.create_rectangle(
                    cx,
                    cy,
                    cx,
                    cy,
                    outline="#2979FF",
                    width=2,
                    dash=(5, 3),
                    tags="selection_box",
                )

    def _mouse_drag(self, event):
        # Handle text mode with drag threshold
        if self._mode == "add_text" and self._drag_start:
            bx, by = self._ev_board(event)
            bx, by = self._snap_pos(bx, by)
            sx, sy = self._drag_start
            # Check if we've moved enough to start dragging (at least 10px)
            if abs(bx - sx) > 10 or abs(by - sy) > 10:
                # Start drawing drag rectangle
                if not self._rubber_rect:
                    cx0, cy0 = self._to_canvas(sx, sy)
                    cx1, cy1 = self._to_canvas(bx, by)
                    self._rubber_rect = self._cv.create_rectangle(
                        cx0,
                        cy0,
                        cx1,
                        cy1,
                        outline="#FF9800",
                        width=2,
                        dash=(5, 3),
                        tags="rubber",
                    )
                else:
                    cx0, cy0 = self._to_canvas(sx, sy)
                    cx1, cy1 = self._to_canvas(bx, by)
                    self._cv.coords(self._rubber_rect, cx0, cy0, cx1, cy1)
            return

        # Handle drag-to-select box (no snap — free selection)
        if (
            self._selection_rect
            and not self._drag_block
            and not self._drag_shape
            and not self._rubber_rect
        ):
            bx, by = self._ev_board(event)
            sx, sy = self._drag_start
            cx0, cy0 = self._to_canvas(sx, sy)
            cx1, cy1 = self._to_canvas(bx, by)
            self._cv.coords(self._selection_rect, cx0, cy0, cx1, cy1)
            return

        # Handle text box drag (rubber rectangle)
        if self._rubber_rect and self._mode == "add_text":
            bx, by = self._ev_board(event)
            bx, by = self._snap_pos(bx, by)
            sx, sy = self._drag_start
            cx0, cy0 = self._to_canvas(sx, sy)
            cx1, cy1 = self._to_canvas(bx, by)
            self._cv.coords(self._rubber_rect, cx0, cy0, cx1, cy1)
            return

        # Handle dragging multiple objects
        if len(self._selected_objects) > 1 and (self._drag_shape or self._drag_block):
            if not hasattr(self, "_multi_drag_start") or not hasattr(
                self, "_multi_drag_initial"
            ):
                return

            bx, by = self._ev_board(event)
            start_x, start_y = self._multi_drag_start
            dx = bx - start_x
            dy = by - start_y

            # Move all selected objects by delta from their initial positions
            for obj in self._selected_objects:
                initial = self._multi_drag_initial[id(obj)]
                x1, y1, x2, y2 = initial
                w = x2 - x1
                h = y2 - y1

                # Calculate new position
                obj.x1 = x1 + dx
                obj.y1 = y1 + dy
                obj.x2 = obj.x1 + w
                obj.y2 = obj.y1 + h

                # Constrain to bounds
                obj.x1 = max(0, min(obj.x1, A4_W - w))
                obj.y1 = max(0, min(obj.y1, A4_H - h))
                obj.x2 = obj.x1 + w
                obj.y2 = obj.y1 + h

                # Update canvas
                if isinstance(obj, PlotBlock):
                    cx1, cy1 = self._to_canvas(obj.x1, obj.y1)
                    cx2, cy2 = self._to_canvas(obj.x2, obj.y2)
                    if obj.rect_id:
                        self._cv.coords(obj.rect_id, cx1, cy1, cx2, cy2)
                    if obj.image_id:
                        self._cv.coords(obj.image_id, cx1, cy1)
                    if obj.label_id:
                        self._cv.coords(obj.label_id, (cx1 + cx2) / 2, (cy1 + cy2) / 2)
                elif isinstance(obj, Shape):
                    self._draw_shape(obj)

            # Redraw handles for all selected objects while dragging
            self._clear_all_handles()
            for obj in self._selected_objects:
                if isinstance(obj, PlotBlock):
                    self._draw_handles(obj, clear_first=False)
                elif isinstance(obj, Shape):
                    self._draw_handles_shape(obj, clear_first=False)
                elif isinstance(obj, TextObject):
                    self._draw_handles_text(obj, clear_first=False)
            return

        # Handle dragging a single shape to move it
        if self._drag_shape:
            bx, by = self._ev_board(event)
            s = self._drag_shape
            offset_x, offset_y = self._drag_offset

            # Calculate new position (snap top-left corner to grid)
            new_x1 = self._snap(bx - offset_x)
            new_y1 = self._snap(by - offset_y)
            w = s.x2 - s.x1
            h = s.y2 - s.y1

            # Constrain to artboard bounds
            new_x1 = max(0, min(new_x1, A4_W - w))
            new_y1 = max(0, min(new_y1, A4_H - h))

            # Update shape coordinates
            s.x1 = new_x1
            s.y1 = new_y1
            s.x2 = new_x1 + w
            s.y2 = new_y1 + h

            # Redraw shape
            self._draw_shape(s)
            self._draw_handles_shape(s)
            return

        # Handle dragging a single block to move it
        if self._drag_block:
            bx, by = self._ev_board(event)
            b = self._drag_block
            offset_x, offset_y = self._drag_offset

            # Calculate new position (snap top-left corner to grid)
            new_x1 = self._snap(bx - offset_x)
            new_y1 = self._snap(by - offset_y)
            w = b.x2 - b.x1
            h = b.y2 - b.y1

            # Constrain to artboard bounds
            new_x1 = max(0, min(new_x1, A4_W - w))
            new_y1 = max(0, min(new_y1, A4_H - h))

            # Update block coordinates
            b.x1 = new_x1
            b.y1 = new_y1
            b.x2 = new_x1 + w
            b.y2 = new_y1 + h

            # Update canvas items
            cx1, cy1 = self._to_canvas(b.x1, b.y1)
            cx2, cy2 = self._to_canvas(b.x2, b.y2)
            if b.rect_id:
                self._cv.coords(b.rect_id, cx1, cy1, cx2, cy2)
            if b.image_id:
                self._cv.coords(b.image_id, cx1, cy1)
            if b.label_id:
                self._cv.coords(b.label_id, (cx1 + cx2) / 2, (cy1 + cy2) / 2)
            self._draw_handles(b)
            return

        # Handle dragging a single text object to move it
        if self._drag_text:
            bx, by = self._ev_board(event)
            t = self._drag_text
            offset_x, offset_y = self._drag_offset

            # Calculate new position (snap top-left corner to grid)
            new_x1 = self._snap(bx - offset_x)
            new_y1 = self._snap(by - offset_y)
            w = t.x2 - t.x1
            h = t.y2 - t.y1

            # Constrain to artboard bounds
            new_x1 = max(0, min(new_x1, A4_W - w))
            new_y1 = max(0, min(new_y1, A4_H - h))

            # Update text coordinates
            t.x1 = new_x1
            t.y1 = new_y1
            t.x2 = new_x1 + w
            t.y2 = new_y1 + h

            # Update canvas
            self._draw_text(t)
            self._draw_handles_text(t)
            return

        # Handle resizing multiple selected objects
        if self._resize_corner and self._resize_all_objects:
            bx, by = self._ev_board(event)
            bx, by = self._snap_pos(bx, by)
            c = self._resize_corner

            # Use the overall group bounding box as the scale reference
            gx1, gy1, gx2, gy2 = self._resize_group_bbox
            gw = gx2 - gx1
            gh = gy2 - gy1

            # Compute scale from how the dragged corner has moved, relative to
            # the opposite (fixed) corner of the group bounding box.
            if c == "se":  # anchor = NW (gx1, gy1)
                scale_x = (bx - gx1) / gw if gw > 0 else 1
                scale_y = (by - gy1) / gh if gh > 0 else 1
            elif c == "sw":  # anchor = NE (gx2, gy1)
                scale_x = (gx2 - bx) / gw if gw > 0 else 1
                scale_y = (by - gy1) / gh if gh > 0 else 1
            elif c == "ne":  # anchor = SW (gx1, gy2)
                scale_x = (bx - gx1) / gw if gw > 0 else 1
                scale_y = (gy2 - by) / gh if gh > 0 else 1
            else:  # nw — anchor = SE (gx2, gy2)
                scale_x = (gx2 - bx) / gw if gw > 0 else 1
                scale_y = (gy2 - by) / gh if gh > 0 else 1

            # Prevent flipping
            scale_x = max(scale_x, 0.01)
            scale_y = max(scale_y, 0.01)

            # Apply Shift constraint (proportional scaling)
            if self._shift_pressed:
                avg_scale = (scale_x + scale_y) / 2
                scale_x = scale_y = avg_scale

            # Resize each object relative to the group anchor
            for obj in self._resize_all_objects:
                ix1, iy1, ix2, iy2 = self._resize_initial_dims[id(obj)]

                if c == "se":  # anchor = NW (gx1, gy1)
                    obj.x1 = gx1 + (ix1 - gx1) * scale_x
                    obj.x2 = gx1 + (ix2 - gx1) * scale_x
                    obj.y1 = gy1 + (iy1 - gy1) * scale_y
                    obj.y2 = gy1 + (iy2 - gy1) * scale_y
                elif c == "sw":  # anchor = NE (gx2, gy1)
                    obj.x1 = gx2 - (gx2 - ix1) * scale_x
                    obj.x2 = gx2 - (gx2 - ix2) * scale_x
                    obj.y1 = gy1 + (iy1 - gy1) * scale_y
                    obj.y2 = gy1 + (iy2 - gy1) * scale_y
                elif c == "ne":  # anchor = SW (gx1, gy2)
                    obj.x1 = gx1 + (ix1 - gx1) * scale_x
                    obj.x2 = gx1 + (ix2 - gx1) * scale_x
                    obj.y1 = gy2 - (gy2 - iy1) * scale_y
                    obj.y2 = gy2 - (gy2 - iy2) * scale_y
                else:  # nw — anchor = SE (gx2, gy2)
                    obj.x1 = gx2 - (gx2 - ix1) * scale_x
                    obj.x2 = gx2 - (gx2 - ix2) * scale_x
                    obj.y1 = gy2 - (gy2 - iy1) * scale_y
                    obj.y2 = gy2 - (gy2 - iy2) * scale_y

                # Enforce minimum size
                MIN = 20 if isinstance(obj, Shape) else 40
                if obj.x2 - obj.x1 < MIN:
                    obj.x2 = obj.x1 + MIN
                if obj.y2 - obj.y1 < MIN:
                    obj.y2 = obj.y1 + MIN

                # Update display
                if isinstance(obj, PlotBlock):
                    cx1, cy1 = self._to_canvas(obj.x1, obj.y1)
                    cx2, cy2 = self._to_canvas(obj.x2, obj.y2)
                    if obj.rect_id:
                        self._cv.coords(obj.rect_id, cx1, cy1, cx2, cy2)
                    if obj.image_id:
                        self._cv.coords(obj.image_id, cx1, cy1)
                    if obj.label_id:
                        self._cv.coords(obj.label_id, (cx1 + cx2) / 2, (cy1 + cy2) / 2)
                elif isinstance(obj, Shape):
                    self._draw_shape(obj)
                elif isinstance(obj, TextObject):
                    self._draw_text(obj)

            # Redraw handles for all selected
            self._clear_all_handles()
            for obj in self._resize_all_objects:
                if isinstance(obj, PlotBlock):
                    self._draw_handles(obj, clear_first=False)
                elif isinstance(obj, Shape):
                    self._draw_handles_shape(obj, clear_first=False)
                elif isinstance(obj, TextObject):
                    self._draw_handles_text(obj, clear_first=False)
            return

        # Handle resizing (blocks and shapes)
        if self._resize_corner and (self._resize_block or self._resize_shape):
            bx, by = self._ev_board(event)
            bx, by = self._snap_pos(bx, by)
            obj = self._resize_block if self._resize_block else self._resize_shape
            c = self._resize_corner
            MIN = 20 if self._resize_shape else 40

            # Special handling for lines
            if self._resize_shape and self._resize_shape.shape_type == "line":
                # For lines, determine which endpoint to move based on grabbed corner
                # The line has endpoints (x1,y1) and (x2,y2)
                # The corner names correspond to bounding box corners

                # Calculate which endpoint is closer to each corner
                corners_pos = {
                    "nw": (min(obj.x1, obj.x2), min(obj.y1, obj.y2)),
                    "ne": (max(obj.x1, obj.x2), min(obj.y1, obj.y2)),
                    "sw": (min(obj.x1, obj.x2), max(obj.y1, obj.y2)),
                    "se": (max(obj.x1, obj.x2), max(obj.y1, obj.y2)),
                }
                corner_x, corner_y = corners_pos[c]

                # Determine which endpoint is closer to the grabbed corner
                dist1 = (obj.x1 - corner_x) ** 2 + (obj.y1 - corner_y) ** 2
                dist2 = (obj.x2 - corner_x) ** 2 + (obj.y2 - corner_y) ** 2

                move_endpoint1 = (
                    dist1 <= dist2
                )  # True = move (x1,y1), False = move (x2,y2)

                # Get anchor point (the endpoint we're not moving)
                if move_endpoint1:
                    anchor_x, anchor_y = obj.x2, obj.y2
                else:
                    anchor_x, anchor_y = obj.x1, obj.y1

                # Apply Shift constraint for 45-degree angles
                if self._shift_pressed:
                    dx = bx - anchor_x
                    dy = by - anchor_y
                    angle = math.degrees(math.atan2(dy, dx)) % 360
                    snapped_angle = round(angle / 45) * 45
                    dist = math.sqrt(dx * dx + dy * dy)
                    rad = math.radians(snapped_angle)
                    bx = anchor_x + int(dist * math.cos(rad))
                    by = anchor_y + int(dist * math.sin(rad))

                # Update the endpoint
                if move_endpoint1:
                    obj.x1 = max(0, min(A4_W, bx))
                    obj.y1 = max(0, min(A4_H, by))
                else:
                    obj.x2 = max(0, min(A4_W, bx))
                    obj.y2 = max(0, min(A4_H, by))

                # Update display
                self._draw_shape(self._resize_shape)
                self._draw_handles_shape(self._resize_shape)
                return

            if self._shift_pressed and hasattr(self, "_resize_orig_dims"):
                # Proportional scaling from opposite corner
                ox1, oy1, ox2, oy2 = self._resize_orig_dims
                orig_w = ox2 - ox1
                orig_h = oy2 - oy1
                aspect = orig_w / orig_h if orig_h > 0 else 1

                # Determine which corner is being dragged and scale proportionally
                if c == "se":
                    new_w = max(MIN, bx - obj.x1)
                    new_h = new_w / aspect
                    obj.x2 = obj.x1 + new_w
                    obj.y2 = obj.y1 + new_h
                elif c == "sw":
                    new_w = max(MIN, obj.x2 - bx)
                    new_h = new_w / aspect
                    obj.x1 = obj.x2 - new_w
                    obj.y2 = obj.y1 + new_h
                elif c == "ne":
                    new_w = max(MIN, bx - obj.x1)
                    new_h = new_w / aspect
                    obj.x2 = obj.x1 + new_w
                    obj.y1 = obj.y2 - new_h
                elif c == "nw":
                    new_w = max(MIN, obj.x2 - bx)
                    new_h = new_w / aspect
                    obj.x1 = obj.x2 - new_w
                    obj.y1 = obj.y2 - new_h
            else:
                # Normal non-proportional resizing
                if "n" in c:
                    obj.y1 = max(0, min(by, obj.y2 - MIN))
                if "s" in c:
                    obj.y2 = min(A4_H, max(by, obj.y1 + MIN))
                if "w" in c:
                    obj.x1 = max(0, min(bx, obj.x2 - MIN))
                if "e" in c:
                    obj.x2 = min(A4_W, max(bx, obj.x1 + MIN))

            # Update display
            if self._resize_block:
                b = self._resize_block
                cx1, cy1 = self._to_canvas(b.x1, b.y1)
                cx2, cy2 = self._to_canvas(b.x2, b.y2)
                if b.rect_id:
                    self._cv.coords(b.rect_id, cx1, cy1, cx2, cy2)
                if b.image_id:
                    self._cv.coords(b.image_id, cx1, cy1)
                self._draw_handles(b)
            elif self._resize_shape:
                self._draw_shape(self._resize_shape)
                self._draw_handles_shape(self._resize_shape)
            return

        # Handle resizing text objects
        if self._resize_corner and self._resize_text:
            bx, by = self._ev_board(event)
            bx, by = self._snap_pos(bx, by)
            obj = self._resize_text
            c = self._resize_corner
            MIN = 20

            # Normal non-proportional resizing
            if "n" in c:
                obj.y1 = max(0, min(by, obj.y2 - MIN))
            if "s" in c:
                obj.y2 = min(A4_H, max(by, obj.y1 + MIN))
            if "w" in c:
                obj.x1 = max(0, min(bx, obj.x2 - MIN))
            if "e" in c:
                obj.x2 = min(A4_W, max(bx, obj.x1 + MIN))

            # Scale font size proportionally with the height change
            orig_dims = getattr(self, "_resize_orig_dims", None)
            orig_font = getattr(self, "_resize_text_orig_font", obj.font_size)
            if orig_dims:
                orig_h = orig_dims[3] - orig_dims[1]
                new_h = obj.y2 - obj.y1
                if orig_h > 0:
                    obj.font_size = max(6, round(orig_font * new_h / orig_h))

            # Update display
            self._draw_text(obj)
            self._draw_handles_text(obj)
            return

        # Handle drawing new box or shape
        if (
            self._mode in ("draw", "draw_line", "draw_rect", "draw_circle")
            and self._drag_start
        ):
            bx, by = self._ev_board(event)
            bx, by = self._snap_pos(bx, by)
            sx, sy = self._drag_start

            # Apply Shift constraints
            if self._shift_pressed:
                if self._mode == "draw_line":
                    # Snap line to 45-degree angles
                    dx = bx - sx
                    dy = by - sy
                    angle = math.degrees(math.atan2(dy, dx)) % 360
                    snapped_angle = round(angle / 45) * 45
                    dist = math.sqrt(dx * dx + dy * dy)
                    rad = math.radians(snapped_angle)
                    bx = sx + int(dist * math.cos(rad))
                    by = sy + int(dist * math.sin(rad))
                elif self._mode in ("draw_rect", "draw_circle"):
                    # Make square/circle (equal width and height)
                    dx = bx - sx
                    dy = by - sy
                    size = max(abs(dx), abs(dy))
                    bx = sx + (size if dx >= 0 else -size)
                    by = sy + (size if dy >= 0 else -size)

            cx0, cy0 = self._to_canvas(sx, sy)
            cx1, cy1 = self._to_canvas(bx, by)
            self._cv.coords(self._rubber_rect, cx0, cy0, cx1, cy1)
            return

    def _mouse_up(self, event):
        # Handle finishing a text box drag
        if self._mode == "add_text":
            bx, by = self._ev_board(event)
            bx, by = self._snap_pos(bx, by)
            sx, sy = self._drag_start

            # Check if we have a drag rectangle (user dragged)
            if self._rubber_rect:
                # User is dragging to create custom-sized text box
                self._cv.delete(self._rubber_rect)
                self._rubber_rect = None
                self._drag_start = None

                # Calculate text box dimensions
                x1, x2 = min(sx, bx), max(sx, bx)
                y1, y2 = min(sy, by), max(sy, by)

                # Require minimum size
                w, h = abs(bx - sx), abs(by - sy)
                if w < 20 or h < 20:
                    self._set_status(
                        "Text box too small — please drag at least 20 × 20 px."
                    )
                    return

                # Create text object and place entry widget on canvas
                self._save_state()
                text_obj = TextObject(x1, y1, "")
                text_obj.x2 = x2
                text_obj.y2 = y2
                self._texts.append(text_obj)

                # Edit on canvas
                self._edit_text_on_canvas(text_obj)
                self._set_status("Type text directly. Press Enter when done.")
            else:
                # User just clicked (no significant drag) - create default size box
                w, h = 80, 30  # Default text box size
                x1, y1 = sx, by
                x2, y2 = x1 + w, y1 + h

                # Constrain to board
                x2 = min(x2, A4_W)
                y2 = min(y2, A4_H)

                self._save_state()
                text_obj = TextObject(x1, y1, "")
                text_obj.x2 = x2
                text_obj.y2 = y2
                self._texts.append(text_obj)

                # Edit on canvas
                self._edit_text_on_canvas(text_obj)
                self._set_status("Type text. Press Enter when done.")
            self._drag_start = None
            return

        # Handle finishing a drag-to-select box
        if self._selection_rect:
            bx, by = self._ev_board(event)
            sx, sy = self._drag_start
            self._cv.delete(self._selection_rect)
            self._selection_rect = None
            self._drag_start = None

            # Find all objects within selection box
            x1, x2 = min(sx, bx), max(sx, bx)
            y1, y2 = min(sy, by), max(sy, by)

            selected = []
            for block in self._blocks:
                # Check if block center is within selection
                cx = (block.x1 + block.x2) / 2
                cy = (block.y1 + block.y2) / 2
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    selected.append(block)

            for shape in self._shapes:
                # Check if shape center is within selection
                cx = (shape.x1 + shape.x2) / 2
                cy = (shape.y1 + shape.y2) / 2
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    selected.append(shape)

            # Update selection
            if selected:
                if self._is_cmd_pressed(event):
                    # Add to existing selection
                    for obj in selected:
                        if obj not in self._selected_objects:
                            self._selected_objects.append(obj)
                else:
                    # Replace selection - unhighlight previous
                    for prev_obj in self._selected_objects:
                        if isinstance(prev_obj, PlotBlock):
                            self._unhighlight(prev_obj)
                        elif isinstance(prev_obj, Shape):
                            self._unhighlight_shape(prev_obj)
                    self._selected_objects = selected

                # Update visual feedback - highlight all selected objects
                self._clear_all_handles()
                for obj in self._selected_objects:
                    if isinstance(obj, PlotBlock):
                        self._highlight(obj)
                    elif isinstance(obj, Shape):
                        self._highlight_shape(obj)

                # Update single selection for compatibility
                if self._selected_objects:
                    obj = self._selected_objects[0]
                    if isinstance(obj, PlotBlock):
                        self._selected = obj
                        self._selected_shape = None
                    elif isinstance(obj, Shape):
                        self._selected_shape = obj
                        self._selected = None

                self._set_status(f"Selected {len(self._selected_objects)} object(s).")
            return

        # Handle finishing a shape drag
        if self._drag_shape:
            self._drag_shape = None
            self._drag_offset = (0, 0)
            # Clean up multi-drag state
            if hasattr(self, "_multi_drag_start"):
                del self._multi_drag_start
            if hasattr(self, "_multi_drag_initial"):
                del self._multi_drag_initial
            self._save_state()  # Save after moving shape
            return

        # Handle finishing a text drag
        if self._drag_text:
            self._drag_text = None
            self._drag_offset = (0, 0)
            # Clean up multi-drag state
            if hasattr(self, "_multi_drag_start"):
                del self._multi_drag_start
            if hasattr(self, "_multi_drag_initial"):
                del self._multi_drag_initial
            self._save_state()  # Save after moving text
            return

        # Handle finishing a block drag
        if self._drag_block:
            b = self._drag_block
            self._drag_block = None
            self._drag_offset = (0, 0)
            # Clean up multi-drag state
            if hasattr(self, "_multi_drag_start"):
                del self._multi_drag_start
            if hasattr(self, "_multi_drag_initial"):
                del self._multi_drag_initial
            self._save_state()  # Save after moving
            if b.df is not None:
                self._render_block(b)
            else:
                self._draw_handles(b)
            return

        # Handle finishing a multi-select resize
        if self._resize_corner and self._resize_all_objects:
            self._save_state()
            self._resize_corner = None
            self._resize_all_objects = []
            if hasattr(self, "_resize_group_bbox"):
                del self._resize_group_bbox
            if hasattr(self, "_resize_initial_dims"):
                self._resize_initial_dims = {}
            return

        # Handle finishing a resize
        if self._resize_corner and (
            self._resize_block or self._resize_shape or self._resize_text
        ):
            if self._resize_block:
                b = self._resize_block
                self._resize_block = None
                self._resize_corner = None
                if hasattr(self, "_resize_orig_dims"):
                    del self._resize_orig_dims
                if hasattr(self, "_resize_shape"):
                    self._resize_shape = None
                self._save_state()
                if b.df is not None:
                    self._render_block(b)
                else:
                    self._draw_handles(b)
                # Refresh size fields in panel
                self._aes.load_block(b)
            elif self._resize_shape:
                s = self._resize_shape
                self._resize_shape = None
                self._resize_corner = None
                if hasattr(self, "_resize_orig_dims"):
                    del self._resize_orig_dims
                if hasattr(self, "_resize_block"):
                    self._resize_block = None
                self._save_state()
                self._draw_shape(s)
                self._draw_handles_shape(s)
                # Refresh size fields in panel
                self._aes.load_shape(s, self._draw_shape)
            elif self._resize_text:
                t = self._resize_text
                self._resize_text = None
                self._resize_corner = None
                if hasattr(self, "_resize_orig_dims"):
                    del self._resize_orig_dims
                self._save_state()
                self._draw_text(t)
                self._draw_handles_text(t)
                # Refresh size fields in panel
                self._aes.load_text(t, self._draw_text)
            return

        # Handle finishing drawing a new box or shape
        if self._drag_start:
            bx, by = self._ev_board(event)
            bx, by = self._snap_pos(bx, by)
            sx, sy = self._drag_start
            self._drag_start = None
            if self._rubber_rect:
                self._cv.delete(self._rubber_rect)
                self._rubber_rect = None

            # Apply Shift constraints (same as in _mouse_drag)
            if self._shift_pressed:
                if self._mode == "draw_line":
                    # Snap line to 45-degree angles
                    dx = bx - sx
                    dy = by - sy
                    angle = math.degrees(math.atan2(dy, dx)) % 360
                    snapped_angle = round(angle / 45) * 45
                    dist = math.sqrt(dx * dx + dy * dy)
                    rad = math.radians(snapped_angle)
                    bx = sx + int(dist * math.cos(rad))
                    by = sy + int(dist * math.sin(rad))
                elif self._mode in ("draw_rect", "draw_circle"):
                    # Make square/circle (equal width and height)
                    dx = bx - sx
                    dy = by - sy
                    size = max(abs(dx), abs(dy))
                    bx = sx + (size if dx >= 0 else -size)
                    by = sy + (size if dy >= 0 else -size)

            # For lines, check distance; for shapes, check width/height
            if self._mode == "draw_line":
                dist = math.sqrt((bx - sx) ** 2 + (by - sy) ** 2)
                if dist < 10:
                    self._set_status("Line too short — please drag at least 10 px.")
                    return
            else:
                w, h = abs(bx - sx), abs(by - sy)
                if w < 10 or h < 10:
                    self._set_status(
                        "Shape too small — please drag at least 10 × 10 px."
                    )
                    return

            x1, x2 = min(sx, bx), max(sx, bx)
            y1, y2 = min(sy, by), max(sy, by)

            if self._mode == "draw":
                if w < 30 or h < 30:
                    self._set_status("Box too small — please drag at least 30 × 30 px.")
                    return
                self._save_state()  # Save before creating
                block = PlotBlock(x1, y1, x2, y2)
                self._blocks.append(block)
                self._draw_empty_block(block)
                self._open_config(block, is_edit=False)
            elif self._mode == "draw_line":
                self._save_state()  # Save before creating
                shape = Shape(sx, sy, bx, by, "line")
                shape.color = self._shape_color
                shape.line_width = self._shape_line_width
                self._shapes.append(shape)
                self._draw_shape(shape)
                self._select_shape(shape)
                self._mode_select()
            elif self._mode == "draw_rect":
                self._save_state()  # Save before creating
                shape = Shape(x1, y1, x2, y2, "rectangle")
                shape.color = self._shape_color
                shape.line_width = self._shape_line_width
                self._shapes.append(shape)
                self._draw_shape(shape)
                self._select_shape(shape)
                self._mode_select()
            elif self._mode == "draw_circle":
                self._save_state()  # Save before creating
                shape = Shape(x1, y1, x2, y2, "circle")
                shape.color = self._shape_color
                shape.line_width = self._shape_line_width
                self._shapes.append(shape)
                self._draw_shape(shape)
                self._select_shape(shape)
                self._mode_select()
            return

    def _mouse_dbl(self, event):
        bx, by = self._ev_board(event)
        hit_block = self._block_at(bx, by)
        hit_shape = self._shape_at(bx, by)
        hit_text = self._text_at(bx, by)

        if hit_block:
            if self._mode == "select":
                if hit_block is self._guide_object:
                    # Toggle off: demote back to just selected (handles only)
                    self._clear_guide_visual(hit_block)
                    self._guide_object = None
                    self._set_status(f"Plot {hit_block.bid} guide cleared.")
                else:
                    self._set_guide(hit_block)
                    self._set_status(f"Plot {hit_block.bid} set as alignment guide.")
            else:
                self._open_config(hit_block, is_edit=True)
        elif hit_shape:
            if hit_shape is self._guide_object:
                self._clear_guide_visual(hit_shape)
                self._guide_object = None
                self._set_status(f"Shape {hit_shape.sid} guide cleared.")
            else:
                self._set_guide(hit_shape)
                self._set_status(f"Shape {hit_shape.sid} set as alignment guide.")
        elif hit_text:
            # Open text editing dialog
            self._edit_text(hit_text)

    def _mouse_motion(self, event):
        """Update cursor based on what's under the mouse."""
        if self._mode == "draw":
            self._cv.configure(cursor="crosshair")
            return

        cx = self._cv.canvasx(event.x)
        cy = self._cv.canvasy(event.y)

        # Check if hovering over a resize handle
        for item in self._cv.find_overlapping(cx - 2, cy - 2, cx + 2, cy + 2):
            tags = self._cv.gettags(item)
            if "resize_handle" in tags:
                for tag in tags:
                    if tag == "nw":
                        self._cv.configure(cursor="top_left_corner")
                        return
                    elif tag == "ne":
                        self._cv.configure(cursor="top_right_corner")
                        return
                    elif tag == "sw":
                        self._cv.configure(cursor="bottom_left_corner")
                        return
                    elif tag == "se":
                        self._cv.configure(cursor="bottom_right_corner")
                        return

        # Check if hovering over a block or shape (for moving)
        bx, by = self._ev_board(event)
        if self._block_at(bx, by, pad=HOVER_PAD) or self._shape_at(
            bx, by, pad=HOVER_PAD
        ):
            self._cv.configure(cursor="fleur")  # move cursor
        else:
            self._cv.configure(cursor="arrow")

    # -----------------------------------------------------------------------
    # Block drawing
    # -----------------------------------------------------------------------
    def _draw_empty_block(self, block: PlotBlock):
        cx1, cy1 = self._to_canvas(block.x1, block.y1)
        cx2, cy2 = self._to_canvas(block.x2, block.y2)
        block.rect_id = self._cv.create_rectangle(
            cx1,
            cy1,
            cx2,
            cy2,
            outline="#2979FF",
            width=2,
            dash=(6, 3),
            fill="",
            tags=(f"blk{block.bid}", "block"),
        )
        block.label_id = self._cv.create_text(
            (cx1 + cx2) / 2,
            (cy1 + cy2) / 2,
            text=f"Plot {block.bid}\n(tap to configure)",
            fill="#777",
            font=("", 10),
            justify="center",
            tags=(f"blk{block.bid}", "block"),
        )

    def _render_block(self, block: PlotBlock):
        try:
            fig = PlotRenderer.render(block)
        except Exception as exc:
            messagebox.showerror("Render error", str(exc), parent=self.root)
            return

        _, _, pil_img = fig_to_photoimage(fig)
        plt.close(fig)

        cx1, cy1 = self._to_canvas(block.x1, block.y1)
        cx2, cy2 = self._to_canvas(block.x2, block.y2)

        # Scale image to exactly fill the block's canvas area (fixes bbox_inches mismatch)
        target_w = max(1, int(cx2 - cx1))
        target_h = max(1, int(cy2 - cy1))
        if pil_img.size != (target_w, target_h):
            pil_img = pil_img.resize((target_w, target_h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(pil_img)

        if block.image_id:
            self._cv.delete(block.image_id)
        if block.label_id:
            self._cv.delete(block.label_id)
            block.label_id = None

        if block.rect_id:
            self._cv.coords(block.rect_id, cx1, cy1, cx2, cy2)
            # Hide outline by default - will be shown if selected
            self._cv.itemconfig(block.rect_id, outline="", dash=(), width=0)

        block._photo = photo
        block._pil_img = pil_img
        block.image_id = self._cv.create_image(
            cx1, cy1, anchor="nw", image=photo, tags=(f"blk{block.bid}", "block")
        )

        if block.rect_id:
            self._cv.tag_raise(block.rect_id)
        if self._selected == block:
            self._highlight(block)

        self._set_status(
            f"Plot {block.bid} rendered · {block.width_px}×{block.height_px} px"
        )

    # -----------------------------------------------------------------------
    # Selection highlight
    # -----------------------------------------------------------------------
    def _clear_guide_visual(self, obj):
        """Remove the orange guide indicator from an object."""
        if isinstance(obj, PlotBlock):
            if obj.rect_id:
                self._cv.itemconfig(obj.rect_id, outline="", width=0, dash=())
        elif isinstance(obj, Shape):
            if obj.item_id:
                try:
                    if obj.shape_type == "line":
                        self._cv.itemconfig(
                            obj.item_id, width=obj.line_width, fill=obj.color
                        )
                    else:
                        self._cv.itemconfig(
                            obj.item_id, width=obj.line_width, outline=obj.color
                        )
                except tk.TclError:
                    pass
        elif isinstance(obj, TextObject):
            if obj.item_id:
                try:
                    self._cv.itemconfig(obj.item_id, fill=obj.color)
                except tk.TclError:
                    pass

    def _set_guide(self, obj):
        """Set obj as the alignment guide and apply the orange visual indicator."""
        if self._guide_object is not None and self._guide_object is not obj:
            self._clear_guide_visual(self._guide_object)
        self._guide_object = obj
        if isinstance(obj, PlotBlock):
            if obj.rect_id:
                self._cv.itemconfig(obj.rect_id, outline="#FF6D00", width=3, dash=())
        elif isinstance(obj, Shape):
            if obj.item_id:
                try:
                    if obj.shape_type == "line":
                        self._cv.itemconfig(
                            obj.item_id, width=obj.line_width + 2, fill="#FF6D00"
                        )
                    else:
                        self._cv.itemconfig(
                            obj.item_id, width=obj.line_width + 2, outline="#FF6D00"
                        )
                except tk.TclError:
                    pass
        elif isinstance(obj, TextObject):
            if obj.item_id:
                try:
                    self._cv.itemconfig(obj.item_id, fill="#FF6D00")
                except tk.TclError:
                    pass

    def _highlight(self, block: PlotBlock):
        if block.rect_id and block is self._guide_object:
            # Show orange outline only for the guide object
            self._cv.itemconfig(block.rect_id, outline="#FF6D00", width=3, dash=())
        # Draw handles for all selected objects
        self._draw_handles(block, clear_first=False)

    def _unhighlight(self, block: PlotBlock):
        if block.rect_id:
            # Hide outline when not selected
            self._cv.itemconfig(block.rect_id, outline="", width=0, dash=())
        # Don't clear handles here if other objects are selected
        if block not in self._selected_objects:
            for h in self._resize_handles:
                try:
                    self._cv.delete(h)
                except:
                    pass

    def _draw_handles(self, block: PlotBlock, clear_first=True):
        if clear_first:
            self._clear_handles()
        HS = 5
        corners = {
            "nw": (block.x1, block.y1),
            "ne": (block.x2, block.y1),
            "sw": (block.x1, block.y2),
            "se": (block.x2, block.y2),
        }
        for name, (bx, by) in corners.items():
            cx, cy = self._to_canvas(bx, by)
            h = self._cv.create_rectangle(
                cx - HS,
                cy - HS,
                cx + HS,
                cy + HS,
                fill="white",
                outline="#FF6D00",
                width=2,
                tags=("resize_handle", name),
            )
            self._resize_handles.append(h)

    def _clear_handles(self):
        for h in self._resize_handles:
            self._cv.delete(h)
        self._resize_handles = []

    def _clear_all_handles(self):
        """Clear all resize handles (for multi-select)."""
        self._clear_handles()

    def _select_all(self):
        """Select all blocks and shapes."""
        self._selected_objects = self._blocks + self._shapes
        self._clear_all_handles()
        for obj in self._selected_objects:
            if isinstance(obj, PlotBlock):
                self._highlight(obj)
            elif isinstance(obj, Shape):
                self._highlight_shape(obj)
        if self._selected_objects:
            self._set_status(f"Selected all {len(self._selected_objects)} objects.")
        else:
            self._set_status("No objects to select.")

    def _select_block(self, block):
        # Clear any existing shape or text selection when selecting a block
        if self._selected_shape:
            self._unhighlight_shape(self._selected_shape)
            self._selected_shape = None
        if self._selected_text:
            self._unhighlight_text(self._selected_text)
            self._selected_text = None

        if self._selected and self._selected != block:
            self._unhighlight(self._selected)
        self._selected = block
        if block:
            self._highlight(block)
            self._aes.load_block(block)
            self._set_status(
                f"Selected Plot {block.bid} · double-click to reconfigure data / type."
            )
        else:
            self._aes.clear()
            self._set_status("No block selected.")

    # -----------------------------------------------------------------------
    # Dialogs
    # -----------------------------------------------------------------------
    def _open_config(self, block: PlotBlock, is_edit: bool):
        dlg = PlotConfigDialog(self.root, block, is_edit=is_edit)
        self.root.wait_window(dlg)
        if dlg.result:
            self._save_state()  # Save after configuring plot
            self._render_block(block)
            self._select_block(block)
            self._mode_select()

    def _edit_selected(self):
        if not self._selected:
            self._set_status(
                "Nothing selected — switch to Select mode and click a block first."
            )
            return
        self._open_config(self._selected, is_edit=True)

    def _delete_selected(self):
        # Delete selected plot block (with confirmation)
        if self._selected:
            b = self._selected
            if not messagebox.askyesno(
                "Delete block", f"Remove Plot {b.bid}?", parent=self.root
            ):
                return
            self._save_state()
            for item in (b.rect_id, b.image_id, b.label_id):
                if item:
                    self._cv.delete(item)
            self._blocks.remove(b)
            if self._guide_object is b:
                self._guide_object = None
            self._selected = None
            self._aes.clear()
            self._set_status("Block deleted.")
            return

        # Delete selected shape (with confirmation)
        if self._selected_shape:
            s = self._selected_shape
            if not messagebox.askyesno(
                "Delete shape", f"Remove Shape {s.sid}?", parent=self.root
            ):
                return
            self._save_state()
            if s.item_id:
                self._cv.delete(s.item_id)
            self._shapes.remove(s)
            if self._guide_object is s:
                self._guide_object = None
            self._selected_shape = None
            self._aes.clear_shape_properties()
            self._clear_handles()
            self._set_status("Shape deleted.")
            return

        # Delete selected text object (with confirmation)
        if self._selected_text:
            t = self._selected_text
            if not messagebox.askyesno(
                "Delete text", f"Remove Text {t.tid}?", parent=self.root
            ):
                return
            self._save_state()
            if t.item_id:
                self._cv.delete(t.item_id)
            self._texts.remove(t)
            if self._guide_object is t:
                self._guide_object = None
            self._selected_text = None
            self._aes.clear_shape_properties()
            self._clear_handles()
            self._set_status("Text deleted.")
            return

        self._set_status("Nothing selected to delete.")

    def _delete_key(self):
        """Delete key handler - no confirmation dialog."""
        # Delete multiple selected objects
        if len(self._selected_objects) > 1:
            self._save_state()
            if self._guide_object in self._selected_objects:
                self._guide_object = None
            for obj in self._selected_objects:
                if isinstance(obj, PlotBlock):
                    for item in (obj.rect_id, obj.image_id, obj.label_id):
                        if item:
                            self._cv.delete(item)
                    self._blocks.remove(obj)
                elif isinstance(obj, Shape):
                    if obj.item_id:
                        self._cv.delete(obj.item_id)
                    self._shapes.remove(obj)
                elif isinstance(obj, TextObject):
                    if obj.item_id:
                        self._cv.delete(obj.item_id)
                    self._texts.remove(obj)
            count = len(self._selected_objects)
            self._selected_objects = []
            self._selected = None
            self._selected_shape = None
            self._selected_text = None
            self._aes.clear()
            self._aes.clear_shape_properties()
            self._clear_all_handles()
            self._set_status(f"{count} objects deleted (Undo with Cmd+Z).")
            return

        # Delete selected plot block
        if self._selected:
            self._save_state()
            b = self._selected
            for item in (b.rect_id, b.image_id, b.label_id):
                if item:
                    self._cv.delete(item)
            self._blocks.remove(b)
            self._selected = None
            self._selected_objects = []
            self._aes.clear()
            self._set_status("Block deleted (Undo with Cmd+Z).")
            return

        # Delete selected shape
        if self._selected_shape:
            self._save_state()
            s = self._selected_shape
            if s.item_id:
                self._cv.delete(s.item_id)
            self._shapes.remove(s)
            self._selected_shape = None
            self._selected_objects = []
            self._aes.clear_shape_properties()
            self._clear_handles()
            self._set_status("Shape deleted (Undo with Cmd+Z).")
            return

        # Delete selected text
        if self._selected_text:
            self._save_state()
            t = self._selected_text
            if t.item_id:
                self._cv.delete(t.item_id)
            self._texts.remove(t)
            self._selected_text = None
            self._selected_objects = []
            self._aes.clear_shape_properties()
            self._clear_handles()
            self._set_status("Text deleted (Undo with Cmd+Z).")
            return

    # -----------------------------------------------------------------------
    # Undo/Redo System
    # -----------------------------------------------------------------------
    def _save_state(self):
        """Save current state for undo."""
        state = {
            "blocks": copy.deepcopy(self._blocks),
            "shapes": copy.deepcopy(self._shapes),
            "texts": copy.deepcopy(self._texts),
        }
        self._undo_stack.append(state)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self):
        """Undo the last action."""
        if not self._undo_stack:
            self._set_status("Nothing to undo.")
            return

        # Save current state to redo stack
        current_state = {
            "blocks": copy.deepcopy(self._blocks),
            "shapes": copy.deepcopy(self._shapes),
            "texts": copy.deepcopy(self._texts),
        }
        self._redo_stack.append(current_state)

        # Restore previous state
        state = self._undo_stack.pop()
        self._blocks = copy.deepcopy(state["blocks"])
        self._shapes = copy.deepcopy(state["shapes"])
        self._texts = copy.deepcopy(state.get("texts", []))

        # Clear selections
        self._selected = None
        self._selected_shape = None
        self._selected_text = None
        self._selected_objects = []
        self._aes.clear()
        self._aes.clear_shape_properties()

        # Redraw everything
        self._redraw_all()
        self._set_status("Undo successful.")

    def _redo(self):
        """Redo the last undone action."""
        if not self._redo_stack:
            self._set_status("Nothing to redo.")
            return

        # Save current state to undo stack
        current_state = {
            "blocks": copy.deepcopy(self._blocks),
            "shapes": copy.deepcopy(self._shapes),
            "texts": copy.deepcopy(self._texts),
        }
        self._undo_stack.append(current_state)

        # Restore redo state
        state = self._redo_stack.pop()
        self._blocks = copy.deepcopy(state["blocks"])
        self._shapes = copy.deepcopy(state["shapes"])
        self._texts = copy.deepcopy(state.get("texts", []))

        # Clear selections
        self._selected = None
        self._selected_shape = None
        self._selected_text = None
        self._selected_objects = []
        self._aes.clear()
        self._aes.clear_shape_properties()

        # Redraw everything
        self._redraw_all()
        self._set_status("Redo successful.")

    def _redraw_all(self):
        """Redraw all blocks and shapes after undo/redo."""
        # Clear canvas except background
        for item in self._cv.find_all():
            tags = self._cv.gettags(item)
            if "bg" not in tags and "artboard" not in tags and "ruler" not in tags:
                self._cv.delete(item)

        # Reset IDs
        for block in self._blocks:
            block.rect_id = None
            block.image_id = None
            block.label_id = None
            block._pil_img = None

        for shape in self._shapes:
            shape.item_id = None

        for text in self._texts:
            text.item_id = None

        # Redraw blocks
        for block in self._blocks:
            if block.df is not None:
                self._render_block(block)
            else:
                self._draw_empty_block(block)

        # Redraw shapes
        for shape in self._shapes:
            self._draw_shape(shape)

        # Redraw texts
        for text in self._texts:
            self._draw_text(text)

    # -----------------------------------------------------------------------
    # Copy/Paste System
    # -----------------------------------------------------------------------
    def _copy(self):
        """Copy selected object(s) to clipboard."""
        if len(self._selected_objects) > 1:
            self._clipboard = copy.deepcopy(self._selected_objects)
            self._set_status(
                f"{len(self._selected_objects)} objects copied to clipboard."
            )
        elif self._selected:
            self._clipboard = copy.deepcopy(self._selected)
            self._set_status(f"Plot {self._selected.bid} copied to clipboard.")
        elif self._selected_shape:
            self._clipboard = copy.deepcopy(self._selected_shape)
            self._set_status(f"Shape {self._selected_shape.sid} copied to clipboard.")
        else:
            self._set_status("Nothing selected to copy.")

    def _cut(self):
        """Cut selected object(s) to clipboard."""
        if len(self._selected_objects) > 1:
            self._clipboard = copy.deepcopy(self._selected_objects)
            self._save_state()
            for obj in self._selected_objects:
                if isinstance(obj, PlotBlock):
                    for item in (obj.rect_id, obj.image_id, obj.label_id):
                        if item:
                            self._cv.delete(item)
                    self._blocks.remove(obj)
                elif isinstance(obj, Shape):
                    if obj.item_id:
                        self._cv.delete(obj.item_id)
                    self._shapes.remove(obj)
            count = len(self._selected_objects)
            self._selected_objects = []
            self._selected = None
            self._selected_shape = None
            self._aes.clear()
            self._aes.clear_shape_properties()
            self._clear_all_handles()
            self._set_status(f"{count} objects cut to clipboard (Paste with Cmd+V).")
        elif self._selected:
            self._clipboard = copy.deepcopy(self._selected)
            self._save_state()
            b = self._selected
            for item in (b.rect_id, b.image_id, b.label_id):
                if item:
                    self._cv.delete(item)
            self._blocks.remove(b)
            self._selected = None
            self._aes.clear()
            self._set_status(f"Plot cut to clipboard (Paste with Cmd+V).")
        elif self._selected_shape:
            self._clipboard = copy.deepcopy(self._selected_shape)
            self._save_state()
            s = self._selected_shape
            if s.item_id:
                self._cv.delete(s.item_id)
            self._shapes.remove(s)
            self._selected_shape = None
            self._aes.clear_shape_properties()
            self._clear_handles()
            self._set_status(f"Shape cut to clipboard (Paste with Cmd+V).")
        else:
            self._set_status("Nothing selected to cut.")

    def _paste(self):
        """Paste object(s) from clipboard."""
        if self._clipboard is None:
            self._set_status("Clipboard is empty.")
            return

        self._save_state()

        # Offset to avoid overlapping with original
        offset = 20

        # Handle multiple objects
        if isinstance(self._clipboard, list):
            pasted_objects = []
            for item in self._clipboard:
                if isinstance(item, PlotBlock):
                    block = copy.deepcopy(item)
                    block.x1 += offset
                    block.y1 += offset
                    block.x2 += offset
                    block.y2 += offset

                    # Keep within bounds
                    if block.x2 > A4_W:
                        block.x1 -= block.x2 - A4_W
                        block.x2 = A4_W
                    if block.y2 > A4_H:
                        block.y1 -= block.y2 - A4_H
                        block.y2 = A4_H

                    # Clear IDs so new canvas items are created
                    block.rect_id = None
                    block.image_id = None
                    block.label_id = None
                    block._pil_img = None

                    self._blocks.append(block)

                    if block.df is not None:
                        self._render_block(block)
                    else:
                        self._draw_empty_block(block)

                    pasted_objects.append(block)

                elif isinstance(item, Shape):
                    shape = copy.deepcopy(item)
                    shape.x1 += offset
                    shape.y1 += offset
                    shape.x2 += offset
                    shape.y2 += offset

                    # Keep within bounds
                    if shape.x2 > A4_W:
                        shape.x1 -= shape.x2 - A4_W
                        shape.x2 = A4_W
                    if shape.y2 > A4_H:
                        shape.y1 -= shape.y2 - A4_H
                        shape.y2 = A4_H

                    # Clear ID so new canvas item is created
                    shape.item_id = None

                    self._shapes.append(shape)
                    self._draw_shape(shape)
                    pasted_objects.append(shape)

            # Select pasted objects
            self._selected_objects = pasted_objects
            self._clear_all_handles()
            for obj in pasted_objects:
                if isinstance(obj, PlotBlock):
                    self._draw_handles(obj)
                elif isinstance(obj, Shape):
                    self._draw_handles_shape(obj)

            self._set_status(f"{len(pasted_objects)} objects pasted.")
            return

        if isinstance(self._clipboard, PlotBlock):
            block = copy.deepcopy(self._clipboard)
            block.x1 += offset
            block.y1 += offset
            block.x2 += offset
            block.y2 += offset

            # Keep within bounds
            if block.x2 > A4_W:
                block.x1 -= block.x2 - A4_W
                block.x2 = A4_W
            if block.y2 > A4_H:
                block.y1 -= block.y2 - A4_H
                block.y2 = A4_H

            # Clear IDs so new canvas items are created
            block.rect_id = None
            block.image_id = None
            block.label_id = None
            block._pil_img = None

            self._blocks.append(block)

            if block.df is not None:
                self._render_block(block)
            else:
                self._draw_empty_block(block)

            self._select_block(block)
            self._set_status(f"Plot pasted.")

        elif isinstance(self._clipboard, Shape):
            shape = copy.deepcopy(self._clipboard)
            shape.x1 += offset
            shape.y1 += offset
            shape.x2 += offset
            shape.y2 += offset

            # Keep within bounds
            if shape.x2 > A4_W:
                shape.x1 -= shape.x2 - A4_W
                shape.x2 = A4_W
            if shape.y2 > A4_H:
                shape.y1 -= shape.y2 - A4_H
                shape.y2 = A4_H

            # Clear ID so new canvas item is created
            shape.item_id = None

            self._shapes.append(shape)
            self._draw_shape(shape)
            self._select_shape(shape)
            self._set_status(f"Shape pasted.")

    def _on_aes_update(self, block: PlotBlock):
        if block.df is not None:
            self._render_block(block)
        else:
            # Update canvas items for empty blocks (no data yet)
            cx1, cy1 = self._to_canvas(block.x1, block.y1)
            cx2, cy2 = self._to_canvas(block.x2, block.y2)
            if block.rect_id:
                self._cv.coords(block.rect_id, cx1, cy1, cx2, cy2)
            if block.label_id:
                self._cv.coords(block.label_id, (cx1 + cx2) / 2, (cy1 + cy2) / 2)
        # Refresh selection handles whenever the block changes size
        if self._selected == block:
            self._clear_handles()
            self._draw_handles(block)

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    def _export_png(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")],
            title="Save artboard as PNG",
            initialfile="figure.png",
            parent=self.root,
        )
        if not path:
            return
        # Ensure .png extension
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            canvas_img = Image.new("RGB", (A4_W, A4_H), "white")
            for block in self._blocks:
                if block._pil_img is None:
                    continue
                img = block._pil_img.convert("RGBA")
                canvas_img.paste(img, (int(block.x1), int(block.y1)), img.split()[3])
            canvas_img.save(path, dpi=(DPI, DPI))
        except Exception as exc:
            messagebox.showerror("Export error", str(exc), parent=self.root)

    def _export_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF document", "*.pdf"), ("All files", "*.*")],
            title="Save artboard as PDF",
            initialfile="figure.pdf",
            parent=self.root,
        )
        if not path:
            return
        # Ensure .pdf extension
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self._export_vector(path, "pdf")
        except Exception as exc:
            messagebox.showerror("Export error", str(exc), parent=self.root)

    def _export_svg(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("SVG vector", "*.svg"), ("All files", "*.*")],
            title="Save artboard as SVG",
            initialfile="figure.svg",
            parent=self.root,
        )
        if not path:
            return
        # Ensure .svg extension
        if not path.lower().endswith(".svg"):
            path += ".svg"
        try:
            self._export_vector(path, "svg")
        except Exception as exc:
            messagebox.showerror("Export error", str(exc), parent=self.root)

    def _export_vector(self, path, fmt):
        """Export artboard as PDF or SVG using matplotlib."""
        if not self._blocks:
            raise ValueError("No plots to export")

        # Create a figure matching A4 size
        fig = Figure(figsize=(A4_W / DPI, A4_H / DPI), dpi=DPI)
        fig.patch.set_facecolor("white")

        # Render each block onto the figure
        for block in self._blocks:
            if block.df is None or block.plot_type is None:
                continue

            # Calculate position as fraction of A4 size
            left = block.x1 / A4_W
            bottom = 1 - (block.y2 / A4_H)  # invert Y for matplotlib
            width = (block.x2 - block.x1) / A4_W
            height = (block.y2 - block.y1) / A4_H

            # Create axes at the correct position
            ax = fig.add_axes([left, bottom, width, height])

            # Render the plot
            PlotRenderer.render_to_ax(block, ax, fig)

        # Render shapes
        ax_main = fig.add_axes([0, 0, 1, 1], frameon=False)
        ax_main.set_xlim(0, A4_W)
        ax_main.set_ylim(0, A4_H)
        ax_main.invert_yaxis()  # Match canvas coordinates
        ax_main.axis("off")

        for shape in self._shapes:
            if shape.shape_type == "line":
                line = Line2D(
                    [shape.x1, shape.x2],
                    [shape.y1, shape.y2],
                    color=shape.color,
                    linewidth=shape.line_width,
                )
                ax_main.add_line(line)
            elif shape.shape_type == "rectangle":
                rect = Rectangle(
                    (shape.x1, shape.y1),
                    shape.x2 - shape.x1,
                    shape.y2 - shape.y1,
                    edgecolor=shape.color,
                    facecolor=shape.fill if shape.fill else "none",
                    linewidth=shape.line_width,
                )
                ax_main.add_patch(rect)
            elif shape.shape_type == "circle":
                # Use Ellipse for circles/ovals
                cx = (shape.x1 + shape.x2) / 2
                cy = (shape.y1 + shape.y2) / 2
                w = shape.x2 - shape.x1
                h = shape.y2 - shape.y1
                circle = Ellipse(
                    (cx, cy),
                    w,
                    h,
                    edgecolor=shape.color,
                    facecolor=shape.fill if shape.fill else "none",
                    linewidth=shape.line_width,
                )
                ax_main.add_patch(circle)

        # Save as vector format
        fig.savefig(path, format=fmt, dpi=DPI)
        plt.close(fig)

    # -----------------------------------------------------------------------
    # Help
    # -----------------------------------------------------------------------
    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("How to use Research Plot Studio")
        win.geometry("500x500")
        win.grab_set()

        txt = tk.Text(
            win,
            wrap="word",
            padx=16,
            pady=14,
            font=("", 10),
            relief="flat",
            bg="#fafafa",
        )
        sb = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)

        # Enable mouse wheel scrolling
        bind_mousewheel(txt, txt, "vertical")

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=8)

        txt.insert(
            "end",
            """\
KTFIGURE — Quick-start guide
─────────────────────────────

TOOLBAR (left to right)
   ⬚ Select  — default mode; click objects to select/move/resize
   ✏ Plot    — drag on artboard to create a new plot region
   Shapes    — line, rectangle, circle tools
   🅃 Text   — click to drop a text label; drag to set a custom size
   Edit plot — reopen data / type dialog for selected plot
   Delete    — remove the selected object(s)
   PNG / PDF / SVG — export the artboard

MODES & ACTIONS
   Select is always the default.  After placing any object (plot, shape,
   text) the tool automatically returns to Select mode.

1. INSERT A PLOT REGION
   Click "Plot" in the toolbar then click-and-drag on the white A4
   artboard (minimum 30 × 30 px). A dialog opens automatically.
   • Tab "1 · Data"  — click "Browse CSV / TSV…" to load your file.
   • Tab "2 · Plot type"  — pick a type and map X / Y / Hue / Size columns.
   • Click "Apply ▶" to render.

2. ADD SHAPES
   Pick Line, Rectangle, or Circle from the toolbar and drag on the
   artboard. After drawing, the tool returns to Select automatically.

3. ADD TEXT
   Click "Text" then click anywhere on the artboard — a default-size box
   appears and you can type immediately. Press Enter when done.
   Drag instead of clicking to create a custom-sized text box.
   Font size scales automatically when you resize the text box.

4. SELECT & MULTI-SELECT
   Click any object to select it (handles appear at corners).
   Cmd/Ctrl+Click or Shift+Click to add/remove from selection.
   Drag on empty canvas to rubber-band select multiple objects.
   Click on empty canvas to deselect everything.

5. MOVE & RESIZE
   Drag a selected object to move it.
   Drag a corner handle to resize.
   With multiple objects selected, dragging moves or resizes all of them
   in sync — all four corner handles work correctly.

6. PROPERTIES (right panel)
   • Plot selected  → shows plot aesthetics (labels, theme, font, line,
                       colour, grid, legend). Click the colour swatch
                       directly to open the colour picker.
   • Shape selected → shows Shape Properties (colour, line width, style,
                       fill, arrowhead). Click swatches to pick colours.
   • Text selected  → shows Text Properties (content, colour, font, size,
                       bold, italic). Click the colour swatch to pick.

7. EDIT / DELETE
   Double-click any plot to reopen its data/type dialog.
   Select an object then press Delete/Backspace, or click "Delete" in
   the toolbar. Undo with Cmd+Z / Ctrl+Z.

8. EXPORT
   • PNG — raster image (best for presentations / web)
   • PDF — vector document (best for publications)
   • SVG — vector graphic (best for Illustrator / Inkscape)
   File extensions are added automatically if omitted.

SUPPORTED PLOT TYPES
   scatter · line · bar · barh · box · violin
   strip · swarm · histogram · kde · heatmap · count · regression
""",
        )
        txt.configure(state="disabled")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    if not PIL_AVAILABLE:
        print("=" * 60)
        print("ERROR: Pillow is required.")
        print("Please run:  pip install pillow")
        print("=" * 60)
        sys.exit(1)

    # Set process title on macOS to show "ktfigure" in dock/menu instead of "python3.12"
    try:
        if sys.platform == "darwin":
            # macOS: Use objc to set the process title
            from Foundation import NSProcessInfo

            pid = os.getpid()
            # Try to set the process name via libc
            libc = ctypes.CDLL(None)
            try:
                # Set argv[0] which affects some system displays
                libc.pthread_setname_np("ktfigure")
            except AttributeError:
                # Alternative: use ctypes to call Cocoa APIs
                try:
                    objc = __import__("objc")
                    NSProcessInfo.processInfo().setProcessName_("ktfigure")
                except Exception:
                    pass
    except Exception:
        pass  # Silently continue if process title setting fails

    root = tk.Tk()

    # Set app icon
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "ktfigure_logo.png")
        if os.path.exists(icon_path):
            icon_img = Image.open(icon_path)
            icon_photo = ImageTk.PhotoImage(icon_img)
            root.iconphoto(True, icon_photo)
    except Exception:
        # Silently fail if icon can't be loaded
        pass

    style = ttk.Style(root)
    for t in ("clam", "alt", "default"):
        if t in style.theme_names():
            style.theme_use(t)
            break

    BG = "#ffffff"
    FG = "#1e293b"
    MID = "#f1f5f9"
    ACC = "#3b82f6"
    BORDER = "#e2e8f0"
    MUTED = "#64748b"

    style.configure(
        ".", background=BG, foreground=FG, font=("", 10), bordercolor=BORDER
    )
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("TCheckbutton", background=BG, foreground=FG)
    style.configure(
        "TButton",
        background=ACC,
        foreground="white",
        padding=(8, 4),
        relief="flat",
        borderwidth=0,
    )
    style.map("TButton", background=[("active", "#2563eb"), ("pressed", "#1d4ed8")])
    style.configure(
        "TEntry",
        fieldbackground=MID,
        foreground=FG,
        bordercolor=BORDER,
        padding=5,
        relief="flat",
    )
    style.configure(
        "TCombobox", fieldbackground=MID, foreground=FG, bordercolor=BORDER, padding=4
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", MID)],
        foreground=[("disabled", MUTED)],
    )
    style.configure(
        "TSpinbox", fieldbackground=MID, foreground=FG, bordercolor=BORDER, padding=4
    )
    style.configure("TSeparator", background=BORDER)
    style.configure("Sash", sashthickness=6, sashpad=2, gripcount=10)
    style.configure("TPanedwindow", background=BORDER)
    style.configure("TNotebook", background=MID, bordercolor=BORDER)
    style.configure("TNotebook.Tab", background=MID, foreground=MUTED, padding=(12, 5))
    style.map(
        "TNotebook.Tab", background=[("selected", BG)], foreground=[("selected", ACC)]
    )
    style.configure(
        "Treeview", background=BG, fieldbackground=BG, foreground=FG, rowheight=22
    )
    style.configure(
        "Treeview.Heading", background=MID, foreground=MUTED, font=("", 9, "bold")
    )

    KTFigure(root)
    root.mainloop()


if __name__ == "__main__":
    main()
