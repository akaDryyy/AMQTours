from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk


class SubstitutionPanel:
    """UI and formatting logic for creating Challonge substitute lines."""

    def __init__(self, root, parent, get_tour, normalize_key, set_status, colors):
        self.root = root
        self.parent = parent
        self.get_tour = get_tour
        self.normalize_key = normalize_key
        self.set_status = set_status
        self.colors = colors
        self.snapshots = {}
        self.elos = {}
        self.aliases = {}
        self.rows = []
        self.snapshot_key = None
        self.active_tour_id = None
        self.popup = None
        self.popup_list = None
        self.popup_target = None
        self.total_rounds = tk.StringVar(value="6")

        self._build()
        self.apply_theme(colors)
        self.set_output("No teams were made yet")

    def _build(self):
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(2, weight=1)
        actions = ttk.Frame(self.parent)
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="Add Sub", command=self.add_row).pack(side="left")
        ttk.Label(actions, text="Total rounds").pack(side="left", padx=(14, 6))
        ttk.Entry(actions, textvariable=self.total_rounds, width=5).pack(side="left")

        self.rows_frame = ttk.Frame(self.parent)
        self.rows_frame.grid(row=1, column=0, sticky="ew")
        self.rows_frame.columnconfigure(0, weight=1)
        self.rows_frame.columnconfigure(1, weight=1)
        ttk.Label(self.rows_frame, text="Player out").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Label(self.rows_frame, text="Sub").grid(row=0, column=1, sticky="w", padx=(6, 6))
        ttk.Label(self.rows_frame, text="Rounds").grid(row=0, column=2, sticky="w", padx=(6, 6))

        self.results = tk.Text(self.parent, height=18, wrap="word", borderwidth=1, relief="solid", font=("Consolas", 10))
        self.results.grid(row=2, column=0, sticky="nsew", pady=(10, 8))
        self.results.configure(state="disabled")
        ttk.Button(self.parent, text="Copy", command=self.copy_output).grid(row=3, column=0, sticky="w")
        self.total_rounds.trace_add("write", lambda *_args: self.refresh_output())

    def apply_theme(self, colors):
        self.colors = colors
        self.results.configure(
            background=colors["field"],
            foreground=colors["text"],
            insertbackground=colors["text"],
            selectbackground=colors["accent"],
            inactiveselectbackground=colors["accent"],
            highlightbackground=colors["border"],
            highlightcolor=colors["accent"],
        )
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.configure(bg=colors["border"])
        if self.popup_list is not None and self.popup_list.winfo_exists():
            self.popup_list.configure(
                background=colors["field"],
                foreground=colors["text"],
                selectbackground=colors["accent"],
                selectforeground=colors["selected_text"],
                highlightbackground=colors["border"],
                highlightcolor=colors["accent"],
            )

    def select_tour(self, tour_id):
        if self.active_tour_id == tour_id:
            return
        self.active_tour_id = tour_id
        self.snapshot_key = None
        self.elos = {}
        self.aliases = {}
        self.clear_rows(refresh=False)
        self.refresh_output()

    def update_elo_context(self, elos, aliases):
        self.elos = elos
        self.aliases = aliases
        self.refresh_output()

    def set_snapshot(self, tour, snapshot):
        if snapshot:
            self.snapshots[tour["id"]] = snapshot

    def reset_after_solver(self):
        self.clear_rows(refresh=False)
        self.snapshot_key = None
        self.refresh_output()

    def load_snapshot(self, tour):
        if not tour:
            return None
        if tour["id"] in self.snapshots:
            return self.snapshots[tour["id"]]
        state_path = Path(tour["state_path"])
        for filename in ("latest_teams.json", "latest_inhouse_teams.json"):
            path = state_path / filename
            if not path.exists():
                continue
            try:
                snapshot = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if snapshot.get("teams"):
                self.snapshots[tour["id"]] = snapshot
                return snapshot
        return None

    @staticmethod
    def team_players(snapshot):
        players = []
        for team in snapshot.get("teams", {}).values():
            players.extend(team.get("players", []))
        return players

    def default_round_count(self, snapshot):
        player_count = len(self.team_players(snapshot))
        if player_count >= 24:
            return "5"
        if player_count == 16:
            return "6"
        if player_count == 8:
            return "3"
        return "6"

    def clear_rows(self, refresh=True):
        for row in self.rows:
            for widget in row["widgets"]:
                widget.destroy()
        self.rows = []
        if refresh:
            self.refresh_output()

    def set_output(self, text):
        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        self.results.insert("1.0", text)
        self.results.configure(state="disabled")

    def add_row(self):
        snapshot = self.load_snapshot(self.get_tour())
        if not snapshot:
            self.set_output("No teams were made yet")
            return
        player_names = [player["name"] for player in self.team_players(snapshot)]
        if not player_names:
            self.set_output("No teams were made yet")
            return
        replacement_names = sorted(self.elos, key=str.lower) or player_names
        row_number = len(self.rows) + 1
        player_out = ttk.Combobox(self.rows_frame, values=player_names, state="normal")
        substitute = ttk.Combobox(self.rows_frame, values=replacement_names, state="normal")
        rounds = ttk.Entry(self.rows_frame, width=12)
        remove = ttk.Button(self.rows_frame, text="Remove")
        player_out.grid(row=row_number, column=0, sticky="ew", padx=(0, 6), pady=3)
        substitute.grid(row=row_number, column=1, sticky="ew", padx=(6, 6), pady=3)
        rounds.grid(row=row_number, column=2, sticky="w", padx=(6, 6), pady=3)
        remove.grid(row=row_number, column=3, sticky="w", pady=3)
        row = {
            "player_out": player_out,
            "substitute": substitute,
            "rounds": rounds,
            "widgets": (player_out, substitute, rounds, remove),
        }
        remove.configure(command=lambda current=row: self.remove_row(current))
        self.bind_picker(player_out, player_names)
        self.bind_picker(substitute, replacement_names)
        rounds.bind("<KeyRelease>", lambda _event: self.refresh_output())
        self.rows.append(row)
        self.refresh_output()

    def remove_row(self, row):
        if row not in self.rows:
            return
        for widget in row["widgets"]:
            widget.destroy()
        self.rows.remove(row)
        for row_number, current in enumerate(self.rows, start=1):
            for widget in current["widgets"]:
                widget.grid_configure(row=row_number)
        self.refresh_output()

    def bind_picker(self, combobox, candidates):
        combobox.sub_candidates = candidates
        combobox.bind("<FocusIn>", lambda _event, box=combobox: self.show_dropdown(box))
        combobox.bind("<FocusOut>", lambda _event, box=combobox: self.schedule_dropdown_hide(box))
        combobox.bind("<Button-1>", lambda event, box=combobox: self.on_picker_click(event, box))
        combobox.bind("<KeyRelease>", lambda event, box=combobox: self.on_picker_key_release(event, box))
        combobox.bind("<Return>", lambda _event, box=combobox: self.lock_player(box))

    def player_matches(self, player, query):
        names = set(self.aliases.get(player, {player}))
        names.add(player)
        return not query or any(query in self.normalize_key(name) for name in names)

    def filter_players(self, combobox):
        query = self.normalize_key(combobox.get())
        players = [player for player in getattr(combobox, "sub_candidates", []) if self.player_matches(player, query)]
        combobox.configure(values=players)
        if self.popup_target is combobox:
            self.populate_popup(players)
        return players

    def ensure_popup(self):
        if self.popup is not None and self.popup.winfo_exists():
            return
        self.popup = tk.Toplevel(self.root)
        self.popup.withdraw()
        self.popup.overrideredirect(True)
        self.popup.configure(bg=self.colors["border"])
        self.popup.attributes("-topmost", True)
        frame = ttk.Frame(self.popup, padding=1)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.popup_list = tk.Listbox(frame, height=8, activestyle="none", exportselection=False)
        self.popup_list.grid(row=0, column=0, sticky="nsew")
        self.popup_list.bind("<ButtonRelease-1>", self.choose_popup_player)
        self.popup_list.bind("<Return>", self.choose_popup_player)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.popup_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.popup_list.configure(yscrollcommand=scrollbar.set)
        self.apply_theme(self.colors)

    def populate_popup(self, players):
        if self.popup_list is None:
            return
        self.popup_list.delete(0, "end")
        for player in players:
            self.popup_list.insert("end", player)
        if players:
            self.popup_list.selection_set(0)

    def show_dropdown(self, combobox):
        players = self.filter_players(combobox)
        if not players:
            self.hide_dropdown()
            return
        self.ensure_popup()
        self.popup_target = combobox
        self.populate_popup(players)
        x = combobox.winfo_rootx()
        y = combobox.winfo_rooty() + combobox.winfo_height()
        height = min(len(players), 8) * 22 + 4
        self.popup.geometry(f"{combobox.winfo_width()}x{height}+{x}+{y}")
        self.popup.deiconify()
        self.popup.lift()
        combobox.focus_set()

    def hide_dropdown(self):
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.withdraw()
        self.popup_target = None

    def schedule_dropdown_hide(self, combobox):
        def hide_if_focus_left():
            focus = self.root.focus_get()
            if focus not in (combobox, self.popup_list):
                self.hide_dropdown()

        combobox.after(120, hide_if_focus_left)

    def on_picker_click(self, event, combobox):
        if event.x >= combobox.winfo_width() - 24:
            self.show_dropdown(combobox)
            return "break"
        combobox.after_idle(lambda: self.show_dropdown(combobox))

    def on_picker_key_release(self, event, combobox):
        if event.keysym in {"Return", "KP_Enter", "Up", "Down"}:
            return
        if event.keysym == "Escape":
            self.hide_dropdown()
            return
        self.show_dropdown(combobox)
        self.refresh_output()

    def resolve_player(self, combobox):
        value = self.normalize_key(combobox.get())
        if not value:
            return None
        matches = []
        for player in getattr(combobox, "sub_candidates", []):
            aliases = self.aliases.get(player, [])
            if value == self.normalize_key(player) or any(value == self.normalize_key(alias) for alias in aliases):
                matches.append(player)
        return matches[0] if len(matches) == 1 else None

    def lock_player(self, combobox):
        player = self.resolve_player(combobox)
        if player is None:
            matches = self.filter_players(combobox)
            player = matches[0] if matches else None
        if player is None:
            self.set_status("No matching player in the current player list.")
            return "break"
        combobox.set(player)
        self.filter_players(combobox)
        self.hide_dropdown()
        self.refresh_output()
        return "break"

    def choose_popup_player(self, _event=None):
        if self.popup_target is None or self.popup_list is None:
            return "break"
        selected = self.popup_list.curselection()
        if not selected:
            return "break"
        target = self.popup_target
        target.set(self.popup_list.get(selected[0]))
        self.filter_players(target)
        target.focus_set()
        self.hide_dropdown()
        self.refresh_output()
        return "break"

    @staticmethod
    def parse_rounds(value, total_rounds):
        try:
            rounds = [int(part.strip()) for part in value.split(",") if part.strip()]
        except ValueError as exc:
            raise ValueError("Rounds must be comma-separated whole numbers.") from exc
        if not rounds or any(round_number < 1 or round_number > total_rounds for round_number in rounds):
            raise ValueError(f"Rounds must be between 1 and {total_rounds}.")
        if len(rounds) != len(set(rounds)):
            raise ValueError("Duplicate rounds detected, please double-check rounds")
        return sorted(rounds)

    def refresh_output(self):
        tour = self.get_tour()
        snapshot = self.load_snapshot(tour)
        if not snapshot:
            self.set_output("No teams were made yet")
            return
        player_count = len(self.team_players(snapshot))
        snapshot_key = (tour["id"], player_count, tuple(sorted(snapshot.get("teams", {}))))
        if self.snapshot_key != snapshot_key:
            self.snapshot_key = snapshot_key
            self.total_rounds.set(self.default_round_count(snapshot))
        if not self.rows:
            self.set_output("Add a substitute to generate Challonge lines.")
            return
        try:
            total_rounds = int(self.total_rounds.get().strip())
            if total_rounds <= 0:
                raise ValueError("Total rounds must be at least 1.")
            substitutions = {}
            for row in self.rows:
                player_out = self.resolve_player(row["player_out"])
                substitute = self.resolve_player(row["substitute"])
                if not player_out or not substitute or not row["rounds"].get().strip():
                    self.set_output("Choose both players and enter rounds for every substitute.")
                    return
                if player_out == substitute:
                    raise ValueError("A player cannot substitute for themselves.")
                rounds = self.parse_rounds(row["rounds"].get(), total_rounds)
                details = substitutions.setdefault(player_out, {"rounds": set(), "subs": []})
                if details["rounds"].intersection(rounds):
                    raise ValueError("Duplicate rounds detected, please double-check rounds")
                details["rounds"].update(rounds)
                details["subs"].append((substitute, rounds))

            lines = []
            for team in snapshot.get("teams", {}).values():
                players = team.get("players", [])
                if not any(player["name"] in substitutions for player in players):
                    continue
                parts = []
                for player in players:
                    name = player["name"]
                    rating = float(player["rating"])
                    if name not in substitutions:
                        parts.append(f"{name} ({rating:.3f})")
                        continue
                    details = substitutions[name]
                    remaining = [round_number for round_number in range(1, total_rounds + 1) if round_number not in details["rounds"]]
                    if remaining:
                        rounds_text = ", ".join(str(round_number) for round_number in remaining)
                        parts.append(f"{name} [{rounds_text}] ({rating:.3f})")
                    for substitute, rounds in details["subs"]:
                        substitute_rating = self.elos.get(substitute)
                        if substitute_rating is None:
                            raise ValueError(f"No elo found for {substitute}.")
                        rounds_text = ", ".join(str(round_number) for round_number in rounds)
                        parts.append(f"{substitute} [{rounds_text}] ({float(substitute_rating):.3f})")
                total = sum(float(player["rating"]) for player in players)
                guesses = "".join(str(player.get("guess", "")) for player in players)
                lines.append(f"{' '.join(parts)} | Total = {total:.3f} | Guesses = [{guesses}]")
            self.set_output("\n".join(lines) if lines else "Add a substitute to generate Challonge lines.")
        except ValueError as exc:
            self.set_output(str(exc))

    def copy_output(self):
        text = self.results.get("1.0", "end").strip()
        if not text or text == "No teams were made yet":
            self.set_status("No substitute line to copy.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.set_status("Copied substitute lines.")
