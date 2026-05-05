import pandas as pd
import os
import csv
import json
from modules.support.cleanData import *
from modules.support.trim import *
from modules.support.computeRanks import *
from modules.support.changelogMVPs import *
from modules.support.readCredentials import readCredentials
from modules.support.getAliases import *
from modules.support.getRanks import getRanks

def get_player_stats(path, tabStats, tabIDs, type):
    gc = readCredentials(path)

    sheetName = "NGM Stats Export v2"
    sheet = gc.open(sheetName)
    wks = sheet.get_worksheet_by_id(tabStats)
    wks_ids = sheet.get_worksheet_by_id(tabIDs)

    idtable = os.path.join(path, "ids.csv")
    statstable = os.path.join(path, "stats.csv")
    cleanedstats = os.path.join(path, "stats_clean.csv")
    cleanedstatsyear = os.path.join(path, "stats_clean_year.csv")
    fullstats = os.path.join(path, "stats_clean_full.csv")

    rows = wks.get_all_values()
    with open(statstable, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
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

def guess_gr(thresholds, avg_gr):
    if avg_gr:
        for threshold, result in thresholds:
            if avg_gr >= threshold:
                return result
    return "x"

def get_guess_watched(name, player_stats, idtable, oneg, twog, threeg, fourg):
    try:
        alias_df = pd.read_csv(idtable)
        alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
        player_id = alias_df.loc[alias_df["Player Name"] == name, 'Player ID'].iloc[0]
        avg_gr = player_stats.loc[player_stats["Player ID"] == player_id, "Guess rate"].mean()
        if pd.isna(avg_gr):
            avg_gr = None
    except IndexError:
        avg_gr = None
    return guess_gr([
    (fourg, '5'),
    (threeg, '4'),
    (twog, '3'),
    (oneg, '2'),
    (-float('inf'), '1')
], avg_gr)

def get_guess_random(name, player_stats, idtable, oneg, twog, threeg):
    try:
        alias_df = pd.read_csv(idtable)
        alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
        player_id = alias_df.loc[alias_df["Player Name"] == name, 'Player ID'].iloc[0]
        avg_gr = player_stats.loc[player_stats["Player ID"] == player_id, "Guess rate"].mean()
        if pd.isna(avg_gr):
            avg_gr = None
    except IndexError:
        avg_gr = None
    return guess_gr([
        (threeg, '4'),
        (twog, '3'),
        (oneg, '2'),
        (-float('inf'), '1')
    ], avg_gr)

def get_guess_watched_28_gr(name, player_stats, idtable, zerog, oneg, twog, threeg, fourg):
    try:
        alias_df = pd.read_csv(idtable)
        alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
        player_id = alias_df.loc[alias_df["Player Name"] == name, 'Player ID'].iloc[0]
        avg_gr = player_stats.loc[player_stats["Player ID"] == player_id, "Guess rate"].mean()
        if pd.isna(avg_gr):
            avg_gr = None
    except IndexError:
        avg_gr = None
    return guess_gr([
        (fourg, '5'),
        (threeg, '4'),
        (twog, '3'),
        (oneg, '2'),
        (zerog, '1'),
        (-float('inf'), '0')
    ], avg_gr)

def add_to_tourlist(tour, folder):
   with open(f"./{folder}/tourlist.txt", "a") as f:
    f.write("\n")
    f.write(tour)

def get_blacklist():
    with open("./blacklist.json") as f:
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
            if player_id in ranks:
                players_ids[name] = ranks[player_id]
    return players_ids

def get_mvps(folder):
    with open(f"./{folder}/mvps.txt", encoding="utf-8") as f:
     content = f.read()
     return content

def get_changelog(folder):
    with open(f"./{folder}/changelog.txt", encoding="utf-8") as f:
     content = f.read()
     return content

def get_tourlist(folder):
    with open(f"./{folder}/tourlist.txt", encoding="utf-8") as f:
     return f.read()
