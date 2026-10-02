from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from tour_config import TOURS


MODE_SELECTIONS = {
    "usual": "1",
    "usual_house": "1",
    "watched": "2",
    "watched_house": "2",
    "watched_draft": "2",
    "watched_0_100": "3",
    "watched_op": "4",
    "watched_0_100_op": "5",
    "watched_ed": "6",
    "watched_ins": "7",
    "watched_ins_no_chanting": "8",
    "watched_oped": "9",
    "watched_2_8": "10",
    "watched_5s": "11",
    "watched_x_2009": "12",
    "random_op": "13",
    "random_ed": "14",
    "random_ins": "15",
    "random_oped": "16",
    "random_chanting": "17",
}


class HostStatsService:
    """Own one tour's local JSON collection and non-interactive stats runs."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.stats_root = self.project_root / "stats"

    @staticmethod
    def expected_games(snapshot: dict) -> int:
        player_count = sum(
            len(team.get("players", []))
            for team in snapshot.get("teams", {}).values()
        )
        if player_count <= 0:
            return 0
        if player_count <= 8:
            return 3
        if player_count <= 16:
            return 12
        if player_count <= 24:
            return 15
        return 20

    @staticmethod
    def workspace(tour: dict) -> Path:
        return Path(tour["state_path"]) / "stats"

    def paths(self, tour: dict) -> dict[str, Path]:
        workspace = self.workspace(tour)
        return {
            "workspace": workspace,
            "jsons": workspace / "jsons",
            "codes": workspace / "codes.txt",
            "state": workspace / "host_stats_state.json",
        }

    def load_state(self, tour: dict) -> dict:
        path = self.paths(tour)["state"]
        if not path.exists():
            return {"games": [], "guess_counts": {}, "substitute_teams": {}, "substitute_team_labels": {}}
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"games": [], "guess_counts": {}, "substitute_teams": {}, "substitute_team_labels": {}}
        state.setdefault("games", [])
        state.setdefault("guess_counts", {})
        state.setdefault("substitute_teams", {})
        state.setdefault("substitute_team_labels", {})
        return state

    def save_state(self, tour: dict, state: dict) -> None:
        paths = self.paths(tour)
        paths["workspace"].mkdir(parents=True, exist_ok=True)
        paths["state"].write_text(json.dumps(state, indent=2), encoding="utf-8")

    def prepare_workspace(
        self,
        tour: dict,
        codes_text: str,
        challonge_link: str,
        substitute_players=(),
        substitute_team_labels=None,
    ) -> None:
        paths = self.paths(tour)
        paths["jsons"].mkdir(parents=True, exist_ok=True)
        # The Host Script display also includes the AMQ setup code and guess
        # legend. The stats script's codes.txt accepts only team/sub rows,
        # Average, and the final Challonge URL.
        lines = []
        for line in codes_text.splitlines():
            stripped = line.strip()
            lower = stripped.casefold()
            if "<yourchallongeurlhere>" in lower:
                continue
            if (
                "| total =" in lower
                or lower.startswith(("average", "avg", "sub:"))
                or stripped.startswith("http")
            ):
                lines.append(line.replace("\\_", "_"))
        if substitute_players:
            sub_text = ", ".join(f"{name} ({rating:.3f})" for name, rating in substitute_players)
            lines.append(f"subs: {sub_text}")
        if substitute_team_labels:
            state = self.load_state(tour)
            state["substitute_team_labels"].update(substitute_team_labels)
            self.save_state(tour, state)
        link = challonge_link.strip()
        if link and not any(line.strip().lower().startswith("http") for line in lines):
            lines.extend(["", link])
        paths["codes"].write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    @staticmethod
    def _song_names(song: dict) -> set[str]:
        names: set[str] = set()
        guesses = song.get("correctGuessPlayers", [])
        if isinstance(guesses, dict):
            guesses = list(guesses.values())
        if isinstance(guesses, list):
            for entry in guesses:
                if isinstance(entry, str):
                    names.add(entry.strip().casefold())
                elif isinstance(entry, dict):
                    for key in ("name", "playerName", "username", "amqName"):
                        value = entry.get(key)
                        if isinstance(value, str) and value.strip():
                            names.add(value.strip().casefold())
                            break
        list_states = song.get("listStates", [])
        if isinstance(list_states, dict):
            list_states = list(list_states.values())
        if isinstance(list_states, list):
            for entry in list_states:
                if isinstance(entry, dict):
                    value = entry.get("name")
                    if isinstance(value, str) and value.strip():
                        names.add(value.strip().casefold())
        return names

    @classmethod
    def detect_matchup(cls, json_path: Path, snapshot: dict, substitute_teams: dict | None = None) -> tuple[str, str] | None:
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        name_to_team = {
            str(player["name"]).strip().casefold(): team_id
            for team_id, team in snapshot.get("teams", {}).items()
            for player in team.get("players", [])
        }
        name_to_team.update({
            str(name).strip().casefold(): team_id
            for name, team_id in (substitute_teams or {}).items()
            if team_id in snapshot.get("teams", {})
        })
        team_counts = Counter()
        for song in payload.get("songs", []):
            for name in cls._song_names(song):
                team_id = name_to_team.get(name)
                if team_id:
                    team_counts[team_id] += 1
        if len(team_counts) == 2:
            return tuple(sorted(team_counts))
        if len(team_counts) > 2:
            ranked = team_counts.most_common(3)
            # A tour JSON can mention a few incidental players. Treat the
            # two clear leaders as the match only when they beat third place.
            if len(ranked) == 2 or ranked[1][1] > ranked[2][1]:
                return tuple(sorted((ranked[0][0], ranked[1][0])))
        return None

    @staticmethod
    def _team_label(snapshot: dict, team_id: str) -> str:
        team = snapshot.get("teams", {}).get(team_id, {})
        return str(team.get("label") or team_id)

    @staticmethod
    def _json_fingerprint(path: Path) -> str:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            songs = payload.get("songs") if isinstance(payload, dict) else None
            if isinstance(songs, list):
                encoded = json.dumps(songs, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
                return hashlib.sha256(encoded).hexdigest()
        except (OSError, json.JSONDecodeError):
            pass
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def add_json(self, tour: dict, source: Path, snapshot: dict, game_id: str | None = None, substitute_teams: dict | None = None) -> dict:
        paths = self.paths(tour)
        paths["jsons"].mkdir(parents=True, exist_ok=True)
        state = self.load_state(tour)
        if substitute_teams:
            state["substitute_teams"].update(substitute_teams)
        matchup = self.detect_matchup(source, snapshot, state["substitute_teams"])
        fingerprint = self._json_fingerprint(source)
        for existing_game in state["games"]:
            for file_name in existing_game.get("files", []):
                existing_path = paths["jsons"] / file_name
                if existing_path.exists() and self._json_fingerprint(existing_path) == fingerprint:
                    return {"duplicate_game": existing_game, "matchup": matchup, "state": state}
        if game_id is None:
            game_id = f"game-{len(state['games']) + 1}"
            state["games"].append({"id": game_id, "teams": list(matchup or ()), "files": [], "score": None})
        game = next(game for game in state["games"] if game["id"] == game_id)
        if not game.get("teams") and matchup:
            game["teams"] = list(matchup)
        digest = hashlib.sha1(source.read_bytes()).hexdigest()[:10]
        # Keep the export's leading song count intact: ngm_stats reads it from
        # the filename to handle partial/disconnected exports correctly.
        destination = paths["jsons"] / f"{source.stem} [{game_id}-{digest}]{source.suffix}"
        if not destination.exists():
            shutil.copy2(source, destination)
        if destination.name not in game["files"]:
            game["files"].append(destination.name)
        self.save_state(tour, state)
        return {"game": game, "matchup": matchup, "state": state}

    def set_score(self, tour: dict, game_id: str, snapshot: dict, score1: int, score2: int) -> None:
        state = self.load_state(tour)
        game = next(game for game in state["games"] if game["id"] == game_id)
        teams = game.get("teams", [])
        if len(teams) != 2:
            return
        game["score"] = {
            "team1": self._team_label(snapshot, teams[0]),
            "team2": self._team_label(snapshot, teams[1]),
            "score1": int(score1),
            "score2": int(score2),
        }
        self.save_state(tour, state)

    def set_game_teams(self, tour: dict, game_id: str, teams: tuple[str, str]) -> None:
        state = self.load_state(tour)
        game = next(game for game in state["games"] if game["id"] == game_id)
        game["teams"] = list(teams)
        self.save_state(tour, state)

    def reconcile_game_matchups(self, tour: dict, snapshot: dict, substitute_teams: dict | None = None) -> None:
        paths = self.paths(tour)
        state = self.load_state(tour)
        if substitute_teams:
            state["substitute_teams"].update(substitute_teams)
            changed = True
        else:
            changed = False
        for game in state["games"]:
            if game.get("teams"):
                continue
            for file_name in game.get("files", []):
                matchup = self.detect_matchup(paths["jsons"] / file_name, snapshot, state["substitute_teams"])
                if matchup:
                    game["teams"] = list(matchup)
                    changed = True
                    break
        if changed:
            self.save_state(tour, state)

    def clear_jsons(self, tour: dict) -> None:
        paths = self.paths(tour)
        if paths["jsons"].exists():
            for path in paths["jsons"].glob("*.json"):
                path.unlink()
        self.save_state(tour, {"games": [], "guess_counts": {}, "substitute_teams": {}, "substitute_team_labels": {}})

    def _load_stats_module(self):
        module_name = "amq_host_ngm_stats"
        spec = importlib.util.spec_from_file_location(module_name, self.stats_root / "ngm_stats.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load stats/ngm_stats.py.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        def local_error(title, details=None, fixes=None, wait=False):
            lines = [str(title)]
            if details:
                lines.extend(str(detail) for detail in details)
            if fixes:
                lines.extend(str(fix) for fix in fixes)
            raise ValueError("\n".join(lines))

        # The standalone helper normally waits for Enter after validation
        # failures. In the GUI, surface the same details in the Stats tab.
        module.common_error = local_error
        json_processing = sys.modules.get("JsonProcessing")
        if json_processing is not None:
            json_processing.common_error = local_error
        return module

    def _selection(self, tour: dict, eru_mode: bool) -> str:
        if tour["id"] not in MODE_SELECTIONS:
            raise ValueError(f"Stats are not mapped for {tour['label']} yet.")
        return MODE_SELECTIONS[tour["id"]] + ("a" if eru_mode else "")

    def run_local(self, tour: dict, eru_mode: bool) -> dict:
        paths = self.paths(tour)
        if not paths["codes"].exists():
            raise ValueError("Make teams first so the Stats tab can prepare codes.txt.")
        state = self.load_state(tour)
        selection = self._selection(tour, eru_mode)
        module = self._load_stats_module()
        scores = [game["score"] for game in state["games"] if game.get("score")]
        return module.run_ngm_sheet_stats(
            True,
            selection=selection,
            workspace_dir=str(paths["workspace"]),
            codes_path=str(paths["codes"]),
            local_scores=scores,
            substitute_team_labels=state.get("substitute_team_labels", {}),
            return_data=True,
            include_extra_stats=False,
        )

    def finalize(self, tour: dict, eru_mode: bool) -> dict:
        paths = self.paths(tour)
        if not paths["codes"].exists():
            raise ValueError("Make teams first so the Stats tab can prepare codes.txt.")
        state = self.load_state(tour)
        return self._load_stats_module().run_ngm_sheet_stats(
            False,
            selection=self._selection(tour, eru_mode),
            workspace_dir=str(paths["workspace"]),
            codes_path=str(paths["codes"]),
            substitute_team_labels=state.get("substitute_team_labels", {}),
            return_data=True,
            include_extra_stats=True,
        )

    @staticmethod
    def guess_count(tour: dict, gr: float, maximum_guesses: int) -> str:
        config = tour.get("solver", {})
        thresholds = config.get("thresholds", {})
        mode = config.get("guess_mode")
        if mode == "watched_28":
            return "5" if gr >= thresholds["four"] else "4" if gr >= thresholds["three"] else "3" if gr >= thresholds["two"] else "2" if gr >= thresholds["one"] else "1" if gr >= thresholds["zero"] else "0"
        if mode in {"random", "random5g"}:
            if maximum_guesses >= 5 and gr >= 40:
                return "5"
            return "4" if gr >= thresholds["three"] else "3" if gr >= thresholds["two"] else "2" if gr >= thresholds["one"] else "1"
        return "5" if gr >= thresholds["four"] else "4" if gr >= thresholds["three"] else "3" if gr >= thresholds["two"] else "2" if gr >= thresholds["one"] else "1"


class StatsPanel:
    def __init__(self, host, parent, project_root: Path):
        self.host = host
        self.service = HostStatsService(project_root)
        self.frame = parent
        self.running = False
        self.latest_images: list[Path] = []
        self.json_items: dict[str, tuple[str, str]] = {}
        self.mode_var = tk.StringVar(value="Make teams to prepare Stats.")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text = tk.StringVar(value="0 / 0 games")
        self.status_var = tk.StringVar(value="Upload game JSONs to generate local stats.")
        self.challonge_var = tk.StringVar()
        self._build()
        self.host.bind("<Button-1>", self._clear_game_selection, add="+")

    def _clear_game_selection(self, event):
        if event.widget is self.games_table:
            if not self.games_table.identify_row(event.y):
                self.games_table.selection_remove(self.games_table.selection())
            return
        if event.widget not in (self.upload_button, self.delete_button):
            self.games_table.selection_remove(self.games_table.selection())

    def _build(self):
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(4, weight=1)
        top = ttk.Frame(self.frame)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Challonge Link").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.challonge_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        action_button = {"style": "Tool.TButton", "width": 12}
        self.upload_button = ttk.Button(top, text="Upload JSONs", command=self.upload_jsons, **action_button)
        self.upload_button.grid(row=0, column=2)
        self.delete_button = ttk.Button(top, text="Delete", command=self.delete_selected_json, **action_button)
        self.delete_button.grid(row=0, column=3, padx=(8, 0))
        ttk.Button(top, text="Clear", command=self.clear_jsons, **action_button).grid(row=0, column=4, padx=(8, 0))
        ttk.Button(top, text="Export Image", command=self.export_image, **action_button).grid(row=0, column=5, padx=(8, 0))
        ttk.Button(top, text="Finalize", command=self.finalize, **action_button).grid(row=0, column=6, padx=(8, 0))

        progress = ttk.Frame(self.frame)
        progress.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        progress.columnconfigure(0, weight=1)
        ttk.Progressbar(progress, maximum=100, variable=self.progress_var).grid(row=0, column=0, sticky="ew")
        ttk.Label(progress, textvariable=self.progress_text).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(self.frame, textvariable=self.status_var, style="Subtle.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 8))

        games_frame = ttk.LabelFrame(self.frame, text="Uploaded Games", padding=8, style="Stats.TLabelframe")
        games_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        games_frame.columnconfigure(0, weight=1)
        self.games_table = ttk.Treeview(games_frame, columns=("teams", "jsons", "score"), show="tree headings", height=5)
        self.games_table.heading("#0", text="Round / JSON")
        self.games_table.column("#0", width=230, anchor="w")
        for column, title, width in (("teams", "Teams", 330), ("jsons", "Files", 70), ("score", "Score", 100)):
            self.games_table.heading(column, text=title)
            self.games_table.column(column, width=width, anchor="w")
        self.games_table.grid(row=0, column=0, sticky="ew")
        self.games_table.bind("<Double-1>", lambda _event: self.edit_selected_score())

        stats_frame = ttk.LabelFrame(self.frame, text="Current Stats", padding=8, style="Stats.TLabelframe")
        stats_frame.grid(row=4, column=0, sticky="nsew")
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.rowconfigure(0, weight=1)
        self.stats_table = ttk.Treeview(stats_frame, show="headings", height=14)
        self.stats_table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(stats_frame, orient="vertical", command=self.stats_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.stats_table.configure(yscrollcommand=scrollbar.set)

    def _tour_and_snapshot(self):
        tour = TOURS[self.host.selected_tour_id]
        path = Path(tour["state_path"]) / "latest_teams.json"
        if not path.exists():
            raise ValueError("Make teams before using the Stats tab.")
        try:
            return tour, json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("The current team snapshot could not be read.") from exc

    def _substitute_players(self):
        panel = getattr(self.host, "substitution_panel", None)
        return panel.stats_substitute_players() if panel is not None else ()

    def _substitute_teams(self, tour, snapshot):
        panel = getattr(self.host, "substitution_panel", None)
        if panel is None:
            return {}
        return panel.stats_team_aliases(tour, snapshot)

    def _substitute_team_labels(self, tour, snapshot):
        return {
            name: self.service._team_label(snapshot, team_id)
            for name, team_id in self._substitute_teams(tour, snapshot).items()
        }

    def refresh_context(self):
        try:
            tour, snapshot = self._tour_and_snapshot()
        except ValueError as exc:
            self.mode_var.set(str(exc))
            self.progress_var.set(0)
            self.progress_text.set("0 / 0 games")
            self._refresh_games(None, None)
            return
        self.service.reconcile_game_matchups(tour, snapshot, self._substitute_teams(tour, snapshot))
        self._refresh_games(tour, snapshot)

    def _refresh_games(self, tour, snapshot):
        for item in self.games_table.get_children():
            self.games_table.delete(item)
        self.json_items.clear()
        if not tour or not snapshot:
            return
        state = self.service.load_state(tour)
        expected = self.service.expected_games(snapshot)
        completed = len(state["games"])
        self.progress_var.set((completed / expected * 100) if expected else 0)
        self.progress_text.set(f"{completed} / {expected} games")
        for game in state["games"]:
            teams = game.get("teams", [])
            team_text = " vs ".join(self.service._team_label(snapshot, team) for team in teams) or "Unidentified"
            score = game.get("score") or {}
            score_text = f"{score.get('score1')} : {score.get('score2')}" if score else "Pending"
            round_label = game["id"].replace("-", " ").title()
            round_iid = f"round:{game['id']}"
            self.games_table.insert("", "end", iid=round_iid, text=round_label, values=(team_text, len(game.get("files", [])), score_text))
            for index, file_name in enumerate(game.get("files", []), start=1):
                file_iid = f"json:{game['id']}:{index}"
                self.json_items[file_iid] = (game["id"], file_name)
                self.games_table.insert(round_iid, "end", iid=file_iid, text=file_name, values=("", "", ""))

    def _selected_round_id(self):
        selected = self.games_table.selection()
        if not selected:
            return None
        item_id = selected[0]
        if item_id in self.json_items:
            return self.json_items[item_id][0]
        if item_id.startswith("round:"):
            return item_id.removeprefix("round:")
        return None

    def upload_jsons(self):
        try:
            tour, snapshot = self._tour_and_snapshot()
        except ValueError as exc:
            messagebox.showerror("Stats", str(exc), parent=self.host)
            return
        files = filedialog.askopenfilenames(parent=self.host, title="Select AMQ JSON exports", filetypes=[("JSON files", "*.json")])
        if not files:
            return
        state = self.service.load_state(tour)
        selected_game_id = self._selected_round_id()
        selected_game = next((game for game in state["games"] if game["id"] == selected_game_id), None)
        added_any = False
        for file_name in files:
            source = Path(file_name)
            substitute_teams = self._substitute_teams(tour, snapshot)
            matchup = self.service.detect_matchup(source, snapshot, substitute_teams)
            game_id = None
            if selected_game:
                selected_teams = tuple(selected_game.get("teams", []))
                if matchup and selected_teams and selected_teams != matchup:
                    messagebox.showwarning(
                        "Different Round",
                        f"{source.name} is not the same matchup as the selected {selected_game['id']}. Select the correct round or upload without selecting one to create a new round.",
                        parent=self.host,
                    )
                    continue
                game_id = selected_game["id"]
            result = self.service.add_json(tour, source, snapshot, game_id, substitute_teams)
            state = result["state"]
            if result.get("duplicate_game"):
                existing_game = result["duplicate_game"]
                messagebox.showwarning(
                    "Identical JSON",
                    f"This JSON has the same songs/data as a file already attached to {existing_game['id']}. It was not added twice.",
                    parent=self.host,
                )
                continue
            game = result["game"]
            added_any = True
            if not game.get("teams"):
                game = self.choose_game_teams(tour, snapshot, game)
            if game and game.get("teams") and not game.get("score"):
                self.prompt_score(tour, snapshot, game)
        self._refresh_games(tour, snapshot)
        if added_any:
            self.regenerate()

    def prompt_score(self, tour, snapshot, game):
        teams = game.get("teams", [])
        if len(teams) != 2:
            return
        first = self.service._team_label(snapshot, teams[0])
        second = self.service._team_label(snapshot, teams[1])
        current_score = game.get("score") or {}
        dialog = tk.Toplevel(self.host)
        dialog.title("Enter Score")
        dialog.resizable(False, False)
        dialog.configure(background=self.host.colors["bg"])
        dialog.transient(self.host)
        dialog.grab_set()
        ttk.Label(dialog, text=first).grid(row=0, column=0, padx=(12, 6), pady=(12, 4))
        ttk.Label(dialog, text=second).grid(row=0, column=1, padx=(6, 12), pady=(12, 4))
        score1_var = tk.StringVar(value=str(current_score.get("score1", "")))
        score2_var = tk.StringVar(value=str(current_score.get("score2", "")))
        score1_entry = ttk.Entry(dialog, textvariable=score1_var, width=12, justify="center")
        score2_entry = ttk.Entry(dialog, textvariable=score2_var, width=12, justify="center")
        score1_entry.grid(row=1, column=0, padx=(12, 6), pady=(0, 12))
        score2_entry.grid(row=1, column=1, padx=(6, 12), pady=(0, 12))
        result = {"changed": False}

        def save():
            try:
                score1, score2 = int(score1_var.get().strip()), int(score2_var.get().strip())
                if score1 < 0 or score2 < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Enter Score", "Enter non-negative whole numbers for both teams.", parent=dialog)
                return
            if current_score.get("score1") == score1 and current_score.get("score2") == score2:
                dialog.destroy()
                return
            self.service.set_score(tour, game["id"], snapshot, score1, score2)
            result["changed"] = True
            dialog.destroy()

        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=2, column=0, sticky="e", padx=6, pady=(0, 12))
        ttk.Button(dialog, text="Save Score", style="Tool.TButton", command=save).grid(row=2, column=1, sticky="w", padx=6, pady=(0, 12))
        dialog.bind("<Return>", lambda _event: save())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        score1_entry.focus_set()
        self.host.wait_window(dialog)
        return result["changed"]

    def choose_game_teams(self, tour, snapshot, game):
        options = [
            (team_id, self.service._team_label(snapshot, team_id))
            for team_id in snapshot.get("teams", {})
        ]
        if len(options) < 2:
            return None
        labels = {label: team_id for team_id, label in options}
        dialog = tk.Toplevel(self.host)
        dialog.title("Identify Uploaded Game")
        dialog.resizable(False, False)
        dialog.transient(self.host)
        dialog.grab_set()
        ttk.Label(dialog, text="The JSON could not reliably identify two teams. Select the teams that played.").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8)
        )
        first = tk.StringVar(value=options[0][1])
        second = tk.StringVar(value=options[1][1])
        ttk.Label(dialog, text="First team").grid(row=1, column=0, sticky="w", padx=(12, 6), pady=(0, 4))
        ttk.Label(dialog, text="Second team").grid(row=1, column=1, sticky="w", padx=(6, 12), pady=(0, 4))
        first_picker = ttk.Combobox(dialog, textvariable=first, values=list(labels), state="readonly", width=34)
        second_picker = ttk.Combobox(dialog, textvariable=second, values=list(labels), state="readonly", width=34)
        first_picker.grid(row=2, column=0, sticky="ew", padx=(12, 6))
        second_picker.grid(row=2, column=1, sticky="ew", padx=(6, 12))
        result = {"game": None}

        def save():
            first_id = labels.get(first.get())
            second_id = labels.get(second.get())
            if not first_id or not second_id or first_id == second_id:
                messagebox.showerror("Identify Uploaded Game", "Choose two different teams.", parent=dialog)
                return
            self.service.set_game_teams(tour, game["id"], (first_id, second_id))
            result["game"] = next(
                item for item in self.service.load_state(tour)["games"] if item["id"] == game["id"]
            )
            dialog.destroy()

        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=3, column=0, sticky="e", padx=6, pady=12)
        ttk.Button(dialog, text="Use Teams", command=save).grid(row=3, column=1, sticky="w", padx=6, pady=12)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        first_picker.focus_set()
        self.host.wait_window(dialog)
        return result["game"]

    def edit_selected_score(self):
        try:
            tour, snapshot = self._tour_and_snapshot()
        except ValueError as exc:
            messagebox.showerror("Stats", str(exc), parent=self.host)
            return
        game_id = self._selected_round_id()
        if not game_id:
            messagebox.showinfo("Stats", "Select an uploaded round to edit its score.", parent=self.host)
            return
        game = next((item for item in self.service.load_state(tour)["games"] if item["id"] == game_id), None)
        if game is None:
            return
        teams_changed = False
        if not game.get("teams"):
            game = self.choose_game_teams(tour, snapshot, game)
            teams_changed = game is not None
        if game is None:
            return
        score_changed = self.prompt_score(tour, snapshot, game)
        if score_changed or teams_changed:
            self._refresh_games(tour, snapshot)
            self.regenerate()

    def delete_selected_json(self):
        selected = self.games_table.selection()
        if not selected or selected[0] not in self.json_items:
            messagebox.showinfo("Stats", "Expand a round and select a JSON file to delete.", parent=self.host)
            return
        game_id, file_name = self.json_items[selected[0]]
        if not messagebox.askyesno("Delete JSON", f"Delete {file_name} from {game_id}?", parent=self.host):
            return
        try:
            tour, snapshot = self._tour_and_snapshot()
            state = self.service.load_state(tour)
            game = next(item for item in state["games"] if item["id"] == game_id)
            game["files"].remove(file_name)
            path = self.service.paths(tour)["jsons"] / file_name
            if path.exists():
                path.unlink()
            if not game["files"]:
                state["games"].remove(game)
            self.service.save_state(tour, state)
        except (OSError, StopIteration, ValueError) as exc:
            messagebox.showerror("Delete JSON", str(exc), parent=self.host)
            return
        self._refresh_games(tour, snapshot)
        if any(game.get("files") for game in state["games"]):
            self.regenerate()
        else:
            for item in self.stats_table.get_children():
                self.stats_table.delete(item)
            self.latest_images = []
            self.status_var.set("Deleted the last uploaded JSON.")

    def clear_jsons(self):
        if self.running:
            return
        if not messagebox.askyesno(
            "Clear all JSONs?",
            "Clear all JSONs for the current tour? This cannot be undone.",
            parent=self.host,
        ):
            return
        try:
            tour, snapshot = self._tour_and_snapshot()
            self.service.clear_jsons(tour)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Clear JSONs", str(exc), parent=self.host)
            return
        self._refresh_games(tour, snapshot)
        for item in self.stats_table.get_children():
            self.stats_table.delete(item)
        self.latest_images = []
        self.status_var.set("Cleared all JSONs for this tour.")

    def regenerate(self):
        if self.running:
            return
        try:
            tour, snapshot = self._tour_and_snapshot()
            codes_text = self.host.codes_text.get("1.0", "end-1c")
            if not codes_text.strip():
                raise ValueError("Make teams before generating local stats.")
            self.service.prepare_workspace(
                tour,
                codes_text,
                self.challonge_var.get(),
                self._substitute_players(),
                self._substitute_team_labels(tour, snapshot),
            )
        except ValueError as exc:
            messagebox.showerror("Stats", str(exc), parent=self.host)
            return
        self.running = True
        self.status_var.set("Generating local stats...")
        threading.Thread(target=self._run_in_background, args=(tour, snapshot), daemon=True).start()

    def _run_in_background(self, tour, snapshot):
        try:
            result = self.service.run_local(tour, self.host.balance_mode == "eru")
            error = None
        except Exception as exc:
            result = None
            error = f"{type(exc).__name__}: {exc}"
        self.host.after(0, lambda: self._finish_run(tour, snapshot, result, error))

    def finalize(self):
        if self.running:
            return
        link = self.challonge_var.get().strip()
        if not link:
            link = simpledialog.askstring(
                "Finalize Stats",
                "Enter the final Challonge link:",
                parent=self.host,
            )
            if not link or not link.strip():
                return
            link = link.strip()
            self.challonge_var.set(link)
        if not messagebox.askyesno(
            "Finalize Stats",
            "This exports every final stats image to Downloads and appends this tour's stats to Google Sheets. Continue?",
            parent=self.host,
        ):
            return
        try:
            tour, snapshot = self._tour_and_snapshot()
            codes_text = self.host.codes_text.get("1.0", "end-1c")
            if not codes_text.strip():
                raise ValueError("Make teams before finalizing stats.")
            self.service.prepare_workspace(
                tour,
                codes_text,
                link,
                self._substitute_players(),
                self._substitute_team_labels(tour, snapshot),
            )
        except ValueError as exc:
            messagebox.showerror("Finalize Stats", str(exc), parent=self.host)
            return
        self.running = True
        self.status_var.set("Finalizing stats and sending them to Google Sheets...")
        threading.Thread(target=self._finalize_in_background, args=(tour, snapshot), daemon=True).start()

    def _finalize_in_background(self, tour, snapshot):
        try:
            result = self.service.finalize(tour, self.host.balance_mode == "eru")
            error = None
        except Exception as exc:
            result = None
            error = f"{type(exc).__name__}: {exc}"
        self.host.after(0, lambda: self._finish_finalize(tour, snapshot, result, error))

    def _finish_run(self, tour, snapshot, result, error):
        self.running = False
        if error:
            self.status_var.set(f"Stats generation failed: {error}")
            messagebox.showerror("Stats", error, parent=self.host)
            return
        players = result["players"]
        self.latest_images = [Path(path) for path in result.get("images", [])]
        self._populate_stats(players)
        self._notify_guess_changes(tour, snapshot, players)
        self.status_var.set(f"Updated local stats from {len(self.service.load_state(tour)['games'])} game(s).")

    def _finish_finalize(self, tour, snapshot, result, error):
        self.running = False
        if error:
            self.status_var.set(f"Finalizing stats failed: {error}")
            messagebox.showerror("Finalize Stats", error, parent=self.host)
            return
        players = result["players"]
        self.latest_images = [Path(path) for path in result.get("images", [])]
        self._populate_stats(players)
        exported = self._export_images("AMQ Final Stats")
        self.status_var.set("Final stats exported and sent to Google Sheets.")
        messagebox.showinfo(
            "Finalize Stats",
            f"Sent final stats to Google Sheets and exported {len(exported)} image(s) to Downloads.",
            parent=self.host,
        )

    def _populate_stats(self, frame):
        columns = [column for column in ("Player name", "Guess rate", "Usefulness", "erigs", "avg/8", "Total hit", "Total songs", "W-L-T") if column in frame.columns]
        self.stats_table.configure(columns=columns)
        for column in columns:
            self.stats_table.heading(column, text=column)
            self.stats_table.column(column, width=120, anchor="center")
        for item in self.stats_table.get_children():
            self.stats_table.delete(item)
        for _, row in frame.iterrows():
            self.stats_table.insert("", "end", values=[row[column] for column in columns])

    def _notify_guess_changes(self, tour, snapshot, frame):
        if self.host.balance_mode == "eru":
            return
        new_players = getattr(self.host, "stats_newly_rated_players", set())
        if not new_players or "Player name" not in frame or "Guess rate" not in frame:
            return
        state = self.service.load_state(tour)
        old_guesses = {
            player["name"].casefold(): str(player.get("guess", ""))
            for team in snapshot.get("teams", {}).values()
            for player in team.get("players", [])
        }
        notices = []
        for _, row in frame.iterrows():
            name = str(row["Player name"])
            if name.casefold() not in {player.casefold() for player in new_players}:
                continue
            try:
                gr = float(row["Guess rate"])
            except (TypeError, ValueError):
                continue
            guess = self.service.guess_count(tour, gr, int(self.host.maximum_guesses.get()))
            previous = state["guess_counts"].get(name.casefold(), old_guesses.get(name.casefold()))
            state["guess_counts"][name.casefold()] = guess
            if previous and previous != guess:
                notices.append(f"{name} is now {guess} guesses ({gr:.3f}%)!")
        self.service.save_state(tour, state)
        if notices:
            messagebox.showinfo("Guess Count Changed", "\n".join(notices), parent=self.host)

    def export_image(self):
        image = next((path for path in self.latest_images if path.exists()), None)
        if image is None:
            messagebox.showerror("Stats", "Generate local stats before exporting an image.", parent=self.host)
            return
        target = self._export_images("AMQ Stats", [image])[0]
        self.status_var.set(f"Exported {target.name} to Downloads.")

    def _export_images(self, prefix, images=None):
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H%M%S")
        exported = []
        for index, image in enumerate(images or self.latest_images, start=1):
            if not image.exists():
                continue
            target = downloads / f"{prefix} {timestamp} {index}.png"
            shutil.copy2(image, target)
            exported.append(target)
        return exported
