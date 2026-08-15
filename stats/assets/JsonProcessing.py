import os
import json
import re
import hashlib
import unicodedata
from collections import defaultdict

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

from TourClasses import *
from TourFunctions import *

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
        if not file_name.startswith("amq_song_export"):
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


def common_error(title, details=None, fixes=None, wait=True):
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
    if wait:
        input("\nPress Enter to exit.")
    raise SystemExit(1)


def clean_player_name(name):
    text = str(name).replace("\ufeff", "").strip()
    return "".join(char for char in text if unicodedata.category(char) != "Cf").strip()


def normalize_player_name(name):
    return clean_player_name(name).casefold()


def resolve_player_name(input_name, available_pool, alias_to_id, id_to_aliases):
    exact_match = next((n for n in available_pool if normalize_player_name(n) == normalize_player_name(input_name)), None)
    if exact_match:
        return exact_match

    player_id = alias_to_id.get(normalize_player_name(input_name))
    if player_id is None:
        return None

    aliases = id_to_aliases.get(player_id, set())
    return next((n for n in available_pool if normalize_player_name(n) in aliases), None)


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


def validate_challonge_finalized(challonge_data):
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
        if not file_name.startswith("amq_song_export"):
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
        name = masquerade_mapping.get(normalize_player_name(name), name)
    name = clean_player_name(name)

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
        name = clean_player_name(name)
        if not name:
            continue
        if normalize_player_name(name) in ignored_tokens:
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

