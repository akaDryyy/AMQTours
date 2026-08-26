from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import threading
import asyncio
import tkinter as tk
import traceback
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from tkinter import ttk

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data"
if str(DATA_ROOT) not in sys.path:
    sys.path.insert(0, str(DATA_ROOT))
REQUIREMENTS_PATH = DATA_ROOT / "requirements.txt"

from modules.support.dependencies import ensure_dependencies


ensure_dependencies(REQUIREMENTS_PATH)

from modules.support.hostConfig import (
    CATEGORIES,
    LINKS,
    SETUP_TOURS,
    load_setup_codes,
)
from modules.support import hostHistory
from modules.support.playerRatings import MissingRatingsError, normalize_alias_key, resolve_player_ratings
from modules.main.substitutionPanel import SubstitutionPanel
from modules.main.hostUpdater import HostScriptUpdater
from tour_config import TOURS


UI_SETTINGS_PATH = PROJECT_ROOT / "config" / "ui_settings.json"
HOST_VERSION_PATH = PROJECT_ROOT / "config" / "host_script_version.json"
SETUP_CODES_PATH = PROJECT_ROOT / "config" / "setup_codes.json"
SETUP_CODES = load_setup_codes(SETUP_CODES_PATH)
PLAYER_PATTERN = re.compile(r"^(.*?)\s*(?:\(([^()]*)\))?\s*$")


class AMQTourUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AMQ Host Script")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.selected_tour_id = "usual"
        self.selected_category = "Random"
        self.ui_ready = False
        self.category_buttons: dict[str, ttk.Button] = {}
        self.tour_buttons: dict[str, ttk.Button] = {}
        self.players_placeholder = "name (Rank), name (Rank), ..."
        self.players_placeholder_active = False
        self.solver_running = False
        self.rank_vars: dict[str, tk.StringVar] = {}
        self.rank_check_generation = 0
        self.startup_eloscrape_done = threading.Event()
        self.startup_eloscrape_running = False
        self.startup_eloscrape_errors = []
        self.ui_settings = self.load_ui_settings()
        saved_tour_id = self.ui_settings.get("selected_tour_id")
        if saved_tour_id in TOURS:
            self.selected_tour_id = saved_tour_id
        self.selected_category = self.category_for_tour(self.selected_tour_id)
        self.boot_tour_ids = set(self.ui_settings.get("boot_tour_ids") or self.default_boot_tour_ids())
        self.do_not_autoload = bool(self.ui_settings.get("do_not_autoload", False))
        self.boot_mode_vars: dict[str, tk.BooleanVar] = {}
        self.loaded_tour_ids: set[str] = set()
        self.loading_tour_ids: set[str] = set()
        self.tour_load_events: dict[str, threading.Event] = {}
        self.tour_load_lock = threading.Lock()
        self.last_startup_status = ""
        self.version_update_running = False
        self.host_updater = HostScriptUpdater(PROJECT_ROOT, HOST_VERSION_PATH)
        self.host_version_state = {
            "status": "checking",
            "local": "",
            "remote": "",
            "message": "Host Script version: checking...",
        }
        self.dark_mode = tk.BooleanVar(value=bool(self.ui_settings.get("dark_mode", False)))
        self.tk_text_widgets: list[tk.Text] = []
        self.tk_list_widgets: list[tk.Listbox] = []
        self.setup_guess_time = tk.StringVar()
        self.setup_difficulty = tk.StringVar()
        self.setup_quagsual = tk.BooleanVar(value=False)
        self.setup_fey_watched = tk.BooleanVar(value=False)
        self.setup_active_key = None
        self.current_setup_code = ""
        self.challonge_items = []
        self.mvp_running = False
        self.update_elos_running = False
        self.recalculate_running = False
        self.latest_inhouse_teams = {}
        self.inhouse_result_rows = []
        self.inhouse_logging = False
        self.elos_search_var = tk.StringVar()
        self.whitelist_players: list[str] = []
        self.whitelist_popup = None
        self.whitelist_popup_list = None
        self.whitelist_popup_target = None

        self._configure_style()
        self._build_layout()
        self.select_category(self.selected_category, select_first=False)
        self.select_tour(self.selected_tour_id)
        self.ui_ready = True
        self.after(300, self.start_startup_eloscrape)
        self.after(600, self.start_host_version_check)

    def _configure_style(self):
        self.colors = self._theme_colors()
        self.configure(bg=self.colors["bg"])
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=self.colors["bg"])
        self.style.configure("Panel.TFrame", background=self.colors["panel"])
        self.style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 10))
        self.style.configure("Panel.TLabel", background=self.colors["panel"], foreground=self.colors["text"], font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", background=self.colors["bg"], foreground=self.colors["title"], font=("Segoe UI", 18, "bold"))
        self.style.configure("Subtle.TLabel", background=self.colors["panel"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        self.style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6), background=self.colors["button"], foreground=self.colors["text"], bordercolor=self.colors["border"])
        self.style.configure("Selected.TButton", font=("Segoe UI", 10), padding=(10, 6), background=self.colors["selected"], foreground=self.colors["selected_text"], bordercolor=self.colors["selected"])
        self.style.configure("Tool.TButton", font=("Segoe UI", 10), padding=(12, 7), background=self.colors["button"], foreground=self.colors["text"], bordercolor=self.colors["border"])
        self.style.configure(
            "TCheckbutton",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            fieldbackground=self.colors["field"],
            indicatorbackground=self.colors["field"],
            indicatorforeground=self.colors["text"],
            indicatorcolor=self.colors["field"],
            focuscolor=self.colors["bg"],
            font=("Segoe UI", 10),
        )
        self.style.configure("TEntry", fieldbackground=self.colors["field"], foreground=self.colors["text"], bordercolor=self.colors["border"])
        self.style.configure("TCombobox", fieldbackground=self.colors["field"], foreground=self.colors["text"], background=self.colors["button"], bordercolor=self.colors["border"], arrowcolor=self.colors["text"])
        self.style.configure("TSpinbox", fieldbackground=self.colors["field"], foreground=self.colors["text"], bordercolor=self.colors["border"])
        self.style.configure("TNotebook", background=self.colors["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        self.style.configure("TNotebook.Tab", padding=(14, 8), width=18, font=("Segoe UI", 10), background=self.colors["button"], foreground=self.colors["text"], borderwidth=1)
        self.style.configure("Horizontal.TProgressbar", troughcolor=self.colors["progress_track"], background=self.colors["accent"], bordercolor=self.colors["border"], lightcolor=self.colors["accent"], darkcolor=self.colors["accent"])
        self.style.configure("Treeview", background=self.colors["field"], fieldbackground=self.colors["field"], foreground=self.colors["text"], bordercolor=self.colors["border"])
        self.style.configure("Treeview.Heading", background=self.colors["button"], foreground=self.colors["text"], font=("Segoe UI", 10, "bold"))
        self.style.map("TButton", background=[("active", self.colors["button_active"])])
        self.style.map("Selected.TButton", background=[("active", self.colors["selected"])])
        self.style.map(
            "TCheckbutton",
            background=[
                ("active", self.colors["bg"]),
                ("pressed", self.colors["bg"]),
                ("selected", self.colors["bg"]),
                ("!selected", self.colors["bg"]),
            ],
            foreground=[
                ("active", self.colors["text"]),
                ("pressed", self.colors["text"]),
                ("selected", self.colors["text"]),
                ("!selected", self.colors["text"]),
            ],
            indicatorbackground=[
                ("active", self.colors["field"]),
                ("pressed", self.colors["field"]),
                ("selected", self.colors["accent"]),
                ("!selected", self.colors["field"]),
            ],
            indicatorcolor=[
                ("active", self.colors["field"]),
                ("pressed", self.colors["field"]),
                ("selected", self.colors["accent"]),
                ("!selected", self.colors["field"]),
            ],
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.colors["field"])],
            foreground=[("readonly", self.colors["text"])],
            background=[("readonly", self.colors["button"]), ("active", self.colors["button_active"])],
            selectbackground=[("readonly", self.colors["field"])],
            selectforeground=[("readonly", self.colors["text"])],
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", self.colors["panel"]), ("active", self.colors["button_active"])],
            padding=[("selected", (14, 8)), ("!selected", (14, 8))],
            expand=[("selected", [0, 0, 0, 0]), ("!selected", [0, 0, 0, 0])],
        )
        self.style.map("Treeview", background=[("selected", self.colors["accent"])], foreground=[("selected", self.colors["selected_text"])])
        self.option_add("*TCombobox*Listbox.background", self.colors["field"])
        self.option_add("*TCombobox*Listbox.foreground", self.colors["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", self.colors["accent"])
        self.option_add("*TCombobox*Listbox.selectForeground", self.colors["selected_text"])

    def _theme_colors(self):
        if self.dark_mode.get():
            return {
                "bg": "#0f172a",
                "panel": "#182235",
                "field": "#111827",
                "text": "#e5e7eb",
                "title": "#f8fafc",
                "muted": "#94a3b8",
                "placeholder": "#64748b",
                "border": "#334155",
                "button": "#223047",
                "button_active": "#2d3d59",
                "selected": "#38bdf8",
                "selected_text": "#082f49",
                "accent": "#38bdf8",
                "progress_track": "#273449",
            }
        return {
            "bg": "#f4f6f8",
            "panel": "#ffffff",
            "field": "#ffffff",
            "text": "#1f2933",
            "title": "#111827",
            "muted": "#64748b",
            "placeholder": "#94a3b8",
            "border": "#cbd5e1",
            "button": "#f8fafc",
            "button_active": "#e2e8f0",
            "selected": "#2563eb",
            "selected_text": "#ffffff",
            "accent": "#2563eb",
            "progress_track": "#dbe4ee",
        }

    def toggle_theme(self):
        self.save_ui_settings()
        self._configure_style()
        self.apply_widget_theme()

    def load_ui_settings(self):
        try:
            with UI_SETTINGS_PATH.open(encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def save_ui_settings(self):
        self.ui_settings["dark_mode"] = self.dark_mode.get()
        self.ui_settings["boot_tour_ids"] = sorted(self.boot_tour_ids)
        self.ui_settings["selected_tour_id"] = self.selected_tour_id
        self.ui_settings["do_not_autoload"] = self.do_not_autoload
        UI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with UI_SETTINGS_PATH.open("w", encoding="utf-8") as f:
            json.dump(self.ui_settings, f, indent=2)

    def category_for_tour(self, tour_id):
        for category, entries in CATEGORIES.items():
            if any(entry_tour_id == tour_id for _label, entry_tour_id in entries):
                return category
        return "Random"

    def is_tour_loaded(self, tour_id):
        with self.tour_load_lock:
            return tour_id in self.loaded_tour_ids

    def loadable_tour_ids(self):
        return [
            tour_id
            for tour_id, tour in TOURS.items()
            if tour.get("eloscrape") or tour.get("inhouse") or tour.get("dry_elo")
        ]

    def default_boot_tour_ids(self):
        return self.loadable_tour_ids()

    def tour_requires_startup_load(self, tour):
        return bool(tour.get("eloscrape") or tour.get("inhouse") or tour.get("dry_elo"))

    def selected_boot_tour_ids(self):
        selected = set(self.boot_tour_ids)
        if not self.do_not_autoload:
            selected.add(self.selected_tour_id)
        return [tour_id for tour_id in self.loadable_tour_ids() if tour_id in selected]

    def open_settings_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Settings")
        dialog.configure(bg=self.colors["bg"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, text="Load On Startup", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(
            frame,
            text="Choose which modes sync when the host script opens. Skipped modes will sync the first time you open or use them.",
            wraplength=520,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        do_not_autoload_var = tk.BooleanVar(value=self.do_not_autoload)
        ttk.Checkbutton(
            frame,
            text="Do not autoload",
            variable=do_not_autoload_var,
        ).grid(row=2, column=0, columnspan=3, sticky="w")
        ttk.Label(
            frame,
            text="When enabled, opening an unloaded mode will not sync it. It will load when you use Make Teams.",
            wraplength=520,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 8))

        vars_by_tour = {}
        row = 4
        for category in ["Random", "Watched", "Speed", "Inhouse"]:
            available = [(label, tour_id) for label, tour_id in CATEGORIES.get(category, []) if tour_id in TOURS and tour_id in self.loadable_tour_ids()]
            if not available:
                continue
            ttk.Label(frame, text=category, font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(8, 4))
            row += 1
            col = 0
            for label, tour_id in available:
                var = tk.BooleanVar(value=tour_id in self.boot_tour_ids)
                vars_by_tour[tour_id] = var
                ttk.Checkbutton(frame, text=label, variable=var).grid(row=row, column=col, sticky="w", padx=(0, 18), pady=2)
                col += 1
                if col >= 3:
                    col = 0
                    row += 1
            if col:
                row += 1

        button_row = ttk.Frame(frame)
        button_row.grid(row=row, column=0, columnspan=3, sticky="e", pady=(16, 0))

        def select_all():
            for var in vars_by_tour.values():
                var.set(True)

        def clear_all():
            for var in vars_by_tour.values():
                var.set(False)

        def save():
            self.boot_tour_ids = {tour_id for tour_id, var in vars_by_tour.items() if var.get()}
            self.do_not_autoload = do_not_autoload_var.get()
            self.save_ui_settings()
            self.set_status("Startup sync settings saved.")
            dialog.destroy()

        ttk.Button(button_row, text="Select All", command=select_all).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(button_row, text="Clear", command=clear_all).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(button_row, text="Cancel", command=dialog.destroy).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(button_row, text="Save", command=save).grid(row=0, column=3)

    def tour_load_event(self, tour_id):
        with self.tour_load_lock:
            event = self.tour_load_events.get(tour_id)
            if event is None:
                event = threading.Event()
                self.tour_load_events[tour_id] = event
            return event

    def mark_tour_load_finished(self, tour_id, success):
        with self.tour_load_lock:
            self.loading_tour_ids.discard(tour_id)
            if success:
                self.loaded_tour_ids.add(tour_id)
            event = self.tour_load_events.get(tour_id)
            if event is None:
                event = threading.Event()
                self.tour_load_events[tour_id] = event
            event.set()

    def start_lazy_load_tour(self, tour, reason=""):
        if not self.tour_requires_startup_load(tour):
            event = self.tour_load_event(tour["id"])
            event.set()
            return event

        tour_id = tour["id"]
        with self.tour_load_lock:
            if tour_id in self.loaded_tour_ids:
                event = self.tour_load_events.get(tour_id) or threading.Event()
                event.set()
                self.tour_load_events[tour_id] = event
                return event
            if tour_id in self.loading_tour_ids:
                return self.tour_load_events[tour_id]
            event = threading.Event()
            self.tour_load_events[tour_id] = event
            self.loading_tour_ids.add(tour_id)

        status = reason or f"Loading {tour['label']} before use..."
        self.after(0, lambda s=status: self.set_status(s))
        threading.Thread(target=self.lazy_load_tour_in_background, args=(tour,), daemon=True).start()
        return event

    def lazy_load_tour_in_background(self, tour):
        success = False
        try:
            self.startup_eloscrape_done.wait()

            def progress_callback(percent, message):
                status = f"Loading {tour['label']} - {message}" if message else f"Loading {tour['label']}"
                self.after(0, lambda p=percent, s=status: self.update_eloscrape_progress(p, s))

            self.sync_tour_mode_on_boot(tour, progress_callback)
            success = True
            self.after(0, lambda t=tour: self.update_eloscrape_progress(100, f"{t['label']} loaded."))
            self.after(0, self.refresh_elos)
            self.after(0, self.refresh_update_info)
        except Exception as exc:
            error_message = f"{tour['label']}: {type(exc).__name__}: {exc}"
            self.startup_eloscrape_errors.append(error_message)
            self.after(0, lambda e=error_message: self.update_eloscrape_progress(100, f"Load failed: {e}"))
        finally:
            self.mark_tour_load_finished(tour["id"], success)

    def wait_for_tour_loaded(self, tour_id):
        tour = TOURS[tour_id]
        if not self.tour_requires_startup_load(tour):
            return
        self.wait_for_startup_eloscrape()
        with self.tour_load_lock:
            loaded = tour_id in self.loaded_tour_ids
        if loaded:
            return
        event = self.start_lazy_load_tour(tour, f"Loading {tour['label']} before use...")
        event.wait()
        with self.tour_load_lock:
            loaded = tour_id in self.loaded_tour_ids
        if not loaded:
            raise RuntimeError(f"{tour['label']} could not finish loading. Check the startup sync message.")

    def startup_done_message(self, base_message):
        version_message = self.host_version_state.get("message", "")
        if version_message and self.host_version_state.get("status") != "checking":
            return f"{base_message}. {version_message}"
        return base_message

    def remember_startup_status(self, base_message):
        self.last_startup_status = base_message
        self.update_eloscrape_progress(100, self.startup_done_message(base_message))

    def start_host_version_check(self):
        threading.Thread(target=self.host_version_check_in_background, daemon=True).start()

    def host_version_check_in_background(self):
        state = self.host_updater.check_version()
        self.after(0, lambda s=state: self.finish_host_version_check(s))

    def finish_host_version_check(self, state):
        self.host_version_state = state
        if getattr(self, "update_script_button", None):
            if state.get("status") == "update_available":
                self.update_script_button.grid()
            else:
                self.update_script_button.grid_remove()
        if self.last_startup_status:
            self.update_eloscrape_progress(self.elo_progress_var.get(), self.startup_done_message(self.last_startup_status))

    def run_host_script_update(self):
        if self.version_update_running:
            return
        self.version_update_running = True
        self.update_script_button.configure(state="disabled")
        self.set_status("Updating host script...")
        threading.Thread(target=self.host_script_update_in_background, daemon=True).start()

    def host_script_update_in_background(self):
        try:
            result = self.host_updater.install_update()
            error = None
        except Exception as exc:
            result = ""
            error = f"{type(exc).__name__}: {exc}"
        self.after(0, lambda r=result, e=error: self.finish_host_script_update(r, e))

    def finish_host_script_update(self, result="", error=None):
        self.version_update_running = False
        self.update_script_button.configure(state="normal")
        if error:
            self.set_status("Update failed.")
            self.update_eloscrape_progress(self.elo_progress_var.get(), f"Update failed: {error}")
            return
        self.update_script_button.grid_remove()
        self.host_version_state["status"] = "up_to_date"
        self.host_version_state["message"] = result
        self.set_status(result)
        self.update_eloscrape_progress(self.elo_progress_var.get(), result)

    def apply_widget_theme(self):
        for widget in getattr(self, "tk_text_widgets", []):
            widget.configure(
                background=self.colors["field"],
                foreground=self.colors["text"],
                insertbackground=self.colors["text"],
                selectbackground=self.colors["accent"],
                inactiveselectbackground=self.colors["accent"],
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["accent"],
            )
            widget.tag_configure("placeholder", foreground=self.colors["placeholder"])
        for widget in getattr(self, "tk_list_widgets", []):
            widget.configure(
                background=self.colors["field"],
                foreground=self.colors["text"],
                selectbackground=self.colors["accent"],
                selectforeground=self.colors["selected_text"],
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["accent"],
            )
        if hasattr(self, "substitution_panel"):
            self.substitution_panel.apply_theme(self.colors)
        if hasattr(self, "tour_list_canvas"):
            self.tour_list_canvas.configure(
                background=self.colors["panel"],
                highlightbackground=self.colors["panel"],
            )

    def _build_layout(self):
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="AMQ Host Script", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Settings", command=self.open_settings_dialog).grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.update_script_button = ttk.Button(header, text="Update", command=self.run_host_script_update)
        self.update_script_button.grid(row=0, column=2, sticky="e", padx=(8, 0))
        self.update_script_button.grid_remove()
        for index, (label, url) in enumerate(LINKS.items(), start=3):
            ttk.Button(header, text=label, command=lambda u=url: webbrowser.open(u)).grid(row=0, column=index, sticky="e", padx=(8, 0))
        ttk.Checkbutton(header, text="Dark Mode", variable=self.dark_mode, command=self.toggle_theme).grid(row=0, column=len(LINKS) + 3, sticky="e", padx=(14, 0))
        self.elo_status_var = tk.StringVar(value="Eloscrape: waiting to start")
        ttk.Label(header, textvariable=self.elo_status_var).grid(row=1, column=0, columnspan=len(LINKS) + 4, sticky="w", pady=(4, 0))
        progress_row = ttk.Frame(header)
        progress_row.grid(row=2, column=0, columnspan=len(LINKS) + 4, sticky="ew", pady=(6, 0))
        progress_row.columnconfigure(0, weight=1)
        self.elo_progress_var = tk.DoubleVar(value=0)
        self.elo_progress_text_var = tk.StringVar(value="0%")
        self.elo_progress = ttk.Progressbar(progress_row, mode="determinate", maximum=100, variable=self.elo_progress_var)
        self.elo_progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_row, textvariable=self.elo_progress_text_var).grid(row=0, column=1, sticky="e", padx=(10, 0))

        sidebar = ttk.Frame(root, style="Panel.TFrame", padding=12)
        sidebar.grid(row=1, column=0, sticky="nsw", padx=(0, 14))
        sidebar.configure(width=190, height=600)
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(7, weight=1)
        ttk.Label(sidebar, text="Categories", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))

        for index, category in enumerate(["Random", "Watched", "Speed", "Inhouse"], start=1):
            button = ttk.Button(sidebar, text=category, width=18, command=lambda c=category: self.select_category(c))
            button.grid(row=index, column=0, sticky="ew", pady=3)
            self.category_buttons[category] = button

        ttk.Separator(sidebar).grid(row=5, column=0, sticky="ew", pady=12)
        ttk.Label(sidebar, text="Tour Types", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=6, column=0, sticky="w", pady=(0, 8))

        self.tour_list_canvas = tk.Canvas(sidebar, borderwidth=0, highlightthickness=0, height=260)
        self.tour_list_canvas.grid(row=7, column=0, columnspan=2, sticky="nsew")
        self.tour_list = ttk.Frame(self.tour_list_canvas, style="Panel.TFrame")
        self.tour_list_window = self.tour_list_canvas.create_window((0, 0), window=self.tour_list, anchor="nw")
        self.tour_list.columnconfigure(0, weight=1, minsize=166)
        self.tour_list_canvas.bind("<Configure>", self.on_tour_list_canvas_resize)
        self.tour_list.bind("<Configure>", self.update_tour_list_scrollregion)
        self.bind_tour_list_scroll(self.tour_list_canvas)
        self.bind_tour_list_scroll(self.tour_list)

        self.recalculate_button = ttk.Button(sidebar, text="Recalculate All", width=18, command=self.confirm_recalculate_all)
        self.recalculate_button.grid(row=8, column=0, columnspan=2, sticky="sew", pady=(12, 0))

        content = ttk.Frame(root)
        content.grid(row=1, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        self.tour_title = ttk.Label(content, text="", style="Title.TLabel")
        self.tour_title.grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.main_notebook = ttk.Notebook(content)
        self.main_notebook.grid(row=1, column=0, sticky="nsew")

        self.setup_tab = ttk.Frame(self.main_notebook, padding=14)
        self.solver_tab = ttk.Frame(self.main_notebook, padding=14)
        self.update_tab = ttk.Frame(self.main_notebook, padding=14)
        self.elos_tab = ttk.Frame(self.main_notebook, padding=14)

        self._build_setup_tab()
        self._build_solver_tab()
        self._build_update_tab()
        self._build_elos_tab()

    def _build_setup_tab(self):
        self.setup_tab.columnconfigure(1, weight=1)
        self.setup_tab.rowconfigure(3, weight=1)

        ttk.Label(self.setup_tab, text="Guess Time").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.setup_guess_combo = ttk.Combobox(self.setup_tab, textvariable=self.setup_guess_time, state="readonly", width=12)
        self.setup_guess_combo.grid(row=0, column=1, sticky="w", pady=(0, 8))
        self.setup_guess_combo.bind("<<ComboboxSelected>>", self.on_setup_changed)

        ttk.Label(self.setup_tab, text="Difficulty").grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.setup_difficulty_combo = ttk.Combobox(self.setup_tab, textvariable=self.setup_difficulty, state="readonly", width=12)
        self.setup_difficulty_combo.grid(row=1, column=1, sticky="w", pady=(0, 8))
        self.setup_difficulty_combo.bind("<<ComboboxSelected>>", self.on_setup_changed)

        self.setup_quagsual_check = ttk.Checkbutton(self.setup_tab, text="Quagsual", variable=self.setup_quagsual, command=self.on_setup_changed)
        self.setup_quagsual_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.setup_fey_watched_check = ttk.Checkbutton(self.setup_tab, text="Fey Watched", variable=self.setup_fey_watched, command=self.on_setup_changed)
        self.setup_fey_watched_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.setup_note = ttk.Label(self.setup_tab, text="", style="Subtle.TLabel")
        self.setup_note.grid(row=3, column=0, columnspan=2, sticky="nw", pady=(2, 0))

    def _build_solver_tab(self):
        self.solver_tab.columnconfigure(1, weight=1)
        self.solver_tab.rowconfigure(2, weight=1)
        self.solver_tab.rowconfigure(6, weight=1)

        controls = ttk.Frame(self.solver_tab)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        controls.columnconfigure(3, weight=1)

        ttk.Label(controls, text="Team Size").grid(row=0, column=0, sticky="w")
        self.team_size = tk.StringVar(value="4")
        ttk.Spinbox(controls, from_=1, to=12, width=6, textvariable=self.team_size).grid(row=0, column=1, padx=(8, 24), sticky="w")

        self.separate_t1 = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Separate T1s", variable=self.separate_t1).grid(row=0, column=2, padx=(0, 24), sticky="w")

        self.split_tour = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Split Tour", variable=self.split_tour).grid(row=0, column=3, sticky="w")

        ttk.Label(self.solver_tab, text="Players", font=("Segoe UI", 11, "bold")).grid(row=1, column=0, sticky="w")
        ttk.Label(self.solver_tab, text="Whitelist", font=("Segoe UI", 11, "bold")).grid(row=1, column=1, sticky="w", padx=(14, 0))

        self.players_text = tk.Text(self.solver_tab, height=12, wrap="word", borderwidth=1, relief="solid", font=("Segoe UI", 10))
        self.players_text.grid(row=2, column=0, sticky="nsew", pady=(6, 12), padx=(0, 14))
        self.players_text.tag_configure("placeholder", foreground="#94a3b8")
        self.tk_text_widgets.append(self.players_text)
        self.show_players_placeholder()
        self.players_text.bind("<FocusIn>", self.on_players_focus_in)
        self.players_text.bind("<FocusOut>", self.on_players_focus_out)
        self.players_text.bind("<<Modified>>", self.on_players_modified)

        whitelist_panel = ttk.Frame(self.solver_tab)
        whitelist_panel.grid(row=2, column=1, sticky="nsew", pady=(6, 12))
        whitelist_panel.columnconfigure(0, weight=1)
        whitelist_panel.columnconfigure(1, weight=1)
        whitelist_panel.rowconfigure(2, weight=1)
        self.whitelist_a = ttk.Combobox(whitelist_panel, values=[], state="normal")
        self.whitelist_b = ttk.Combobox(whitelist_panel, values=[], state="normal")
        self.whitelist_a.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.whitelist_b.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        for combobox in (self.whitelist_a, self.whitelist_b):
            combobox.bind("<FocusIn>", lambda _event, box=combobox: self.show_whitelist_dropdown(box))
            combobox.bind("<FocusOut>", lambda _event, box=combobox: self.schedule_whitelist_dropdown_hide(box))
            combobox.bind("<Button-1>", lambda event, box=combobox: self.on_whitelist_click(event, box))
            combobox.bind("<KeyRelease>", lambda event, box=combobox: self.on_whitelist_key_release(event, box))
            combobox.bind("<Return>", lambda _event, box=combobox: self.lock_whitelist_player(box))
        ttk.Button(whitelist_panel, text="Add Pair", command=self.add_whitelist_pair).grid(row=1, column=0, columnspan=2, sticky="ew", pady=8)
        list_frame = ttk.Frame(whitelist_panel)
        list_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.whitelist_list = tk.Listbox(list_frame, height=6, activestyle="none")
        self.whitelist_list.grid(row=0, column=0, sticky="nsew")
        self.tk_list_widgets.append(self.whitelist_list)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.whitelist_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.whitelist_list.configure(yscrollcommand=scrollbar.set)
        self.remove_pair_button = ttk.Button(whitelist_panel, text="Remove Selected Pair", command=self.remove_whitelist_pair)
        self.remove_pair_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        actions = ttk.Frame(self.solver_tab)
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.solver_button = ttk.Button(actions, text="Make Teams", style="Tool.TButton", command=self.run_solver)
        self.solver_button.pack(side="left")
        ttk.Button(actions, text="Copy Codes", command=lambda: self.clipboard_from_text(self.codes_text)).pack(side="left")

        self.rank_assignment_frame = ttk.Frame(self.solver_tab)
        self.rank_assignment_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.rank_assignment_frame.columnconfigure(0, weight=1)
        self.rank_assignment_header = ttk.Label(self.rank_assignment_frame, text="", font=("Segoe UI", 11, "bold"))
        self.rank_assignment_header.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.rank_fields = ttk.Frame(self.rank_assignment_frame)
        self.rank_fields.grid(row=1, column=0, sticky="ew")
        self.rank_assignment_note = ttk.Label(self.rank_assignment_frame, text="Enter numeric ratings for these players, then press Make Teams again.", style="Subtle.TLabel")
        self.rank_assignment_note.grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.rank_assignment_frame.grid_remove()

        ttk.Label(self.solver_tab, text="Codes", font=("Segoe UI", 11, "bold")).grid(row=5, column=0, columnspan=2, sticky="w")
        self.codes_text = tk.Text(self.solver_tab, height=10, wrap="word", borderwidth=1, relief="solid", font=("Consolas", 10))
        self.codes_text.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        self.tk_text_widgets.append(self.codes_text)
        self.apply_widget_theme()

    def _build_update_tab(self):
        self.update_tab.columnconfigure(0, weight=1)
        self.update_tab.columnconfigure(1, weight=1)
        self.update_tab.rowconfigure(4, weight=1)

        self.update_elos_button = ttk.Button(self.update_tab, text="Update Elos", style="Tool.TButton", command=self.run_update_elos)
        self.update_elos_button.grid(row=2, column=0, sticky="w")

        self.challonge_label = ttk.Label(self.update_tab, text="Challonge Link")
        self.challonge_label.grid(row=1, column=0, sticky="w", pady=(18, 4))
        self.challonge_input_row = ttk.Frame(self.update_tab)
        self.challonge_input_row.grid(row=2, column=0, sticky="ew", padx=(0, 12))
        self.challonge_input_row.columnconfigure(0, weight=1)
        self.challonge_link = ttk.Entry(self.challonge_input_row)
        self.challonge_link.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.challonge_run_button = ttk.Button(self.challonge_input_row, text="Run Eloscrape", command=self.run_manual_eloscrape)
        self.challonge_run_button.grid(row=0, column=1, sticky="e")

        self.selected_challonge_var = tk.StringVar(value="Select a Challonge")
        self.selected_challonge_label = ttk.Label(self.update_tab, textvariable=self.selected_challonge_var, font=("Segoe UI", 11, "bold"))
        self.selected_challonge_label.grid(row=1, column=1, sticky="w", pady=(18, 4))
        self.changelog_action_row = ttk.Frame(self.update_tab)
        self.changelog_action_row.grid(row=2, column=1, sticky="w")
        self.mvp_run_button = ttk.Button(self.changelog_action_row, text="Run MVPs", command=self.run_mvp_for_selected)
        self.mvp_run_button.pack(side="left")
        self.download_changelog_button = ttk.Button(self.changelog_action_row, text="Download", command=self.download_selected_changelog)
        self.download_changelog_button.pack(side="left", padx=(8, 0))
        self.download_mvps_button = ttk.Button(self.changelog_action_row, text="Save MVPs + Changelog", command=self.download_dry_outputs)
        self.download_mvps_button.pack(side="left", padx=(8, 0))

        self.history_heading_label = ttk.Label(self.update_tab, text="Challonges", font=("Segoe UI", 11, "bold"))
        self.history_heading_label.grid(row=3, column=0, sticky="w", pady=(18, 6))
        self.mvp_heading_label = ttk.Label(self.update_tab, text="MVPs", font=("Segoe UI", 11, "bold"))
        self.mvp_heading_label.grid(row=3, column=1, sticky="w", pady=(18, 6))

        self.results_frame = ttk.Frame(self.update_tab)
        self.results_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 10))
        self.results_frame.columnconfigure(6, weight=1)
        ttk.Label(self.results_frame, text="Rounds").grid(row=0, column=0, sticky="w")
        self.inhouse_round_count = tk.StringVar(value="")
        ttk.Spinbox(self.results_frame, from_=1, to=50, width=6, textvariable=self.inhouse_round_count).grid(row=0, column=1, sticky="w", padx=(8, 14))
        ttk.Button(self.results_frame, text="Build Result Rows", command=self.build_inhouse_result_rows).grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.inhouse_log_button = ttk.Button(self.results_frame, text="Log Results", style="Tool.TButton", command=self.run_log_inhouse_results)
        self.inhouse_log_button.grid(row=0, column=3, sticky="w")
        self.inhouse_changelog_button = ttk.Button(self.results_frame, text="View Changelog", command=self.run_view_inhouse_changelog)
        self.inhouse_changelog_button.grid(row=0, column=4, sticky="w", padx=(8, 0))
        self.inhouse_download_button = ttk.Button(self.results_frame, text="Download", command=self.download_selected_changelog)
        self.inhouse_download_button.grid(row=0, column=5, sticky="w", padx=(8, 0))
        self.inhouse_team_summary = ttk.Label(self.results_frame, text="", style="Subtle.TLabel")
        self.inhouse_team_summary.grid(row=1, column=0, columnspan=7, sticky="w", pady=(8, 4))
        self.inhouse_rows_frame = ttk.Frame(self.results_frame)
        self.inhouse_rows_frame.grid(row=2, column=0, columnspan=7, sticky="ew")
        self.results_frame.grid_remove()

        self.left_panel = ttk.Frame(self.update_tab)
        self.left_panel.grid(row=4, column=0, sticky="nsew", padx=(0, 12))
        self.left_panel.columnconfigure(0, weight=1)
        self.left_panel.rowconfigure(0, weight=1)
        self.challonge_list = tk.Listbox(self.left_panel, height=12, activestyle="none")
        self.challonge_list.grid(row=0, column=0, sticky="nsew")
        self.challonge_list.bind("<<ListboxSelect>>", self.on_challonge_selected)
        self.tk_list_widgets.append(self.challonge_list)
        challonge_scrollbar = ttk.Scrollbar(self.left_panel, orient="vertical", command=self.challonge_list.yview)
        challonge_scrollbar.grid(row=0, column=1, sticky="ns")
        self.challonge_list.configure(yscrollcommand=challonge_scrollbar.set)

        self.update_info = tk.Text(self.update_tab, height=12, wrap="word", borderwidth=1, relief="solid", font=("Segoe UI", 10))
        self.update_info.grid(row=4, column=1, sticky="nsew")
        self.tk_text_widgets.append(self.update_info)
        self.apply_widget_theme()

    def _build_elos_tab(self):
        self.elos_tab.columnconfigure(0, weight=2)
        self.elos_tab.columnconfigure(1, weight=3)
        self.elos_tab.rowconfigure(0, weight=1)

        elos_panel = ttk.Frame(self.elos_tab)
        elos_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        elos_panel.columnconfigure(0, weight=1)
        elos_panel.rowconfigure(1, weight=1)
        elos_controls = ttk.Frame(elos_panel)
        elos_controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        elos_controls.columnconfigure(1, weight=1)
        ttk.Label(elos_controls, text="Search").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.elos_search_entry = ttk.Entry(elos_controls, textvariable=self.elos_search_var)
        self.elos_search_entry.grid(row=0, column=1, sticky="ew")
        self.elos_search_entry.bind("<KeyRelease>", lambda _event: self.refresh_elos())
        self.elos_table = ttk.Treeview(elos_panel, columns=("player", "elo"), show="headings", height=20)
        self.elos_table.heading("player", text="Player")
        self.elos_table.heading("elo", text="Elo")
        self.elos_table.column("player", width=180, anchor="w", stretch=True)
        self.elos_table.column("elo", width=90, anchor="e", stretch=False)
        self.elos_table.grid(row=1, column=0, sticky="nsew")

        sub_panel = ttk.Frame(self.elos_tab)
        sub_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.substitution_panel = SubstitutionPanel(
            root=self,
            parent=sub_panel,
            get_tour=lambda: TOURS.get(self.selected_tour_id),
            normalize_key=self.normalize_alias_key,
            set_status=self.set_status,
            colors=self.colors,
        )

    def select_category(self, category: str, select_first=True):
        self.selected_category = category
        for name, button in self.category_buttons.items():
            button.configure(style="Selected.TButton" if name == category else "TButton")

        for child in self.tour_list.winfo_children():
            child.destroy()
        self.tour_buttons.clear()
        self.tour_list_canvas.yview_moveto(0)

        for row, (label, tour_id) in enumerate(CATEGORIES[category]):
            if tour_id and tour_id in TOURS:
                button = ttk.Button(self.tour_list, text=label, width=18, command=lambda tid=tour_id: self.select_tour(tid))
                button.grid(row=row, column=0, sticky="ew", pady=3)
                self.bind_tour_list_scroll(button)
                self.tour_buttons[tour_id] = button
            else:
                button = ttk.Button(self.tour_list, text=f"{label}  (soon)", width=18, state="disabled")
                button.grid(row=row, column=0, sticky="ew", pady=3)
                self.bind_tour_list_scroll(button)

        self.after_idle(self.update_tour_list_scrollregion)

        first_tour = next((tour_id for _, tour_id in CATEGORIES[category] if tour_id in TOURS), None)
        if first_tour and select_first:
            self.select_tour(first_tour)

    def on_tour_list_canvas_resize(self, event):
        self.tour_list_canvas.itemconfigure(self.tour_list_window, width=event.width)
        self.update_tour_list_scrollregion()

    def update_tour_list_scrollregion(self, _event=None):
        self.tour_list_canvas.configure(scrollregion=self.tour_list_canvas.bbox("all"))

    def bind_tour_list_scroll(self, widget):
        widget.bind("<MouseWheel>", self.on_tour_list_mousewheel, add="+")
        widget.bind("<Button-4>", lambda _event: self.tour_list_canvas.yview_scroll(-1, "units"), add="+")
        widget.bind("<Button-5>", lambda _event: self.tour_list_canvas.yview_scroll(1, "units"), add="+")

    def on_tour_list_mousewheel(self, event):
        if event.delta:
            self.tour_list_canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def select_tour(self, tour_id: str):
        self.selected_tour_id = tour_id
        tour = TOURS[tour_id]
        self.substitution_panel.select_tour(tour_id)
        if self.ui_ready:
            self.save_ui_settings()
        self.tour_title.configure(text=tour["label"])
        self.rank_check_generation += 1
        self.clear_rank_assignment()
        for key, button in self.tour_buttons.items():
            button.configure(style="Selected.TButton" if key == tour_id else "TButton")

        self._show_tour_tabs()
        self._set_update_tab_title(tour)
        self.refresh_setup_tab()
        self.update_challonge_input_visibility(tour)
        self.update_elos_button_visibility()
        self.refresh_elos()
        self.refresh_update_info()
        self.set_status(f"Selected {tour['label']}.")
        if self.ui_ready and not self.do_not_autoload and self.tour_requires_startup_load(tour):
            with self.tour_load_lock:
                loaded = tour_id in self.loaded_tour_ids
                loading = tour_id in self.loading_tour_ids
            if not loaded and not loading:
                if self.startup_eloscrape_running and tour_id in self.boot_tour_ids:
                    self.set_status(f"{tour['label']} is loading during startup sync.")
                else:
                    self.start_lazy_load_tour(tour, f"Loading {tour['label']} before use...")
        if self.ui_ready and (not self.do_not_autoload or self.is_tour_loaded(tour_id)):
            self.after_idle(self.schedule_rank_assignment_check)

    def _show_tour_tabs(self):
        tabs = self.main_notebook.tabs()
        for tab in tabs:
            self.main_notebook.forget(tab)
        if self.current_setup_key():
            self.main_notebook.add(self.setup_tab, text="Setup")
        self.main_notebook.add(self.solver_tab, text="Make Teams")
        self.main_notebook.add(self.update_tab, text="Eloscrape")
        self.main_notebook.add(self.elos_tab, text="Elos/Subs")

    def _set_update_tab_title(self, tour):
        update_title = "Results" if tour.get("supports_inhouse") else ("MVPs / Changelog" if tour.get("dry_elo") else "Eloscrape")
        if str(self.update_tab) in self.main_notebook.tabs():
            self.main_notebook.tab(str(self.update_tab), text=update_title)

    def refresh_setup_tab(self):
        setup_key = self.current_setup_key()
        self.setup_active_key = setup_key
        if not setup_key:
            self.current_setup_code = ""
            self.setup_note.configure(text="")
            return

        config = SETUP_CODES.get(setup_key, {})
        self.setup_guess_combo.configure(values=config.get("guess_times", []))
        self.setup_difficulty_combo.configure(values=config.get("difficulties", []))

        self.setup_guess_time.set(config.get("default_guess_time", ""))
        self.setup_difficulty.set(config.get("default_difficulty", ""))
        self.setup_quagsual.set(False)
        self.setup_fey_watched.set(False)

        if setup_key == "random":
            self.setup_quagsual_check.grid()
        else:
            self.setup_quagsual_check.grid_remove()
        if setup_key == "watched":
            self.setup_fey_watched_check.grid()
        else:
            self.setup_fey_watched_check.grid_remove()
        self.refresh_setup_code()

    def on_setup_changed(self, _event=None):
        self.refresh_setup_code()

    def refresh_setup_code(self):
        setup_key = self.setup_active_key
        self.current_setup_code = self.selected_setup_code()
        self.update_setup_control_states()
        config = SETUP_CODES.get(setup_key or "", {})
        difficulty = self.setup_difficulty.get()
        elo_difficulties = set(config.get("elo_difficulties", []))
        if setup_key == "random" and self.setup_quagsual.get():
            self.setup_note.configure(text="Counts for elo.")
        elif setup_key == "watched" and self.setup_fey_watched.get():
            self.setup_note.configure(text="Counts for elo.")
        elif difficulty in elo_difficulties:
            self.setup_note.configure(text="Counts for elo.")
        elif setup_key in {"random", "watched"}:
            self.setup_note.configure(text="Does not count for elo.")
        else:
            self.setup_note.configure(text="")

    def current_setup_key(self):
        return SETUP_TOURS.get(self.selected_tour_id)

    def selected_setup_code(self):
        setup_key = self.setup_active_key
        config = SETUP_CODES.get(setup_key or "", {})
        if setup_key == "random" and self.setup_quagsual.get():
            return config.get("quagsual", "")
        if setup_key == "watched" and self.setup_fey_watched.get():
            return config.get("fey_watched", "")
        return config.get("codes", {}).get(self.setup_guess_time.get(), {}).get(self.setup_difficulty.get(), "")

    def update_setup_control_states(self):
        if (
            (self.setup_active_key == "random" and self.setup_quagsual.get())
            or (self.setup_active_key == "watched" and self.setup_fey_watched.get())
        ):
            self.setup_guess_combo.configure(state="disabled")
            self.setup_difficulty_combo.configure(state="disabled")
            return
        self.setup_guess_combo.configure(state="readonly")
        self.setup_difficulty_combo.configure(state="readonly")

    def update_challonge_input_visibility(self, tour):
        widgets = (self.challonge_label, self.challonge_input_row)
        if tour.get("supports_inhouse"):
            for widget in widgets:
                widget.grid_remove()
            self.update_elos_button.grid_remove()
            self.selected_challonge_label.grid_remove()
            self.changelog_action_row.grid_remove()
            self.mvp_heading_label.configure(text="Log")
            self.results_frame.grid()
            self.refresh_inhouse_results_ui(tour)
            return

        self.selected_challonge_label.grid()
        self.changelog_action_row.grid()
        self.results_frame.grid_remove()
        self.download_changelog_button.pack_forget()
        self.download_mvps_button.pack_forget()
        if tour.get("dry_elo"):
            self.mvp_run_button.configure(text="Run MVPs", command=self.run_mvp_for_selected)
            self.download_mvps_button.pack(side="left", padx=(8, 0))
            self.mvp_heading_label.configure(text="MVPs")
            for widget in widgets:
                widget.grid_remove()
            self.update_elos_button.grid()
            return
        self.mvp_run_button.configure(text="View Changelog", command=self.run_view_changelog)
        self.download_changelog_button.pack(side="left", padx=(8, 0))
        self.mvp_heading_label.configure(text="Changelog")
        self.update_elos_button.grid_remove()
        self.challonge_label.grid()
        self.challonge_input_row.grid()

    def update_elos_button_visibility(self):
        tour = TOURS[self.selected_tour_id]
        if not tour.get("dry_elo"):
            self.update_elos_button.grid_remove()
            return
        self.update_elos_button.grid()

    def show_players_placeholder(self):
        self.players_placeholder_active = True
        self.players_text.delete("1.0", "end")
        self.players_text.insert("1.0", self.players_placeholder, "placeholder")
        self.players_text.edit_modified(False)

    def on_players_focus_in(self, _event=None):
        if self.players_placeholder_active:
            self.players_placeholder_active = False
            self.players_text.delete("1.0", "end")
            self.players_text.edit_modified(False)

    def on_players_focus_out(self, _event=None):
        if not self.players_text.get("1.0", "end").strip():
            self.show_players_placeholder()

    def on_players_modified(self, _event=None):
        if not self.players_text.edit_modified():
            return
        self.players_text.edit_modified(False)
        if self.players_placeholder_active:
            return
        self.clear_rank_assignment()
        self.after_idle(self.refresh_player_input_state)

    def refresh_player_input_state(self):
        self.refresh_player_selects(show_status=False)
        self.schedule_rank_assignment_check()

    def refresh_player_selects(self, show_status=True):
        players = [name for name, _rank in self.parse_player_entries(allow_placeholder=True)]
        self.whitelist_players = players
        self.filter_whitelist_players(self.whitelist_a)
        self.filter_whitelist_players(self.whitelist_b)
        if show_status:
            self.set_status(f"Loaded {len(players)} players into whitelist selectors.")

    def filter_whitelist_players(self, combobox):
        query = self.normalize_alias_key(combobox.get())
        players = [
            player
            for player in self.whitelist_players
            if not query or query in self.normalize_alias_key(player)
        ]
        combobox.configure(values=players)
        if self.whitelist_popup_target is combobox:
            self.populate_whitelist_popup(players)
        return players

    def ensure_whitelist_popup(self):
        if self.whitelist_popup is not None and self.whitelist_popup.winfo_exists():
            return
        self.whitelist_popup = tk.Toplevel(self)
        self.whitelist_popup.withdraw()
        self.whitelist_popup.overrideredirect(True)
        self.whitelist_popup.configure(bg=self.colors["border"])
        self.whitelist_popup.attributes("-topmost", True)

        frame = ttk.Frame(self.whitelist_popup, padding=1)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.whitelist_popup_list = tk.Listbox(frame, height=8, activestyle="none", exportselection=False)
        self.whitelist_popup_list.grid(row=0, column=0, sticky="nsew")
        self.whitelist_popup_list.bind("<ButtonRelease-1>", self.choose_whitelist_popup_player)
        self.whitelist_popup_list.bind("<Return>", self.choose_whitelist_popup_player)
        self.tk_list_widgets.append(self.whitelist_popup_list)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.whitelist_popup_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.whitelist_popup_list.configure(yscrollcommand=scrollbar.set)
        self.apply_widget_theme()

    def populate_whitelist_popup(self, players):
        if self.whitelist_popup_list is None:
            return
        self.whitelist_popup_list.delete(0, "end")
        for player in players:
            self.whitelist_popup_list.insert("end", player)
        if players:
            self.whitelist_popup_list.selection_set(0)

    def show_whitelist_dropdown(self, combobox):
        players = self.filter_whitelist_players(combobox)
        if not players:
            self.hide_whitelist_dropdown()
            return
        self.ensure_whitelist_popup()
        self.whitelist_popup_target = combobox
        self.populate_whitelist_popup(players)
        height = min(len(players), 8) * 22 + 4
        x = combobox.winfo_rootx()
        y = combobox.winfo_rooty() + combobox.winfo_height()
        self.whitelist_popup.geometry(f"{combobox.winfo_width()}x{height}+{x}+{y}")
        self.whitelist_popup.deiconify()
        self.whitelist_popup.lift()
        combobox.focus_set()

    def hide_whitelist_dropdown(self):
        if self.whitelist_popup is not None and self.whitelist_popup.winfo_exists():
            self.whitelist_popup.withdraw()
        self.whitelist_popup_target = None

    def schedule_whitelist_dropdown_hide(self, combobox):
        def hide_if_focus_left():
            focus = self.focus_get()
            if focus not in (combobox, self.whitelist_popup_list):
                self.hide_whitelist_dropdown()

        combobox.after(120, hide_if_focus_left)

    def on_whitelist_click(self, event, combobox):
        if event.x >= combobox.winfo_width() - 24:
            self.show_whitelist_dropdown(combobox)
            return "break"
        combobox.after_idle(lambda: self.show_whitelist_dropdown(combobox))

    def on_whitelist_key_release(self, event, combobox):
        if event.keysym in {"Return", "KP_Enter", "Up", "Down"}:
            return
        if event.keysym == "Escape":
            self.hide_whitelist_dropdown()
            return
        self.show_whitelist_dropdown(combobox)

    def choose_whitelist_popup_player(self, _event=None):
        if self.whitelist_popup_target is None or self.whitelist_popup_list is None:
            return "break"
        selected = self.whitelist_popup_list.curselection()
        if not selected:
            return "break"
        player = self.whitelist_popup_list.get(selected[0])
        target = self.whitelist_popup_target
        target.set(player)
        self.filter_whitelist_players(target)
        target.focus_set()
        self.hide_whitelist_dropdown()
        return "break"

    def lock_whitelist_player(self, combobox):
        player = self.resolve_whitelist_player(combobox.get())
        if player is None:
            query = self.normalize_alias_key(combobox.get())
            matches = [
                name
                for name in self.whitelist_players
                if not query or query in self.normalize_alias_key(name)
            ]
            player = matches[0] if matches else None
        if player is None:
            self.set_status("No matching player in the current player list.")
            return "break"
        combobox.set(player)
        self.filter_whitelist_players(combobox)
        self.hide_whitelist_dropdown()
        return "break"

    def resolve_whitelist_player(self, value):
        normalized_value = self.normalize_alias_key(value)
        if not normalized_value:
            return None
        matches = [
            player
            for player in self.whitelist_players
            if self.normalize_alias_key(player) == normalized_value
        ]
        return matches[0] if len(matches) == 1 else None

    def schedule_rank_assignment_check(self):
        self.rank_check_generation += 1
        generation = self.rank_check_generation
        try:
            player_entries = self.parse_player_entries(allow_placeholder=True)
        except ValueError:
            return
        if not player_entries:
            self.clear_rank_assignment()
            return
        tour_id = self.selected_tour_id
        if self.do_not_autoload and not self.is_tour_loaded(tour_id):
            self.hide_rank_assignment()
            return
        manual_ratings = self.manual_ratings()
        threading.Thread(
            target=self.rank_assignment_check_in_background,
            args=(generation, tour_id, player_entries, manual_ratings),
            daemon=True,
        ).start()

    def rank_assignment_check_in_background(self, generation, tour_id, player_entries, manual_ratings):
        try:
            self.wait_for_tour_loaded(tour_id)
            resolve_player_ratings(TOURS[tour_id], player_entries, manual_ratings, DATA_ROOT / "aliases.txt")
            missing = []
            error = None
        except MissingRatingsError as exc:
            missing = exc.names
            error = None
        except Exception as exc:
            missing = []
            error = f"{type(exc).__name__}: {exc}"
        self.after(0, lambda g=generation, m=missing, e=error: self.finish_rank_assignment_check(g, m, e))

    def finish_rank_assignment_check(self, generation, missing, error=None):
        if generation != self.rank_check_generation:
            return
        if error:
            self.set_status(f"Could not check player ratings: {error}")
            return
        if missing:
            self.show_rank_assignment(missing)
            self.set_status("Assign missing ratings.")
        else:
            self.hide_rank_assignment()

    def parse_player_entries(self, allow_placeholder=False):
        if self.players_placeholder_active:
            return [] if allow_placeholder else self.fail("Add players first.")

        raw = self.players_text.get("1.0", "end").replace("\n", ",")
        players = []
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue
            match = PLAYER_PATTERN.match(item)
            if not match:
                raise ValueError(f"Could not read player entry: {item}")
            name = match.group(1).strip().lower()
            rank = self.parse_pasted_rank(match.group(2))
            if name and name not in [player_name for player_name, _ in players]:
                players.append((name, rank))
        return players

    def parse_pasted_rank(self, rank_text):
        if rank_text is None:
            return None
        rank_text = rank_text.strip()
        try:
            return float(rank_text)
        except ValueError:
            return None

    def fail(self, message):
        raise ValueError(message)

    def add_whitelist_pair(self):
        player_a = self.resolve_whitelist_player(self.whitelist_a.get())
        player_b = self.resolve_whitelist_player(self.whitelist_b.get())
        if not player_a or not player_b:
            self.set_status("Type or select two players from the current player list.")
            return
        if player_a == player_b:
            self.set_status("Pick two different players for a whitelist pair.")
            return
        self.whitelist_list.insert("end", f"{player_a} + {player_b}")
        self.whitelist_a.set("")
        self.whitelist_b.set("")
        self.filter_whitelist_players(self.whitelist_a)
        self.filter_whitelist_players(self.whitelist_b)

    def remove_whitelist_pair(self):
        selected = list(self.whitelist_list.curselection())
        for index in reversed(selected):
            self.whitelist_list.delete(index)

    def whitelist_pairs(self):
        pairs = []
        for index in range(self.whitelist_list.size()):
            value = self.whitelist_list.get(index)
            if " + " in value:
                player_a, player_b = value.split(" + ", 1)
                pairs.append([player_a.strip().lower(), player_b.strip().lower()])
        return pairs

    def manual_ratings(self):
        current_players = {name for name, _rank in self.parse_player_entries(allow_placeholder=True)}
        ratings = {}
        for name, var in self.rank_vars.items():
            if name not in current_players:
                continue
            value = var.get().strip()
            if not value:
                continue
            try:
                ratings[name] = float(value)
            except ValueError as exc:
                raise ValueError(f"Rating for {name} must be numeric.") from exc
        return ratings

    def show_rank_assignment(self, missing):
        for child in self.rank_fields.winfo_children():
            child.destroy()

        self.rank_assignment_header.configure(text="Assign Missing Ratings")
        current_values = {name: var.get() for name, var in self.rank_vars.items()}
        self.rank_vars = {}

        for index, name in enumerate(missing):
            row = index // 3
            col = (index % 3) * 2
            ttk.Label(self.rank_fields, text=name).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=3)
            var = tk.StringVar(value=current_values.get(name, ""))
            ttk.Entry(self.rank_fields, textvariable=var, width=10).grid(row=row, column=col + 1, sticky="w", padx=(0, 18), pady=3)
            self.rank_vars[name] = var

        self.rank_assignment_frame.grid()

    def hide_rank_assignment(self):
        self.rank_assignment_frame.grid_remove()

    def clear_rank_assignment(self):
        for child in self.rank_fields.winfo_children():
            child.destroy()
        self.rank_vars = {}
        self.rank_assignment_frame.grid_remove()

    def run_solver(self):
        if self.solver_running:
            return
        try:
            snapshot = self.solver_snapshot()
        except Exception as exc:
            self.finish_solver(error=f"{type(exc).__name__}: {exc}")
            return
        self.solver_running = True
        self.solver_button.configure(state="disabled")
        self.codes_text.delete("1.0", "end")
        self.codes_text.insert("1.0", "Solving...\n")
        self.set_status("Solving...")
        threading.Thread(target=self.solve_in_background, args=(snapshot,), daemon=True).start()

    def solver_snapshot(self):
        player_entries = self.parse_player_entries()
        return {
            "tour_id": self.selected_tour_id,
            "team_size": int(self.team_size.get()),
            "separate_t1": self.separate_t1.get(),
            "split_tour": self.split_tour.get(),
            "player_entries": player_entries,
            "whitelist_pairs": self.whitelist_pairs(),
            "manual_ratings": self.manual_ratings(),
            "setup_code": self.current_setup_code,
        }

    def solve_in_background(self, snapshot):
        try:
            self.wait_for_startup_eloscrape(write_solver_note=True)
            self.wait_for_tour_loaded(snapshot["tour_id"])
            final_code = self.solve_selected_tour(snapshot)
        except MissingRatingsError as exc:
            missing_names = exc.names
            self.after(0, lambda names=missing_names: self.finish_solver(missing=names))
            return
        except Exception as exc:
            details = traceback.format_exc()
            error = f"{type(exc).__name__}: {exc}\n\n{details}"
            self.after(0, lambda error=error: self.finish_solver(error=error))
            return
        self.after(0, lambda: self.finish_solver(final_code=final_code))

    def wait_for_startup_eloscrape(self, write_solver_note=False):
        if not self.startup_eloscrape_done.is_set():
            self.after(0, lambda: self.set_status("Waiting for startup eloscrape..."))
            if write_solver_note:
                self.after(0, lambda: self.codes_text.insert("end", "Waiting for startup eloscrape to finish...\n"))
            self.startup_eloscrape_done.wait()

    def finish_solver(self, final_code=None, error=None, missing=None):
        self.solver_running = False
        self.solver_button.configure(state="normal")
        self.codes_text.delete("1.0", "end")
        if missing:
            self.show_rank_assignment(missing)
            self.codes_text.insert("1.0", "Some players need ratings before teams can be made.\n")
            self.set_status("Assign missing ratings.")
        elif error:
            self.codes_text.insert("1.0", error)
            self.set_status("Solver failed.")
        else:
            self.hide_rank_assignment()
            self.codes_text.insert("1.0", final_code)
            tour = TOURS[self.selected_tour_id]
            if tour.get("supports_inhouse"):
                self.refresh_inhouse_results_ui(tour)
            self.substitution_panel.reset_after_solver()
            self.set_status("Solver finished.")

    def solve_selected_tour(self, snapshot):
        tour = TOURS[snapshot["tour_id"]]
        from modules.main.hostSolver import save_latest_team_snapshot, solve_selected_tour

        final_code, team_snapshot = solve_selected_tour(tour, snapshot, DATA_ROOT / "aliases.txt")
        if team_snapshot:
            self.substitution_panel.set_snapshot(tour, team_snapshot)
            if tour.get("supports_inhouse"):
                self.latest_inhouse_teams[tour["id"]] = team_snapshot
            save_latest_team_snapshot(tour, team_snapshot)
        return final_code

    def normalize_alias_key(self, name):
        return normalize_alias_key(name)

    def run_manual_eloscrape(self):
        tour = TOURS[self.selected_tour_id]
        link = self.challonge_link.get().strip()
        if not link:
            self.set_status("Add a Challonge link first.")
            return
        if not tour.get("eloscrape"):
            self.set_status("This tour does not use manual Challonge eloscrape.")
            return
        self.challonge_run_button.configure(state="disabled")
        self.set_status("Running eloscrape...")
        threading.Thread(target=self.manual_eloscrape_in_background, args=(tour, link), daemon=True).start()

    def save_tourlist_link(self, tour, link):
        normalized_link = link.rstrip("/")
        tourlist_path = Path(tour["state_path"]) / "tourlist.txt"
        current_links = []
        if tourlist_path.exists():
            current_links = [line.strip().rstrip("/") for line in tourlist_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        updated_links = [normalized_link] + [current_link for current_link in current_links if current_link.lower() != normalized_link.lower()]
        tourlist_path.write_text("\n".join(updated_links) + "\n", encoding="utf-8")

    def manual_eloscrape_in_background(self, tour, link):
        try:
            self.wait_for_tour_loaded(tour["id"])
            self.sync_tour_from_sheet(tour)
            self.save_tourlist_link(tour, link)
            self.clear_eloscrape_local_state(tour)

            def progress_callback(percent, message):
                status = f"Eloscrape: {tour['label']} - {message}" if message else f"Eloscrape: {tour['label']}"
                self.after(0, lambda p=percent, s=status: self.update_eloscrape_progress(p, s))

            self.run_tour_eloscrape(
                tour,
                progress_callback,
                force_refresh_tour_ids=[self.tour_id_from_link(link)],
                force_refresh_tour_urls=[link],
            )
        except Exception as exc:
            details = traceback.format_exc()
            error = f"{type(exc).__name__}: {exc}\n\n{details}"
            self.after(0, lambda error=error: self.finish_manual_eloscrape(error=error))
            return
        self.after(0, lambda: self.finish_manual_eloscrape(tour=tour, selected_tour_id=self.tour_id_from_link(link)))

    def finish_manual_eloscrape(self, tour=None, selected_tour_id=None, error=None):
        self.challonge_run_button.configure(state="normal")
        if error:
            self.write_update_text(error)
            self.set_status("Eloscrape failed.")
            return
        self.update_eloscrape_progress(100, "Eloscrape finished")
        self.refresh_elos()
        if tour and not tour.get("dry_elo"):
            self.refresh_challonge_list(tour)
            if selected_tour_id:
                self.select_challonge_by_tour_id(selected_tour_id)
            try:
                self.write_update_text(self.selected_changelog_text(tour, selected_tour_id or self.selected_changelog_tour_id()))
                self.set_status("Changelog loaded.")
            except Exception as exc:
                self.write_update_text(f"{type(exc).__name__}: {exc}")
                self.set_status("Changelog failed.")
            return
        self.refresh_update_info()

    def start_startup_eloscrape(self):
        if self.startup_eloscrape_running or self.startup_eloscrape_done.is_set():
            return
        self.startup_eloscrape_running = True
        threading.Thread(target=self.run_startup_eloscrape, daemon=True).start()

    def confirm_recalculate_all(self):
        if self.recalculate_running:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Recalculate All")
        dialog.configure(bg=self.colors["bg"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            frame,
            text="Pressing Confirm will run eloscrape for all gamemodes from scratch. Continue?",
            wraplength=360,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        def close():
            dialog.grab_release()
            dialog.destroy()

        def confirm():
            close()
            self.run_recalculate_all()

        ttk.Button(frame, text="Cancel", command=close).grid(row=1, column=0, sticky="e", padx=(0, 8))
        ttk.Button(frame, text="Confirm", style="Tool.TButton", command=confirm).grid(row=1, column=1, sticky="e")
        dialog.protocol("WM_DELETE_WINDOW", close)
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def run_recalculate_all(self):
        if self.recalculate_running:
            return
        self.recalculate_running = True
        self.recalculate_button.configure(state="disabled")
        if self.startup_eloscrape_running and not self.startup_eloscrape_done.is_set():
            self.update_eloscrape_progress(0, "Waiting for current eloscrape before recalculating")
            threading.Thread(target=self.wait_then_recalculate_all, daemon=True).start()
            return
        self.start_recalculate_all_thread()

    def wait_then_recalculate_all(self):
        self.startup_eloscrape_done.wait()
        self.start_recalculate_all_thread()

    def start_recalculate_all_thread(self):
        self.startup_eloscrape_running = True
        self.startup_eloscrape_done.clear()
        with self.tour_load_lock:
            self.loaded_tour_ids.clear()
            self.loading_tour_ids = set(self.loadable_tour_ids())
            self.tour_load_events = {tour_id: threading.Event() for tour_id in self.loading_tour_ids}
        self.after(0, lambda: self.update_eloscrape_progress(0, "Eloscrape: recalculating all modes from scratch"))
        threading.Thread(target=self.recalculate_all_in_background, daemon=True).start()

    def recalculate_all_in_background(self):
        tours = [tour for tour in TOURS.values() if tour.get("eloscrape") or tour.get("inhouse") or tour.get("dry_elo")]
        total = len(tours)
        try:
            for index, tour in enumerate(tours, start=1):
                base_progress = 100 * (index - 1) / total if total else 0
                progress_span = 100 / total if total else 100

                def progress_callback(percent, message, t=tour, base=base_progress, span=progress_span):
                    overall = base + (span * percent / 100)
                    status = f"Recalculating: {t['label']} - {message}" if message else f"Recalculating: {t['label']}"
                    self.after(0, lambda p=overall, s=status: self.update_eloscrape_progress(p, s))

                self.after(0, lambda t=tour, p=base_progress: self.update_eloscrape_progress(p, f"Recalculating: {t['label']}"))
                try:
                    self.sync_tour_from_sheet(tour)
                    if tour.get("dry_elo"):
                        if progress_callback:
                            progress_callback(10, "Refreshing stats and elos")
                        from modules.support.mvpGenerator import update_dry_elos_for_tour

                        update_dry_elos_for_tour(tour)
                        if progress_callback:
                            progress_callback(100, "Dry elo updated")
                    else:
                        self.clear_eloscrape_local_state(tour)
                        self.run_tour_eloscrape(
                            tour,
                            progress_callback,
                            use_local_cache=False,
                            ignore_sheet_cache=True,
                        )
                    self.mark_tour_load_finished(tour["id"], True)
                    completed_progress = 100 * index / total if total else 100
                    self.after(0, lambda p=completed_progress, t=tour: self.update_eloscrape_progress(p, f"Recalculating: {t['label']} done"))
                except Exception as exc:
                    error_message = f"{tour['label']}: {type(exc).__name__}: {exc}"
                    self.startup_eloscrape_errors.append(error_message)
                    self.mark_tour_load_finished(tour["id"], False)
                    completed_progress = 100 * index / total if total else 100
                    self.after(0, lambda p=completed_progress, e=error_message: self.update_eloscrape_progress(p, f"Recalculate failed: {e}"))
            self.after(0, lambda: self.update_eloscrape_progress(100, "Eloscrape finished"))
        finally:
            self.recalculate_running = False
            self.startup_eloscrape_running = False
            self.startup_eloscrape_done.set()
            self.after(0, self.finish_recalculate_all)

    def clear_eloscrape_local_state(self, tour):
        state_path = Path(tour["state_path"])
        for filename in ("eloscrape_state.json", "eloscrape_cache.json"):
            path = state_path / filename
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def finish_recalculate_all(self):
        self.recalculate_button.configure(state="normal")
        self.refresh_elos()
        self.refresh_update_info()
        self.set_status("Eloscrape recalculation finished.")

    def run_startup_eloscrape(self):
        tours = [TOURS[tour_id] for tour_id in self.selected_boot_tour_ids()]
        total = len(tours)
        try:
            if not tours:
                self.after(0, lambda: self.remember_startup_status("Startup sync skipped"))
                return
            self.after(0, lambda: self.update_eloscrape_progress(0, "Sync: checking selected tour modes"))
            for index, tour in enumerate(tours, start=1):
                with self.tour_load_lock:
                    self.loading_tour_ids.add(tour["id"])
                    self.tour_load_events[tour["id"]] = threading.Event()
                base_progress = 100 * (index - 1) / total if total else 0
                progress_span = 100 / total if total else 100

                def progress_callback(percent, message, t=tour, base=base_progress, span=progress_span):
                    overall = base + (span * percent / 100)
                    status = f"Sync: {t['label']} - {message}" if message else f"Sync: {t['label']}"
                    self.after(0, lambda p=overall, s=status: self.update_eloscrape_progress(p, s))

                self.after(0, lambda t=tour, p=base_progress: self.update_eloscrape_progress(p, f"Sync: {t['label']}"))
                try:
                    self.sync_tour_mode_on_boot(tour, progress_callback)
                    self.mark_tour_load_finished(tour["id"], True)
                    completed_progress = 100 * index / total if total else 100
                    self.after(0, lambda p=completed_progress, t=tour: self.update_eloscrape_progress(p, f"Sync: {t['label']} done"))
                except Exception as exc:
                    error_message = f"{tour['label']}: {type(exc).__name__}: {exc}"
                    self.startup_eloscrape_errors.append(error_message)
                    self.mark_tour_load_finished(tour["id"], False)
                    completed_progress = 100 * index / total if total else 100
                    self.after(0, lambda p=completed_progress, e=error_message: self.update_eloscrape_progress(p, f"Sync failed: {e}"))
            self.after(0, lambda: self.remember_startup_status("Eloscrape finished"))
        finally:
            self.startup_eloscrape_running = False
            self.startup_eloscrape_done.set()
            self.after(0, self.refresh_elos)
            self.after(0, self.refresh_update_info)

    def sync_tour_mode_on_boot(self, tour, progress_callback):
        if tour.get("eloscrape") or tour.get("inhouse"):
            self.sync_tour_from_sheet(tour)
            self.run_tour_eloscrape(tour, progress_callback, use_local_cache=True)
            return
        if tour.get("dry_elo"):
            if progress_callback:
                progress_callback(10, "Refreshing stats and elos")
            from modules.support.mvpGenerator import update_dry_elos_for_tour

            update_dry_elos_for_tour(tour)
            if progress_callback:
                progress_callback(100, "Dry elo updated")

    def sync_tour_from_sheet(self, tour):
        self.sync_ids_from_sheet_if_available(tour)
        if tour.get("eloscrape"):
            self.sync_tourlist_from_sheet(tour)

    def sync_ids_from_sheet_if_available(self, tour):
        sheet_cfg = tour.get("sheet", {})
        if not sheet_cfg.get("tab_ids"):
            return
        from utils import sync_ids_from_sheet

        sync_ids_from_sheet(
            tour["state_path"],
            sheetName=sheet_cfg.get("name", "NGM Stats Export v2"),
            tabIDs=sheet_cfg["tab_ids"],
        )

    def sync_tourlist_from_sheet(self, tour):
        from modules.support.readCredentials import readCredentials

        scrape_cfg = tour["eloscrape"]
        tourlist_cell = scrape_cfg.get("tourlist_cell")
        if not tourlist_cell:
            return

        sheet_name = scrape_cfg.get("sheet_name", tour["sheet"]["name"])
        storage_gid = scrape_cfg.get("elo_storage_gid", tour["sheet"]["elo_storage_gid"])
        gc = readCredentials(tour["state_path"])
        sheet = gc.open(sheet_name)
        wks = sheet.get_worksheet_by_id(storage_gid)
        values = wks.get_values(tourlist_cell)
        sheet_text = values[0][0] if values and values[0] else ""
        links = []
        seen = set()
        for line in sheet_text.splitlines():
            link = line.strip().rstrip("/")
            if not link:
                continue
            key = link.lower()
            if key in seen:
                continue
            links.append(link)
            seen.add(key)

        tourlist_path = Path(tour["state_path"]) / "tourlist.txt"
        tourlist_path.write_text(("\n".join(links) + "\n") if links else "", encoding="utf-8")

    def run_tour_eloscrape(
            self,
            tour,
            progress_callback=None,
            use_local_cache=False,
            force_refresh_tour_ids=None,
            force_refresh_tour_urls=None,
            ignore_sheet_cache=False,
        ):
        from modules.main.eloscrape import EloScrape

        cache_signature = self.eloscrape_cache_signature(tour)
        if use_local_cache:
            if self.eloscrape_cache_is_current(tour, cache_signature):
                if progress_callback:
                    progress_callback(100, "Local cache up to date")
                return "cached"
            if tour.get("eloscrape") or tour.get("inhouse"):
                self.clear_eloscrape_local_state(tour)

        if tour.get("eloscrape"):
            scrape_cfg = tour["eloscrape"]
            eloscraper = EloScrape(
                directory=tour["state_path"],
                tabEloStorage=scrape_cfg.get("elo_storage_gid", tour["sheet"]["elo_storage_gid"]),
                tabEloStorageCell=scrape_cfg.get("elo_storage_cell", tour["sheet"]["elo_storage_cell"]),
                sheetName=scrape_cfg.get("sheet_name", tour["sheet"]["name"]),
                cache_mode=scrape_cfg.get("cache_mode"),
                **scrape_cfg["trueskill"],
            )
            asyncio.run(eloscraper.eloscrape(
                tourlist_cell=scrape_cfg["tourlist_cell"],
                progress_callback=progress_callback,
                force_refresh_tour_ids=force_refresh_tour_ids,
                force_refresh_tour_urls=force_refresh_tour_urls,
                ignore_sheet_cache=ignore_sheet_cache,
            ))
            self.write_eloscrape_cache_manifest(tour, cache_signature)
            return "updated"

        if tour.get("inhouse"):
            inhouse_cfg = tour["inhouse"]
            eloscraper = EloScrape(
                directory=tour["state_path"],
                tabEloStorage=tour["sheet"]["elo_storage_gid"],
                tabEloStorageCell=tour["sheet"]["elo_storage_cell"],
                sheetName=tour["sheet"]["name"],
                cache_mode=inhouse_cfg.get("cache_mode"),
                inhouse_type=inhouse_cfg.get("inhouse_type"),
                **inhouse_cfg["trueskill"],
            )
            asyncio.run(eloscraper.eloscrape(
                backlog_cell=inhouse_cfg.get("backlog_cell"),
                progress_callback=progress_callback,
                ignore_sheet_cache=ignore_sheet_cache,
            ))
            self.write_eloscrape_cache_manifest(tour, cache_signature)
            return "updated"

    def eloscrape_cache_signature(self, tour):
        payload = {
            "version": 3,
            "tour_id": tour["id"],
            "cache_mode": tour.get("eloscrape", {}).get("cache_mode") or tour.get("inhouse", {}).get("cache_mode"),
            "trueskill": tour.get("eloscrape", {}).get("trueskill") or tour.get("inhouse", {}).get("trueskill"),
        }

        if tour.get("eloscrape"):
            payload["source"] = "tourlist"
            payload["tourlist"] = self.tourlist_links(tour)
        elif tour.get("inhouse"):
            payload["source"] = "inhouseData"
            payload["events"] = self.inhouse_signature_events(tour)
            if payload["events"] is None:
                payload["unavailable_at"] = datetime.now(timezone.utc).isoformat()

        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return {
            "version": payload["version"],
            "source": payload.get("source"),
            "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "payload": payload,
        }

    def inhouse_signature_events(self, tour):
        try:
            from modules.support.inhouseData import load_inhouse_tours

            events = load_inhouse_tours(tour["state_path"], tour["inhouse"]["inhouse_type"])
        except Exception:
            return None
        simplified = []
        for event in events:
            matches = []
            for round_key, round_matches in sorted(event.get("matches_by_round", {}).items(), key=lambda item: str(item[0])):
                for match in round_matches:
                    matches.append({
                        "round": round_key,
                        "p1": match.get("player1", {}).get("id"),
                        "p2": match.get("player2", {}).get("id"),
                        "winner": match.get("winner_id"),
                        "loser": match.get("loser_id"),
                        "scores": match.get("scores", {}),
                    })
            simplified.append({
                "tour_id": event.get("tour_id"),
                "time": str(event.get("time")),
                "matches": matches,
            })
        return simplified

    def eloscrape_cache_is_current(self, tour, signature):
        state_path = Path(tour["state_path"])
        if not (state_path / "elos.json").exists():
            return False
        if not (state_path / "eloscrape_state.json").exists():
            return False
        if tour.get("eloscrape") and self.tourlist_links(tour) and not (state_path / "elo_history.json").exists():
            return False
        if tour.get("eloscrape") and self.tourlist_links(tour) and not (state_path / "elo_history_latest.json").exists():
            return False

        manifest_path = state_path / "eloscrape_cache.json"
        if not manifest_path.exists():
            return False
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return manifest.get("hash") == signature.get("hash")

    def write_eloscrape_cache_manifest(self, tour, signature):
        manifest = {
            "hash": signature.get("hash"),
            "source": signature.get("source"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        path = Path(tour["state_path"]) / "eloscrape_cache.json"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def update_eloscrape_progress(self, percent, message):
        percent = max(0, min(100, percent))
        self.elo_progress_var.set(percent)
        self.elo_progress_text_var.set(f"{percent:.0f}%")
        self.set_eloscrape_status(message)

    def set_eloscrape_status(self, message):
        self.elo_status_var.set(message)
        self.set_status(message)

    def refresh_update_info(self):
        tour = TOURS[self.selected_tour_id]
        self.refresh_challonge_list(tour)
        self.write_update_text(self.default_update_text(tour))

    def refresh_challonge_list(self, tour):
        self.challonge_items = []
        self.challonge_list.delete(0, "end")
        if tour.get("supports_inhouse"):
            self.history_heading_label.configure(text="History")
            self.selected_challonge_var.set("In-house Results")
            self.refresh_inhouse_event_list(tour)
            return
        if tour.get("dry_elo"):
            self.refresh_previous_tour_list(tour)
            return

        self.history_heading_label.configure(text="Challonges")
        links = self.tourlist_links(tour)
        dates = self.tour_history_dates(tour)
        rows = []
        for fallback_index, link in enumerate(links):
            tour_id = self.tour_id_from_link(link)
            tour_time = dates.get(tour_id, "")
            date_label = tour_time[:10] if tour_time else "No date"
            rows.append((tour_time, fallback_index, date_label, link, tour_id))

        rows.sort(key=lambda item: (self.history_sort_value(item[0]), -item[1]), reverse=True)
        self.challonge_items = rows
        for _tour_time, _fallback_index, date_label, link, _tour_id in rows:
            self.challonge_list.insert("end", f"{date_label}  {link}")

        if rows:
            self.challonge_list.selection_set(0)
            self.on_challonge_selected()
        else:
            self.selected_challonge_var.set("No Challonge selected")

    def refresh_previous_tour_list(self, tour):
        self.history_heading_label.configure(text="Previous Tours")
        rows = self.previous_tour_rows(tour)
        self.challonge_items = rows
        for timestamp, fallback_index, date_label, detail, tour_key in rows:
            self.challonge_list.insert("end", f"{date_label}  {detail}")

        if rows:
            self.challonge_list.selection_set(0)
            self.on_challonge_selected()
        else:
            self.selected_challonge_var.set("No previous tour selected")

    def previous_tour_rows(self, tour):
        return hostHistory.previous_tour_rows(tour)

    def default_update_text(self, tour):
        if tour.get("dry_elo"):
            return self.dry_elo_report_text(tour)
        if tour.get("supports_inhouse"):
            return "Make teams, build result rows, then log the finished rounds."
        return ""

    def dry_elo_report_text(self, tour, mvp_text=None, intro=None):
        sections = []
        if intro:
            sections.append(intro)
        if mvp_text is not None:
            sections.append(mvp_text.strip())
        else:
            mvps = self._read_text(tour, "mvps.txt", "").strip()
            if mvps:
                sections.append(mvps)

        changelog = self._read_text(tour, "changelog.txt", "").strip()
        if not changelog:
            changelog = "No rating changes >= 0.15."
        sections.append("# Changelog\n" + changelog)
        return "\n\n".join(sections)

    def mvp_report_text(self, tour, mvp_text):
        if tour and tour.get("dry_elo"):
            return self.dry_elo_report_text(tour, mvp_text=mvp_text)
        return mvp_text.strip()

    def load_latest_inhouse_teams(self, tour):
        if tour["id"] in self.latest_inhouse_teams:
            return self.latest_inhouse_teams[tour["id"]]
        path = Path(tour["state_path"]) / "latest_inhouse_teams.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        self.latest_inhouse_teams[tour["id"]] = data
        return data

    def refresh_inhouse_results_ui(self, tour):
        if not hasattr(self, "inhouse_team_summary"):
            return
        data = self.load_latest_inhouse_teams(tour)
        if not data:
            self.inhouse_team_summary.configure(text="Make teams first, then come back here to record results.")
            self.clear_inhouse_result_rows()
            return
        self.clear_inhouse_result_rows()
        self.inhouse_team_summary.configure(text="Select teams by their T1 names, enter scores, then log results.")

    def clear_inhouse_result_rows(self):
        if not hasattr(self, "inhouse_rows_frame"):
            return
        for child in self.inhouse_rows_frame.winfo_children():
            child.destroy()
        self.inhouse_result_rows = []

    def build_inhouse_result_rows(self):
        tour = TOURS[self.selected_tour_id]
        data = self.load_latest_inhouse_teams(tour)
        self.clear_inhouse_result_rows()
        if not data:
            return
        teams = data.get("teams", {})
        team_labels = [team["label"] for team in teams.values()]
        if len(team_labels) < 2:
            self.inhouse_team_summary.configure(text="At least two teams are needed to log in-house results.")
            return
        team_id_by_label = {team["label"]: team_id for team_id, team in teams.items()}
        rounds_text = self.inhouse_round_count.get().strip()
        if not rounds_text:
            self.inhouse_team_summary.configure(text="Enter the number of rounds, then click Build Result Rows.")
            return
        rounds = int(rounds_text)
        if rounds <= 0:
            raise ValueError("Rounds must be at least 1.")

        headers = ["Round", "Team A", "Score", "Team B", "Score"]
        for column, label in enumerate(headers):
            ttk.Label(self.inhouse_rows_frame, text=label, font=("Segoe UI", 9, "bold")).grid(row=0, column=column, sticky="w", padx=(0, 8), pady=(0, 4))

        self.inhouse_result_rows = []
        for round_number in range(1, rounds + 1):
            row_index = round_number
            team1_var = tk.StringVar(value=team_labels[0])
            team2_var = tk.StringVar(value=team_labels[1])
            team1_score = tk.StringVar(value="")
            team2_score = tk.StringVar(value="")

            ttk.Label(self.inhouse_rows_frame, text=str(round_number)).grid(row=row_index, column=0, sticky="w", padx=(0, 8), pady=2)
            ttk.Combobox(self.inhouse_rows_frame, textvariable=team1_var, values=team_labels, state="readonly", width=18).grid(row=row_index, column=1, sticky="ew", padx=(0, 8), pady=2)
            ttk.Entry(self.inhouse_rows_frame, textvariable=team1_score, width=6).grid(row=row_index, column=2, sticky="w", padx=(0, 8), pady=2)
            ttk.Combobox(self.inhouse_rows_frame, textvariable=team2_var, values=team_labels, state="readonly", width=18).grid(row=row_index, column=3, sticky="ew", padx=(0, 8), pady=2)
            ttk.Entry(self.inhouse_rows_frame, textvariable=team2_score, width=6).grid(row=row_index, column=4, sticky="w", padx=(0, 8), pady=2)
            self.inhouse_result_rows.append({
                "round": round_number,
                "team1": team1_var,
                "team2": team2_var,
                "team1_score": team1_score,
                "team2_score": team2_score,
                "team_id_by_label": team_id_by_label,
            })

    def run_log_inhouse_results(self):
        if self.inhouse_logging:
            return
        try:
            tour = TOURS[self.selected_tour_id]
            event = self.build_inhouse_event()
        except Exception as exc:
            self.write_update_text(f"{type(exc).__name__}: {exc}")
            self.set_status("Could not log in-house results.")
            return
        self.inhouse_logging = True
        self.inhouse_log_button.configure(state="disabled")
        self.write_update_text("Logging in-house results...")
        self.set_status("Logging in-house results...")
        threading.Thread(target=self.log_inhouse_results_background, args=(tour, event), daemon=True).start()

    def build_inhouse_event(self):
        tour = TOURS[self.selected_tour_id]
        data = self.load_latest_inhouse_teams(tour)
        if not data:
            raise ValueError("Make teams before logging results.")
        if not self.inhouse_result_rows:
            raise ValueError("Build result rows first.")

        event_time = datetime.now(timezone.utc)
        event_id = f"{tour['id']}_{event_time.strftime('%Y%m%d_%H%M%S')}"
        matches = []
        for row in self.inhouse_result_rows:
            team1_id = row["team_id_by_label"][row["team1"].get()]
            team2_id = row["team_id_by_label"][row["team2"].get()]
            if team1_id == team2_id:
                raise ValueError(f"Round {row['round']} uses the same team twice.")
            score1 = int(row["team1_score"].get())
            score2 = int(row["team2_score"].get())
            if score1 == score2:
                winner_id = None
                loser_id = None
            elif score1 > score2:
                winner_id = team1_id
                loser_id = team2_id
            else:
                winner_id = team2_id
                loser_id = team1_id
            matches.append({
                "round": row["round"],
                "team1_id": team1_id,
                "team2_id": team2_id,
                "team1_score": score1,
                "team2_score": score2,
                "winner": winner_id,
                "loser": loser_id,
            })

        return {
            "source": "inhouse",
            "inhouse_type": tour["inhouse"]["inhouse_type"],
            "tour_id": event_id,
            "time": event_time.isoformat(),
            "teams": data["teams"],
            "matches": matches,
        }

    def log_inhouse_results_background(self, tour, event):
        try:
            from modules.support.inhouseData import append_inhouse_event

            self.wait_for_tour_loaded(tour["id"])
            rows_written = append_inhouse_event(tour["state_path"], event)
            self.run_tour_eloscrape(tour)
        except Exception as exc:
            details = traceback.format_exc()
            error = f"{type(exc).__name__}: {exc}\n\n{details}"
            self.after(0, lambda error=error: self.finish_log_inhouse_results(error=error))
            return
        self.after(0, lambda: self.finish_log_inhouse_results(rows_written=rows_written))

    def finish_log_inhouse_results(self, rows_written=0, error=None):
        self.inhouse_logging = False
        self.inhouse_log_button.configure(state="normal")
        if error:
            self.write_update_text(error)
            self.set_status("In-house logging failed.")
            return
        self.refresh_elos()
        tour = TOURS[self.selected_tour_id]
        self.refresh_challonge_list(tour)
        try:
            changelog_text = self.latest_changelog_text(tour)
        except Exception as exc:
            self.write_update_text(
                f"Logged {rows_written} result rows to inhouseData and updated elos.\n\n"
                f"Could not load latest changelog: {type(exc).__name__}: {exc}"
            )
            self.set_status("In-house results logged.")
            return
        self.write_update_text(f"Logged {rows_written} result rows to inhouseData and updated elos.\n\n{changelog_text}")
        self.set_status("In-house results logged. Changelog loaded.")

    def run_view_inhouse_changelog(self):
        if self.mvp_running:
            return
        tour = TOURS[self.selected_tour_id]
        self.mvp_running = True
        self.inhouse_changelog_button.configure(state="disabled")
        self.write_update_text("Loading changelog...")
        self.set_status("Loading in-house changelog...")
        selected_tour_id = self.selected_changelog_tour_id()
        threading.Thread(target=self.inhouse_changelog_in_background, args=(tour, selected_tour_id), daemon=True).start()

    def inhouse_changelog_in_background(self, tour, selected_tour_id=None):
        try:
            self.wait_for_tour_loaded(tour["id"])
            self.run_tour_eloscrape(tour, use_local_cache=True)
            changelog_text = self.selected_changelog_text(tour, selected_tour_id)
        except Exception as exc:
            details = traceback.format_exc()
            error = f"{type(exc).__name__}: {exc}\n\n{details}"
            self.after(0, lambda error=error: self.finish_inhouse_changelog(error=error))
            return
        self.after(0, lambda: self.finish_inhouse_changelog(changelog_text=changelog_text))

    def finish_inhouse_changelog(self, changelog_text=None, error=None):
        self.mvp_running = False
        self.inhouse_changelog_button.configure(state="normal")
        if error:
            self.write_update_text(error)
            self.set_status("In-house changelog failed.")
            return
        self.write_update_text(changelog_text or "")
        self.set_status("In-house changelog loaded.")

    def refresh_inhouse_event_list(self, tour):
        rows = hostHistory.inhouse_history_rows(tour)
        self.challonge_items = rows
        for _event_time, _fallback_index, _date_label, label, _event_id in rows:
            self.challonge_list.insert("end", label)

        if rows:
            self.challonge_list.selection_set(0)
            self.on_challonge_selected()
        else:
            self.selected_challonge_var.set("No in-house history selected")

    def tourlist_links(self, tour):
        return hostHistory.tourlist_links(tour)

    def tour_history_dates(self, tour):
        return hostHistory.tour_history_dates(tour)

    def history_sort_value(self, value):
        return hostHistory.history_sort_value(value)

    def tour_id_from_link(self, link):
        return hostHistory.tour_id_from_link(link)

    def on_challonge_selected(self, _event=None):
        selected = self.challonge_list.curselection()
        if not selected:
            return
        index = selected[0]
        if index >= len(self.challonge_items):
            return
        _tour_time, _fallback_index, date_label, link, _tour_id = self.challonge_items[index]
        self.selected_challonge_var.set(f"{date_label}  {link}")

    def select_challonge_by_tour_id(self, tour_id):
        selected_key = str(tour_id).strip().lower()
        for index, item in enumerate(self.challonge_items):
            if str(item[4]).strip().lower() == selected_key:
                self.challonge_list.selection_clear(0, "end")
                self.challonge_list.selection_set(index)
                self.challonge_list.see(index)
                self.on_challonge_selected()
                return True
        return False

    def run_update_elos(self):
        if self.update_elos_running:
            return
        tour = TOURS[self.selected_tour_id]
        if not tour.get("dry_elo"):
            self.set_status("This tour does not use dry elo updates.")
            return
        self.update_elos_running = True
        self.update_elos_button.configure(state="disabled")
        self.write_update_text("Updating elos...")
        self.set_status("Updating elos...")
        threading.Thread(target=self.update_elos_in_background, args=(tour,), daemon=True).start()

    def update_elos_in_background(self, tour):
        try:
            from modules.support.mvpGenerator import update_dry_elos_for_tour

            self.wait_for_tour_loaded(tour["id"])
            updated_elos = update_dry_elos_for_tour(tour)
        except Exception as exc:
            details = traceback.format_exc()
            error = f"{type(exc).__name__}: {exc}\n\n{details}"
            self.after(0, lambda error=error: self.finish_update_elos(error=error))
            return
        self.after(0, lambda: self.finish_update_elos(tour=tour, updated_count=len(updated_elos)))

    def finish_update_elos(self, tour=None, updated_count=0, error=None):
        self.update_elos_running = False
        self.update_elos_button.configure(state="normal")
        if error:
            self.write_update_text(error)
            self.set_status("Update elos failed.")
            return
        self.refresh_elos()
        if tour:
            self.refresh_challonge_list(tour)
        self.write_update_text("Elos have been updated. Select your tour from the list of previous tours and press Run MVPs")
        self.set_status("Elos updated.")

    def run_view_changelog(self):
        if self.mvp_running:
            return
        tour = TOURS[self.selected_tour_id]
        if tour.get("dry_elo"):
            self.run_mvp_for_selected()
            return
        self.mvp_running = True
        self.mvp_run_button.configure(state="disabled")
        self.download_changelog_button.configure(state="disabled")
        message = "Waiting for eloscrape to finish..." if self.startup_eloscrape_running else "Loading changelog..."
        self.write_update_text(message)
        self.set_status(message)
        threading.Thread(target=self.changelog_in_background, args=(tour, self.selected_changelog_tour_id()), daemon=True).start()

    def changelog_in_background(self, tour, selected_tour_id=None):
        try:
            self.wait_for_tour_loaded(tour["id"])
            if tour.get("eloscrape"):
                self.sync_tour_from_sheet(tour)
                self.run_tour_eloscrape(tour, use_local_cache=True)
            changelog_text = self.selected_changelog_text(tour, selected_tour_id)
        except Exception as exc:
            details = traceback.format_exc()
            error = f"{type(exc).__name__}: {exc}\n\n{details}"
            self.after(0, lambda error=error: self.finish_view_changelog(error=error))
            return
        self.after(0, lambda: self.finish_view_changelog(tour=tour, changelog_text=changelog_text))

    def finish_view_changelog(self, tour=None, changelog_text=None, error=None):
        self.mvp_running = False
        self.mvp_run_button.configure(state="normal")
        self.download_changelog_button.configure(state="normal")
        if error:
            self.write_update_text(error)
            self.set_status("Changelog failed.")
            return
        self.write_update_text(changelog_text or "")
        self.set_status("Changelog loaded.")

    def latest_changelog_path(self, tour):
        return hostHistory.latest_changelog_path(tour)

    def selected_changelog_tour_id(self):
        selected = self.challonge_list.curselection()
        if selected:
            index = selected[0]
            if index < len(self.challonge_items):
                return self.challonge_items[index][4]
        return None

    def selected_changelog_entry(self, tour, selected_tour_id=None):
        return hostHistory.selected_changelog_entry(tour, selected_tour_id)

    def selected_changelog_text(self, tour, selected_tour_id=None):
        return hostHistory.selected_changelog_text(tour, selected_tour_id)

    def latest_changelog_text(self, tour):
        return hostHistory.latest_changelog_text(tour)

    def download_selected_changelog(self):
        tour = TOURS[self.selected_tour_id]
        selected_tour_id = self.selected_changelog_tour_id()
        try:
            changelog_text = self.selected_changelog_text(tour, selected_tour_id)
        except Exception as exc:
            self.write_update_text(f"{type(exc).__name__}: {exc}")
            self.set_status("No changelog file found.")
            return
        self.download_content_to_downloads(tour, hostHistory.safe_history_filename(selected_tour_id), changelog_text)

    def download_dry_outputs(self):
        tour = TOURS[self.selected_tour_id]
        files = [
            Path(tour["state_path"]) / "mvps.txt",
            Path(tour["state_path"]) / "changelog.txt",
        ]
        existing = [path for path in files if path.exists()]
        if not existing:
            self.write_update_text("Missing mvps.txt and changelog.txt. Run MVPs or Update Elos first.")
            self.set_status("No file found.")
            return
        destinations = [self.download_file_to_downloads(tour, path, announce=False) for path in existing]
        if len(existing) == 1 and existing[0].name == "changelog.txt":
            self.set_status("Saved changelog.")
        else:
            self.set_status("Saved MVPs and changelog.")
        self.write_update_text("Saved files to:\n" + "\n".join(str(path) for path in destinations if path))

    def download_named_tour_file(self, tour, filename, missing_message):
        source = Path(tour["state_path"]) / filename
        if not source.exists():
            self.write_update_text(missing_message)
            self.set_status("No file found.")
            return
        self.download_file_to_downloads(tour, source)

    def download_content_to_downloads(self, tour, filename, content):
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        source_name = Path(filename)
        destination = downloads / f"{tour['id']}_{source_name.name}"
        counter = 2
        while destination.exists():
            destination = downloads / f"{tour['id']}_{source_name.stem}_{counter}{source_name.suffix}"
            counter += 1
        try:
            destination.write_text(content, encoding="utf-8")
        except OSError as exc:
            self.write_update_text(f"Could not save file: {exc}")
            self.set_status("Download failed.")
            return None
        self.set_status(f"Downloaded {destination.name}.")
        self.write_update_text(f"Saved file to:\n{destination}")
        return destination

    def download_file_to_downloads(self, tour, source, announce=True):
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        destination = downloads / f"{tour['id']}_{source.name}"
        counter = 2
        while destination.exists():
            destination = downloads / f"{tour['id']}_{source.stem}_{counter}{source.suffix}"
            counter += 1

        try:
            shutil.copyfile(source, destination)
        except OSError as exc:
            self.write_update_text(f"Could not save file: {exc}")
            self.set_status("Download failed.")
            return None

        if announce:
            self.set_status(f"Downloaded {destination.name}.")
            self.write_update_text(f"Saved file to:\n{destination}")
        return destination

    def run_mvp_for_selected(self):
        if self.mvp_running:
            return
        tour = TOURS[self.selected_tour_id]
        selected = self.challonge_list.curselection()
        selected_tour_id = None
        if selected:
            index = selected[0]
            if index < len(self.challonge_items):
                _tour_time, _fallback_index, date_label, link, selected_tour_id = self.challonge_items[index]
                self.selected_challonge_var.set(f"{date_label}  {link}")
        self.mvp_running = True
        self.mvp_run_button.configure(state="disabled")
        self.write_update_text("Generating MVPs...")
        self.set_status("Generating MVPs...")
        threading.Thread(target=self.mvp_in_background, args=(tour, selected_tour_id), daemon=True).start()

    def mvp_in_background(self, tour, selected_tour_id=None):
        try:
            from modules.support.mvpGenerator import generate_mvps_for_tour

            self.wait_for_tour_loaded(tour["id"])
            mvp_text = generate_mvps_for_tour(tour, selected_tour_id=selected_tour_id)
        except Exception as exc:
            details = traceback.format_exc()
            error = f"{type(exc).__name__}: {exc}\n\n{details}"
            self.after(0, lambda error=error: self.finish_mvp_generation(error=error))
            return
        self.after(0, lambda: self.finish_mvp_generation(tour=tour, mvp_text=mvp_text))

    def finish_mvp_generation(self, tour=None, mvp_text=None, error=None):
        self.mvp_running = False
        self.mvp_run_button.configure(state="normal")
        if error:
            self.write_update_text(error)
            self.set_status("MVP generation failed.")
            return
        self.write_update_text(self.mvp_report_text(tour, mvp_text))
        self.set_status("MVPs generated.")

    def write_update_text(self, text):
        self.update_info.configure(state="normal")
        self.update_info.delete("1.0", "end")
        self.update_info.insert("end", text)
        self.update_info.configure(state="disabled")

    def refresh_elos(self):
        for item in self.elos_table.get_children():
            self.elos_table.delete(item)

        tour = TOURS[self.selected_tour_id]
        elos_path = Path(tour["state_path"]) / "elos.json"
        if not elos_path.exists():
            self.set_status("No elos.json found for this tour.")
            return

        try:
            from modules.support.readElos import load_elos

            elos = load_elos(elos_path, Path(tour["state_path"]) / "ids.csv", key_format="name")
        except (OSError, json.JSONDecodeError):
            self.set_status("Could not read elos.json.")
            return

        alias_names = self.elo_alias_names(tour, elos)
        self.substitution_panel.update_elo_context(elos, alias_names)
        query = self.normalize_alias_key(self.elos_search_var.get().strip())
        sorted_elos = sorted(elos.items(), key=lambda item: item[1], reverse=True)
        matched_index = next(
            (
                index
                for index, (player, _elo) in enumerate(sorted_elos)
                if self.elo_matches_search(player, alias_names.get(player, []), query)
            ),
            None,
        ) if query else None
        matched_item = None
        for player, elo in sorted_elos:
            item = self.elos_table.insert("", "end", values=(player, elo))
            if matched_index is not None and player == sorted_elos[matched_index][0]:
                matched_item = item
        if matched_item:
            self.elos_table.selection_set(matched_item)
            self.elos_table.focus(matched_item)
            self.after_idle(lambda item=matched_item, index=matched_index, total=len(sorted_elos): self.center_elo_match(item, index, total))

    def center_elo_match(self, item, index, total):
        if not self.elos_table.exists(item) or not total:
            return
        visible_rows = max(1, self.elos_table.winfo_height() // 22)
        first_row = max(0, min(total - visible_rows, index - visible_rows // 2))
        self.elos_table.yview_moveto(first_row / max(total, 1))
        self.elos_table.selection_set(item)
        self.elos_table.focus(item)

    def elo_alias_names(self, tour, elos):
        names = {player: {player} for player in elos}
        idtable_path = Path(tour["state_path"]) / "ids.csv"
        if not idtable_path.exists():
            return names
        try:
            from modules.support.getAliases import getAliasesDF

            aliases = getAliasesDF(str(idtable_path))
            aliases["Player Name"] = aliases["Player Name"].astype(str).str.strip()
            aliases["_key"] = aliases["Player Name"].str.lower()
            aliases_by_id = aliases.groupby("Player ID")["Player Name"].apply(list).to_dict()
            id_by_name = dict(zip(aliases["_key"], aliases["Player ID"]))
        except Exception:
            return names

        for player in elos:
            player_id = id_by_name.get(player.lower())
            if player_id in aliases_by_id:
                names[player].update(aliases_by_id[player_id])
        return names

    def elo_matches_search(self, player, aliases, query):
        candidates = set(aliases)
        candidates.add(player)
        return any(query in self.normalize_alias_key(candidate) for candidate in candidates)

    def _read_text(self, tour: dict, filename: str, fallback: str) -> str:
        path = Path(tour["state_path"]) / filename
        if not path.exists():
            return fallback
        return path.read_text(encoding="utf-8")

    def clipboard_from_text(self, text_widget: tk.Text):
        text = text_widget.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        self.set_status("Copied.")

    def set_status(self, message: str):
        self.title(f"AMQ Host Script - {message}")


def main():
    app = AMQTourUI()
    app.mainloop()


if __name__ == "__main__":
    main()
