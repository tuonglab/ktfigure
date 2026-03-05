"""
Tests for the center-view button and multi-artboard feature.

These tests require a display (xvfb on Linux CI).
"""

import tkinter as tk
import pytest

from ktfigure import A4_W, A4_H, BOARD_PAD, KTFigure, PlotBlock, Shape, TextObject


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


# ---------------------------------------------------------------------------
# Center-view button
# ---------------------------------------------------------------------------


class TestCenterView:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_center_button_exists(self):
        assert self.app._btn_center is not None

    def test_center_view_does_not_crash(self):
        """Calling _center_view() must not raise."""
        self.app._center_view()
        pump(self.root)

    def test_center_view_sets_status(self):
        self.app._center_view()
        pump(self.root)
        assert "center" in self.app._status.cget("text").lower()

    def test_center_view_at_zoom_2x(self):
        """_center_view must also work when the canvas is zoomed."""
        self.app._set_zoom(2.0)
        pump(self.root)
        self.app._center_view()
        pump(self.root)
        assert "center" in self.app._status.cget("text").lower()


# ---------------------------------------------------------------------------
# Artboard defaults
# ---------------------------------------------------------------------------


class TestArtboardDefaults:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_one_artboard_on_start(self):
        assert len(self.app._artboards) == 1

    def test_active_board_is_zero(self):
        assert self.app._active_board == 0

    def test_board_combo_exists(self):
        assert self.app._board_combo is not None

    def test_board_combo_default_value(self):
        assert self.app._board_var.get() == "1"

    def test_add_board_button_exists(self):
        assert self.app._btn_add_board is not None

    def test_del_board_button_exists(self):
        assert self.app._btn_del_board is not None

    def test_del_board_disabled_with_one_page(self):
        """Delete button must be disabled when there is only one artboard."""
        assert str(self.app._btn_del_board.cget("state")) == "disabled"

    def test_one_tab_button_on_start(self):
        assert len(self.app._artboard_tab_btns) == 1

    def test_first_tab_button_labeled_p1(self):
        # _artboard_tab_btns now holds string values ("1", "2", ...)
        assert self.app._artboard_tab_btns[0] == "1"


# ---------------------------------------------------------------------------
# _sync_artboard
# ---------------------------------------------------------------------------


class TestSyncArtboard:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_sync_artboard_updates_blocks(self):
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)
        app._sync_artboard()
        assert b in app._artboards[0]["blocks"]

    def test_sync_artboard_updates_shapes(self):
        app = self.app
        s = Shape(0, 0, 50, 50, "rectangle")
        app._shapes.append(s)
        app._sync_artboard()
        assert s in app._artboards[0]["shapes"]

    def test_sync_artboard_updates_texts(self):
        app = self.app
        t = TextObject(10, 10)
        app._texts.append(t)
        app._sync_artboard()
        assert t in app._artboards[0]["texts"]


# ---------------------------------------------------------------------------
# _add_artboard
# ---------------------------------------------------------------------------


class TestAddArtboard:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_add_artboard_increments_count(self):
        self.app._add_artboard()
        assert len(self.app._artboards) == 2

    def test_add_artboard_switches_active(self):
        self.app._add_artboard()
        assert self.app._active_board == 1

    def test_add_artboard_new_page_is_empty(self):
        self.app._add_artboard()
        assert self.app._blocks == []
        assert self.app._shapes == []
        assert self.app._texts == []

    def test_add_artboard_creates_tab_button(self):
        self.app._add_artboard()
        pump(self.root)
        assert len(self.app._artboard_tab_btns) == 2

    def test_add_artboard_enables_delete_button(self):
        self.app._add_artboard()
        pump(self.root)
        assert str(self.app._btn_del_board.cget("state")) == "normal"

    def test_add_artboard_sets_status(self):
        self.app._add_artboard()
        assert "page 2" in self.app._status.cget("text").lower()

    def test_add_multiple_artboards(self):
        self.app._add_artboard()
        self.app._add_artboard()
        assert len(self.app._artboards) == 3
        assert self.app._active_board == 2

    def test_prev_artboard_state_preserved(self):
        """Objects on page 1 must survive adding a new page."""
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)
        app._add_artboard()
        # page 2 is active — page 1's blocks should still be in artboards[0]
        assert b in app._artboards[0]["blocks"]


# ---------------------------------------------------------------------------
# _switch_artboard
# ---------------------------------------------------------------------------


class TestSwitchArtboard:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_switch_artboard_changes_active(self):
        app = self.app
        app._add_artboard()
        app._switch_artboard(0)
        assert app._active_board == 0

    def test_switch_to_same_board_is_noop(self):
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)
        app._switch_artboard(0)  # already on 0
        assert b in app._blocks  # block still there

    def test_switch_restores_blocks(self):
        """Blocks from page 1 must be visible when switching back."""
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)
        app._add_artboard()  # switch to page 2
        pump(self.root)
        app._switch_artboard(0)  # back to page 1
        pump(self.root)
        assert b in app._blocks

    def test_switch_isolates_pages(self):
        """Blocks on page 1 must NOT appear on page 2."""
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)
        app._add_artboard()
        pump(self.root)
        assert b not in app._blocks  # page 2 is blank

    def test_switch_clears_selection(self):
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)
        app._selected = b
        app._add_artboard()
        pump(self.root)
        app._switch_artboard(0)
        pump(self.root)
        assert app._selected is None

    def test_switch_updates_tab_buttons(self):
        app = self.app
        app._add_artboard()
        pump(self.root)
        app._switch_artboard(0)
        pump(self.root)
        assert app._active_board == 0
        # Combobox should now show page 1
        assert app._board_var.get() == "1"

    def test_switch_sets_status(self):
        app = self.app
        app._add_artboard()
        pump(self.root)
        app._switch_artboard(0)
        pump(self.root)
        assert "page 1" in app._status.cget("text").lower()


# ---------------------------------------------------------------------------
# _delete_artboard
# ---------------------------------------------------------------------------


class TestDeleteArtboard:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_cannot_delete_last_artboard(self):
        self.app._delete_artboard()
        assert len(self.app._artboards) == 1

    def test_cannot_delete_last_artboard_status(self):
        self.app._delete_artboard()
        assert "cannot" in self.app._status.cget("text").lower()

    def test_delete_artboard_decrements_count(self):
        app = self.app
        app._add_artboard()
        app._delete_artboard()
        assert len(app._artboards) == 1

    def test_delete_artboard_switches_to_previous(self):
        app = self.app
        app._add_artboard()  # now on page 2
        app._delete_artboard()  # delete page 2
        assert app._active_board == 0

    def test_delete_artboard_disables_delete_btn(self):
        app = self.app
        app._add_artboard()
        pump(self.root)
        app._delete_artboard()
        pump(self.root)
        assert str(app._btn_del_board.cget("state")) == "disabled"

    def test_delete_updates_tab_buttons(self):
        app = self.app
        app._add_artboard()
        pump(self.root)
        app._delete_artboard()
        pump(self.root)
        assert len(app._artboard_tab_btns) == 1

    def test_delete_sets_status(self):
        app = self.app
        app._add_artboard()
        app._delete_artboard()
        assert "deleted" in app._status.cget("text").lower()

    def test_delete_first_page_when_on_second(self):
        """Delete page 1 while on page 2; the remaining page (originally page 2)
        becomes the only page at index 0."""
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)  # put block on page 1
        app._add_artboard()  # go to page 2
        pump(self.root)
        app._switch_artboard(0)  # back to page 1
        pump(self.root)
        app._delete_artboard()  # delete page 1 (active=0)
        pump(self.root)
        # Should now be on the only remaining page (originally page 2)
        assert len(app._artboards) == 1
        assert app._active_board == 0
        assert app._blocks == []  # page 2 was blank


# ---------------------------------------------------------------------------
# Undo/redo sync across artboards
# ---------------------------------------------------------------------------


class TestArtboardUndoRedo:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_undo_syncs_blocks_to_artboard(self):
        """After undo the artboard dict must reflect the new _blocks reference."""
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)
        app._save_state()
        app._undo()
        pump(self.root)
        # The artboard dict must now point at the same list as _blocks
        assert app._artboards[app._active_board]["blocks"] is app._blocks

    def test_redo_syncs_blocks_to_artboard(self):
        """After redo the artboard dict must reflect the new _blocks reference."""
        app = self.app
        b = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b)
        app._save_state()
        app._undo()
        pump(self.root)
        app._redo()
        pump(self.root)
        assert app._artboards[app._active_board]["blocks"] is app._blocks

    def test_undo_on_page2_does_not_affect_page1(self):
        """Undo on page 2 must not touch page 1's content."""
        app = self.app
        b1 = PlotBlock(0, 0, 100, 100)
        app._blocks.append(b1)
        app._save_state()

        app._add_artboard()  # switch to page 2
        pump(self.root)
        b2 = PlotBlock(10, 10, 200, 200)
        app._blocks.append(b2)
        app._save_state()
        app._undo()
        pump(self.root)
        # page 2 should have no blocks after undo
        assert b2 not in app._blocks

        # Switch back to page 1 and verify b1 is intact
        app._switch_artboard(0)
        pump(self.root)
        assert b1 in app._blocks


# ---------------------------------------------------------------------------
# Theme interaction
# ---------------------------------------------------------------------------


class TestArtboardTheme:
    def setup_method(self):
        self.root, self.app = make_app()

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_artboard_controls_survive_theme_switch(self):
        app = self.app
        app._on_theme_click()
        pump(self.root)
        assert app._btn_add_board is not None
        assert app._btn_del_board is not None
        assert app._btn_center is not None

    def test_artboard_count_preserved_after_theme_switch(self):
        app = self.app
        app._add_artboard()
        app._on_theme_click()
        pump(self.root)
        assert len(app._artboards) == 2
        assert len(app._artboard_tab_btns) == 2
