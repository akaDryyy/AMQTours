import os, sys, json, re, gspread, hashlib

ASSETS_MODULE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
if ASSETS_MODULE_DIR not in sys.path:
    sys.path.insert(0, ASSETS_MODULE_DIR)

from TourClasses import *
from TourFunctions import *
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import tkinter as tk
from tkinter import messagebox, ttk
from collections import defaultdict, Counter
import numpy as np
from html import escape
from shutil import which

try:
    from html2image import Html2Image
    from PIL import Image
except ImportError:
    Html2Image = None
    Image = None


def find_codes_path(script_dir):
    parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
    candidates = [
        os.path.join(script_dir, "codes.txt"),
        os.path.join(os.getcwd(), "codes.txt"),
        os.path.join(parent_dir, "codes.txt"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def read_codes_text(script_dir):
    codes_path = find_codes_path(script_dir)
    if not os.path.exists(codes_path):
        return ""
    with open(codes_path, "r", encoding="utf-8") as codes_file:
        return codes_file.read()



def discover_json_files(json_dir, regex):
    json_files = []
    if not os.path.isdir(json_dir):
        return json_files
    for file_name in os.listdir(json_dir):
        if not file_name.lower().endswith(".json"):
            continue
        songs_played = None
        if not file_name.startswith("amq_song_expoert"):
            reg_match = re.search(regex, file_name)
            if reg_match is not None:
                songs_played = int(reg_match.group(1))
        json_files.append((file_name, songs_played))
    return json_files


def parse_bruteforce_codes(codes_path, teams_re):
    if not os.path.exists(codes_path):
        return None, None, "codes.txt was not found"
    teams = []
    average_rank = None
    try:
        with open(codes_path, "r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line:
                    continue
                if line.lower().startswith(("average", "avg")):
                    match = re.search(r"(-?\d+(?:\.\d+)?)", line)
                    if match:
                        average_rank = float(match.group(1))
                    continue
                if line.lower().startswith(("http", "sub")):
                    continue
                team_text = line.split("|", 1)[0].strip()
                matches = re.findall(teams_re, team_text)
                if not matches:
                    return None, None, f"could not parse this codes.txt line: {raw_line.rstrip()}"
                teams.append([(name, float(rank)) for name, rank in matches])
    except Exception as exc:
        return None, None, str(exc)
    if not teams:
        return None, None, "codes.txt had no teams"
    if average_rank is None:
        team_totals = [sum(rank for _, rank in team) for team in teams]
        average_rank = float(np.mean(team_totals)) if team_totals else None
    return teams, average_rank, None


def observed_players_from_songs(songs):
    observed = set()
    for song in songs:
        observed.update(get_correct_guess_player_names(song))
        observed.update(
            list_state.get("name")
            for list_state in get_list_state_entries(song)
            if isinstance(list_state, dict) and list_state.get("name")
        )
    return observed


def resolve_bruteforce_rosters(json_payloads, codes_path, teams_re):
    teams, average_rank, error = parse_bruteforce_codes(codes_path, teams_re)
    if error:
        print(f"Brute-force: codes.txt skipped: {error}.")
        return None, None, None
    normalized_team_members = {
        name.strip().casefold(): idx
        for idx, team in enumerate(teams)
        for name, _ in team
    }
    rosters_by_file = {}
    for file_name, songs in json_payloads:
        observed = observed_players_from_songs(songs)
        if not observed:
            print("Brute-force: codes.txt skipped because a JSON had no visible players.")
            return None, None, None
        team_indexes = set()
        for player in observed:
            team_idx = normalized_team_members.get(str(player).strip().casefold())
            if team_idx is None:
                print(f"Brute-force: codes.txt skipped because {player} was not found in codes.txt.")
                return None, None, None
            team_indexes.add(team_idx)
        if len(team_indexes) != 2:
            print(f"Brute-force: codes.txt skipped because {file_name} did not resolve to exactly two teams.")
            return None, None, None
        roster = []
        for team_idx in sorted(team_indexes):
            roster.extend(teams[team_idx])
        rosters_by_file[file_name] = roster
    return rosters_by_file, teams, average_rank


def make_bruteforce_player(name, rank=None):
    return {
        "Rank": rank,
        "Player name": name,
        "Guess rate": 0.0,
        "Usefulness": 0.0,
        "erigs": 0,
        "7/8s": 0,
        "avg/8": 0.0,
        "Lives taken": 0,
        "Lives saved": 0,
        "Total songs": 0,
        "OP guess rate": 0.0,
        "ED guess rate": 0.0,
        "IN guess rate": 0.0,
        "Rigs": 0,
        "Rigs missed": 0,
        "Onlist": 0.0,
        "Offlist": 0.0,
        "_hits": 0,
        "_op_hit": 0,
        "_op_played": 0,
        "_ed_hit": 0,
        "_ed_played": 0,
        "_in_hit": 0,
        "_in_played": 0,
        "_avg8_sum": 0,
        "_onlist_hit": 0,
        "_usefulness_sum": 0.0,
    }


def run_bruteforce_stats(directory, json_dir, codes_path, teams_re, regex):
    json_files = discover_json_files(json_dir, regex)
    if not json_files:
        print("Brute-force: no JSON files found in jsons folder.")
        return

    json_payloads = []
    for file_name, songs_played in json_files:
        with open(os.path.join(json_dir, file_name), "r", encoding="utf-8") as file:
            data = json.load(file)
        songs = data.get("songs", [])
        if songs_played is None:
            songs_played = len(songs)
        json_payloads.append((file_name, songs[:songs_played]))

    rosters_by_file, teams, average_rank = resolve_bruteforce_rosters(json_payloads, codes_path, teams_re)
    codes_are_valid = rosters_by_file is not None and teams is not None and average_rank is not None
    team_size = len(teams[0]) if codes_are_valid and teams else None
    include_rank = codes_are_valid
    inferred_team_size = team_size
    if inferred_team_size is None:
        inferred_team_size = max((len(observed_players_from_songs(songs)) // 2 for _, songs in json_payloads), default=0)
    include_usefulness = inferred_team_size is not None and inferred_team_size > 0
    scale_usefulness = include_usefulness and codes_are_valid and average_rank not in (None, 0)
    usefulness_calc = Usefulness(inferred_team_size, average_rank or 0) if include_usefulness else None
    stats = {}
    type_labels = {1: "OP", 2: "ED", 3: "IN"}
    detected_song_types = set()

    for file_name, songs in json_payloads:
        if codes_are_valid:
            roster_with_ranks = rosters_by_file[file_name]
        else:
            roster_with_ranks = [(name, None) for name in sorted(observed_players_from_songs(songs), key=lambda n: str(n).casefold())]
        if not roster_with_ranks:
            continue

        roster_names = [name for name, _ in roster_with_ranks]
        for player, rank in roster_with_ranks:
            stats.setdefault(player, make_bruteforce_player(player, rank))

        for song in songs:
            if "videoUrl" not in song:
                print(f"Brute-force: skipped incomplete song in {file_name}.")
                continue
            correct = set(get_correct_guess_player_names(song))
            list_states = get_list_state_entries(song)
            listers = {state.get("name") for state in list_states if isinstance(state, dict) and state.get("name")}
            song_type = type_labels.get(song.get("songInfo", {}).get("type"))
            if song_type:
                detected_song_types.add(song_type)
            num_correct = len(correct)

            for player in roster_names:
                row = stats.setdefault(player, make_bruteforce_player(player))
                row["Total songs"] += 1
                if song_type == "OP":
                    row["_op_played"] += 1
                elif song_type == "ED":
                    row["_ed_played"] += 1
                elif song_type == "IN":
                    row["_in_played"] += 1

            for player in correct:
                row = stats.setdefault(player, make_bruteforce_player(player))
                row["_hits"] += 1
                row["_avg8_sum"] += num_correct
                if include_usefulness:
                    row["_usefulness_sum"] += usefulness_calc.get_usefulness(num_correct)
                if num_correct == 1:
                    row["erigs"] += 1
                if song_type == "OP":
                    row["_op_hit"] += 1
                elif song_type == "ED":
                    row["_ed_hit"] += 1
                elif song_type == "IN":
                    row["_in_hit"] += 1

            if roster_names and num_correct == max(0, len(roster_names) - 1):
                for player in roster_names:
                    if player not in correct:
                        stats[player]["7/8s"] += 1

            for player in listers:
                row = stats.setdefault(player, make_bruteforce_player(player))
                row["Rigs"] += 1
                if player in correct:
                    row["_onlist_hit"] += 1
                else:
                    row["Rigs missed"] += 1

    rows = []
    for row in stats.values():
        played = row["Total songs"]
        hits = row["_hits"]
        offlist_played = played - row["Rigs"]
        offlist_hits = hits - row["_onlist_hit"]
        row["Guess rate"] = round(100 * hits / played, 3) if played else 0.0
        if include_usefulness and played:
            usefulness_value = row["_usefulness_sum"]
            if scale_usefulness:
                usefulness_value *= average_rank * 2
            row["Usefulness"] = round(usefulness_value / played, 3)
        else:
            row["Usefulness"] = 0.0
        row["avg/8"] = round(row["_avg8_sum"] / hits, 3) if hits else 0.0
        row["OP guess rate"] = round(100 * row["_op_hit"] / row["_op_played"], 3) if row["_op_played"] else 0.0
        row["ED guess rate"] = round(100 * row["_ed_hit"] / row["_ed_played"], 3) if row["_ed_played"] else 0.0
        row["IN guess rate"] = round(100 * row["_in_hit"] / row["_in_played"], 3) if row["_in_played"] else 0.0
        row["Onlist"] = round(100 * row["_onlist_hit"] / row["Rigs"], 3) if row["Rigs"] else 0.0
        row["Offlist"] = round(100 * offlist_hits / offlist_played, 3) if offlist_played else 0.0
        rows.append({key: value for key, value in row.items() if not key.startswith("_")})

    if not rows:
        print("Brute-force: no visible player stats could be calculated.")
        return

    final_order = []
    if include_rank:
        final_order.append("Rank")
    final_order.extend(["Player name", "Guess rate"])
    if include_usefulness:
        final_order.append("Usefulness")
    final_order.extend([
        "erigs", "7/8s", "avg/8", "Lives taken", "Lives saved", "Total songs",
        "OP guess rate", "ED guess rate", "IN guess rate", "Rigs", "Rigs missed", "Onlist", "Offlist",
    ])
    song_type_columns = {
        "OP": {"OP guess rate"},
        "ED": {"ED guess rate"},
        "IN": {"IN guess rate"},
    }
    if detected_song_types:
        unused_columns = set().union(*(columns for song_type, columns in song_type_columns.items() if song_type not in detected_song_types))
        final_order = [column for column in final_order if column not in unused_columns]
    df = pd.DataFrame(rows)
    df.sort_values("Guess rate", ascending=False, inplace=True)
    df_to_png(
        df=df[final_order],
        path=directory,
        filename="Stats.png",
        reverse_cols=["avg/8", "Rigs missed"],
        exclude_columns=["Rank", "Guess rate", "7/8s"],
        separators=[separator for separator in ["Player name", "Usefulness", "7/8s", "Total songs"] if separator in final_order],
    )
    print(f"Brute-force Stats1 saved at {os.path.join(directory, 'Stats.png')}")


def read_challonge_link_from_codes(codes_path):
    if not os.path.exists(codes_path):
        return None
    with open(codes_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line.startswith("http"):
                return line
    return None


def common_error(title, details=None, fixes=None):
    print("\n=== Common setup issue detected ===")
    print(title)
    if details:
        print("\nWhat I found:")
        for detail in details:
            print(f"- {detail}")
    if fixes:
        print("\nHow to fix it:")
        for fix in fixes:
            print(f"- {fix}")
    try:
        print("----------------")
        continue_anyways = input("Do you want to try to continue anyways? [y/N]")
    except (ValueError, IndexError):
        print("Exiting...")
        raise SystemExit(1)
    if continue_anyways.upper() != "Y":
        print("Exiting...")
        raise SystemExit(1)


def known_player_name(name, playerDB, alias_to_id):
    normalized = normalize_player_name(name)
    if normalized in alias_to_id:
        return True
    try:
        return playerDB.lookup_player_name(name) is not None
    except Exception:
        return False


def validate_codes_file(codes_path, teams_re, require_challonge=True):
    if not os.path.exists(codes_path):
        common_error(
            "Missing codes.txt",
            [f"The script looked for codes.txt at {codes_path}."],
            ["Put codes.txt in the same folder as ngm-stats.py, then run the script again."],
        )

    with open(codes_path, "r", encoding="utf-8") as file:
        lines = [line.rstrip("\n") for line in file]

    nonempty_lines = [line.strip() for line in lines if line.strip()]
    if not nonempty_lines:
        common_error(
            "codes.txt is empty.",
            ["The script needs team codes, an Average line, and a Challonge link."],
            ["Paste the full tour code block into codes.txt before running stats."],
        )

    challonge_link = None
    average_found = False
    team_sizes = []
    bad_lines = []
    bad_sub_lines = []

    for raw_line in nonempty_lines:
        line = raw_line.strip()
        lower = line.casefold()
        if lower.startswith(("average", "avg")):
            average_found = re.search(r"-?\d+(?:\.\d+)?", line) is not None
            continue
        if line.startswith("http"):
            challonge_link = line
            continue
        if lower.startswith("sub"):
            sub_text = line.split(":", 1)[-1].strip()
            if sub_text and not re.findall(teams_re, sub_text):
                bad_sub_lines.append(line)
            continue

        team_text = line.split("|", 1)[0].strip()
        matches = re.findall(teams_re, team_text)
        if not matches:
            bad_lines.append(line)
            continue
        team_sizes.append(len(matches))

    if bad_lines or bad_sub_lines or not team_sizes:
        details = []
        if bad_lines:
            details.extend(f"Could not parse team line: {line}" for line in bad_lines[:5])
        if bad_sub_lines:
            details.extend(f"Could not parse sub line: {line}" for line in bad_sub_lines[:5])
        if not team_sizes:
            details.append("No valid team lines were found.")
        common_error(
            "codes.txt does not look like a valid tour code block.",
            details,
            [
                "Make sure each team line looks like: player (rank) player (rank) ... | Total = ... | Guesses = [...]",
                "Make sure sub lines use the same player (rank) format.",
                "If this is from a different tour, replace codes.txt with the current tour's code block.",
            ],
        )

    if len(set(team_sizes)) > 1:
        common_error(
            "codes.txt has teams with different player counts.",
            [f"Detected team sizes: {sorted(set(team_sizes))}."],
            ["Check for a broken paste, missing player, or extra player in one of the team lines."],
        )

    if not average_found:
        common_error(
            "codes.txt is missing the Average line.",
            ["The stats script uses the Average value for rank/usefulness calculations."],
            ["Paste the complete code block, including the Average line, into codes.txt."],
        )

    if require_challonge and not challonge_link:
        common_error(
            "Missing Challonge link.",
            ["No line starting with http was found in codes.txt."],
            ["Paste the Challonge link at the bottom of codes.txt, under the Average line."],
        )

    return challonge_link


def match_has_final_score(match):
    scores = match.get("scores")
    if not isinstance(scores, list) or len(scores) < 2:
        return False
    try:
        score1 = int(scores[0])
        score2 = int(scores[1])
    except (TypeError, ValueError):
        return False
    return score1 != score2 or str(match.get("state", "")).casefold() in {"complete", "completed"}


def parse_challonge_rounds(rounds_text):
    if not rounds_text:
        return []
    rounds = []
    for raw_round in rounds_text.split(","):
        raw_round = raw_round.strip()
        if not raw_round:
            continue
        try:
            rounds.append(int(raw_round))
        except ValueError:
            common_error(
                "Could not parse Challonge substitute round data.",
                [f"Round tag [{rounds_text}] is not a comma-separated list of round numbers."],
                [
                    "Check the sub round notation in Challonge/codes.",
                    "Use values like [1], [2], or [1,2] when marking sub rounds.",
                ],
            )
    return rounds


def validate_challonge_finalized(challonge_data, is_local):
    incomplete = []
    for round_key, matches in challonge_data.get("matches_by_round", {}).items():
        for match_index, match in enumerate(matches, start=1):
            p1 = match.get("player1", {}).get("display_name", "")
            p2 = match.get("player2", {}).get("display_name", "")
            if not p1 or not p2:
                continue
            if not match_has_final_score(match):
                incomplete.append(f"Round {round_key}, match {match_index}: {p1} vs {p2}")

    if incomplete:
        common_error(
            "Challonge is not finalized yet.",
            incomplete[:6],
            [
                "Finalize/report all matches on Challonge first.",
                "If a match was a tie in-game, make sure Challonge still has a completed result the script can read.",
            ],
        )


def validate_challonge_players_against_codes(challonge_data, teamDB, playerDB, alias_to_id, id_to_aliases, masquerade_mapping=None):
    missing = []
    for round_key, matches in challonge_data.get("matches_by_round", {}).items():
        for match in matches:
            for side in ("player1", "player2"):
                display_name = match.get(side, {}).get("display_name", "")
                for name, rounds_played, _ in parse_challonge_display_players(display_name):
                    rounds = parse_challonge_rounds(rounds_played)
                    if rounds and int(round_key) not in rounds:
                        continue
                    if lookup_tour_player_by_name(name, teamDB, playerDB, alias_to_id, id_to_aliases, masquerade_mapping) is None:
                        missing.append(name)

    if missing:
        common_error(
            "Challonge has player/sub data that is not in codes.txt.",
            [f"{name} appeared on Challonge but was not found in the current tour teams." for name in sorted(set(missing))],
            [
                "If this player was a substitute, add them to the sub line in codes.txt.",
                "If the player is in codes.txt under another AMQ name, add the alias to NGM Stats Export v2.",
                "If Challonge has the wrong player/sub data, fix Challonge and rerun the script.",
            ],
        )


def json_file_fingerprint(songs):
    payload = json.dumps(songs, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_json_payload(file_name, json_data, songs_played):
    songs = json_data.get("songs") if isinstance(json_data, dict) else None
    if not isinstance(songs, list) or not songs:
        common_error(
            "JSON by disconnected player detected.",
            [f"{file_name} has no usable songs list."],
            [
                "Delete this JSON and export the lobby JSON again from a player who stayed connected.",
                "Also check that this JSON is from the current tour, not an older run.",
            ],
        )
    if songs_played is not None and songs_played > len(songs):
        common_error(
            "JSON by disconnected player detected.",
            [f"{file_name} says it should have {songs_played} songs, but only {len(songs)} were found."],
            ["Re-export the JSON or remove the broken file from the jsons folder."],
        )

    checked_songs = songs[:songs_played] if songs_played is not None else songs
    for index, song in enumerate(checked_songs, start=1):
        if not isinstance(song, dict) or "videoUrl" not in song:
            common_error(
                "JSON by disconnected player detected.",
                [f"{file_name} is missing crucial song data at song {index}."],
                [
                    "This usually happens when the exporting player disconnected/refreshed.",
                    "Delete this JSON and use a complete export from another player.",
                ],
            )
    return checked_songs


def preflight_json_files(json_dir, regex, teamDB=None, playerDB=None, alias_to_id=None, id_to_aliases=None, masquerade_mapping=None):
    if not os.path.isdir(json_dir):
        common_error(
            "Missing jsons folder.",
            [f"The script looked for JSON files at {json_dir}."],
            ["Create a jsons folder next to ngm-stats.py and put the tour JSON exports there."],
        )

    json_files = [file_name for file_name in sorted(os.listdir(json_dir)) if file_name.lower().endswith(".json")]
    if not json_files:
        common_error(
            "No JSON files found.",
            [f"The jsons folder is empty: {json_dir}"],
            ["Put the AMQ song export JSON files for this tour into the jsons folder."],
        )

    fingerprints = defaultdict(list)
    unresolved_known = defaultdict(set)
    unresolved_aliases = defaultdict(set)

    for file_name in json_files:
        songs_played = None
        if not file_name.startswith("amq_song_expoert"):
            reg_match = re.search(regex, file_name)
            if reg_match is not None:
                songs_played = int(reg_match.group(1))

        path = os.path.join(json_dir, file_name)
        try:
            with open(path, "r", encoding="utf8") as file:
                json_data = json.load(file)
        except Exception as exc:
            common_error(
                "Could not read JSON file.",
                [f"{file_name}: {exc}"],
                ["Make sure the file is a real AMQ song export JSON and not a renamed text/html file."],
            )

        if songs_played is None:
            songs = json_data.get("songs") if isinstance(json_data, dict) else []
            songs_played = len(songs) if isinstance(songs, list) else None
        songs = validate_json_payload(file_name, json_data, songs_played)
        fingerprints[json_file_fingerprint(songs)].append(file_name)

        if teamDB is None:
            continue
        observed = observed_players_from_songs(songs)
        if not observed:
            common_error(
                "JSON by disconnected player detected.",
                [f"{file_name} has no visible players in correct guesses or list states."],
                ["Delete this JSON and export again from a complete lobby export."],
            )
        for observed_name in observed:
            player = lookup_tour_player_by_name(
                observed_name,
                teamDB,
                playerDB,
                alias_to_id,
                id_to_aliases,
                masquerade_mapping,
            )
            if player is not None:
                continue
            if known_player_name(observed_name, playerDB, alias_to_id):
                unresolved_known[file_name].add(observed_name)
            else:
                unresolved_aliases[file_name].add(observed_name)

    duplicate_sets = [names for names in fingerprints.values() if len(names) > 1]
    if duplicate_sets:
        common_error(
            "Identical JSON detected.",
            [f"These files contain the same songs/data: {', '.join(names)}" for names in duplicate_sets],
            [
                "Delete the duplicate JSON file.",
                "If this came from a previous tour, clear the jsons folder before rerunning stats.",
            ],
        )

    if unresolved_aliases:
        details = []
        for file_name, names in unresolved_aliases.items():
            details.append(f"{file_name}: {', '.join(sorted(names))}")
        common_error(
            "New alias detected that is not in the alias list.",
            details,
            [
                "Add the player's current AMQ name/alias to NGM Stats Export v2.",
                "If this JSON is from a previous tour, delete it from the jsons folder.",
            ],
        )

    if unresolved_known:
        details = []
        for file_name, names in unresolved_known.items():
            details.append(f"{file_name}: {', '.join(sorted(names))}")
        common_error(
            "JSON player is not on the current codes.txt roster.",
            details,
            [
                "If this was a substitute, add the sub to codes.txt.",
                "If this JSON is from a previous tour, delete it from the jsons folder.",
                "If the player is in codes.txt under another name, add the missing alias to NGM Stats Export v2.",
            ],
        )

    return True


def get_player_name_from_entry(entry):
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for key in ("name", "playerName", "username", "amqName", "player"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                nested_name = get_player_name_from_entry(value)
                if nested_name:
                    return nested_name
    return None


def get_correct_guess_player_names(song):
    players = song.get("correctGuessPlayers", [])
    if isinstance(players, dict):
        names = []
        for key, value in players.items():
            name = get_player_name_from_entry(value) if isinstance(value, dict) else None
            if not name:
                name = str(key)
            if name:
                names.append(name)
        return names
    if not isinstance(players, list):
        return []
    names = []
    for entry in players:
        name = get_player_name_from_entry(entry)
        if name:
            names.append(name)
    return names


def get_list_state_entries(song):
    list_states = song.get("listStates", [])
    if isinstance(list_states, dict):
        return list(list_states.values())
    return list_states if isinstance(list_states, list) else []


def parse_answer_time_value(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return None


def collect_answer_time_entries_from_container(container):
    entries = []
    if isinstance(container, dict):
        name = get_player_name_from_entry(container)
        time_value = None
        for key in ("answerTime", "answer_time", "time", "guessTime", "guess_time", "responseTime", "response_time"):
            if key in container:
                time_value = parse_answer_time_value(container.get(key))
                break
        if name and time_value is not None:
            entries.append((name, time_value))
        else:
            for name_key, raw_time in container.items():
                if isinstance(raw_time, dict):
                    mapped_name = get_player_name_from_entry(raw_time) or str(name_key)
                    mapped_time = None
                    for key in ("answerTime", "answer_time", "time", "guessTime", "guess_time", "responseTime", "response_time"):
                        if key in raw_time:
                            mapped_time = parse_answer_time_value(raw_time.get(key))
                            break
                    if mapped_name and mapped_time is not None:
                        entries.append((mapped_name, mapped_time))
                    else:
                        entries.extend(collect_answer_time_entries_from_container(raw_time))
                elif isinstance(raw_time, list):
                    entries.extend(collect_answer_time_entries_from_container(raw_time))
                else:
                    parsed_time = parse_answer_time_value(raw_time)
                    if parsed_time is not None:
                        entries.append((str(name_key), parsed_time))
    elif isinstance(container, list):
        for item in container:
            entries.extend(collect_answer_time_entries_from_container(item))
    return entries


def get_answer_time_entries(song):
    entries = []
    for field in ("correctGuessTimes", "correctAnswerTimes"):
        if field in song:
            entries.extend(collect_answer_time_entries_from_container(song.get(field)))
    for entry in song.get("correctGuessPlayers", []):
        if isinstance(entry, dict):
            entries.extend(collect_answer_time_entries_from_container(entry))

    deduped = []
    seen = set()
    for name, time_value in entries:
        key = (str(name).casefold(), time_value)
        if key not in seen:
            seen.add(key)
            deduped.append((name, time_value))
    return deduped


def average_answer_time_for_song(song):
    values = [time_value for _, time_value in get_answer_time_entries(song)]
    return round(float(np.mean(values)), 3) if values else ""


def get_tour_player_pool(teamDB):
    players = []
    for team in teamDB.teams:
        players.extend(team.players)
        players.extend(team.subs)
    players.extend(teamDB.subs)
    unique_players = {}
    for player in players:
        if player is not None:
            unique_players[player.player_id] = player
    return list(unique_players.values())


def lookup_tour_player_by_name(name, teamDB, playerDB, alias_to_id, id_to_aliases, masquerade_mapping=None):
    if masquerade_mapping:
        name = masquerade_mapping.get(str(name).strip().casefold(), name)

    tour_players = get_tour_player_pool(teamDB)
    tour_names = [player.name for player in tour_players]
    resolved_name = resolve_player_name(name, tour_names, alias_to_id, id_to_aliases)
    if resolved_name:
        return next((player for player in tour_players if normalize_player_name(player.name) == normalize_player_name(resolved_name)), None)

    player = playerDB.lookup_player_name(name)
    if player is None:
        return None
    return next((tour_player for tour_player in tour_players if tour_player.player_id == player.player_id), None)


def require_tour_player(name, teamDB, playerDB, alias_to_id, id_to_aliases, context, masquerade_mapping=None):
    player = lookup_tour_player_by_name(name, teamDB, playerDB, alias_to_id, id_to_aliases, masquerade_mapping)
    if player is not None:
        return player
    if known_player_name(name, playerDB, alias_to_id):
        common_error(
            "JSON player is not on the current codes.txt roster.",
            [f"{name} from {context} was not found in the current tour teams."],
            [
                "If this player was a substitute, add the sub to codes.txt.",
                "If this JSON is from a previous tour, delete it from the jsons folder.",
                "For Masquerade mode, make sure codes.txt maps real AMQ name first and Challonge/lobby name second.",
            ],
        )
    common_error(
        "New alias detected that is not in the alias list.",
        [f"{name} from {context} was not found in NGM Stats Export v2 aliases."],
        [
            "Add this AMQ name/alias to NGM Stats Export v2.",
            "If this JSON is from a previous tour, delete it from the jsons folder.",
        ],
    )


def read_masquerade_mapping_from_codes(codes_path):
    if not os.path.exists(codes_path):
        return {}
    mapping = {}
    with open(codes_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("http"):
                continue
            header_check = re.sub(r"\s+", " ", line.replace("\t", " ")).casefold()
            if header_check in {"amq name masq name", "amq masq"}:
                continue
            if "|" in line or re.search(r"\([^)]*\)", line):
                continue
            parts = [part.strip() for part in line.split("\t") if part.strip()]
            if len(parts) < 2:
                parts = line.split()
            if len(parts) < 2:
                continue
            amq_name, masq_name = parts[0].strip(), parts[1].strip()
            if amq_name and masq_name:
                mapping[masq_name.casefold()] = amq_name
    return mapping


def extract_challonge_store_data(html):
    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script"):
        content = script.string
        if not content:
            continue
        match = re.search(
            r"window\._initialStoreState\['TournamentStore'\]\s*=\s*({.*?});",
            content,
            re.DOTALL,
        )
        if match:
            data_str = match.group(1)
            data_str = data_str.replace("'", '"')
            data_str = re.sub(r",\s*}", "}", data_str)
            data_str = re.sub(r",\s*]", "]", data_str)
            return json.loads(data_str)
    raise RuntimeError("Could not read Challonge tournament data.")


def parse_challonge_display_players(display_name):
    player_text = (display_name or "").split("|", 1)[0]
    pattern = r"([^\s\[(|]+)(?:\s*\[(.*?)\])?(?:\s*\((-?\d+(?:\.\d+)?)\))?"
    ignored_tokens = {"total", "guesses", "average", "avg", "="}
    parsed_players = []
    for name, rounds_text, rank_text in re.findall(pattern, player_text):
        if not name:
            continue
        if name.casefold() in ignored_tokens:
            continue
        if re.fullmatch(r"-?\d+(?:\.\d+)?", name):
            continue
        parsed_players.append((name, rounds_text, rank_text))
    return parsed_players


def parse_masquerade_rank(rank_text):
    try:
        return float(rank_text)
    except (TypeError, ValueError):
        return 0.0


def resolve_masquerade_name(masq_name, mapping, playerDB, alias_to_id, id_to_aliases):
    amq_name = mapping.get(str(masq_name).strip().casefold())
    if not amq_name:
        raise ValueError(f"No AMQ name mapping was provided for masquerade name '{masq_name}'.")
    available = [player.name for player in playerDB.players]
    resolved = resolve_player_name(amq_name, available, alias_to_id, id_to_aliases)
    if not resolved:
        raise ValueError(f"Mapped AMQ name '{amq_name}' for masquerade name '{masq_name}' was not found in the valid alias list.")
    return resolved


def build_masquerade_teams(teamDB, playerDB, avg_df, challonge_data, mapping, alias_to_id, id_to_aliases):
    seen_teams = set()
    for matches in challonge_data.get("matches_by_round", {}).values():
        for match in matches:
            for side in ["player1", "player2"]:
                display = match.get(side, {}).get("display_name", "")
                parsed_players = parse_challonge_display_players(display)
                if not parsed_players:
                    continue
                resolved_players = []
                for masq_name, _, rank_text in parsed_players:
                    resolved_name = resolve_masquerade_name(masq_name, mapping, playerDB, alias_to_id, id_to_aliases)
                    player = playerDB.lookup_player_name(resolved_name)
                    player.rank = parse_masquerade_rank(rank_text)
                    player.set_averages(avg_df)
                    resolved_players.append(player)
                team_key = tuple(player.player_id for player in resolved_players)
                if team_key in seen_teams:
                    continue
                seen_teams.add(team_key)
                team_string = " ".join(f"{player.name} ({player.rank})" for player in resolved_players)
                team = Team(team_string=team_string)
                for player in resolved_players:
                    team.add_player(player)
                teamDB.add_team(team)
    if not teamDB.teams:
        raise RuntimeError("No teams could be built from the Challonge page.")
    return teamDB.teams[0].get_team_size()



def prepare_masquerade_codes(original_codes_path, output_codes_path, playerDB, alias_to_id, id_to_aliases):
    challonge_link = read_challonge_link_from_codes(original_codes_path)
    if not challonge_link:
        raise RuntimeError("codes.txt must contain a Challonge link for Masquerade mode.")
    html = download_challonge_page(challonge_link)
    challonge_data = extract_challonge_store_data(html)
    codes_mapping = read_masquerade_mapping_from_codes(original_codes_path)
    if not codes_mapping:
        raise RuntimeError("codes.txt must contain masquerade mapping rows before the Challonge link.")

    canonical_mapping = {}
    display_name_by_player = {}
    team_lines = []
    seen_teams = set()
    team_totals = []
    for matches in challonge_data.get("matches_by_round", {}).values():
        for match in matches:
            for side in ["player1", "player2"]:
                display = match.get(side, {}).get("display_name", "")
                parsed_players = parse_challonge_display_players(display)
                if not parsed_players:
                    continue
                team_parts = []
                team_key = []
                team_total = 0.0
                for masq_name, _, rank_text in parsed_players:
                    canonical_name = resolve_masquerade_name(masq_name, codes_mapping, playerDB, alias_to_id, id_to_aliases)
                    canonical_mapping[str(masq_name).strip().casefold()] = canonical_name
                    display_name_by_player[canonical_name] = str(masq_name).strip()
                    rank = parse_masquerade_rank(rank_text)
                    team_parts.append(f"{canonical_name} ({rank:.3f})")
                    team_key.append(canonical_name.casefold())
                    team_total += rank
                team_key = tuple(team_key)
                if team_key in seen_teams:
                    continue
                seen_teams.add(team_key)
                team_totals.append(team_total)
                team_lines.append(" ".join(team_parts) + f" | Total = {team_total:.3f}")

    if not team_lines:
        raise RuntimeError("No teams could be built from the Challonge page.")
    average = float(np.mean(team_totals)) if team_totals else 0.0
    with open(output_codes_path, "w", encoding="utf-8") as file:
        file.write("\n".join(team_lines))
        file.write(f"\n\nAverage: {average:.4f}\n\n{challonge_link}\n")
    return output_codes_path, canonical_mapping, display_name_by_player

def lookup_masquerade_wlt_player(name, masquerade_mapping, playerDB, alias_to_id, id_to_aliases):
    if masquerade_mapping:
        name = resolve_masquerade_name(name, masquerade_mapping, playerDB, alias_to_id, id_to_aliases)
    return playerDB.lookup_player_name(name)

def run_ngm_sheet_stats(is_local):
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    ASSETS = os.path.join(DIRECTORY, "assets")
    JSONS = os.path.join(DIRECTORY, "jsons")
    TEAMS = find_codes_path(DIRECTORY)
    TEAMS_RE = r"(\S+)\s*\((-?[\d.]+)\)"
    REGEX = r"\D*(\d{1,2})\s*(\(.*?\))?\.json$"
    os.makedirs(ASSETS, exist_ok=True)
    
    MAIN_SHEET_RANDOM=0
    MAIN_SHEET_WATCHED=1719516221
    SHEET_PLAYER_IDS=1903970832
    MAIN_SHEET_SPEED=165193471
    MAIN_SHEET_OTHER=2090958619
    MAIN_SHEET_OPS=591917504
    MAIN_SHEET_EDS=601464032
    MAIN_SHEET_INS=2075065970
    MAIN_SHEET_OPEDS=1506914251
    MAIN_SHEET_5S=676003100
    MAIN_SHEET_WATCHED_INS=1177294729
    MAIN_SHEET_WATCHED_EDS=484347985

    TEAM_AVG = 0
    TEAM_SIZE = 0

    playerDB = PlayerDB()
    teamDB = TeamDB()
    tourGames = TourGames()
    songDB = SongDB()

    sheetName = "NGM Stats Export v2"
    sheetId = NGM_STATS_SHEET_ID
    orderToSheet = [
        "Timestamp",
        "Rank", 
        "Player name", 
        "Guess rate", 
        "Usefulness",
        "erigs",
        "0/8s",
        "7/8s",
        "avg/8",
        "# 3/8s or below",
        "OP guess rate", 
        "ED guess rate",
        "IN guess rate",
        "Lives taken",
        "Lives saved",
        "Total hit",
        "Total songs",
        "WIN",
        "LOSE",
        "TIE",
    ]

    watchedColumns = [
        "Onlist",
        "Offlist",
        "Rig %",
        "Rigs",
        "Solo rigs",
        "Missed solos",
        "Rigs hit",
        "Rigs missed",
        "Lives lost on rigs",
        "Offlist erigs",
        "avg/8 of your rigs"
    ]

    txtvar = """=== NGMC Stats Calculator ===
[1]: Random FL
[2]: Watched FL
[3]: Watched OPs
[4]: Watched EDs
[5]: Watched INs
[6]: Watched INs -chanting
[7]: Watched FL 2+8s
[8]: Watched FL 5s
[9]: Watched -2009
[10]: Random OPs
[11]: Random EDs
[12]: Random INs
[13]: Random OPEDs
[14]: Random Chanting
[15]: Other Random
[16]: Other Watched
[17]: Brute-force
[18]: Masquerade
"""

    print(txtvar)
    is_list = False
    is_other = False
    brute_force = False
    masquerade_mode = False
    masquerade_name_by_player = {}
    masquerade_mapping = {}
    server_average_mode = "random_fl"
    tour_type_label = "Random FL"
    while True:
        try:
            gamemode = input("Select game mode [#]:")
        except (ValueError, IndexError):
            print("Please input a valid choice")
        break
    match gamemode:
        case "1":
            gamemode = MAIN_SHEET_RANDOM
            sendToSheet = gamemode
            server_average_mode = "random_fl"
            tour_type_label = "Random FL"
        case "2":
            gamemode = MAIN_SHEET_WATCHED
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_fl"
            tour_type_label = "Watched FL"
            orderToSheet.extend(watchedColumns)
        case "3":
            gamemode = "Watched OP"
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_op"
            tour_type_label = "Watched OP"
            orderToSheet.extend(watchedColumns)
        case "4":
            gamemode = MAIN_SHEET_WATCHED_EDS
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_ed"
            tour_type_label = "Watched ED"
            orderToSheet.extend(watchedColumns)
        case "5":
            gamemode = MAIN_SHEET_WATCHED_INS
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_in"
            tour_type_label = "Watched IN"
            orderToSheet.extend(watchedColumns)
        case "6":
            gamemode = "Watched IN (-chanting)"
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_in_no_chanting"
            tour_type_label = "Watched IN (-chanting)"
            orderToSheet.extend(watchedColumns)
        case "7":
            gamemode = MAIN_SHEET_SPEED
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_fl_speed"
            tour_type_label = "Watched FL 2+8s"
            orderToSheet.extend(watchedColumns)
        case "8":
            gamemode = MAIN_SHEET_5S
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_fl_5s"
            tour_type_label = "Watched FL 5s"
            orderToSheet.extend(watchedColumns)
        case "9":
            gamemode = "Watched -2009"
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_pre_2009"
            tour_type_label = "Watched -2009"
            orderToSheet.extend(watchedColumns)
        case "10":
            gamemode = MAIN_SHEET_OPS
            sendToSheet = gamemode
            server_average_mode = "random_op"
            tour_type_label = "Random OP"
        case "11":
            gamemode = MAIN_SHEET_EDS
            sendToSheet = gamemode
            server_average_mode = "random_ed"
            tour_type_label = "Random ED"
        case "12":
            gamemode = MAIN_SHEET_INS
            sendToSheet = gamemode
            server_average_mode = "random_in"
            tour_type_label = "Random IN"
        case "13":
            gamemode = MAIN_SHEET_OPEDS
            sendToSheet = gamemode
            server_average_mode = "random_oped"
            tour_type_label = "Random OPED"
        case "14":
            gamemode = "Random Chanting"
            sendToSheet = gamemode
            server_average_mode = "random_chanting"
            tour_type_label = "Random Chanting"
        case "15":
            gamemode = MAIN_SHEET_RANDOM
            sendToSheet = MAIN_SHEET_OTHER
            is_other = True
            server_average_mode = "random_fl"
            tour_type_label = "Other Random"
        case "16":
            gamemode = MAIN_SHEET_WATCHED
            sendToSheet = MAIN_SHEET_OTHER
            is_list = True
            is_other = True
            server_average_mode = "watched_fl"
            tour_type_label = "Other Watched"
            orderToSheet.extend(watchedColumns)
        case "17":
            brute_force = True
        case "18":
            masquerade_mode = True
            gamemode = MAIN_SHEET_RANDOM
            sendToSheet = gamemode
            server_average_mode = "random_fl"
            tour_type_label = "Masquerade"

    if brute_force:
        run_bruteforce_stats(DIRECTORY, JSONS, TEAMS, TEAMS_RE, REGEX)
        _ = input('\npress enter to close')
        return

    challonge_link = None
    if not masquerade_mode:
        challonge_link = validate_codes_file(TEAMS, TEAMS_RE, require_challonge=True)
    preflight_json_files(JSONS, REGEX)

    # Grab necessary files
    gc = get_gspread_client(DIRECTORY)
    sync_chanting_ids_file(gc, ASSETS)
    
    sheet = gc.open_by_key(sheetId)
    wks = get_worksheet_by_ref(sheet, gamemode)
    rows_stats = wks.get_all_values()
    wks_ids = sheet.get_worksheet_by_id(SHEET_PLAYER_IDS)
    rows_ids = wks_ids.get_all_values()
    alias_to_id, id_to_aliases = load_player_aliases(gc)

    avg_df = clean_data(rows_ids, rows_stats, 6, 10, is_list)
    avg_df = avg_df.sort_values(["Player ID", "Timestamp"])

    # Build player DB
    for name, pid in rows_ids[1:]:
        playerDB.add_player(Player(name=name, player_id=int(pid)))
    playerDB.build_lookups()

    if masquerade_mode:
        try:
            TEAMS, masquerade_mapping, masquerade_name_by_player = prepare_masquerade_codes(
                TEAMS,
                os.path.join(ASSETS, "masquerade_codes.generated.txt"),
                playerDB,
                alias_to_id,
                id_to_aliases,
            )
            print(f"Masquerade: generated team data at {TEAMS}")
        except Exception as exc:
            input(f"Masquerade setup failed: {exc}\nPress Enter to exit.")
            return

    # Obtain the tour players
    html = None
    with open(TEAMS, "r", encoding="utf-8") as file:
        for line in file.readlines():
            if line.lower().startswith(("average", "avg")):
                avg_match = re.search(r"-?\d+(?:\.\d+)?", line)
                if not avg_match:
                    common_error(
                        "codes.txt has an invalid Average line.",
                        [line.strip()],
                        ["Paste the complete Average line from codes.txt, such as Average: 31.2045."],
                    )
                TEAM_AVG = float(avg_match.group(0))
            if line.startswith("http"):
                challonge_link = line.strip()
                try:
                    html = download_challonge_page(challonge_link)
                except Exception as exc:
                    common_error(
                        "Could not open the Challonge link.",
                        [str(exc)],
                        [
                            "Open the Challonge link in your browser once to make sure it loads.",
                            "If it opens in the browser, Challonge is probably blocking the script temporarily; try again in a bit.",
                            "If it does not open in the browser, fix the Challonge link in codes.txt.",
                        ],
                    )
            if line.lower().startswith(("sub")):
                if line.split(':')[-1]:
                    for name, rank in re.findall(r'(\S+)\s*\(([\d.]+)\)', line):
                        p_name = name
                        p_rank = float(rank)
                        subbing_player = playerDB.lookup_player_name(p_name)
                        if subbing_player is None:
                            common_error(
                                "New alias detected in codes.txt.",
                                [f"{p_name} from the sub line was not found in the alias/player list."],
                                [
                                    "Add this AMQ name or alias to NGM Stats Export v2.",
                                    "If the name is misspelled in codes.txt, fix codes.txt and rerun.",
                                ],
                            )
                        subbing_player.rank = p_rank
                        subbing_player.set_averages(avg_df)
                        teamDB.add_sub(subbing_player)
            else:
                line = line.split("|", 1)[0]
                match = re.findall(TEAMS_RE, line)
                if match:
                    team_id = line.strip()
                    new_team = Team(team_string=team_id)
                    for player in match:
                        player_name, player_rank = player
                        new_player = playerDB.lookup_player_name(player_name)
                        if new_player is None:
                            common_error(
                                "New alias detected in codes.txt.",
                                [f"{player_name} was not found in the alias/player list."],
                                [
                                    "Add this AMQ name or alias to NGM Stats Export v2.",
                                    "If the name is misspelled in codes.txt, fix codes.txt and rerun.",
                                ],
                            )
                        new_player.rank = float(player_rank)
                        new_player.set_averages(avg_df)
                        new_team.add_player(new_player)
                    teamDB.add_team(new_team)
    TEAM_SIZE = new_team.get_team_size()
    playerDB.build_lookups()
    USEFULNESS = Usefulness(TEAM_SIZE, TEAM_AVG)
    
    # Handle W-L-T
    if not html:
        common_error(
            "Missing Challonge link.",
            ["The script could not find or download a Challonge page from codes.txt."],
            ["Paste the Challonge link at the bottom of codes.txt, then rerun stats."],
        )
    try:
        data = extract_challonge_store_data(html)
    except Exception as exc:
        common_error(
            "Could not read Challonge tournament data.",
            [str(exc)],
            [
                "Check that the Challonge link points to the tournament page, not a dashboard/editor page.",
                "If Challonge is temporarily blocking/loading slowly, try again in a bit.",
            ],
        )
    validate_challonge_finalized(data, is_local)
    validate_challonge_players_against_codes(data, teamDB, playerDB, alias_to_id, id_to_aliases, masquerade_mapping)

    for round_key, matches in data["matches_by_round"].items():
        for match in matches:
            match_playersTeam1 = match["player1"]["display_name"]
            match_playersTeam2 = match["player2"]["display_name"]
            playersTeam1 = parse_challonge_display_players(match_playersTeam1)
            playersTeam2 = parse_challonge_display_players(match_playersTeam2)

            scoreT1 = match["scores"][0]
            scoreT2 = match["scores"][1]
            matchResult = "WIN" if scoreT1 > scoreT2 else "LOSE" if scoreT1 < scoreT2 else "TIE"
            inverse_result = {"WIN": "LOSE", "LOSE": "WIN", "TIE": "TIE"}

            player_info = []

            # Team 1 players
            for name, rounds_played, rank in playersTeam1:
                rounds = parse_challonge_rounds(rounds_played)
                try:
                    player_info.append((name, rounds, float(rank) if rank else None, matchResult))
                except ValueError:
                    player_info.append((name, rounds, None, matchResult))

            # Team 2 players
            for name, rounds_played, rank in playersTeam2:
                rounds = parse_challonge_rounds(rounds_played)
                try:
                    player_info.append((name, rounds, float(rank) if rank else None, inverse_result[matchResult]))
                except ValueError:
                    player_info.append((name, rounds, None, matchResult))

            for name, rounds_played, _, result in player_info:
                if not rounds_played or int(round_key) in rounds_played:
                    WLTplayer = teamDB.lookup_player(
                        lookup_masquerade_wlt_player(name, masquerade_mapping, playerDB, alias_to_id, id_to_aliases)
                    )
                    try:
                        WLTplayer.add(result)
                    except AttributeError:
                        common_error(
                            "Sub/player mismatch between Challonge and codes.txt.",
                            [f"{name} appeared in Challonge W-L-T data but was not found in the current tour teams."],
                            [
                                "If this player was a substitute, add them to the sub line in codes.txt.",
                                "If this is a new alias, add it to NGM Stats Export v2.",
                                "If Challonge has the wrong sub data, fix the Challonge match data and rerun.",
                            ],
                        )

    # Handle sub placement
    if teamDB.subs:
        print("Subs have been found. Please assign to correct team:")
        for sub in teamDB.subs:
            print(f"Which of the following teams did {sub.name} sub for?")
            options = (teamDB.teams)
            for i, team in enumerate(options, start=1):
                print(f"[{i}] {team.team_string}")
            while True:
                try:
                    num_choice = int(input("Choice: "))
                except (ValueError, IndexError):
                    print("Please input a valid choice")
                options[num_choice-1].add_sub(sub)
                break

    preflight_json_files(JSONS, REGEX, teamDB, playerDB, alias_to_id, id_to_aliases, masquerade_mapping)

    # Parse the jsons
    list_guess_counts = defaultdict(list)
    raw_json_songs = []
    for file_name in sorted(os.listdir(JSONS)):
        if not file_name.lower().endswith(".json"):
            continue
        if file_name.startswith('amq_song_expoert'):
            songs_played = None
        else:
            reg_match = re.search(REGEX, file_name)
            if reg_match is None:
                songs_played = None
            else:
                songs_played = int(reg_match.group(1))
        
        with open(os.path.join(JSONS, file_name), 'r', encoding="utf8") as f:
            try:
                json_data = json.load(f)
                if songs_played is None:
                    songs_played = len(json_data["songs"])
            except Exception as exc:
                common_error(
                    "Could not read JSON file.",
                    [f"{file_name}: {exc}"],
                    ["Make sure the file is a real AMQ song export JSON and not a renamed text/html file."],
                )
        
        game = Game(file_name)
        playersSeen = []
        json_file_songs = []

        # Parse each song
        for song in json_data['songs'][:songs_played]:
            # Probably downloaded after the user disconnected or refreshed the page
            if 'videoUrl' not in song:
                common_error(
                    "JSON by disconnected player detected.",
                    [f"{file_name} is missing crucial song data at song {song.get('songNumber', '?')}."],
                    [
                        "This usually happens when the exporting player disconnected/refreshed.",
                        "Delete this JSON and use a complete export from another player.",
                    ],
                )

            json_file_songs.append(song)
            if is_list:
                lobby_guesses = len(get_correct_guess_player_names(song))
                for list_state in get_list_state_entries(song):
                    if not isinstance(list_state, dict):
                        continue
                    player_name = list_state.get("name")
                    if player_name:
                        list_guess_counts[player_name].append(lobby_guesses)

            single_song = Song(song)
            songDB.add_song(single_song)
            game.add_song(single_song)
            game.add(single_song.song_type)
            game.add("difficulty", single_song.song_difficulty)
            game.add("vintage", single_song.vintage)

            # Handle the players
            for correctGuesser in get_correct_guess_player_names(song):
                guesser = require_tour_player(
                    correctGuesser,
                    teamDB,
                    playerDB,
                    alias_to_id,
                    id_to_aliases,
                    f"{file_name} song {song.get('songNumber', '?')} correct guesses",
                    masquerade_mapping,
                )
                single_song.add_guesser(guesser)
                if guesser not in playersSeen:
                    playersSeen.append(guesser)
            for playerGotInList in get_list_state_entries(song):
                if not isinstance(playerGotInList, dict) or not playerGotInList.get("name"):
                    continue
                watcher = require_tour_player(
                    playerGotInList["name"],
                    teamDB,
                    playerDB,
                    alias_to_id,
                    id_to_aliases,
                    f"{file_name} song {song.get('songNumber', '?')} list states",
                    masquerade_mapping,
                )
                single_song.add_rig(watcher)
                watcher.add("rigAmount")
                if watcher not in playersSeen:
                    playersSeen.append(watcher)
            for answer_name, answer_time in get_answer_time_entries(song):
                answer_player = lookup_tour_player_by_name(
                    answer_name,
                    teamDB,
                    playerDB,
                    alias_to_id,
                    id_to_aliases,
                    masquerade_mapping,
                )
                if answer_player is not None:
                    answer_player.add("answerTimeTotal", answer_time)
                    answer_player.add("answerTimeCount")
        
        # Handle missing players
        if len(playersSeen) < 2 * TEAM_SIZE:
            zerozeroT1 = []
            zerozeroT2 = []
            playerT1 = teamDB.lookup_player(playersSeen[0])
            team1 = teamDB.get_team_by_player(playerT1)
            team2 = None
            for player in playersSeen[1:]:
                team2 = teamDB.get_team_by_player(teamDB.lookup_player(player))
                if team2 is not team1:
                    break
            for player in team1.players:
                if player not in playersSeen:
                    zerozeroT1.append(player)
            if team2:
                for player in team2.players:
                    if player not in playersSeen:
                        zerozeroT2.append(player)
            else:
                print("A whole team went 0/0. What a disaster.")
                print(f"Which of the following teams did nothing in the {file_name} game?")
                options = teamDB.teams.copy()
                options.remove(team1)
                for i, team in enumerate(options, start=1):
                    print(f"[{i}] {team.team_string}")
                while True:
                    try:
                        num_choice = int(input("Choice: "))
                    except (ValueError, IndexError):
                        print("Please input a valid choice")
                    team2 = options[num_choice-1]
                    for player in team2.players:
                        zerozeroT2.append(player)
                    break
            
            # If neither team has subs, then we know who went 0/0
            if not team1.subs:
                playersSeen.extend(zerozeroT1)
            if not team2.subs:
                playersSeen.extend(zerozeroT2)
            if len(playersSeen) < TEAM_SIZE * 2:
                t1subs = team1.subs.copy()
                t2subs = team2.subs.copy()
                while len(playersSeen) < TEAM_SIZE * 2:
                    options = (
                        [(p, zerozeroT1) for p in zerozeroT1 if p not in playersSeen] +
                        [(p, zerozeroT2) for p in zerozeroT2 if p not in playersSeen] +
                        [(p, t1subs)  for p in t1subs if p not in playersSeen] +
                        [(p, t2subs)  for p in t2subs if p not in playersSeen]
                    )
                    print(f"A 0/0 has been found inside {file_name}.\n"
                        f"Current players: {[player.name for player in playersSeen]}.\n"
                        "Which of the following is the culprit:")
                    for i, (p, _) in enumerate(options, start=1):
                        print(f"[{i}] {p.name}")
                    try: 
                        choice = int(input("Choice: "))
                    except (ValueError, IndexError):
                        print("Please input a valid choice")
                    player, source_list = options[choice - 1]
                    playersSeen.append(player)
                    source_list.remove(player)

                    # Remove all the impossible options
                    # Example: Team already full and sub not chosen -> Sub should not be an option anymore
                    team1_members = {p.player_id for p in (team1.players + team1.subs)}
                    team2_members = {p.player_id for p in (team2.players + team2.subs)}
                    seen = {p.player_id for p in playersSeen}
                    if len(seen & team1_members) == TEAM_SIZE:
                        zerozeroT1.clear()
                        t1subs.clear()
                    if len(seen & team2_members) == TEAM_SIZE:
                        zerozeroT2.clear()
                        t2subs.clear()

        game.players = playersSeen
        game_player_names = [player.name for player in playersSeen]
        for song in json_file_songs:
            song_label = f"Song {len(raw_json_songs) + 1}"
            raw_json_songs.append((song_label, file_name, song, game_player_names))
        tourGames.add_game(game)
    songDB.build_lookups()

    # Compute metrics
    for game in tourGames.games:
        num_songs = len(game.songs)
        eggs = 0
        for game_song in game.songs:
            num_hitters = len(game_song.playerHit)
            num_listers = len(game_song.playerRig)
            # If egg, give erig miss to list players
            if num_hitters == 0:
                eggs += 1
                for erig_misser in game_song.playerRig:
                    erig_misser.add("erigsmissed")
            # If low count, give players low count hits
            if num_hitters < 4:
                for game_player in game_song.playerHit:
                    game_player.add("low_count_hits")

            team_ids = [p.player_team for p in game_song.playerHit]

            # If your name is the only one from your team, you saved a life
            lifesavers = [p for p in game_song.playerHit if team_ids.count(p.player_team) == 1 and num_hitters > 1]
            for p in lifesavers:
                p.add("livesSaved")

            # If nobody on the enemy team blocked, everyone took a life
            lifetakers = [p for p in game_song.playerHit if len(set(team_ids)) == 1]
            for p in lifetakers:
                p.add("livesTaken")

            # If lifetakers are not on the team of the list rig holder, it means you lost a life on your rig
            lifeLosersOnRig = [p for p in game_song.playerRig if len(set(team_ids)) == 1 and p.player_team not in team_ids]
            for p in lifeLosersOnRig:
                p.add("livesLostOnRig")

            # If lifetakers are offlist, then they took a life on offlist
            offlistLifetakers = [p for p in lifetakers if p not in game_song.playerRig]
            for p in offlistLifetakers:
                p.add("livesTakenOfflist")

            # Offlist erigs
            if num_hitters == 1 and game_song.playerHit[0] not in game_song.playerRig:
                game_song.playerHit[0].add("erigsTakenOfflist")

            # Solo rigs generated
            if num_listers == 1:
                game_song.playerRig[0].add("soloRigs")

            # Skill Issue = Getting 7/8'd
            if num_hitters == 2*TEAM_SIZE - 1:
                playerthatgotSKILLISSUED = next(p for p in game.players if p not in game_song.playerHit)
                playerthatgotSKILLISSUED.add("SKILLISSUE")

            # Per song statistics
            for game_player in game_song.playerHit:
                game_player.add("usefulness", USEFULNESS.get_usefulness(num_hitters))
                if num_hitters == 1:
                    game_player.add("erigs")
                game_player.add("avgoutof", num_hitters)
                game_player.add("avgDifficultyHit", game_song.song_difficulty)
                game_player.add("avgVintageHit", game_song.vintage)
                game_player.add(game_song.song_type)
                game_player.add("totalSongsHit")
                if game_player in game_song.playerRig:
                    game_player.add("list_hit")
            for game_watcher in game_song.playerRig:
                game_watcher.add("avgoutofRigs", num_hitters)
                game_watcher.add("avgVintageRig", game_song.vintage)
                if game_watcher not in game_song.playerHit:
                    game_watcher.add("list_miss")
        for game_player in game.players:
            game_player.add("totalSongsPlayed", num_songs)
            game_player.add("avgDifficultyPlayed", game.difficulty)
            game_player.add("OPplayed", game.OP)
            game_player.add("EDplayed", game.ED)
            game_player.add("INplayed", game.IN)
            game_player.add("eggs", eggs)
            game_player.add("avgVintagePlayed", game.vintage)

    stats_list = []
    scale_usefulness = not masquerade_mode
    for team in teamDB.teams:
        for p in team.players + team.subs:
            p.post_process(TEAM_AVG, scale_usefulness=scale_usefulness)
            d = asdict(p)
            stats_list.append(d)

    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_players = pd.DataFrame(stats_list)
    df_players = df_players.drop(columns=["player_id", "player_team", "avgVintageHit", "avgVintagePlayed", "answerTimeTotal", "answerTimeCount"])
    df_players.sort_values("GR", ascending=False, inplace=True)
    df_players["Timestamp"] = export_time
    df_players = df_players.rename(columns={
        "name": "Player name",
        "rank": "Rank",
        "GR": "Guess rate",
        "OPGR": "OP guess rate",
        "EDGR": "ED guess rate",
        "INGR": "IN guess rate",
        "usefulness": "Usefulness",
        "eggs": "0/8s",
        "erigsmissed": "Missed solos",
        "avgoutof": "avg/8",
        "avgDifficultyHit": "Avg diff hit",
        "OP": "# OPs hit",
        "ED": "# EDs hit",
        "IN": "# INs hit",
        "list_hit": "Rigs hit",
        "list_miss": "Rigs missed",
        "low_count_hits": "# 3/8s or below",
        "totalSongsPlayed": "Total songs",
        "totalSongsHit": "Total hit",
        "avgDifficultyPlayed": "Avg diff played",
        "OPplayed": "# OPs played",
        "EDplayed": "# EDs played",
        "INplayed": "# INs played",
        "OPfractionString": "# OPs correct",
        "EDfractionString": "# EDs correct",
        "INfractionString": "# INs correct",
        "rigAmount": "Rigs",
        "soloRigs": "Solo rigs",
        "avgoutofRigs": "avg/8 of your rigs",
        "SKILLISSUE": "7/8s",
        "DELTAGR": "ΔGR",
        "DELTAUF": "ΔUF",
        "DELTAOP": "ΔOP",
        "DELTAED": "ΔED",
        "DELTAIN": "ΔIN",
        "livesTaken": "Lives taken",
        "livesSaved": "Lives saved",
        "livesLostOnRig": "Lives lost on rigs",
        "erigsTakenOfflist": "Offlist erigs",
        "avgVintageString": "Avg vintage played",
        "avgVintageHitString": "Avg vintage hit",
        "avgVintageRigString": "Avg vintage rig",
        "avgAnswerTime": "Avg answer time",
        "OFFLIST": "Offlist",
        "ONLIST": "Onlist",
        "RIGPERC": "Rig %",
        "WLT": "W-L-T"
    })
    if masquerade_mode:
        masquerade_names_by_key = {
            str(player_name).casefold(): masq_name
            for player_name, masq_name in masquerade_name_by_player.items()
        }
        df_players["Masq name"] = df_players["Player name"].apply(
            lambda name: masquerade_name_by_player.get(name, masquerade_names_by_key.get(str(name).casefold(), ""))
        )
    order = [ 
        "Rank", 
        "Player name", 
        "Guess rate", 
        "Usefulness",
        "erigs",
        "0/8s",
        "7/8s",
        "avg/8",
        "# 3/8s or below",
        "ΔGR",
        "ΔUF",
        "OP guess rate", 
        "ΔOP",
        "# OPs hit",
        "# OPs played",
        "# OPs correct",
        "ED guess rate",
        "ΔED",
        "# EDs hit",
        "# EDs played",
        "# EDs correct",
        "IN guess rate",
        "ΔIN",
        "# INs hit",
        "# INs played",
        "# INs correct",
        "Lives taken",
        "Lives saved",
        "Avg diff hit",
        "Avg diff played",
        "Avg vintage hit",
        "Avg vintage played",
        "Avg answer time",
        "Total hit",
        "Total songs",
        "W-L-T",
        "Onlist",
        "Offlist",
        "Rig %",
        "Rigs",
        "Solo rigs",
        "Missed solos",
        "Rigs hit",
        "Rigs missed",
        "Lives lost on rigs",
        "Offlist erigs",
        "avg/8 of your rigs",
        "Avg vintage rig"
    ]
    if masquerade_mode:
        order.insert(order.index("Player name") + 1, "Masq name")
    df_players_adj = df_players[order]

    # Generate images
    detected_song_types = set()
    for game in tourGames.games:
        if game.OP:
            detected_song_types.add("OP")
        if game.ED:
            detected_song_types.add("ED")
        if game.IN:
            detected_song_types.add("IN")

    selected_song_types = {
        "watched_in": {"IN"},
        "watched_op": {"OP"},
        "watched_in_no_chanting": {"IN"},
        "watched_ed": {"ED"},
        "random_op": {"OP"},
        "random_ed": {"ED"},
        "random_in": {"IN"},
        "random_oped": {"OP", "ED"},
    }.get(server_average_mode)
    if is_other and detected_song_types:
        selected_song_types = detected_song_types
    single_song_type = selected_song_types is not None and len(selected_song_types) == 1

    song_type_column_map = {
        "OP guess rate": "OP",
        "\u0394OP": "OP",
        "# OPs hit": "OP",
        "# OPs played": "OP",
        "# OPs correct": "OP",
        "ED guess rate": "ED",
        "\u0394ED": "ED",
        "# EDs hit": "ED",
        "# EDs played": "ED",
        "# EDs correct": "ED",
        "IN guess rate": "IN",
        "\u0394IN": "IN",
        "# INs hit": "IN",
        "# INs played": "IN",
        "# INs correct": "IN",
    }

    list_only_columns = {"Rigs", "Rigs missed", "Onlist", "Offlist"}

    def mode_columns(columns):
        filtered = [col for col in columns if not (server_average_mode.startswith("random") and col in list_only_columns)]
        if selected_song_types is None:
            return filtered
        if single_song_type:
            return [col for col in filtered if song_type_column_map.get(col) is None]
        return [
            col for col in filtered
            if song_type_column_map.get(col) is None or song_type_column_map[col] in selected_song_types
        ]

    finalOrder1 = mode_columns([
        "Rank",
        "Player name",
        "Guess rate",
        "Usefulness",
        "erigs",
        "7/8s",
        "avg/8",
        "Lives taken",
        "Lives saved",
        "Total songs",
        "OP guess rate",
        "ED guess rate",
        "IN guess rate",
        "Rigs",
        "Rigs missed",
        "Onlist",
        "Offlist",
    ])

    finalOrder2 = mode_columns([
        "Rank", 
        "Player name",
        "Guess rate",
        "\u0394GR", 
        "Usefulness",
        "\u0394UF",
        "OP guess rate", 
        "\u0394OP",
        "# OPs correct",
        "ED guess rate",
        "\u0394ED",
        "# EDs correct",
        "IN guess rate",
        "\u0394IN",
        "# INs correct",
        "Avg diff hit",
        "Avg diff played",
        "Avg vintage hit",
        "Avg vintage played",
        "Avg answer time",
        "W-L-T",
    ])

    finalOrder3 = [
        "Rank", 
        "Player name",
        "Onlist",
        "Offlist",
        "Rig %",
        "Rigs hit",
        "Rigs missed",
        "Rigs",
        "Solo rigs",
        "Missed solos",
        "Lives lost on rigs",
        "Offlist erigs",
        "avg/8 of your rigs",
        "Avg vintage rig"
    ]

    def include_masquerade_name(columns):
        if not masquerade_mode or "Player name" not in columns:
            return columns
        updated = []
        for column in columns:
            updated.append(column)
            if column == "Player name":
                updated.append("Masq name")
        return updated

    finalOrder1 = include_masquerade_name(finalOrder1)
    finalOrder2 = include_masquerade_name(finalOrder2)
    finalOrder3 = include_masquerade_name(finalOrder3)

    if single_song_type:
        single_type_columns = set(song_type_column_map)
        finalOrder1 = [col for col in finalOrder1 if col not in single_type_columns]
        finalOrder2 = [col for col in finalOrder2 if col not in single_type_columns]

    final_df1 = df_players_adj[finalOrder1]
    final_df2 = df_players_adj[finalOrder2]
    final_df3 = df_players_adj[finalOrder3]

    # Song statistics
    current_dir = os.getcwd()
    try:
        os.chdir(ASSETS)
        songDB.post_process()
    finally:
        os.chdir(current_dir)
    saveSongStats(songDB=songDB, path=DIRECTORY, filename="Stats Songs.png")

    # Save to sheet
    wks_send = None
    len_send = None
    if masquerade_mode:
        print("Masquerade: Google Sheet stat submission and JsonData logging skipped.")
    elif is_local:
        print("Local run: Google Sheet stat submission and JsonData logging skipped.")
    else:
        wks_send = get_worksheet_by_ref(sheet, sendToSheet)
        existing_stat_rows = wks_send.get_all_values()
        len_send = len(existing_stat_rows)
        if is_other:
            values = [orderToSheet] + df_players[orderToSheet].values.tolist()
            wks_send.update(values=values, range_name='A'+str(len_send + 2))
        else:
            values = df_players[orderToSheet].values.tolist()
            wks_send.update(values=values, range_name='A'+str(len_send + 2))

        codes_text = read_codes_text(DIRECTORY)

        log_export_data(
            sheet=sheet,
            tour_type=tour_type_label,
            export_time=export_time,
            list_guess_counts=list_guess_counts if is_list else None,
            raw_json_songs=raw_json_songs,
            alias_to_id=alias_to_id,
            id_to_aliases=id_to_aliases,
            codes_text=codes_text,
        )

    reverse_columns = ["avg/8", "Avg diff hit", "Avg diff played", "Avg answer time", "Rigs missed", "Missed solos", "Lives lost on rigs"]
    name_separator = "Masq name" if masquerade_mode else "Player name"
    separators = [name_separator, "Usefulness", "7/8s", "# 3/8s or below", "Lives saved", "Avg vintage played", "Total songs"]
    if single_song_type:
        separators.remove("Total songs")
    if not server_average_mode.startswith("random") and "IN guess rate" in finalOrder1:
        separators.append("IN guess rate")
    separators = [separator for separator in separators if separator in finalOrder1]
    exclude_columns = ["Rank", "Guess rate", "0/8s", "7/8s"]

    path = os.path.join(DIRECTORY, "Stats.png")
    df_to_png(df=final_df1, path=DIRECTORY, filename="Stats.png", reverse_cols=reverse_columns, exclude_columns=exclude_columns, separators=separators)
    print(f"Stats about GR saved at {path}")

    exclude_columns = ["Rank", "Guess rate"]
    separators = [separator for separator in [name_separator, "\u0394UF", "# OPs played", "# EDs played", "# INs played"] if separator in finalOrder2]

    path2 = os.path.join(DIRECTORY, "Stats2.png")
    df_to_png(df=final_df2, path=DIRECTORY, filename="Stats2.png", reverse_cols=reverse_columns, exclude_columns=exclude_columns, separators=separators)
    print(f"Stats about Δ saved at {path2}")

    if is_list:
        exclude_columns = ["Rank"]
        separators = [name_separator, "Offlist", "Rigs Missed", "Offlist erigs"]
        additional_reverse = ["avg/8 of your rigs"]
        reverse_columns.extend(additional_reverse)
        path3 = os.path.join(DIRECTORY, "Stats3 - Watched Exclusive.png")
        df_to_png(df=final_df3, path=DIRECTORY, filename="Stats3 - Watched Exclusive.png", reverse_cols=reverse_columns, exclude_columns=exclude_columns, separators=separators)
        print(f"Stats about watched saved at {path3}")

    if not masquerade_mode:
        export_extra_stats_screenshot(server_average_mode, gc=gc, teamDB=teamDB)

    if wks_send is not None:
        print(f"{wks_send.url}?range={len_send + 2}:{len_send + 2}")
    _ = input('\npress enter to close')


def get_or_create_worksheet(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except Exception:
        return spreadsheet.add_worksheet(title=title, rows=1000, cols=100)


def get_worksheet_by_ref(spreadsheet, worksheet_ref):
    if isinstance(worksheet_ref, int):
        return spreadsheet.get_worksheet_by_id(worksheet_ref)
    return spreadsheet.worksheet(worksheet_ref)


def append_log_rows(worksheet, rows):
    if not rows:
        return
    max_cols = max(len(row) for row in rows)
    padded_rows = [row + [""] * (max_cols - len(row)) for row in rows]
    existing_values = worksheet.get_all_values()
    start_row = len(existing_values) + 1
    try:
        existing_cols = max((len(row) for row in existing_values), default=0)
        target_rows = max(1, start_row + len(padded_rows) - 1)
        target_cols = max(1, existing_cols, max_cols)
        worksheet.resize(rows=target_rows, cols=target_cols)
    except Exception:
        pass
    worksheet.update(values=padded_rows, range_name=f"A{start_row}")


def log_cell_value(value):
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)


JSON_DATA_FIELDS = [
    "songNumber",
    "songInfo.animeNames.english",
    "songInfo.animeNames.romaji",
    "songInfo.artist",
    "songInfo.composerInfo.artistId",
    "songInfo.composerInfo.name",
    "songInfo.arrangerInfo.artistId",
    "songInfo.arrangerInfo.name",
    "songInfo.songName",
    "songInfo.type",
    "songInfo.typeNumber",
    "songInfo.annId",
    "songInfo.annSongId",
    "songInfo.highRisk",
    "songInfo.animeScore",
    "songInfo.animeType",
    "songInfo.vintage",
    "songInfo.animeDifficulty",
    "songInfo.animeTags",
    "songInfo.animeGenre",
    "songInfo.altAnimeNames",
    "songInfo.altAnimeNamesAnswers",
    "songInfo.siteIds.annId",
    "songInfo.siteIds.malId",
    "songInfo.siteIds.kitsuId",
    "songInfo.siteIds.aniListId",
    "songInfo.rebroadcast",
    "songInfo.dub",
    "songInfo.seasonInfo.name",
    "songInfo.seasonInfo.number",
    "songInfo.popularityRank",
    "correctCount",
    "wrongCount",
    "videoUrl",
    "correctGuessPlayers",
    "incorrectGuessPlayers",
    "listStates",
    "codesText",
]

JSON_FILE_NAME_COLUMN_INDEX = 3
JSON_CODES_COLUMN_INDEX = 41
JSON_DATA_COLUMN_FIELDS = [field for field in JSON_DATA_FIELDS if field != "codesText"]
JSON_PACKED_COLUMN_LABELS = ["songLabel"] + JSON_DATA_COLUMN_FIELDS
JSON_CELL_TEXT_LIMIT = 40000


def get_nested_json_value(data, path):
    value = data
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return ""
        value = value[key]
    return value


def normalized_name_for_log(name):
    return str(name).strip().casefold()


def player_identity_for_log(name, alias_to_id):
    normalized = normalize_player_name(name)
    return alias_to_id.get(normalized, normalized)


def get_incorrect_guess_players(song, game_player_names, alias_to_id):
    correct_players = get_correct_guess_player_names(song)
    correct_ids = {player_identity_for_log(player, alias_to_id) for player in correct_players}
    seen_roster_ids = set()
    roster_names = []
    for player_name in game_player_names:
        player_id = player_identity_for_log(player_name, alias_to_id)
        if player_id in seen_roster_ids:
            continue
        seen_roster_ids.add(player_id)
        roster_names.append((player_name, player_id))

    max_incorrect = max(0, 8 - len(correct_ids))
    incorrect_players = [
        player_name for player_name, player_id in roster_names
        if player_id not in correct_ids
    ]
    return incorrect_players[:max_incorrect]


def ordered_song_json_values(song, game_player_names, alias_to_id, codes_text=""):
    incorrect_guess_players = get_incorrect_guess_players(song, game_player_names, alias_to_id)
    values = []
    for field in JSON_DATA_FIELDS:
        if field == "correctCount":
            values.append(len(get_correct_guess_player_names(song)))
        elif field == "wrongCount":
            values.append(len(incorrect_guess_players))
        elif field == "incorrectGuessPlayers":
            values.append(incorrect_guess_players)
        elif field == "codesText":
            values.append(codes_text)
        else:
            values.append(get_nested_json_value(song, field))
    return values


def compact_json_song_record(song_label, song, game_player_names, alias_to_id):
    song_record = {
        "songLabel": song_label,
    }
    for field, value in zip(JSON_DATA_FIELDS, ordered_song_json_values(song, game_player_names, alias_to_id)):
        if field == "codesText":
            continue
        song_record[field] = value
    return song_record


def packed_json_cell(values):
    if not values or all(value == "" for value in values):
        return ""
    return json.dumps(values, ensure_ascii=False)


def build_packed_column_cells(song_records):
    packed_cells = [
        packed_json_cell([song_record.get("songLabel", "") for song_record in song_records])
    ]
    for field in JSON_DATA_COLUMN_FIELDS:
        packed_cells.append(
            packed_json_cell([song_record.get(field, "") for song_record in song_records])
        )
    return packed_cells


def overflowing_packed_columns(packed_cells):
    return [
        label for label, cell in zip(JSON_PACKED_COLUMN_LABELS, packed_cells)
        if len(cell) > JSON_CELL_TEXT_LIMIT
    ]


def split_song_records_for_sheet(song_records, file_name, tour_type, export_time):
    chunks = []
    current_chunk = []

    for song_record in song_records:
        candidate_chunk = current_chunk + [song_record]
        candidate_cells = build_packed_column_cells(candidate_chunk)

        if not overflowing_packed_columns(candidate_cells):
            current_chunk = candidate_chunk
            continue

        if current_chunk:
            chunks.append(build_packed_column_cells(current_chunk))
            current_chunk = [song_record]
        else:
            single_cells = build_packed_column_cells([song_record])
            overflow_columns = ", ".join(overflowing_packed_columns(single_cells)) or "unknown columns"
            print(
                f"Warning: {tour_type} {export_time} {file_name or '[blank json name]'} "
                f"{song_record.get('songLabel', '[unknown song]')} alone exceeds the JsonData limit in: {overflow_columns}."
            )
            chunks.append(single_cells)
            current_chunk = []
            continue

        single_cells = build_packed_column_cells(current_chunk)
        overflow_columns = overflowing_packed_columns(single_cells)
        if overflow_columns:
            print(
                f"Warning: {tour_type} {export_time} {file_name or '[blank json name]'} "
                f"{song_record.get('songLabel', '[unknown song]')} alone exceeds the JsonData limit in: {', '.join(overflow_columns)}."
            )
            chunks.append(single_cells)
            current_chunk = []

    if current_chunk:
        chunks.append(build_packed_column_cells(current_chunk))
    return chunks


def build_compact_json_rows(tour_type, export_time, raw_json_songs, alias_to_id, codes_text):
    songs_by_file = {}
    for song_label, file_name, song, game_player_names in raw_json_songs:
        songs_by_file.setdefault(file_name or "", []).append(
            compact_json_song_record(song_label, song, game_player_names, alias_to_id)
        )

    compact_rows = []
    for file_name, song_records in songs_by_file.items():
        for packed_cells in split_song_records_for_sheet(song_records, file_name, tour_type, export_time):
            compact_row = [tour_type, export_time, packed_cells[0], file_name]
            compact_row.extend(packed_cells[1:])
            compact_row.append(codes_text)
            compact_rows.append(compact_row)
    return compact_rows


def log_export_data(sheet, tour_type, export_time, list_guess_counts, raw_json_songs, alias_to_id, id_to_aliases, codes_text):
    if list_guess_counts:
        list_row = [tour_type, export_time]
        for player_name, guess_counts in sorted(list_guess_counts.items(), key=lambda item: item[0].casefold()):
            list_row.extend([player_name, round(float(np.mean(guess_counts)), 3)])
        list_wks = get_or_create_worksheet(sheet, "ListData")
        append_log_rows(list_wks, [list_row, [""]])

    compact_rows = build_compact_json_rows(tour_type, export_time, raw_json_songs, alias_to_id, codes_text)
    if compact_rows:
        json_wks = get_or_create_worksheet(sheet, "JsonData")
        append_log_rows(json_wks, compact_rows + [[""]])


# --- AMQ EXTRA STATS SCREENSHOT FLOW ---

NGM_STATS_SHEET_NAME = "NGM Stats Export v2"
NGM_STATS_SHEET_ID = "1ihfqssregh74curDyvRE0GAFihQfovUAHpYDrtOIrOA"
SHEET_PLAYER_IDS = 1903970832

SERVER_AVERAGE_SHEET_CANDIDATES = {
    "random_fl": ("Random FL (usual)",),
    "watched_fl": ("Watched FL",),
    "watched_op": ("Watched OP",),
    "watched_in": ("Watched IN",),
    "watched_in_no_chanting": ("Watched IN (-chanting)",),
    "watched_ed": ("Watched ED",),
    "watched_fl_speed": ("Watched 2+8",),
    "watched_fl_5s": ("Watched 5s",),
    "watched_pre_2009": ("Watched -2009",),
    "random_op": ("Random OP",),
    "random_ed": ("Random ED",),
    "random_in": ("Random IN stats",),
    "random_oped": ("Random OPED",),
    "random_chanting": ("Random Chanting",),
}


def get_gspread_client(script_dir):
    parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
    credential_paths = [
        (
            os.path.join(script_dir, "assets", "credentials", "credentials.json"),
            os.path.join(script_dir, "assets", "credentials", "authorized_user.json"),
        ),
        (
            os.path.join(script_dir, "assets", "credentials.json"),
            os.path.join(script_dir, "assets", "authorized_user.json"),
        ),
        (
            os.path.join(parent_dir, "assets", "credentials", "credentials.json"),
            os.path.join(parent_dir, "assets", "credentials", "authorized_user.json"),
        ),
        (
            os.path.join(parent_dir, "credentials", "credentials.json"),
            os.path.join(parent_dir, "credentials", "authorized_user.json"),
        ),
    ]
    credentials_filename, authorized_user_filename = next(
        (
            (credentials, authorized_user)
            for credentials, authorized_user in credential_paths
            if os.path.exists(credentials) and os.path.exists(authorized_user)
        ),
        credential_paths[-1],
    )
    return gspread.oauth(
        credentials_filename=credentials_filename,
        authorized_user_filename=authorized_user_filename
    )


def average_tour_blocks_from_rows(rows, col_idx, is_percent=False):
    tour_values = []
    tour_averages = []
    value_idx = col_idx - 1
    for row in rows[1:]:
        value = parse_stat_cell(row[value_idx] if len(row) > value_idx else None, is_percent)
        if value is None:
            if tour_values:
                tour_averages.append(float(np.mean(tour_values)))
                tour_values = []
        else:
            tour_values.append(value)
    if tour_values:
        tour_averages.append(float(np.mean(tour_values)))
    return float(np.mean(tour_averages)) if tour_averages else None


def normalize_sheet_title(title):
    return re.sub(r"[^a-z0-9]+", "", str(title).casefold())


def get_stats_worksheet(worksheets, candidates):
    by_title = {normalize_sheet_title(ws.title): ws for ws in worksheets}
    for candidate in candidates:
        worksheet = by_title.get(normalize_sheet_title(candidate))
        if worksheet is not None:
            return worksheet

    normalized_candidates = [normalize_sheet_title(candidate) for candidate in candidates]
    for worksheet in worksheets:
        normalized_title = normalize_sheet_title(worksheet.title)
        if any(candidate in normalized_title for candidate in normalized_candidates):
            return worksheet
    return None


def load_server_average_stats(gc):
    stats = {}
    try:
        stats_sheet = gc.open_by_key(NGM_STATS_SHEET_ID)
        worksheets = stats_sheet.worksheets()
    except Exception:
        return stats

    for mode, candidates in SERVER_AVERAGE_SHEET_CANDIDATES.items():
        try:
            worksheet = get_stats_worksheet(worksheets, candidates)
            if worksheet is None:
                continue
            rows = worksheet.get_all_values()
        except Exception:
            continue
        stats[mode] = {
            "guess_rate": average_tour_blocks_from_rows(rows, 4, is_percent=True),
            "attacker": average_tour_blocks_from_rows(rows, 14),
            "blocker": average_tour_blocks_from_rows(rows, 15),
        }
    return stats


def load_player_aliases(gc):
    try:
        sheet = gc.open_by_key(NGM_STATS_SHEET_ID)
        rows = sheet.get_worksheet_by_id(SHEET_PLAYER_IDS).get_all_values()
    except Exception:
        return {}, defaultdict(set)

    alias_to_id = {}
    id_to_aliases = defaultdict(set)
    for row in rows[1:]:
        if len(row) < 2:
            continue
        player_name, player_id = row[0], row[1]
        if not player_name or not player_id:
            continue
        norm_name = normalize_player_name(player_name)
        alias_to_id[norm_name] = player_id
        id_to_aliases[player_id].add(norm_name)
    return alias_to_id, id_to_aliases


def load_chanting_ids(gc):
    try:
        sheet = gc.open_by_key(NGM_STATS_SHEET_ID)
        rows = sheet.worksheet("MiscData").get_all_values()
    except Exception:
        return set()

    chanting_ids = set()
    for row in rows[1:]:
        if not row:
            continue
        value = str(row[0]).strip()
        if value:
            chanting_ids.add(value)
    return chanting_ids


def sync_chanting_ids_file(gc, assets_dir):
    chanting_ids = load_chanting_ids(gc)
    os.makedirs(assets_dir, exist_ok=True)
    with open(os.path.join(assets_dir, "chanting.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(chanting_ids)))
    return chanting_ids


# --- Configuration ---
EXCLUDED_TAGS = {
    "Female Protagonist", "Male Protagonist", "Primarily Female Cast", 
    "Primarily Male Cast", "School", "Heterosexual", "Primarily Teen Cast",
    "Ensemble Cast"
}

def extract_year(vintage_str):
    if not vintage_str: return None
    years = re.findall(r'\d{4}', str(vintage_str))
    if not years: return None
    year_val = float(years[0])
    season_map = {"winter": 0.00, "spring": 0.25, "summer": 0.50, "fall": 0.75}
    v_lower = str(vintage_str).lower()
    decimal = 0.0
    for season, val in season_map.items():
        if season in v_lower:
            decimal = val
            break
    return year_val + decimal

def get_browser():
    browser_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        which("chrome"),
        which("msedge"),
    ]
    return next((path for path in browser_paths if path and os.path.exists(path)), None)

def trim_bottom_white(path_in):
    if Image is None:
        return
    img = Image.open(path_in).convert("RGBA")
    arr = np.array(img)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    non_white = np.any(rgb < 250, axis=2) & (alpha > 0)
    rows = np.where(non_white.any(axis=1))[0]
    if len(rows):
        img.crop((0, 0, img.width, rows[-1] + 8)).save(path_in)

def pct_text(value):
    return "N/A" if value is None or pd.isna(value) else f"{value:.2%}"

def pct_text_with_fraction(value, fraction_string):
    return f"@ {pct_text(value)} ({fraction_string})"

def number_text(value, _ignore=None):
    decimals = 2
    text = "N/A" if value is None or pd.isna(value) else f"{value:.{decimals}f}"
    return f"({text})"

def parse_stat_cell(value, is_percent=False):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        has_percent = text.endswith("%")
        text = text.rstrip("%").replace(",", "")
        try:
            value = float(text)
        except ValueError:
            return None
        if has_percent:
            value /= 100
    elif isinstance(value, (int, float)):
        value = float(value)
    else:
        return None

    if is_percent and value > 1:
        value /= 100
    return value

def normalize_player_name(name):
    return str(name).strip().casefold()

def resolve_player_name(input_name, available_pool, alias_to_id, id_to_aliases):
    exact_match = next((n for n in available_pool if normalize_player_name(n) == normalize_player_name(input_name)), None)
    if exact_match:
        return exact_match

    player_id = alias_to_id.get(normalize_player_name(input_name))
    if player_id is None:
        return None

    aliases = id_to_aliases.get(player_id, set())
    return next((n for n in available_pool if normalize_player_name(n) in aliases), None)

def medal_html(index):
    return ["&#x1F947;", "&#x1F948;", "&#x1F949;"][index]

def ranked_list_html(title, rows, formatter):
    lines = []
    if len(rows[0]) == 2:
        rows = [x + (None,) for x in rows]
    for i, (name, value, details) in enumerate(rows[:3]):
        lines.append(f"<div>{medal_html(i)} {escape(str(name))} {formatter(value, details)}</div>")
    while len(lines) < 3:
        lines.append("<div>&nbsp;</div>")
    return f"""
        <div class="podium">
            <div class="section-title">{escape(title)}</div>
            {''.join(lines)}
        </div>
    """

def line_plot_html(title, value, min_value, max_value, left_label, right_label, value_label, points=None, extra_marker=None):
    if value is None or max_value == min_value:
        pct = 0
    else:
        pct = max(0, min(100, ((value - min_value) / (max_value - min_value)) * 100))
    marker_html = ""
    stat_items = [f"<span><b>Tour Average</b><br>{value_label}</span>"]
    if extra_marker and extra_marker.get("value") is not None and max_value != min_value:
        marker_pct = max(0, min(100, ((extra_marker["value"] - min_value) / (max_value - min_value)) * 100))
        marker_html = f"""
            <div class="scale-marker server" style="left:{marker_pct}%"></div>
        """
        stat_items.append(f'<span class="server-stat"><b>Server Average</b><br>{pct_text(extra_marker["value"])}</span>')
    dots = []
    for name, point_value in points or []:
        if point_value is None or max_value == min_value:
            continue
        point_pct = max(1.5, min(98.5, ((point_value - min_value) / (max_value - min_value)) * 100))
        dots.append(f'<div class="plot-dot" style="left:{point_pct}%" title="{escape(str(name))}"></div>')
    return f"""
        <div class="scale-block">
            <div class="metric-line"><b>{escape(title)}</b></div>
            <div class="scale line-scale">
                {''.join(dots)}
                <div class="scale-marker tour" style="left:{pct}%"></div>
                {marker_html}
            </div>
            <div class="scale-labels">
                <span>{escape(left_label)}</span>
                <span>{escape(right_label)}</span>
            </div>
            <div class="avg-stats">{"".join(stat_items)}</div>
        </div>
    """

def hero_chart_html(title, rows, average_value, server_average=None):
    rows = rows or []
    max_value = max([value for _, _, value in rows] + [average_value or 0, server_average or 0, 1])
    avg_pct = max(0, min(100, ((average_value or 0) / max_value) * 100))
    server_pct = max(0, min(100, ((server_average or 0) / max_value) * 100))
    server_guide = ""
    server_axis = ""
    if server_average is not None:
        server_guide = f'<div class="guide server-guide" style="left:{server_pct}%"></div>'
        server_axis = f'<span class="axis-label server-axis" style="left:{server_pct}%"><b>Server Average</b><br>{number_text(server_average)}</span>'
    html_rows = []
    for tier, name, value in rows:
        width = max(2, min(100, (value / max_value) * 100)) if max_value else 0
        html_rows.append(f"""
            <div class="hero-row">
                <div class="tier">{escape(str(tier))}</div>
                <div class="hero-name">{escape(str(name))}</div>
                <div class="hero-bar-wrap"><div class="hero-bar" style="width:{width}%"></div></div>
                <div class="hero-value">{value}</div>
            </div>
        """)
    if not html_rows:
        html_rows.append('<div class="empty-note">No team data</div>')
    return f"""
        <div class="hero-chart">
            <div class="chart-title">{escape(title)}</div>
            <div class="hero-plot">
                <div class="hero-guides">
                    <div class="guide tour-guide" style="left:{avg_pct}%"></div>
                    {server_guide}
                </div>
                {''.join(html_rows)}
            </div>
            <div class="chart-axis">
                <span class="axis-label tour-axis" style="left:{avg_pct}%"><b>Tour Average</b><br>{number_text(average_value)}</span>
                {server_axis}
            </div>
        </div>
    """

def save_extra_stats_image(data, output_dir, filename):
    if Html2Image is None:
        raise RuntimeError("html2image is not installed. Install it to export the Extra Stats PNG.")

    chanting_html = ""
    if data["has_chanting"]:
        chanting_html = f"""
            <div class="chanting">
                <div class="boxed-title">CHANTING STATS</div>
                <div class="two-col-row"><span>Total chanting songs played</span><span>{data['chanting_total']}</span></div>
                <div class="two-col-row"><span>Average chanting guess rate</span><span>{pct_text(data['chanting_gr'])}</span></div>
                <div class="chant-lists">
                    {ranked_list_html("Top 3 Chanting Lovers", data["chanting_lovers"], pct_text_with_fraction)}
                    {ranked_list_html("Top 3 Chanting Haters", data["chanting_haters"], pct_text_with_fraction)}
                </div>
            </div>
        """

    answer_time_html = ""
    if data.get("answer_time_tryhards") or data.get("answer_time_ballscratchers"):
        answer_time_html = f"""
            <div class="answer-time">
                <div class="boxed-title">ANSWER TIME STATS</div>
                <div class="chant-lists">
                    {ranked_list_html("Top 3 Tryhards", data.get("answer_time_tryhards", []), number_text)}
                    {ranked_list_html("Top 3 Ballscratchers", data.get("answer_time_ballscratchers", []), number_text)}
                </div>
            </div>
        """

    server_marker = None
    if data["server_average_gr"] is not None:
        server_marker = {
            "value": data["server_average_gr"],
            "label": f"Server Average\n{pct_text(data['server_average_gr'])}",
        }

    right_only = data.get("right_only", False)
    dashboard_class = "dashboard right-only" if right_only else "dashboard"
    left_html = ""
    if not right_only:
        left_html = f"""
        <div class="left">
            {line_plot_html("Tour Average GR", data["tour_average_gr"], 0, 1, "0%", "100%", pct_text(data["tour_average_gr"]), data["gr_points"], server_marker)}
            <div class="boxed-title">WATCHED STATS</div>
            {line_plot_html("", data["watched_average"], 0, 8, "0.0", "8.0", number_text(data["watched_average"]), data["difficulty_points"])}
            <div class="podium-grid">
                {ranked_list_html("Top 3 Easiest Lists", data["easiest_lists"], number_text)}
                {ranked_list_html("Top 3 Hardest Lists", data["hardest_lists"], number_text)}
            </div>
            {line_plot_html("", data["vintage_average"], data["vintage_min"], data["vintage_max"], number_text(data["vintage_min"]), number_text(data["vintage_max"]), number_text(data["vintage_average"]), data["vintage_points"])}
            <div class="podium-grid">
                {ranked_list_html("Top 3 Zoomer Lists", data["zoomer_lists"], number_text)}
                {ranked_list_html("Top 3 Boomer Lists", data["boomer_lists"], number_text)}
            </div>
            <div class="summary-table">
                <div class="two-col-row"><span>Most 2/8s</span><span>{escape(data["most_two_eighths"])}</span></div>
                <div class="two-col-row"><span>Highest GR with no erig</span><span>{escape(data["best_no_erig"])}</span></div>
                <div class="two-col-row"><span>&nbsp;</span><span>&nbsp;</span></div>
                <div class="two-col-row"><span>Top erig misser</span><span>{escape(data["top_erig_misser"])}</span></div>
                <div class="two-col-row"><span>Top reverse erig collector</span><span>{escape(data["top_reverse_erig"])}</span></div>
            </div>
        </div>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        background: white;
        color: black;
        font-family: Helvetica, Arial, sans-serif;
        font-size: 18px;
    }}
    .dashboard {{
        width: 1220px;
        min-height: 980px;
        padding: 0;
        display: grid;
        grid-template-columns: 530px 620px;
        gap: 36px;
    }}
    .dashboard.right-only {{
        width: 620px;
        grid-template-columns: 620px;
        gap: 0;
    }}
    .left, .right {{ position: relative; }}
    .metric-line {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        padding: 8px 18px 0 4px;
    }}
    .scale-block {{ margin-bottom: 18px; position: relative; }}
    .scale {{
        height: 44px;
        margin: 0 16px 0 6px;
        position: relative;
        overflow: visible;
    }}
    .line-scale::before {{
        content: "";
        position: absolute;
        left: 0;
        right: 0;
        top: 50%;
        border-top: 5px solid black;
        transform: translateY(-50%);
    }}
    .plot-dot {{
        position: absolute;
        top: 50%;
        width: 3px;
        height: 20px;
        transform: translate(-50%, -50%);
        border-radius: 0;
        background: #ed1c24;
        border: 0;
        box-shadow: none;
    }}
    .scale-marker {{
        position: absolute;
        top: 3px;
        bottom: 3px;
        width: 2px;
        background: black;
    }}
    .scale-marker.server {{
        width: 2px;
        background: #2563eb;
    }}
    .marker-label {{
        position: absolute;
        top: 47px;
        transform: translateX(-50%);
        text-align: center;
        white-space: pre;
        font-size: 16px;
        font-weight: bold;
    }}
    .server-label {{ color: #1d4ed8; }}
    .scale-labels {{
        position: relative;
        height: 22px;
        display: flex;
        justify-content: space-between;
        padding: 0 0 0 8px;
        font-size: 16px;
        font-weight: bold;
        margin-top: -2px;
    }}
    .avg-stats {{
        display: flex;
        gap: 28px;
        align-items: flex-start;
        margin: 0 0 10px 8px;
        font-size: 16px;
        font-weight: normal;
        line-height: 1.2;
    }}
    .avg-stats span {{
        text-align: left;
    }}
    .avg-stats b {{
        font-weight: bold;
    }}
    .server-stat {{ color: #1d4ed8; }}
    .boxed-title {{
        border: 2px solid black;
        height: 31px;
        line-height: 28px;
        padding-left: 5px;
        font-size: 23px;
        font-weight: bold;
        margin: 8px 0 10px;
    }}
    .podium-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        border-left: 1px solid #ccc;
        border-top: 1px solid #ccc;
    }}
    .podium {{
        min-height: 116px;
        border-right: 1px solid #ccc;
        border-bottom: 1px solid #ccc;
        padding: 0 4px 5px;
    }}
    .section-title {{
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 4px;
    }}
    .podium div:not(.section-title) {{
        line-height: 25px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-family: Helvetica, Arial, sans-serif;
    }}
    .summary-table {{
        border-left: 1px solid #ccc;
        border-top: 1px solid #ccc;
        margin-top: 12px;
        font-size: 20px;
    }}
    .summary-table .two-col-row {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        border-bottom: 1px solid #ccc;
    }}
    .summary-table span {{
        padding: 4px;
        border-right: 1px solid #ccc;
    }}
    .summary-table span:first-child {{ font-weight: bold; }}
    .hero-chart {{
        height: 202px;
        border-top: 1px solid #ccc;
        margin-bottom: 10px;
        padding-top: 0;
    }}
    .chart-title {{
        height: 27px;
        border: 2px solid black;
        padding-left: 14px;
        font-weight: bold;
        line-height: 24px;
    }}
    .hero-plot {{
        margin-top: 0;
        position: relative;
        padding-top: 0;
    }}
    .hero-guides {{
        position: absolute;
        left: 147px;
        right: 45px;
        top: 0;
        bottom: 0;
        pointer-events: none;
        z-index: 3;
    }}
    .hero-row {{
        display: grid;
        grid-template-columns: 31px 116px 1fr 45px;
        height: 30px;
        align-items: center;
        font-weight: bold;
    }}
    .tier, .hero-name {{
        height: 30px;
        line-height: 29px;
        border-left: 1px solid black;
        border-bottom: 1px solid black;
        padding-left: 5px;
    }}
    .hero-name {{ border-right: 1px solid black; }}
    .hero-bar-wrap {{
        height: 30px;
        position: relative;
        border-bottom: 1px solid black;
        border-right: 1px solid black;
    }}
    .hero-bar {{
        height: 29px;
        background: #ed1c24;
        border-right: 2px solid black;
    }}
    .hero-value {{
        text-align: right;
        padding-right: 8px;
        font-family: Helvetica, Arial, sans-serif;
    }}
    .guide {{
        position: absolute;
        top: 0;
        bottom: 0;
        width: 2px;
        background: black;
        pointer-events: none;
    }}
    .server-guide {{
        background: #2563eb;
        width: 2px;
    }}
    .chart-axis {{
        position: relative;
        height: 32px;
        margin-left: 147px;
        margin-right: 45px;
        font-size: 16px;
        font-weight: bold;
    }}
    .axis-label {{
        position: absolute;
        top: 2px;
        min-width: 118px;
        transform: translateX(-50%);
        text-align: center;
        line-height: 1.15;
        background: white;
    }}
    .server-axis {{ color: #1d4ed8; }}
    .chanting, .answer-time {{
        margin-top: 18px;
        width: 620px;
    }}
    .chanting .boxed-title, .answer-time .boxed-title {{ margin-bottom: 0; }}
    .two-col-row {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        min-height: 30px;
        border-left: 1px solid #ccc;
        border-bottom: 1px solid #ccc;
    }}
    .two-col-row span {{
        padding: 4px 6px;
        border-right: 1px solid #ccc;
    }}
    .chant-lists {{
        margin-top: 28px;
        display: grid;
        grid-template-columns: 1fr 1fr;
        border-left: 1px solid #ccc;
        border-top: 1px solid #ccc;
    }}
    .empty-note {{ padding: 12px; color: #555; }}
</style>
</head>
<body>
    <div class="{dashboard_class}">
        {left_html}
        <div class="right">
            {hero_chart_html("Top Attacker", data["top_attackers"], data["attacker_average"], data["server_attacker_average"])}
            {hero_chart_html("Top Blocker", data["top_blockers"], data["blocker_average"], data["server_blocker_average"])}
            {chanting_html}
            {answer_time_html}
        </div>
    </div>
</body>
</html>
"""

    hti = Html2Image(
        size=(620 if right_only else 1228, 1120),
        browser_executable=get_browser(),
        custom_flags=[
            "--headless=new",
            "--hide-scrollbars",
            "--disable-gpu",
            "--force-device-scale-factor=1",
        ],
        output_path=output_dir
    )
    hti.screenshot(html_str=html, save_as=filename)
    save_path = os.path.join(output_dir, filename)
    trim_bottom_white(save_path)
    return save_path

# --- UI COMPONENTS ---

class SubSelectionDialog(tk.Toplevel):
    def __init__(self, parent, missing_roster):
        super().__init__(parent)
        self.title("Substitute Resolution")
        self.result = None
        tk.Label(self, text="Multiple roster members are missing.\nWhich player is being replaced by the substitute?", 
                 font=("Arial", 10), padx=20, pady=10).pack()
        self.listbox = tk.Listbox(self, height=len(missing_roster))
        self.listbox.pack(padx=20, pady=5, fill=tk.X)
        for m in missing_roster: self.listbox.insert(tk.END, m)
        ttk.Button(self, text="Confirm", command=self.on_confirm).pack(pady=10)
        self.grab_set(); self.wait_window()
        
    def on_confirm(self):
        sel = self.listbox.curselection()
        if sel: self.result = self.listbox.get(sel[0]); self.destroy()

class ManualMatchDialog(tk.Toplevel):
    def __init__(self, parent, unknown_name, available_pool):
        super().__init__(parent)
        self.title("Manual Match Required")
        self.result = None
        ttk.Label(self, text=f"Could not find match for: '{unknown_name}'", font=("Arial", 10, "bold")).pack(pady=10)
        self.listbox = tk.Listbox(self, height=15); self.listbox.pack(padx=10, fill=tk.BOTH)
        for name in sorted(available_pool): self.listbox.insert(tk.END, name)
        ttk.Button(self, text="Match Selected", command=self.on_match).pack(pady=10)
        self.grab_set(); self.wait_window()

    def on_match(self):
        sel = self.listbox.curselection()
        if sel: self.result = self.listbox.get(sel[0]); self.destroy()

# --- CORE LOGIC ---

def export_extra_stats_screenshot(server_average_mode, gc=None, ask_cleanup=False, teamDB=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, "assets")
    json_dir = os.path.join(script_dir, "jsons")
    os.makedirs(assets_dir, exist_ok=True)
    if tk._default_root is None:
        root = tk.Tk()
        root.withdraw()
    
    json_paths = []
    while True:
        if os.path.exists(json_dir) and os.path.isdir(json_dir):
            json_paths = [os.path.join(json_dir, f) for f in os.listdir(json_dir) if f.endswith(".json")]
        
        if json_paths:
            break
        else:
            retry = messagebox.askyesno("Missing Files", "There is no jsons folder detected or there are no JSON files in the folder. Lock in and press yes to re-run the script")
            if not retry:
                return

    all_known_players = set()
    for path in json_paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f); songs = data.get("songs", [])
                for s in songs:
                    for p in get_correct_guess_player_names(s): all_known_players.add(p)
                    for answer_name, _ in get_answer_time_entries(s): all_known_players.add(answer_name)
                    for ls in get_list_state_entries(s):
                        if isinstance(ls, dict) and ls.get("name"):
                            all_known_players.add(ls["name"])
        except: continue

    raw_assignments = {}
    team_rosters = defaultdict(set)
    t1_lookup = {}
    use_teams = False
    team_size_for_extra = 4
    server_average_gr = None
    if gc is None:
        try:
            gc = get_gspread_client(script_dir)
        except Exception as exc:
            print(f"Extra stats screenshot skipped: could not authorize Google Sheets access: {exc}")
            return None

    chanting_ids = load_chanting_ids(gc)
    alias_to_id, id_to_aliases = load_player_aliases(gc)

    codes_path = find_codes_path(script_dir)
    codes_valid = False
    if os.path.exists(codes_path):
        with open(codes_path, "r", encoding="utf-8") as f:
            if f.read().strip():
                codes_valid = True

    if not codes_valid:
        if not messagebox.askyesno("Codes Missing", "codes.txt is missing or empty, skip team assignment phase?"):
            return
    else:
        with open(codes_path, "r", encoding="utf-8") as f:
            content = f.read()
        for line in content.strip().split('\n'):
            if line.lower().startswith(("average", "avg")):
                avg_match = re.search(r"(-?\d+(?:\.\d+)?)", line)
                if avg_match:
                    server_average_gr = float(avg_match.group(1))
                    if server_average_gr > 1:
                        server_average_gr /= 100

        if teamDB is not None and getattr(teamDB, "teams", None):
            use_teams = True
            team_size_for_extra = teamDB.teams[0].get_team_size() if teamDB.teams else team_size_for_extra
            for t_idx, team in enumerate(teamDB.teams, 1):
                for i, player in enumerate(team.players):
                    tier = f"T{i+1}"
                    raw_assignments[player.name] = (t_idx, tier)
                    team_rosters[t_idx].add(player.name)
                    if tier == "T1":
                        t1_lookup[t_idx] = player.name
                for sub in team.subs:
                    raw_assignments[sub.name] = (t_idx, "Sub")
                    team_rosters[t_idx].add(sub.name)
        else:
            all_teams_data = []
            for line in content.strip().split('\n'):
                lower = line.lower()
                if lower.startswith(("average", "avg", "sub")) or line.startswith("http"):
                    continue
                matches = re.findall(r'([^\s(]+)\s*\([\d.]+\)', line)
                if matches:
                    all_teams_data.append(matches)

            if all_teams_data:
                use_teams = True
                team_size_for_extra = len(all_teams_data[0])
                available = list(all_known_players)
                for t_idx, members in enumerate(all_teams_data, 1):
                    for i, p_in in enumerate(members):
                        tier = f"T{i+1}"
                        match = resolve_player_name(p_in, available, alias_to_id, id_to_aliases)
                        if not match:
                            d = ManualMatchDialog(None, p_in, available)
                            match = d.result
                        if match:
                            raw_assignments[match] = (t_idx, tier)
                            team_rosters[t_idx].add(match)
                            if match in available:
                                available.remove(match)
                            if tier == "T1":
                                t1_lookup[t_idx] = match

    roster_name_pool = list(raw_assignments.keys())

    def extra_player_name(name):
        if not use_teams:
            return name
        return resolve_player_name(name, roster_name_pool, alias_to_id, id_to_aliases) or name

    correct_counts, song_participation = defaultdict(int), defaultdict(int)
    erigs_counts, player_reverse_erigs = defaultdict(int), defaultdict(int)
    player_two_eighths, player_points, player_blocks = defaultdict(int), defaultdict(int), defaultdict(int)
    player_type_correct, player_type_seen = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    player_rigs, player_rigs_hit = defaultdict(int), defaultdict(int)
    all_song_vintages, all_song_difficulties = [], []
    total_correct_answers_sum, total_erigs = 0, 0
    genre_counter, tag_counter = Counter(), Counter()
    player_list_vintages, player_list_correct_counts = defaultdict(list), defaultdict(list) 
    player_missed_erigs, watched_only_valid = defaultdict(int), False
    team_correct_per_song = defaultdict(list)
    team_onlist_synergy, team_offlist_synergy, team_shared_rig_pct = defaultdict(list), defaultdict(list), defaultdict(list)
    
    total_songs_played = 0
    total_chanting_songs = 0
    player_chanting_correct = defaultdict(int)
    player_chanting_seen = defaultdict(int)
    chanting_correct_sum = 0
    player_answer_times = defaultdict(list)

    for path in json_paths:
        with open(path, encoding="utf-8") as f: data = json.load(f); songs = data.get("songs", [])
        if not songs: continue
        
        raw_file_players = set()
        for song in songs:
            for p in get_correct_guess_player_names(song):
                raw_file_players.add(extra_player_name(p))
            for answer_name, _ in get_answer_time_entries(song):
                raw_file_players.add(extra_player_name(answer_name))
            for ls in get_list_state_entries(song):
                if isinstance(ls, dict) and ls.get("name"):
                    raw_file_players.add(extra_player_name(ls["name"]))
        
        final_file_members = set(raw_file_players)
        if use_teams:
            teams_in_file = set(raw_assignments[p][0] for p in raw_file_players if p in raw_assignments)
            for t_id in teams_in_file:
                roster = team_rosters[t_id]
                seen_on_team = [p for p in roster if p in raw_file_players]
                missing = [p for p in roster if p not in raw_file_players]
                needed = max(0, team_size_for_extra - len(seen_on_team))
                if needed and missing:
                    if len(missing) == needed:
                        final_file_members.update(missing)
                    else:
                        remaining = missing[:]
                        for _ in range(needed):
                            if not remaining:
                                break
                            if len(remaining) == 1:
                                final_file_members.add(remaining[0])
                                break
                            d = SubSelectionDialog(None, remaining)
                            if d.result:
                                final_file_members.add(d.result)
                                remaining.remove(d.result)
                            else:
                                break

        apply_rev = (len(final_file_members) % 2 == 0)
        max_songs = max(s.get("songNumber", 0) for s in songs)
        type_totals_this_file = defaultdict(int)

        for song in songs:
            total_songs_played += 1
            si = song.get("songInfo", {}); st = si.get("type")
            
            # Using annSongId for chanting matching
            ann_song_id = str(si.get("annSongId"))
            
            is_chanting = ann_song_id in chanting_ids
            if is_chanting: total_chanting_songs += 1

            if st in [1, 2, 3]: type_totals_this_file[st] += 1
            if isinstance(si.get("animeGenre"), list): genre_counter.update(si.get("animeGenre"))
            if isinstance(si.get("animeTags"), list):
                tag_counter.update([t for t in si.get("animeTags") if t not in EXCLUDED_TAGS])

            correct = {extra_player_name(name) for name in get_correct_guess_player_names(song)}
            ls = get_list_state_entries(song); total_correct_answers_sum += len(correct)
            if is_chanting: chanting_correct_sum += len(correct)
            for answer_name, answer_time in get_answer_time_entries(song):
                answer_name = extra_player_name(answer_name)
                matched_answer_name = answer_name if answer_name in final_file_members else resolve_player_name(answer_name, final_file_members, alias_to_id, id_to_aliases)
                if matched_answer_name:
                    player_answer_times[matched_answer_name].append(answer_time)

            year, diff = extract_year(si.get("vintage")), si.get("animeDifficulty")
            if isinstance(diff, (int, float)): all_song_difficulties.append(diff)
            if year is not None: all_song_vintages.append(year)
            
            song_riggers = {extra_player_name(p["name"]) for p in ls if isinstance(p, dict) and p.get("name")}
            
            if use_teams:
                teams_in_this_file = list(set(raw_assignments[p][0] for p in raw_file_players if p in raw_assignments))
                if len(teams_in_this_file) == 2:
                    tA, tB = teams_in_this_file[0], teams_in_this_file[1]
                    for cur_t, opp_t in [(tA, tB), (tB, tA)]:
                        cur_correct = correct.intersection(team_rosters[cur_t])
                        opp_correct = correct.intersection(team_rosters[opp_t])
                        if not opp_correct:
                            for p in cur_correct: player_points[p] += 1
                        if len(cur_correct) == 1 and len(opp_correct) > 0:
                            player_blocks[list(cur_correct)[0]] += 1

                for t_id in teams_in_this_file:
                    roster = team_rosters[t_id]
                    correct_on_team = correct.intersection(roster)
                    team_correct_per_song[t_id].append(len(correct_on_team) / float(team_size_for_extra or 1))
                    team_riggers = song_riggers.intersection(roster)
                    if team_riggers:
                        team_onlist_synergy[t_id].append(len(correct_on_team) / float(team_size_for_extra or 1))
                        team_shared_rig_pct[t_id].append((len(team_riggers) - 1) / float(max(team_size_for_extra - 1, 1)))
                    else: team_offlist_synergy[t_id].append(len(correct_on_team) / float(team_size_for_extra or 1))

            if len(correct) == 2:
                for p in correct: player_two_eighths[p] += 1
            elif len(correct) == 1: 
                total_erigs += 1; erigs_counts[list(correct)[0]] += 1
            if apply_rev and len(final_file_members - correct) == 1:
                player_reverse_erigs[list(final_file_members - correct)[0]] += 1

            for name in final_file_members:
                if name in correct:
                    correct_counts[name] += 1
                    if st in [1, 2, 3]: player_type_correct[name][st] += 1
                    if is_chanting: player_chanting_correct[name] += 1
                if is_chanting: player_chanting_seen[name] += 1

            if ls:
                watched_only_valid = True
                for p in ls:
                    if not isinstance(p, dict) or not p.get("name"):
                        continue
                    n = extra_player_name(p["name"]); player_rigs[n] += 1
                    if n in correct: player_rigs_hit[n] += 1
                    if year is not None: player_list_vintages[n].append(year)
                    player_list_correct_counts[n].append(len(correct))
                    if len(correct) == 0: player_missed_erigs[n] += 1

        for name in final_file_members:
            song_participation[name] += max_songs
            for t in [1, 2, 3]: player_type_seen[name][t] += type_totals_this_file[t]

    p_rows = []
    for name in song_participation:
        total, correct = song_participation[name], correct_counts[name]
        t_id, tier = raw_assignments.get(name, ("Unassigned", "N/A"))
        t_name = t1_lookup.get(t_id, "Unknown")
        p_rows.append({
            "Team": t_name, "Tier": tier, "Player": name, 
            "Guess Rate": correct/total if total else 0, "Erigs 🔫": erigs_counts[name],
            "Points": player_points[name], "Blocks": player_blocks[name],
            "2/8s": player_two_eighths[name], "Rev. Erigs": player_reverse_erigs[name],
            "Song Count": total,
            "OP GR": player_type_correct[name][1]/player_type_seen[name][1] if player_type_seen[name][1] else np.nan,
            "ED GR": player_type_correct[name][2]/player_type_seen[name][2] if player_type_seen[name][2] else np.nan,
            "IN GR": player_type_correct[name][3]/player_type_seen[name][3] if player_type_seen[name][3] else np.nan,
            "Rigs": player_rigs[name], "Rigs Missed": player_rigs[name]-player_rigs_hit[name],
            "Onlist GR": player_rigs_hit[name]/player_rigs[name] if player_rigs[name] else np.nan,
            "Offlist GR": (correct-player_rigs_hit[name])/(total-player_rigs[name]) if (total-player_rigs[name]) else np.nan
        })
    df_ps = pd.DataFrame(p_rows).sort_values("Guess Rate", ascending=False)
    total_participation = sum(song_participation.values())
    avg_tour_gr = total_correct_answers_sum / total_participation if total_participation else 0

    df_tour = pd.DataFrame([
        ["Average Vintage", round(np.mean(all_song_vintages), 2) if all_song_vintages else "N/A"],
        ["Average Difficulty", round(np.mean(all_song_difficulties), 2) if all_song_difficulties else "N/A"],
        ["Average GR", f"{avg_tour_gr:.2%}"],
        ["Total Erigs", total_erigs],
        ["Total Rev. Erigs", sum(player_reverse_erigs.values())],
        ["Most Popular Genre", f"{genre_counter.most_common(1)[0][0]} ({genre_counter.most_common(1)[0][1]})" if genre_counter else "N/A"],
        ["Most Popular Tag", f"{tag_counter.most_common(1)[0][0]} ({tag_counter.most_common(1)[0][1]})" if tag_counter else "N/A"],
    ], columns=["TOUR STATS", ""])

    team_stat_rows, team_meta = [], []
    if use_teams:
        for t_id in sorted(team_correct_per_song.keys()):
            t_name = t1_lookup.get(t_id, f"Team {t_id}"); roster = team_rosters[t_id]
            t_v = [v for p in roster for v in player_list_vintages[p]]
            t_d = [v for p in roster for v in player_list_correct_counts[p]]
            team_stat_rows.append({"TEAM STATS": t_name, "Avg. Correct": np.mean(team_correct_per_song[t_id]), "Onlist Synergy": np.mean(team_onlist_synergy[t_id]) if team_onlist_synergy[t_id] else 0, "Offlist Synergy": np.mean(team_offlist_synergy[t_id]) if team_offlist_synergy[t_id] else 0, "Shared Rigs": np.mean(team_shared_rig_pct[t_id]) if team_shared_rig_pct[t_id] else 0})
            team_meta.append({"name": t_name, "erigs": sum(erigs_counts[p] for p in roster), "vintage": np.mean(t_v) if t_v else 0, "diff": np.mean(t_d) if t_d else 0})
    
    df_team_stats = pd.DataFrame(team_stat_rows)
    if not df_team_stats.empty:
        df_team_stats = df_team_stats.sort_values("Avg. Correct", ascending=False)

    tier_hero_rows = []
    tier_attackers, tier_blockers = {}, {}
    tier_order = []
    if use_teams:
        tier_order = sorted(
            {attr[1] for attr in raw_assignments.values()},
            key=lambda tier: (0, int(tier[1:])) if str(tier).startswith("T") and str(tier)[1:].isdigit() else (1, str(tier)),
        )
        for tier in tier_order:
            tp = [p for p, attr in raw_assignments.items() if attr[1] == tier]
            if tp:
                bp = max(tp, key=lambda x: player_points[x]); bb = max(tp, key=lambda x: player_blocks[x])
                tier_attackers[tier] = (bp, player_points[bp])
                tier_blockers[tier] = (bb, player_blocks[bb])
                tier_hero_rows.append([tier, f"{bp} ({player_points[bp]})", f"{bb} ({player_blocks[bb]})"])
    df_tier_heroes = pd.DataFrame(tier_hero_rows, columns=["Tier", "Top Attacker", "Top Blocker"])

    plist = list(song_participation.keys())
    diff_data = [(n, np.mean(player_list_correct_counts[n])) for n in plist if player_list_correct_counts[n]]
    vint_data = [(n, np.mean(player_list_vintages[n])) for n in plist if player_list_vintages[n]]
    all_list_correct_counts = [v for values in player_list_correct_counts.values() for v in values]
    all_list_vintages = [v for values in player_list_vintages.values() for v in values]

    no_erig_pool = [n for n in plist if erigs_counts[n] == 0]
    best_no_erig = sorted(no_erig_pool, key=lambda x: (correct_counts[x]/song_participation[x]), reverse=True)[0] if no_erig_pool else "N/A"
    best_no_erig_gr = f"{correct_counts[best_no_erig]/song_participation[best_no_erig]:.2%}" if no_erig_pool else "N/A"
    p_28 = sorted(plist, key=lambda x: player_two_eighths[x], reverse=True)[0] if plist else "N/A"
    m_miss = max(player_missed_erigs, key=player_missed_erigs.get) if player_missed_erigs else "N/A"
    m_rev = max(player_reverse_erigs, key=player_reverse_erigs.get) if player_reverse_erigs else "N/A"

    chan_pct = total_chanting_songs / total_songs_played if total_songs_played else 0
    avg_chan_gr = (chanting_correct_sum / (total_chanting_songs * len(song_participation))) if (total_chanting_songs and song_participation) else 0
    chan_plist = [n for n in song_participation.keys() if player_chanting_seen[n] > 0]
    chan_rates = [(n, player_chanting_correct[n]/player_chanting_seen[n], f"{player_chanting_correct[n]}/{player_chanting_seen[n]}") for n in chan_plist]
    answer_time_rates = [
        (name, float(np.mean(times)))
        for name, times in player_answer_times.items()
        if times
    ]
    server_average_stats = load_server_average_stats(gc)
    selected_server_stats = server_average_stats.get(server_average_mode, {})
    image_server_gr = selected_server_stats.get("guess_rate")
    if image_server_gr is None:
        image_server_gr = server_average_gr
    image_server_attacker = selected_server_stats.get("attacker")
    image_server_blocker = selected_server_stats.get("blocker")
    vintage_min = min([v for _, v in vint_data]) if vint_data else 0
    vintage_max = max([v for _, v in vint_data]) if vint_data else 1
    if vintage_min == vintage_max:
        vintage_min -= 1
        vintage_max += 1

    extra_image_data = {
        "tour_average_gr": avg_tour_gr,
        "server_average_gr": image_server_gr,
        "gr_points": [(row["Player"], row["Guess Rate"]) for row in p_rows],
        "watched_average": np.mean(all_list_correct_counts) if all_list_correct_counts else None,
        "difficulty_points": diff_data,
        "easiest_lists": sorted(diff_data, key=lambda x: x[1], reverse=True)[:3],
        "hardest_lists": sorted(diff_data, key=lambda x: x[1])[:3],
        "vintage_average": np.mean(all_list_vintages) if all_list_vintages else None,
        "vintage_min": vintage_min,
        "vintage_max": vintage_max,
        "vintage_points": vint_data,
        "zoomer_lists": sorted(vint_data, key=lambda x: x[1], reverse=True)[:3],
        "boomer_lists": sorted(vint_data, key=lambda x: x[1])[:3],
        "most_two_eighths": f"{p_28} ({player_two_eighths[p_28]})" if p_28 != "N/A" else "N/A",
        "best_no_erig": f"{best_no_erig} ({best_no_erig_gr})" if no_erig_pool else "N/A",
        "top_erig_misser": f"{m_miss} ({player_missed_erigs.get(m_miss, 0)})" if m_miss != "N/A" else "N/A",
        "top_reverse_erig": f"{m_rev} ({player_reverse_erigs.get(m_rev, 0)})" if m_rev != "N/A" else "N/A",
        "top_attackers": [(tier, tier_attackers[tier][0], tier_attackers[tier][1]) for tier in tier_order if tier in tier_attackers],
        "top_blockers": [(tier, tier_blockers[tier][0], tier_blockers[tier][1]) for tier in tier_order if tier in tier_blockers],
        "attacker_average": np.mean([player_points[n] for n in plist]) if plist else 0,
        "blocker_average": np.mean([player_blocks[n] for n in plist]) if plist else 0,
        "server_attacker_average": image_server_attacker,
        "server_blocker_average": image_server_blocker,
        "has_chanting": bool(chanting_ids),
        "right_only": server_average_mode.startswith("random"),
        "chanting_total": f"{total_chanting_songs} ({chan_pct:.2%})",
        "chanting_gr": avg_chan_gr,
        "chanting_lovers": sorted(chan_rates, key=lambda x: x[1], reverse=True)[:3],
        "chanting_haters": sorted(chan_rates, key=lambda x: x[1])[:3],
        "answer_time_tryhards": sorted(answer_time_rates, key=lambda x: x[1])[:3],
        "answer_time_ballscratchers": sorted(answer_time_rates, key=lambda x: x[1], reverse=True)[:3],
    }

    image_name = "Stats4.png"
    image_status = f"Extra stats image exported to {image_name}."
    try:
        save_extra_stats_image(extra_image_data, script_dir, image_name)
    except Exception as exc:
        image_status = f"Extra stats image could not be exported: {exc}"
        print(image_status)
        return None

    print(image_status)
    if ask_cleanup and messagebox.askyesno("Success", f"{image_status}\nDo you want to delete all processed JSON files?"):
        for path in json_paths:
            try:
                os.remove(path)
            except Exception:
                pass
        messagebox.showinfo("Cleanup", "JSON files deleted.")
    return os.path.join(script_dir, image_name)


def main():
    run_ngm_sheet_stats(False)


if __name__ == "__main__":
    main()
