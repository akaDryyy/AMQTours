import itertools
import random
import math
import time
import gc
import json

import bldm as bldm

TEAMSIZE = 4
TIMELIMIT = 20
START = time.time()

ranks = {}
def process_rank(line):
    rank, rank_players = line.split(':', 2)
    rank = float(rank)
    for player in rank_players.split(','):
        player_guesscount = player.rsplit(' [',2)
        playername = player_guesscount[0]
        ranks[playername.strip().lower()] = rank

with open('ranks.txt', 'r') as file:
    for line in file.readlines():
        process_rank(line)

with open('elos.json', 'r') as f:
    ranks.update(json.load(f))

ranks = {player: rank for player, rank in ranks.items()}

players = {}
with open('players.txt', 'r') as file:
    for player in file.read().split(','):
        player = player.strip().split(' (')[0]
        player = player.strip()
        player_key = player.lower()
        if player_key in ranks:
            new_player = {player: ranks[player_key]}
            players.update(new_player)
        else:
            input(f"[WARN] Player '{player}' not found, enter to continue")

players = dict(sorted(players.items(), key=lambda x:x[1], reverse=True))

def get_player_value(player):
    return int(player.split("(")[1].split(")")[0])

def get_group_sum(group):
    return sum([get_player_value(player) for player in group])

possible_teams = bldm.balanced_partition(list(players.items()), TEAMSIZE, TIMELIMIT, 100)
try:
    print(possible_teams[0])
    print(sum(players.values()) / (len(players) / TEAMSIZE))
except IndexError:
    print('found nothing')