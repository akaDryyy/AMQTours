import os
import csv
import json
from pathlib import Path
from modules.support.cleanData import clean_data
from modules.support.readCredentials import readCredentials
from modules.support.getAliases import getAliasesDF, getAliasesID
from modules.support.getRanks import getRanks
from modules.support.LPProblem import LPProblem
from modules.support.readElos import normalize_player_id

PROJECT_ROOT = Path(__file__).resolve().parent

def sync_ids_from_sheet(path, sheetName, tabIDs):
    gc = readCredentials(path)
    sheet = gc.open(sheetName)
    wks_ids = sheet.get_worksheet_by_id(tabIDs)
    rows_ids = wks_ids.get_all_values()
    idtable = os.path.join(path, "ids.csv")
    with open(idtable, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows_ids)

def create_teams(path, players, team_size, whitelist, blacklist, separateT1):
    aliases = getAliasesDF(os.path.join(path, "ids.csv"))
    def solver_key(player):
        player_id = getAliasesID(aliases, player)
        if player_id is None or str(player_id).strip().lower() in {"", "nan"}:
            normalized_name = "".join(ch if ch.isalnum() else "_" for ch in player.strip().lower())
            return f"name__{normalized_name}"
        return f"id__{player_id}"

    players_ids = {}
    players_ids_ranks = []
    for player, rank in players:
        key = solver_key(player)
        if key in players_ids:
            raise ValueError(f"Duplicate player or alias: {player} and {players_ids[key]} resolve to the same player.")
        players_ids[key] = player
        players_ids_ranks.append((key, rank))

    blacklist_ids = [[solver_key(player1), solver_key(player2)] for (player1, player2) in blacklist]
    whitelist_ids = [[solver_key(player1), solver_key(player2)] for (player1, player2) in whitelist]
    solution = LPProblem(players_ids_ranks, team_size, blacklist_ids, whitelist_ids, max_solutions=1, think_time=15000, separateT1=separateT1)[0]
    teams = [{players_ids[player_id]: solution[player_id] for player_id in solution}]
    return teams

def get_player_stats(
    path,
    tabStats,
    tabIDs,
    type,
    sheetName="NGM Stats Export v2",
    sheetId=None,
    idsSheetName=None,
    idsSheetId=None,
):
    gc = readCredentials(path)

    sheet = gc.open_by_key(sheetId) if sheetId else gc.open(sheetName)
    if isinstance(tabStats, str):
        tab_names = [tabStats]
        if not tabStats.endswith("s"):
            tab_names.append(f"{tabStats}s")
        else:
            tab_names.append(tabStats[:-1])

        last_error = None
        for tab_name in tab_names:
            try:
                wks = sheet.worksheet(tab_name)
                break
            except Exception as exc:
                last_error = exc
        else:
            raise last_error
    else:
        wks = sheet.get_worksheet_by_id(tabStats)
    stats_source_title = getattr(wks, "title", str(tabStats))
    stats_source_id = getattr(wks, "id", tabStats)
    ids_sheet = sheet
    if idsSheetId:
        ids_sheet = gc.open_by_key(idsSheetId)
    elif idsSheetName and (sheetId or idsSheetName != sheetName):
        ids_sheet = gc.open(idsSheetName)
    wks_ids = ids_sheet.get_worksheet_by_id(tabIDs)

    idtable = os.path.join(path, "ids.csv")
    statstable = os.path.join(path, "stats.csv")
    cleanedstats = os.path.join(path, "stats_clean.csv")
    cleanedstatsyear = os.path.join(path, "stats_clean_year.csv")
    fullstats = os.path.join(path, "stats_clean_full.csv")

    rows = wks.get_all_values()
    with open(statstable, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    source_path = os.path.join(path, "stats_source.json")
    with open(source_path, "w", encoding="utf-8") as f:
        json.dump({"stats_tab": tabStats, "worksheet_id": stats_source_id, "worksheet_title": stats_source_title}, f, indent=2)
    
    rows_ids = wks_ids.get_all_values()
    with open(idtable, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows_ids)
    
    maxFallbackWindow = 6
    activeTours = 10

    clean_stats, max_stats = clean_data(idtable, statstable, cleanedstatsyear, maxFallbackWindow, activeTours, type)
    clean_stats = clean_stats.sort_values(["Player ID", "Timestamp"])
    clean_stats.to_csv(cleanedstats, index=False, encoding="utf-8")
    player_stats = clean_stats.sort_values(["Player ID", "Timestamp"])
    max_stats.to_csv(fullstats, index=False, encoding="utf-8")

    return player_stats, idtable

def get_blacklist():
    with open(PROJECT_ROOT / "blacklist.json", encoding="utf-8") as f:
     content = f.read()
     return json.loads(content)

def get_elos(folder):
    players_ids = {}
    idtable = os.path.join(folder, "ids.csv")
    rank_path = os.path.join(folder, "ranks.txt")
    elos_path = os.path.join(folder, "elos.json")
    aliases = getAliasesDF(idtable)
    ranks = getRanks(rank_path, elos_path, aliases)
    aliases["Player Name"] = aliases["Player Name"].str.strip().str.lower()
    id_to_all_names = aliases.groupby("Player ID")["Player Name"].apply(list).to_dict()
    for player_id, names in id_to_all_names.items():
        for name in names:
            key = normalize_player_id(player_id)
            if key in ranks:
                players_ids[name] = ranks[key]
    return players_ids
