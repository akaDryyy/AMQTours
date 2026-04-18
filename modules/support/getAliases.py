from itertools import combinations
import pandas as pd

def getAliases(ALIAS_PATH):
    """Deprecated function"""
    aliases = {}
    with open(ALIAS_PATH, 'r', encoding='utf-8') as f:
        # tab-separated list of aliases, where every line has all names of one player 
        # first of each line should be the main name (current bot name)
        for line in f:
            alias_list = line.split('\t')
            main_name = alias_list[0].strip().lower()
            for alias in alias_list:
                aliases[alias.strip().lower()] = main_name
        
    return aliases

def getAliasesDF(idtable):
    alias_df = pd.read_csv(idtable)
    return alias_df

def getAliasesID(idtable, player_key):
    idtable["Player Name"] = idtable["Player Name"].str.strip().str.lower()
    alias_to_id = dict(zip(idtable["Player Name"], idtable["Player ID"]))

    return alias_to_id.get(player_key.strip().lower())

def getAliasesFirstName(idtable, player_id):
    id_to_primary_name = idtable.groupby("Player ID")["Player Name"].first().to_dict()

    return id_to_primary_name.get(player_id)

def getAliasesAllNames(idtable, player_id):
    idtable["Player Name"] = idtable["Player Name"].str.strip()
    id_to_all_names = idtable.groupby("Player ID")["Player Name"].apply(list).to_dict()
    
    return id_to_all_names.get(player_id, [])