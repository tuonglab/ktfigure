"""
Tests for data-model classes and pure utility functions:
  - default_aesthetics()
  - PlotBlock
  - Shape
  - TextObject
  - PLOT_TYPES / constants
"""
import copy
import pytest

from ktfigure import (
    DPI,
    A4_W,
    A4_H,
    BOARD_PAD,
    PLOT_TYPES,
    SEABORN_STYLES,
    SEABORN_PALETTES,
    LINE_STYLES,
    MARKER_TYPES,
    THEME_LIGHT,
    THEME_DARK,
    PlotBlock,
    Shape,
    TextObject,
    default_aesthetics,
)


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------

class TestConstants:
    def test_dpi(self):
        assert DPI == 96

    def test_a4_dimensions(self):
        assert A4_W == 794
        assert A4_H == 1123

    def test_board_pad(self):
        assert BOARD_PAD == 60

    def test_plot_types_list(self):
        expected = [
            "scatter", "line", "bar", "barh", "box", "violin",
            "strip", "swarm", "histogram", "kde", "heatmap", "count", "regression",
        ]
        assert PLOT_TYPES == expected

    def test_seaborn_styles(self):
        assert "whitegrid" in SEABORN_STYLES
        assert "darkgrid" in SEABORN_STYLES

    def test_line_styles(self):
        assert "-" in LINE_STYLES
        assert "--" in LINE_STYLES

    def test_marker_types(self):
        assert "o" in MARKER_TYPES
        assert "None" in MARKER_TYPES

    def test_theme_light_keys(self):
        required_keys = {"tb", "btn", "btn_fg", "btn_hover", "btn_press",
                         "sep", "canvas", "accent", "status_fg", "panel_bg"}
        assert required_keys.issubset(set(THEME_LIGHT.keys()))

    def test_theme_dark_keys(self):
        required_keys = {"tb", "btn", "btn_fg", "canvas", "accent"}
        assert required_keys.issubset(set(THEME_DARK.keys()))


# ---------------------------------------------------------------------------
# default_aesthetics()
# ---------------------------------------------------------------------------

class TestDefaultAesthetics:
    def test_returns_dict(self):
        a = default_aesthetics()
        assert isinstance(a, dict)

    def test_style(self):
        assert default_aesthetics()["style"] == "whitegrid"

    def test_palette(self):
        assert default_aesthetics()["palette"] == "deep"

    def test_font_family(self):
        assert default_aesthetics()["font_family"] == "DejaVu Sans"

    def test_font_size(self):
        assert default_aesthetics()["font_size"] == 11

    def test_defaults_false(self):
        a = default_aesthetics()
        assert a["use_color"] is False
        assert a["grid"] is True
        assert a["legend"] is True
        assert a["legend_outside"] is True
        assert a["legend_frameon"] is False
        assert a["tick_labels"] is True

    def test_alpha(self):
        assert default_aesthetics()["alpha"] == 0.8

    def test_color(self):
        assert default_aesthetics()["color"] == "#4C72B0"

    def test_hue_palette_empty(self):
        assert default_aesthetics()["hue_palette"] == {}

    def test_returns_new_dict_each_call(self):
        """Mutating one result must not affect another."""
        a1 = default_aesthetics()
        a2 = default_aesthetics()
        a1["style"] = "dark"
        assert a2["style"] == "whitegrid"


# ---------------------------------------------------------------------------
# PlotBlock
# ---------------------------------------------------------------------------

class TestPlotBlock:
    def test_init_normalises_coords(self):
        b = PlotBlock(200, 300, 100, 150)
        assert b.x1 == 100
        assert b.y1 == 150
        assert b.x2 == 200
        assert b.y2 == 300

    def test_init_already_normalised(self):
        b = PlotBlock(10, 20, 200, 300)
        assert b.x1 == 10
        assert b.y1 == 20
        assert b.x2 == 200
        assert b.y2 == 300

    def test_unique_bid(self):
        b1 = PlotBlock(0, 0, 100, 100)
        b2 = PlotBlock(0, 0, 100, 100)
        assert b1.bid != b2.bid

    def test_default_attributes(self):
        b = PlotBlock(0, 0, 200, 200)
        assert b.df is None
        assert b.plot_type is None
        assert b.col_x is None
        assert b.col_y is None
        assert b.col_hue is None
        assert b.col_size is None
        assert b.rect_id is None
        assert b.image_id is None
        assert b.label_id is None
        assert b._photo is None
        assert b._pil_img is None

    def test_aesthetics_is_default(self):
        b = PlotBlock(0, 0, 200, 200)
        assert b.aesthetics == default_aesthetics()

    def test_width_px_normal(self):
        b = PlotBlock(100, 0, 300, 200)
        assert b.width_px == 200

    def test_height_px_normal(self):
        b = PlotBlock(0, 50, 200, 150)
        assert b.height_px == 100

    def test_width_px_minimum_enforced(self):
        """Blocks smaller than 40px should be clamped to 40px."""
        b = PlotBlock(100, 0, 110, 200)  # width = 10, below minimum
        assert b.width_px == 40

    def test_height_px_minimum_enforced(self):
        b = PlotBlock(0, 100, 200, 110)  # height = 10, below minimum
        assert b.height_px == 40

    def test_width_in(self):
        b = PlotBlock(0, 0, DPI * 2, 100)  # 2 inches wide
        assert b.width_in == pytest.approx(2.0)

    def test_height_in(self):
        b = PlotBlock(0, 0, 100, DPI * 3)  # 3 inches tall
        assert b.height_in == pytest.approx(3.0)

    def test_deepcopy_skips_photo(self):
        b = PlotBlock(0, 0, 200, 200)
        # simulate a photo object (non-serialisable); we just use a sentinel
        b._photo = object()
        b2 = copy.deepcopy(b)
        assert b2._photo is None

    def test_deepcopy_preserves_aesthetics(self):
        b = PlotBlock(0, 0, 200, 200)
        b.aesthetics["style"] = "dark"
        b2 = copy.deepcopy(b)
        assert b2.aesthetics["style"] == "dark"

    def test_deepcopy_independent(self):
        b = PlotBlock(0, 0, 200, 200)
        b2 = copy.deepcopy(b)
        b2.aesthetics["style"] = "ticks"
        assert b.aesthetics["style"] != "ticks"


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

class TestShape:
    def test_init_rectangle_normalises(self):
        s = Shape(200, 300, 100, 150, "rectangle")
        assert s.x1 == 100
        assert s.y1 == 150
        assert s.x2 == 200
        assert s.y2 == 300

    def test_init_circle_normalises(self):
        s = Shape(200, 300, 100, 150, "circle")
        assert s.x1 == 100
        assert s.x2 == 200

    def test_init_line_preserves_direction(self):
        """Lines keep original direction (x1 < x2 not guaranteed)."""
        s = Shape(200, 300, 100, 150, "line")
        assert s.x1 == 200
        assert s.y1 == 300
        assert s.x2 == 100
        assert s.y2 == 150

    def test_unique_sid(self):
        s1 = Shape(0, 0, 100, 100, "rectangle")
        s2 = Shape(0, 0, 100, 100, "rectangle")
        assert s1.sid != s2.sid

    def test_default_attributes(self):
        s = Shape(0, 0, 100, 100, "rectangle")
        assert s.color == "#000000"
        assert s.line_width == 2
        assert s.fill == ""
        assert s.arrow is None
        assert s.dash == ()
        assert s.item_id is None

    def test_shape_type_stored(self):
        for st in ("line", "rectangle", "circle"):
            s = Shape(0, 0, 100, 100, st)
            assert s.shape_type == st

    def test_width_px_rectangle(self):
        s = Shape(50, 50, 200, 150, "rectangle")
        assert s.width_px == 150

    def test_height_px_rectangle(self):
        s = Shape(50, 50, 200, 150, "rectangle")
        assert s.height_px == 100

    def test_width_px_line(self):
        s = Shape(0, 0, 100, 0, "line")
        assert s.width_px == 100

    def test_center_x(self):
        s = Shape(0, 0, 200, 100, "rectangle")
        assert s.center_x == pytest.approx(100.0)

    def test_center_y(self):
        s = Shape(0, 0, 200, 100, "rectangle")
        assert s.center_y == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# TextObject
# ---------------------------------------------------------------------------

class TestTextObject:
    def test_init_defaults(self):
        t = TextObject(50, 80)
        assert t.x1 == 50
        assert t.y1 == 80
        assert t.x2 == 150  # x + 100 default width
        assert t.y2 == 110  # y + 30 default height
        assert t.text == "Text"
        assert t.font_family == "DejaVu Sans"
        assert t.font_size == 14
        assert t.color == "#000000"
        assert t.bold is False
        assert t.italic is False
        assert t.item_id is None

    def test_custom_text(self):
        t = TextObject(0, 0, text="Hello")
        assert t.text == "Hello"

    def test_unique_tid(self):
        t1 = TextObject(0, 0)
        t2 = TextObject(0, 0)
        assert t1.tid != t2.tid

    def test_center_x(self):
        t = TextObject(0, 0)
        assert t.center_x == pytest.approx(50.0)  # (0 + 100) / 2

    def test_center_y(self):
        t = TextObject(0, 0)
        assert t.center_y == pytest.approx(15.0)  # (0 + 30) / 2
