from __future__ import annotations

import json
import re
from pathlib import Path

from modules.support.handleCodes import handleCodes
from modules.support.hostConfig import CODE_GENERATORS
from modules.support.hostGuess import GUESS_HANDLERS
from modules.support.playerRatings import resolve_player_ratings


def apply_setup_code(final_code: str, setup_code: str) -> str:
    if not setup_code:
        return final_code
    replacement = f"```{setup_code}```"
    if re.search(r"```.*?```", final_code, flags=re.S):
        return re.sub(r"```.*?```", replacement, final_code, count=1, flags=re.S)
    return f"{replacement}\n\n{final_code}"


def guess_kwargs(tour, player_stats, idtable):
    thresholds = tour["solver"]["thresholds"]
    kwargs = {"player_stats": player_stats, "idtable": idtable}
    if tour["solver"]["guess_mode"] == "watched_28":
        kwargs.update({
            "zerog": thresholds["zero"],
            "oneg": thresholds["one"],
            "twog": thresholds["two"],
            "threeg": thresholds["three"],
            "fourg": thresholds["four"],
        })
    elif tour["solver"]["guess_mode"] == "watched" or tour["solver"]["guess_mode"] == "random5g":
        kwargs.update({
            "oneg": thresholds["one"],
            "twog": thresholds["two"],
            "threeg": thresholds["three"],
            "fourg": thresholds["four"],
        })
    else:
        kwargs.update({
            "oneg": thresholds["one"],
            "twog": thresholds["two"],
            "threeg": thresholds["three"],
        })
    return kwargs


def make_latest_team_snapshot(tour, solution, p_values, teams_number, get_guesses=None, guess_options=None):
    team_map = [[] for _ in range(teams_number)]
    for name, team_index in solution.items():
        team_map[team_index].append((name, p_values[name]))

    teams = {}
    for index, members in enumerate(team_map, start=1):
        team_id = f"team{index}"
        sorted_members = sorted(members, key=lambda item: item[1], reverse=True)
        top_player = sorted_members[0][0] if sorted_members else f"Team {index}"
        players = []
        for name, rating in sorted_members:
            guess = ""
            if get_guesses is not None:
                guess = get_guesses(name, **(guess_options or {}))
            players.append({"name": name, "rating": round(float(rating), 3), "guess": str(guess)})
        teams[team_id] = {
            "label": top_player,
            "display_name": " ".join(f"{name} ({rating:.3f})" for name, rating in sorted_members),
            "players": players,
        }

    return {"tour_id": tour["id"], "teams": teams}


def make_latest_inhouse_snapshot(tour, solution, p_values, teams_number, get_guesses=None, guess_options=None):
    snapshot = make_latest_team_snapshot(tour, solution, p_values, teams_number, get_guesses, guess_options)
    snapshot["inhouse_type"] = tour["inhouse"]["inhouse_type"]
    return snapshot


def solve_player_group(tour, players, team_size, snapshot):
    from utils import create_teams, get_blacklist, get_player_stats

    solver_cfg = tour["solver"]
    teams_number = len(players) // team_size
    p_values = {name: rating for name, rating in players}
    teams = create_teams(
        tour["state_path"],
        players,
        team_size,
        snapshot["whitelist_pairs"],
        get_blacklist(),
        snapshot["separate_t1"],
    )
    player_stats, idtable = get_player_stats(
        path=tour["state_path"],
        tabStats=solver_cfg["stats_tab"],
        tabIDs=tour["sheet"]["tab_ids"],
        type=solver_cfg["stats_type"],
        sheetName=tour["sheet"].get("stats_sheet_name", tour["sheet"]["name"]),
        sheetId=tour["sheet"].get("stats_sheet_id"),
        idsSheetName=tour["sheet"].get("ids_sheet_name"),
        idsSheetId=tour["sheet"].get("ids_sheet_id"),
    )
    guess_options = guess_kwargs(tour, player_stats, idtable)
    get_guesses = GUESS_HANDLERS[solver_cfg["guess_mode"]]
    final_code = handleCodes(
        foundSolutions=teams,
        p_values=p_values,
        k=teams_number,
        get_guesses=get_guesses,
        kwargs_guesses=guess_options,
        get_codes=CODE_GENERATORS[solver_cfg["code_generator"]],
        gamemode=solver_cfg.get("gamemode"),
        gr_based=True,
    )
    final_code = apply_setup_code(final_code, snapshot.get("setup_code", ""))
    Path(tour["state_path"], "codes.txt").write_text(final_code, encoding="utf-8")

    team_snapshot = make_latest_team_snapshot(tour, teams[0], p_values, teams_number, get_guesses, guess_options)
    if tour.get("supports_inhouse"):
        team_snapshot["inhouse_type"] = tour["inhouse"]["inhouse_type"]
    return final_code, team_snapshot


def solve_selected_tour(tour, snapshot, aliases_path):
    solver_cfg = tour["solver"]
    team_size = snapshot["team_size"]
    if team_size <= 0:
        raise ValueError("Team size must be at least 1.")

    if tour.get("dry_elo"):
        from modules.support.mvpGenerator import update_dry_elos_for_tour

        update_dry_elos_for_tour(tour)

    players = resolve_player_ratings(tour, snapshot["player_entries"], snapshot["manual_ratings"], aliases_path)
    if not players:
        raise ValueError("Add players first.")
    if len(players) % team_size != 0:
        raise ValueError(f"{len(players)} players cannot be divided into teams of {team_size}.")

    if solver_cfg.get("sync_ids"):
        from utils import sync_ids_from_sheet

        sync_ids_from_sheet(tour["state_path"], sheetName=tour["sheet"]["name"], tabIDs=tour["sheet"]["tab_ids"])

    if snapshot["split_tour"] and tour.get("supports_inhouse"):
        raise ValueError("Split Tour is not supported for in-house result logging yet.")

    if snapshot["split_tour"] and len(players) >= 32:
        players = sorted(players, key=lambda item: item[1], reverse=True)
        if (len(players) / 2) % 8 == 0:
            separator = len(players) // 2
        else:
            separator = max(0, len(players) // 2 - 4)
        higher_players = players[:separator]
        lower_players = players[separator:]
        lower_code, lower_snapshot = solve_player_group(tour, lower_players, team_size, snapshot)
        higher_code, higher_snapshot = solve_player_group(tour, higher_players, team_size, snapshot)
        combined_teams = {}
        for group, group_snapshot in (("first", lower_snapshot), ("second", higher_snapshot)):
            for team_id, team in group_snapshot["teams"].items():
                combined_teams[f"{group}_{team_id}"] = team
        return "# First Tour\n" + lower_code + "\n\n# Second Tour\n" + higher_code, {"tour_id": tour["id"], "teams": combined_teams}

    return solve_player_group(tour, players, team_size, snapshot)


def save_latest_team_snapshot(tour, snapshot):
    if not snapshot:
        return
    state_path = Path(tour["state_path"])
    state_path.mkdir(parents=True, exist_ok=True)
    (state_path / "latest_teams.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    if tour.get("supports_inhouse"):
        (state_path / "latest_inhouse_teams.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


def save_inhouse_snapshot(tour, snapshot):
    save_latest_team_snapshot(tour, snapshot)
