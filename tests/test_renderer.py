"""
Tests for PlotRenderer — validates that every supported plot type can be
rendered without raising exceptions and that the result is a matplotlib Figure.

These tests do NOT require a display since matplotlib is set to the Agg backend
at import time.
"""
import pytest
import pandas as pd
import numpy as np
from matplotlib.figure import Figure

from ktfigure import PlotBlock, PlotRenderer, default_aesthetics, DPI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_block(df, plot_type, col_x, col_y=None, col_hue=None, col_size=None,
               aesthetics_overrides=None):
    """Return a PlotBlock wired up with *df* and ready to render."""
    b = PlotBlock(0, 0, DPI * 4, DPI * 3)  # 4 × 3 inch block
    b.df = df
    b.plot_type = plot_type
    b.col_x = col_x
    b.col_y = col_y
    b.col_hue = col_hue
    b.col_size = col_size
    if aesthetics_overrides:
        b.aesthetics.update(aesthetics_overrides)
    return b


def assert_figure(fig):
    assert isinstance(fig, Figure)
    assert len(fig.axes) > 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def df():
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "x": rng.integers(1, 10, 40).astype(float),
        "y": rng.normal(20, 5, 40),
        "category": (["A", "B"] * 20),
        "size": rng.integers(1, 5, 40).astype(float),
    })


@pytest.fixture
def heatmap_df():
    return pd.DataFrame({
        "row": ["R1", "R1", "R2", "R2", "R3", "R3"],
        "col": ["C1", "C2", "C1", "C2", "C1", "C2"],
        "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    })


# ---------------------------------------------------------------------------
# PlotRenderer.render() — one test per plot type
# ---------------------------------------------------------------------------

class TestPlotRendererAllTypes:
    def test_scatter(self, df):
        b = make_block(df, "scatter", "x", "y")
        assert_figure(PlotRenderer.render(b))

    def test_scatter_with_hue(self, df):
        b = make_block(df, "scatter", "x", "y", col_hue="category")
        assert_figure(PlotRenderer.render(b))

    def test_scatter_with_size(self, df):
        b = make_block(df, "scatter", "x", "y", col_size="size")
        assert_figure(PlotRenderer.render(b))

    def test_scatter_use_color(self, df):
        b = make_block(df, "scatter", "x", "y",
                       aesthetics_overrides={"use_color": True, "color": "#ff0000"})
        assert_figure(PlotRenderer.render(b))

    def test_line(self, df):
        b = make_block(df, "line", "x", "y")
        assert_figure(PlotRenderer.render(b))

    def test_line_with_hue(self, df):
        b = make_block(df, "line", "x", "y", col_hue="category")
        assert_figure(PlotRenderer.render(b))

    def test_bar(self, df):
        b = make_block(df, "bar", "category", "y")
        assert_figure(PlotRenderer.render(b))

    def test_bar_with_hue(self, df):
        b = make_block(df, "bar", "category", "y", col_hue="category")
        assert_figure(PlotRenderer.render(b))

    def test_barh(self, df):
        b = make_block(df, "barh", "category", "y")
        assert_figure(PlotRenderer.render(b))

    def test_box(self, df):
        b = make_block(df, "box", "category", "y")
        assert_figure(PlotRenderer.render(b))

    def test_box_with_hue(self, df):
        b = make_block(df, "box", "category", "y", col_hue="category")
        assert_figure(PlotRenderer.render(b))

    def test_violin(self, df):
        b = make_block(df, "violin", "category", "y")
        assert_figure(PlotRenderer.render(b))

    def test_strip(self, df):
        b = make_block(df, "strip", "category", "y")
        assert_figure(PlotRenderer.render(b))

    def test_swarm(self, df):
        b = make_block(df, "swarm", "category", "y")
        assert_figure(PlotRenderer.render(b))

    def test_histogram(self, df):
        b = make_block(df, "histogram", "x")
        assert_figure(PlotRenderer.render(b))

    def test_histogram_with_hue(self, df):
        b = make_block(df, "histogram", "x", col_hue="category")
        assert_figure(PlotRenderer.render(b))

    def test_kde(self, df):
        b = make_block(df, "kde", "x")
        assert_figure(PlotRenderer.render(b))

    def test_kde_with_hue(self, df):
        b = make_block(df, "kde", "x", col_hue="category")
        assert_figure(PlotRenderer.render(b))

    def test_count(self, df):
        b = make_block(df, "count", "category")
        assert_figure(PlotRenderer.render(b))

    def test_regression(self, df):
        b = make_block(df, "regression", "x", "y")
        assert_figure(PlotRenderer.render(b))

    def test_heatmap(self, heatmap_df):
        b = make_block(heatmap_df, "heatmap", "col", "row")
        assert_figure(PlotRenderer.render(b))

    def test_unsupported_type(self, df):
        """Unsupported type should render an error message, not raise."""
        b = make_block(df, "unknown_type", "x", "y")
        fig = PlotRenderer.render(b)
        assert_figure(fig)


class TestPlotRendererAesthetics:
    """Test that aesthetic options are applied without raising exceptions."""

    def test_title_set(self, df):
        b = make_block(df, "scatter", "x", "y",
                       aesthetics_overrides={"title": "My Title"})
        fig = PlotRenderer.render(b)
        assert fig.axes[0].get_title() == "My Title"

    def test_xlabel_set(self, df):
        b = make_block(df, "scatter", "x", "y",
                       aesthetics_overrides={"xlabel": "X Axis"})
        fig = PlotRenderer.render(b)
        assert fig.axes[0].get_xlabel() == "X Axis"

    def test_ylabel_set(self, df):
        b = make_block(df, "scatter", "x", "y",
                       aesthetics_overrides={"ylabel": "Y Axis"})
        fig = PlotRenderer.render(b)
        assert fig.axes[0].get_ylabel() == "Y Axis"

    def test_grid_off(self, df):
        b = make_block(df, "scatter", "x", "y",
                       aesthetics_overrides={"grid": False})
        assert_figure(PlotRenderer.render(b))

    def test_legend_off(self, df):
        b = make_block(df, "scatter", "x", "y", col_hue="category",
                       aesthetics_overrides={"legend": False})
        assert_figure(PlotRenderer.render(b))

    def test_legend_inside(self, df):
        b = make_block(df, "scatter", "x", "y", col_hue="category",
                       aesthetics_overrides={"legend": True, "legend_outside": False,
                                             "legend_frameon": True})
        assert_figure(PlotRenderer.render(b))

    def test_tick_labels_off(self, df):
        b = make_block(df, "scatter", "x", "y",
                       aesthetics_overrides={"tick_labels": False})
        assert_figure(PlotRenderer.render(b))

    def test_marker_none(self, df):
        b = make_block(df, "scatter", "x", "y",
                       aesthetics_overrides={"marker": "None"})
        assert_figure(PlotRenderer.render(b))

    def test_custom_hue_palette(self, df):
        b = make_block(df, "scatter", "x", "y", col_hue="category",
                       aesthetics_overrides={"hue_palette": {"A": "#ff0000", "B": "#0000ff"}})
        assert_figure(PlotRenderer.render(b))

    def test_line_style_dashed(self, df):
        b = make_block(df, "line", "x", "y",
                       aesthetics_overrides={"line_style": "--", "line_width": 2.0})
        assert_figure(PlotRenderer.render(b))

    def test_seaborn_style_darkgrid(self, df):
        b = make_block(df, "scatter", "x", "y",
                       aesthetics_overrides={"style": "darkgrid"})
        assert_figure(PlotRenderer.render(b))


class TestPlotRendererRenderToAx:
    """render_to_ax() should write onto an existing axes."""

    def test_render_to_ax(self, df):
        from matplotlib.figure import Figure
        b = make_block(df, "scatter", "x", "y")
        fig = Figure(figsize=(4, 3), dpi=DPI)
        ax = fig.add_subplot(111)
        PlotRenderer.render_to_ax(b, ax, fig)
        # Should have scatter artists on the axes
        assert len(ax.collections) > 0 or len(ax.lines) > 0


class TestPlotRendererErrorHandling:
    """Render errors should be displayed as text, not propagate as exceptions."""

    def test_bad_column_renders_error_text(self, df):
        b = make_block(df, "scatter", "nonexistent_col", "y")
        fig = PlotRenderer.render(b)
        assert_figure(fig)
        # The axes text should contain "Render error"
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("Render error" in t or "error" in t.lower() for t in texts)

    def test_none_df_renders_error(self):
        b = PlotBlock(0, 0, DPI * 4, DPI * 3)
        b.df = None
        b.plot_type = "scatter"
        b.col_x = "x"
        b.col_y = "y"
        # Rendering with None df should show error text, not crash
        fig = PlotRenderer.render(b)
        assert_figure(fig)
        # The axes text should contain "Render error"
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("Render error" in t or "error" in t.lower() for t in texts)
