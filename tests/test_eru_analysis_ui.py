import ast
import time
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from modules.main.eruAnalysis import Condition, PlayerIdentities, unpack_row
from modules.main.eruAnalysisPanel import EruAnalysisPanel


def children(widget):
    for child in widget.winfo_children():
        yield child
        yield from children(child)


class EruAnalysisUITests(unittest.TestCase):
    def setUp(self):
        try:
            self.host = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.addCleanup(self.host.destroy)
        self.host.geometry("740x580")
        self.host.colors = {
            "bg": "#0f172a", "field": "#020617", "text": "#ffffff",
            "accent": "#38bdf8", "selected_text": "#ffffff",
        }
        frame = ttk.Frame(self.host, padding=14)
        frame.pack(fill="both", expand=True)
        self.panel = EruAnalysisPanel(self.host, frame, Path(__file__).parents[1], {
            "Watched": [("Watched", "watched"), ("Draft", "watched_draft")],
            "Eru": [("Eru", "eru")],
        })
        self.panel.service.identities = PlayerIdentities([["name", "id"], ["Player", "1"], ["Alias", "1"]])
        self.panel.service.songs = unpack_row({
            "mode": "Watched FL", "songs": "[1,2]", "year": '["2000", "2020"]',
            "tags": '[["Isekai"], []]', "genres": '[["Fantasy"], ["Drama"]]',
            "correct": '[[{"name": "Alias"}], []]', "wrong": '[[], ["Player"]]',
        }, self.panel.service.identities)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.panel.service.cache_dir = Path(temporary.name)
        loader = patch.object(self.panel.service, "load", return_value=len(self.panel.service.songs))
        loader.start()
        self.addCleanup(loader.stop)
        self.panel.mode.set("Watched - Watched")
        self.host.update()

    def wait(self):
        deadline = time.monotonic() + 5
        while self.panel.busy and time.monotonic() < deadline:
            self.host.update()
            time.sleep(0.01)
        self.assertFalse(self.panel.busy)

    def button(self, parent, label):
        return next(w for w in children(parent) if isinstance(w, ttk.Button) and w.cget("text") == label)

    def popup(self):
        return next(w for w in self.host.winfo_children() if isinstance(w, tk.Toplevel))

    def test_calculate_copy_and_stale_filters(self):
        self.panel.run_calculation()
        self.wait()
        self.assertEqual(self.panel.totals, {"id:1": [2, 1]})
        self.panel.copy_dialog()
        dialog = self.popup()
        text = next(w for w in children(dialog) if isinstance(w, tk.Text))
        text.insert("1.0", "Alias (SS), NewPlayer (None)")
        self.button(dialog, "Copy").invoke()
        self.assertEqual(self.host.clipboard_get(), "Alias (50.00), NewPlayer (0.00)")
        self.panel.start_year.set("2020")
        self.assertIsNone(self.panel.totals)
        self.assertTrue(self.panel.copy_button.instate(["disabled"]))

    def test_picker_apply_cancel_and_clear(self):
        self.panel.choose_values("genres")
        dialog = self.popup()
        next(w for w in children(dialog) if isinstance(w, ttk.Checkbutton) and w.cget("text") == "Fantasy").invoke()
        self.button(dialog, "Apply").invoke()
        self.assertEqual(self.panel.genres, {"Fantasy"})
        self.panel.choose_values("genres")
        dialog = self.popup()
        self.button(dialog, "Clear").invoke()
        self.button(dialog, "Cancel").invoke()
        self.assertEqual(self.panel.genres, {"Fantasy"})
        self.panel.run_calculation()
        self.wait()
        self.assertEqual(self.panel.totals["id:1"], [1, 1])

    def test_condition_link_selection_invalidates_results(self):
        self.panel.update_conditions([Condition("genres", "Fantasy"), Condition("tags", "Isekai")])
        self.panel.run_calculation()
        self.wait()
        self.panel.condition_link.set("AND")
        self.panel.change_condition_link()
        self.assertEqual(self.panel.filters().conditions[1].link, "AND")
        self.assertEqual(self.panel.expression.get(), '(Genre "Fantasy" AND Tag "Isekai")')
        self.assertIsNone(self.panel.totals)
        self.assertTrue(self.panel.copy_button.instate(["disabled"]))

    def test_condition_reorder_remove_and_first_link(self):
        self.panel.update_conditions([Condition("genres", "Fantasy"), Condition("tags", "Isekai", "AND"), Condition("tags", "School")], 1)
        self.panel.move_condition(-1)
        self.assertEqual([item.value for item in self.panel.conditions], ["Isekai", "Fantasy", "School"])
        self.assertTrue(self.panel.link_combo.instate(["disabled"]))
        self.assertEqual(self.panel.expression.get(), '(Tag "Isekai" AND Genre "Fantasy") OR Tag "School"')
        self.panel.remove_condition()
        self.assertEqual(self.panel.tags, {"School"})
        self.assertEqual(len(self.panel.condition_table.get_children()), 2)
        self.panel.remove_condition()
        self.panel.remove_condition()
        self.assertEqual(self.panel.expression.get(), "All songs")
        self.assertEqual(self.panel.filters().conditions, ())

    def test_picker_preserves_existing_links(self):
        self.panel.update_conditions([Condition("genres", "Fantasy"), Condition("tags", "Isekai", "AND")])
        self.panel.choose_values("genres")
        dialog = self.popup()
        next(w for w in children(dialog) if isinstance(w, ttk.Checkbutton) and w.cget("text") == "Drama").invoke()
        self.button(dialog, "Apply").invoke()
        self.assertEqual(self.panel.conditions[1].link, "AND")
        self.assertEqual(self.panel.conditions[2], Condition("genres", "Drama"))

    def test_condition_controls_disabled_while_busy(self):
        self.panel.update_conditions([Condition("genres", "Fantasy"), Condition("tags", "Isekai")])
        self.panel.set_busy(True)
        self.assertTrue(self.panel.link_combo.instate(["disabled"]))
        self.assertTrue(self.panel.condition_remove.instate(["disabled"]))
        before = list(self.panel.conditions)
        self.panel.remove_condition()
        self.assertEqual(self.panel.conditions, before)
        self.panel.set_busy(False)

    def test_wheel_scrolls_from_popup_blank_space_and_children(self):
        for field in ("genres", "tags"):
            with patch.object(self.panel.service, "choices", return_value=[f"Choice {i}" for i in range(70)]):
                self.panel.choose_values(field)
            dialog = self.popup()
            self.host.update()
            canvas = next(w for w in children(dialog) if isinstance(w, tk.Canvas))
            embedded_frame = next(w for w in canvas.winfo_children() if isinstance(w, ttk.Frame))
            check = next(w for w in children(dialog) if isinstance(w, ttk.Checkbutton))
            for target in (dialog, embedded_frame, check):
                canvas.yview_moveto(0)
                target.event_generate("<MouseWheel>", delta=-120)
                self.host.update()
                self.assertGreater(canvas.yview()[0], 0)
            dialog.destroy()

    def test_required_mode_and_invalid_year(self):
        for mode, year in (("", ""), ("Watched - Watched", "bad")):
            self.panel.mode.set(mode)
            self.panel.start_year.set(year)
            with patch("modules.main.eruAnalysisPanel.messagebox.showerror") as error:
                self.panel.run_calculation()
                error.assert_called_once()
            self.assertFalse(self.panel.busy)

    def test_no_mode_records_are_not_replaced(self):
        self.panel.mode.set("Watched - Draft")
        self.panel.run_calculation()
        self.wait()
        self.assertEqual(self.panel.totals, {})
        self.assertIn("No separately labeled", self.panel.status.get())

    def test_load_failure_recovers_controls(self):
        with patch.object(self.panel.service, "load", side_effect=ValueError("Test failure")), patch("modules.main.eruAnalysisPanel.messagebox.showerror") as error:
            self.panel.run_calculation()
            self.wait()
            error.assert_called_once()
        self.assertFalse(self.panel.calculate_button.instate(["disabled"]))
        self.assertTrue(self.panel.copy_button.instate(["disabled"]))

    def test_picker_loads_options_automatically(self):
        songs = self.panel.service.songs
        self.panel.service.songs = None

        def load(*_args, **_kwargs):
            self.panel.service.songs = songs
            return len(songs)

        with patch.object(self.panel.service, "load", side_effect=load) as loader:
            self.panel.choose_values("tags")
            self.wait()
            loader.assert_called_once()
        dialog = self.popup()
        self.assertTrue(any(isinstance(w, ttk.Checkbutton) and w.cget("text") == "Isekai" for w in children(dialog)))
        dialog.destroy()

    def test_only_calculate_and_status_remain(self):
        labels = [w.cget("text") for w in children(self.host) if isinstance(w, ttk.Button)]
        self.assertNotIn("Load Data", labels)
        self.assertNotIn("Refresh Data", labels)
        self.assertIn("Calculate", labels)
        self.assertFalse(any(isinstance(w, ttk.Progressbar) for w in children(self.host)))
        self.assertTrue(any(isinstance(w, ttk.Label) and w.cget("text") == "Link Operator" for w in children(self.host)))

    def test_header_controls_fit_small_panel(self):
        for width in (740, 940):
            self.host.geometry(f"{width}x580")
            self.host.update()
            for widget in (self.panel.copy_button, self.panel.mode_combo, self.panel.end_entry, self.panel.table):
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), self.host.winfo_rootx() + width)

    def test_player_stats_tab_only_in_eru(self):
        source = ast.parse((Path(__file__).parents[1] / "AMQ Host Script.py").read_text(encoding="utf-8"))
        cls = next(node for node in source.body if isinstance(node, ast.ClassDef))
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_show_tour_tabs")
        namespace = {"TOURS": {"eru": {"standalone_eru": True}, "watched": {}}}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "host-tabs", "exec"), namespace)
        self.host.main_notebook = ttk.Notebook(self.host)
        for name in ("setup_tab", "solver_tab", "update_tab", "elos_tab", "stats_tab", "eru_analysis_tab"):
            setattr(self.host, name, ttk.Frame(self.host.main_notebook))
        for mode in ("eru", "watched", "eru"):
            self.host.selected_tour_id = mode
            namespace["_show_tour_tabs"](self.host)
            titles = [self.host.main_notebook.tab(tab, "text") for tab in self.host.main_notebook.tabs()]
            self.assertEqual("Player Stats" in titles, mode == "eru")
            if mode == "eru":
                self.assertEqual(titles, ["Setup", "Make Teams", "Player Stats"])


if __name__ == "__main__":
    unittest.main()
