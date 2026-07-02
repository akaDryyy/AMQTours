import os, sys, json, re, gspread, hashlib

ASSETS_MODULE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
if ASSETS_MODULE_DIR not in sys.path:
    sys.path.insert(0, ASSETS_MODULE_DIR)

from TourClasses import *
from TourFunctions import *
from JsonProcessing import *
from SheetTransmission import *
from ScreenshotBuilder import *
from bs4 import BeautifulSoup
from datetime import datetime, timezone
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
    MAIN_SHEET_SPEED=165193471
    MAIN_SHEET_OTHER=2090958619
    MAIN_SHEET_OPS=591917504
    MAIN_SHEET_EDS=601464032
    MAIN_SHEET_INS=2075065970
    MAIN_SHEET_OPEDS=1506914251
    MAIN_SHEET_5S=676003100
    MAIN_SHEET_WATCHED_INS=1177294729
    MAIN_SHEET_WATCHED_EDS=484347985
    MAIN_SHEET_WATCHED_OPEDS=231019448

    TEAM_AVG = 0
    TEAM_SIZE = 0

    playerDB = PlayerDB()
    teamDB = TeamDB()
    tourGames = TourGames()
    songDB = SongDB()

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
[7]: Watched OPEDs
[8]: Watched FL 2+8s
[9]: Watched FL 5s
[10]: Watched -2009
[11]: Random OPs
[12]: Random EDs
[13]: Random INs
[14]: Random OPEDs
[15]: Random Chanting
[16]: Other Random
[17]: Other Watched
[18]: Brute-force
"""

    if not is_local:
        txtvar += "[19]: Masquerade\n"

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
            gamemode = MAIN_SHEET_WATCHED_OPEDS
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_oped"
            tour_type_label = "Watched OPED"
            orderToSheet.extend(watchedColumns)
        case "8":
            gamemode = MAIN_SHEET_SPEED
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_fl_speed"
            tour_type_label = "Watched FL 2+8s"
            orderToSheet.extend(watchedColumns)
        case "9":
            gamemode = MAIN_SHEET_5S
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_fl_5s"
            tour_type_label = "Watched FL 5s"
            orderToSheet.extend(watchedColumns)
        case "10":
            gamemode = "Watched -2009"
            sendToSheet = gamemode
            is_list = True
            server_average_mode = "watched_pre_2009"
            tour_type_label = "Watched -2009"
            orderToSheet.extend(watchedColumns)
        case "11":
            gamemode = MAIN_SHEET_OPS
            sendToSheet = gamemode
            server_average_mode = "random_op"
            tour_type_label = "Random OP"
        case "12":
            gamemode = MAIN_SHEET_EDS
            sendToSheet = gamemode
            server_average_mode = "random_ed"
            tour_type_label = "Random ED"
        case "13":
            gamemode = MAIN_SHEET_INS
            sendToSheet = gamemode
            server_average_mode = "random_in"
            tour_type_label = "Random IN"
        case "14":
            gamemode = MAIN_SHEET_OPEDS
            sendToSheet = gamemode
            server_average_mode = "random_oped"
            tour_type_label = "Random OPED"
        case "15":
            gamemode = "Random Chanting"
            sendToSheet = gamemode
            server_average_mode = "random_chanting"
            tour_type_label = "Random Chanting"
        case "16":
            gamemode = MAIN_SHEET_RANDOM
            sendToSheet = MAIN_SHEET_OTHER
            is_other = True
            server_average_mode = "random_fl"
            tour_type_label = "Other Random"
        case "17":
            gamemode = MAIN_SHEET_WATCHED
            sendToSheet = MAIN_SHEET_OTHER
            is_list = True
            is_other = True
            server_average_mode = "watched_fl"
            tour_type_label = "Other Watched"
            orderToSheet.extend(watchedColumns)
        case "18":
            brute_force = True
        case "19":
            if is_local:
                print("Masquerade mode requires Challonge and is only available through ngm_stats.py.")
                _ = input('\npress enter to close')
                return
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
        challonge_link = validate_codes_file(TEAMS, TEAMS_RE, require_challonge=not is_local)
    preflight_json_files(JSONS, REGEX)

    sheet_context = load_sheet_context(
        directory=DIRECTORY,
        sheet_id=NGM_STATS_SHEET_ID,
        worksheet_ref=gamemode,
        is_list=is_list,
        assets_dir=ASSETS,
    )
    gc = sheet_context["gc"]
    sheet = sheet_context["sheet"]
    wks = sheet_context["wks"]
    rows_ids = sheet_context["rows_ids"]
    alias_to_id = sheet_context["alias_to_id"]
    id_to_aliases = sheet_context["id_to_aliases"]
    avg_df = sheet_context["avg_df"]

    # Build player DB
    for name, pid in rows_ids[1:]:
        playerDB.add_player(Player(name=str(name).strip(), player_id=int(pid)))
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
                if is_local:
                    continue

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

    # W-L-T is Challonge-derived and intentionally unavailable in local mode.
    data = {"matches_by_round": {}}
    if not is_local:
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
        validate_challonge_finalized(data)
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
            p.post_process(
                TEAM_AVG,
                WLTcheck=not is_local,
                scale_usefulness=scale_usefulness,
            )
            d = asdict(p)
            stats_list.append(d)

    export_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
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
        "watched_oped": {"OP", "ED"},
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
    if is_local:
        finalOrder2.remove("W-L-T")

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
    print(f"Stats about delta saved at {path2}")

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


def main():
    run_ngm_sheet_stats(False)


if __name__ == "__main__":
    main()
