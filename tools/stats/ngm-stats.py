import os, json, re, gspread
from TourClasses import *
from TourFunctions import *
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    JSONS = os.path.join(DIRECTORY, "jsons")
    TEAMS = os.path.join(DIRECTORY, "codes.txt")
    TEAMS_RE = r"(\S+)\s*\((-?[\d.]+)\)"
    REGEX = r"\D*(\d{1,2})\s*(\(.*?\))?\.json$"
    
    MAIN_SHEET_RANDOM=0
    MAIN_SHEET_WATCHED=1719516221
    SHEET_PLAYER_IDS=1903970832
    MAIN_SHEET_SPEED=165193471
    MAIN_SHEET_SAKU=1708161307
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
    hasExtraColumn = False
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
        "TIE"
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
[3]: Watched INs
[4]: Watched EDs
[5]: Watched FL 2+8s
[6]: Watched FL 5s
[7]: Watched FL Saku Elo
[8]: Random OPs
[9]: Random EDs
[10]: Random INs
[11]: Other Random
[12]: Other Watched
"""

    print(txtvar)
    is_list = False
    is_other = False
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
            # hasExtraColumn = False
        case "2":
            gamemode = MAIN_SHEET_WATCHED
            sendToSheet = gamemode
            is_list = True
            orderToSheet.extend(watchedColumns)
        case "3":
            gamemode = MAIN_SHEET_WATCHED_INS
            sendToSheet = gamemode
            is_list = True
            orderToSheet.extend(watchedColumns)
        case "4":
            gamemode = MAIN_SHEET_WATCHED_EDS
            sendToSheet = gamemode
            is_list = True
            orderToSheet.extend(watchedColumns)
        case "5":
            gamemode = MAIN_SHEET_SPEED
            sendToSheet = gamemode
            is_list = True
            orderToSheet.extend(watchedColumns)
        case "6":
            gamemode = MAIN_SHEET_5S
            sendToSheet = gamemode
            is_list = True
            orderToSheet.extend(watchedColumns)
        case "7":
            gamemode = MAIN_SHEET_SAKU
            sendToSheet = gamemode
            is_list = True
            orderToSheet.extend(watchedColumns)
        case "8":
            gamemode = MAIN_SHEET_OPS
            sendToSheet = gamemode
        case "9":
            gamemode = MAIN_SHEET_EDS
            sendToSheet = gamemode
        case "10":
            gamemode = MAIN_SHEET_INS
            sendToSheet = gamemode
        case "11":
            gamemode = MAIN_SHEET_RANDOM
            sendToSheet = MAIN_SHEET_OTHER
            is_other = True
        case "12":
            gamemode = MAIN_SHEET_WATCHED
            sendToSheet = MAIN_SHEET_OTHER
            is_list = True
            is_other = True
            orderToSheet.extend(watchedColumns)

    # Grab necessary files
    PARDIR = os.path.abspath(os.path.join(DIRECTORY, os.pardir))
    gc = gspread.oauth(
        credentials_filename=PARDIR + '/credentials/credentials.json',
        authorized_user_filename=PARDIR + '/credentials/authorized_user.json'
    )
    
    sheet = gc.open(sheetName)
    wks = sheet.get_worksheet_by_id(gamemode)
    rows_stats = wks.get_all_values()
    wks_ids = sheet.get_worksheet_by_id(SHEET_PLAYER_IDS)
    rows_ids = wks_ids.get_all_values()

    avg_df = clean_data(rows_ids, rows_stats, 2, 6, 10, 10, hasExtraColumn)
    avg_df = avg_df.sort_values(["Player ID", "Tournament Date"])
    avg_df = avg_df.groupby("Player ID").apply(trim, include_groups=False).reset_index()
    avg_df["Player ID"] = pd.to_numeric(avg_df["Player ID"], errors="coerce")

    # Build player DB
    for name, pid in rows_ids[1:]:
        playerDB.add_player(Player(name=name, player_id=int(pid)))
    playerDB.build_lookups()

    # Obtain the tour players
    with open(TEAMS, "r", encoding="utf-8") as file:
        for line in file.readlines():
            if line.lower().startswith(("average", "avg")):
                TEAM_AVG = float(line.split(':')[-1].strip())
            if line.startswith("https://"):
                line = line.strip()
                html = download_challonge_page(line)
            if line.lower().startswith(("sub")):
                if line.split(':')[-1]:
                    for name, rank in re.findall(r'(\S+)\s*\(([\d.]+)\)', line):
                        p_name = name
                        p_rank = float(rank)
                        subbing_player = playerDB.lookup_player_name(p_name)
                        subbing_player.rank = p_rank
                        subbing_player.set_averages(avg_df)
                        if subbing_player is None:
                            input(f"{p_name} not found inside IDs. "
                                "If it's a new player ask to add, "
                                "otherwise rename them in `teams.txt` with their AMQ name and run again. "
                                "Press Enter to exit.")
                            exit()
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
                            input(f"{player_name} not found inside IDs. "
                                "If it's a new player ask to add, "
                                "otherwise rename them in `teams.txt` with their AMQ name and run again. "
                                "Press Enter to exit.")
                            exit()
                        new_player.rank = float(player_rank)
                        new_player.set_averages(avg_df)
                        new_team.add_player(new_player)
                    teamDB.add_team(new_team)
    TEAM_SIZE = new_team.get_team_size()
    playerDB.build_lookups()
    USEFULNESS = Usefulness(TEAM_SIZE, TEAM_AVG)
    
    # Handle W-L-T
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script"):
        content = script.string
        if not content:
            continue
        match = re.search(
            r"window\._initialStoreState\['TournamentStore'\]\s*=\s*({.*?});", 
            content, 
            re.DOTALL
        )
        if match:
            data_str = match.group(1)
            data_str = data_str.replace("'", '"')
            data_str = re.sub(r",\s*}", "}", data_str)
            data_str = re.sub(r",\s*]", "]", data_str)
            data = json.loads(data_str)
            break

    for round_key, matches in data["matches_by_round"].items():
        pattern = r"(\w+)(?:\s*\[(.*?)\])?\s*\((.*?)\)"
        for match in matches:
            match_playersTeam1 = match["player1"]["display_name"]
            match_playersTeam2 = match["player2"]["display_name"]
            playersTeam1 = re.findall(pattern, match_playersTeam1)
            playersTeam2 = re.findall(pattern, match_playersTeam2)

            scoreT1 = match["scores"][0]
            scoreT2 = match["scores"][1]
            matchResult = "WIN" if scoreT1 > scoreT2 else "LOSE" if scoreT1 < scoreT2 else "TIE"
            inverse_result = {"WIN": "LOSE", "LOSE": "WIN", "TIE": "TIE"}

            player_info = []

            # Team 1 players
            for name, rounds_played, rank in playersTeam1:
                rounds = [int(x.strip()) for x in rounds_played.split(",")] if rounds_played else []
                try:
                    player_info.append((name, rounds, float(rank) if rank else None, matchResult))
                except ValueError:
                    player_info.append((name, rounds, None, matchResult))

            # Team 2 players
            for name, rounds_played, rank in playersTeam2:
                rounds = [int(x.strip()) for x in rounds_played.split(",")] if rounds_played else []
                try:
                    player_info.append((name, rounds, float(rank) if rank else None, inverse_result[matchResult]))
                except ValueError:
                    player_info.append((name, rounds, None, matchResult))

            for name, rounds_played, _, result in player_info:
                if not rounds_played or int(round_key) in rounds_played:
                    WLTplayer = teamDB.lookup_player(playerDB.lookup_player_name(name))
                    try:
                        WLTplayer.add(result)
                    except AttributeError:
                        print(f"{name} not found. The player was a sub or needs manual adding to IDs.")
                        exit()

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

    # Parse the jsons
    for file_name in os.listdir(JSONS):
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
            except:
                input(f"Failed to load {f}. Check the file extension. Press Enter to exit.")
                exit()
        
        game = Game(file_name)
        playersSeen = []

        # Parse each song
        for song in json_data['songs'][:songs_played]:
            # Probably downloaded after the user disconnected or refreshed the page
            if 'videoUrl' not in song:
                print(f"The following file is incomplete: {file_name}. "
                        "A disconnection might have occurred. Press Enter to exit.")
                exit()

            single_song = Song(song)
            songDB.add_song(single_song)
            game.add_song(single_song)
            game.add(single_song.song_type)
            game.add("difficulty", single_song.song_difficulty)
            game.add("vintage", single_song.vintage)

            # Handle the players
            for correctGuesser in song["correctGuessPlayers"]:
                # Get the correct Player which is inside the team
                try:
                    guesser = teamDB.lookup_player(playerDB.lookup_player_name(correctGuesser))
                except AttributeError:
                    print(f"{correctGuesser} not found. Might be an alias not yet known?")
                single_song.add_guesser(guesser)
                if guesser not in playersSeen:
                    playersSeen.append(guesser)
            for playerGotInList in song["listStates"]:
                watcher = teamDB.lookup_player(playerDB.lookup_player_name(playerGotInList["name"]))
                single_song.add_rig(watcher)
                watcher.add("rigAmount")
                if watcher not in playersSeen:
                    playersSeen.append(watcher)
        
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
    for team in teamDB.teams:
        for p in team.players + team.subs:
            p.post_process(TEAM_AVG)
            d = asdict(p)
            stats_list.append(d)

    df_players = pd.DataFrame(stats_list)
    df_players = df_players.drop(columns=["player_id", "player_team", "avgVintageHit", "avgVintagePlayed"])
    df_players.sort_values("GR", ascending=False, inplace=True)
    df_players["Timestamp"] = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
        "OFFLIST": "Offlist",
        "ONLIST": "Onlist",
        "RIGPERC": "Rig %",
        "WLT": "W-L-T"
    })
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
        "ED guess rate",
        "ΔED",
        "# EDs hit",
        "# EDs played",
        "IN guess rate",
        "ΔIN",
        "# INs hit",
        "# INs played",
        "Lives taken",
        "Lives saved",
        "Avg diff hit",
        "Avg diff played",
        "Avg vintage hit",
        "Avg vintage played",
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
    df_players_adj = df_players[order]

    # Generate images
    finalOrder1 = [
        "Rank", 
        "Player name", 
        "Guess rate", 
        "Usefulness",
        "erigs",
        "0/8s",
        "7/8s",
        "avg/8",
        "# 3/8s or below",
        "Total hit",
        "Total songs",
        "Lives taken",
        "Lives saved",
        "Avg diff hit",
        "Avg diff played",
        "Avg vintage hit",
        "Avg vintage played",
        "W-L-T"
    ]

    finalOrder2 = [
        "Rank", 
        "Player name",
        "Guess rate",
        "ΔGR", 
        "Usefulness",
        "ΔUF",
        "OP guess rate", 
        "ΔOP",
        "# OPs hit",
        "# OPs played",
        "ED guess rate",
        "ΔED",
        "# EDs hit",
        "# EDs played",
        "IN guess rate",
        "ΔIN",
        "# INs hit",
        "# INs played"
    ]

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

    final_df1 = df_players_adj[finalOrder1]
    final_df2 = df_players_adj[finalOrder2]
    final_df3 = df_players_adj[finalOrder3]

    # Song statistics
    songDB.post_process()
    saveSongStats(songDB=songDB, path=DIRECTORY, filename="Stats Songs.png")

    # Save to sheet
    wks_send = sheet.get_worksheet_by_id(sendToSheet)
    len_send = len(wks_send.get_all_values())
    if is_other:
        values = [orderToSheet] + df_players[orderToSheet].values.tolist()
        wks_send.update(values=values, range_name='A'+str(len_send + 2))
    else:
        values = df_players[orderToSheet].values.tolist()
        wks_send.update(values=values, range_name='A'+str(len_send + 2))

    reverse_columns = ["avg/8", "Avg diff hit", "Avg diff played", "Rigs missed", "Missed solos", "Lives lost on rigs"]
    separators = ["Player name", "Usefulness", "# 3/8s or below", "Lives saved", "Avg vintage played", "Total songs"]
    exclude_columns = ["Rank", "Guess rate", "0/8s", "7/8s"]

    path = os.path.join(DIRECTORY, "Stats.png")
    df_to_png(df=final_df1, path=DIRECTORY, filename="Stats.png", reverse_cols=reverse_columns, exclude_columns=exclude_columns, separators=separators)
    print(f"Stats about GR saved at {path}")

    exclude_columns = ["Rank", "Guess rate"]
    separators = ["Player name", "ΔUF", "# OPs played", "# EDs played"]

    path2 = os.path.join(DIRECTORY, "Stats2.png")
    df_to_png(df=final_df2, path=DIRECTORY, filename="Stats2.png", reverse_cols=None, exclude_columns=exclude_columns, separators=separators)
    print(f"Stats about Δ saved at {path2}")

    if is_list:
        exclude_columns = ["Rank"]
        separators = ["Player name", "Offlist", "Rigs Missed", "Offlist erigs"]

        path3 = os.path.join(DIRECTORY, "Stats3 - Watched Exclusive.png")
        df_to_png(df=final_df3, path=DIRECTORY, filename="Stats3 - Watched Exclusive.png", reverse_cols=reverse_columns, exclude_columns=exclude_columns, separators=separators)
        print(f"Stats about watched saved at {path3}")

    print(f"{wks_send.url}?range={len_send + 2}:{len_send + 2}")
    _ = input('\npress enter to close')

if __name__ == "__main__":
    main()