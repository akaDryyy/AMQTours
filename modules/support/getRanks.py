import json
from modules.support.getAliases import *
from modules.support.saveElos import *

def getRanks(RANKS_PATH, ELOS_PATH=None, ALIAS_PATH=None, returnFixup=False):
    ranks = {}
    post_ranks_fixup = {}
    def process_rank(line):
        rank, rank_players = line.split(':', 2)
        rank = float(rank)
        rank_players = rank_players.strip().lower()
        for player in rank_players.split(','):
            if returnFixup:
                ranks[player.strip().lower()] = rank
                if player.strip() != '':
                    post_ranks_fixup[player.strip().lower()] = rank
            else:
                player_guesscount = player.rsplit(' [',2)
                playername = player_guesscount[0]
                ranks[playername.strip().lower()] = rank

    with open(RANKS_PATH, 'r') as file:
        for line in file.readlines():
            process_rank(line)

    ranks = {player: rank for player, rank in ranks.items()}
    updated_elos = {getAliasesID(ALIAS_PATH, player) or player: rating for player, rating in ranks.items()}

    if ELOS_PATH:
        raw_ranks = load_composite_dict_from_json(ELOS_PATH)
        cleaned_ranks = {id: v for (id, k), v in raw_ranks.items()}

        updated_elos.update(cleaned_ranks)

    if returnFixup:
        return updated_elos, raw_ranks, post_ranks_fixup
    else:
        return updated_elos