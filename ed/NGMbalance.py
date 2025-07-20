import itertools
import random

TEAMAVG_DIFF = 0.5

ranks = {}
def process_rank(line):
    rank, rank_players = line.split(':', 2)
    rank = float(rank)
    for player in rank_players.split(','):
        ranks[player.strip().lower()] = rank

with open('eds_TL.txt', 'r') as file:
    for line in file.readlines():
        process_rank(line)

players = []
with open('players.txt', 'r') as file:
    for player in file.read().split(','):
        player = player.strip().split(' ')[0]
        player = player.strip()
        player_key = player.lower()
        if player_key in ranks:
            player = f'{player} ({ranks[player_key]})'
            players.append(player)
        else:
            print(f"[WARN] Player '{player}' not found")

def get_player_value(player):
    return float(player.split("(")[1].split(")")[0])

def get_group_sum(group):
    return sum([get_player_value(player) for player in group])

def balance_players(players, group_size):
    groups = [[] for i in range(len(players)//group_size)]
    players_sorted = sorted(players, key=lambda x: get_player_value(x), reverse=True)

    for i, player in enumerate(players_sorted):
        groups[i%len(groups)].append(player)

    count = 0
    while count < 500000:
        count += 1
        group_sums = [get_group_sum(group) for group in groups]
        max_sum = max(group_sums)
        min_sum = min(group_sums)
        if max_sum - min_sum <= TEAMAVG_DIFF:
            break
        max_group = groups[group_sums.index(max_sum)]
        min_group = groups[group_sums.index(min_sum)]
        max_player = max_group.pop(random.randint(0, len(max_group)-1))
        min_player = min_group.pop(random.randint(0, len(min_group)-1))
        min_group.append(max_player)
        max_group.append(min_player)

    return groups, max_sum - min_sum

runs = 5
for j in range(runs):
    groups, avg = balance_players(players, 4)
    teamavg = 0
    if avg <= TEAMAVG_DIFF:
        print(f'Results #{j+1}:')

        for i, group in enumerate(groups):
            sg = sorted(group, key=lambda x: get_player_value(x), reverse=True)
            player_names = ' '.join(sg)
            group_sums = sum([get_player_value(player) for player in group])
            print(f"{player_names} = {group_sums}")
            teamavg += group_sums
        
        print(f"\n{4*teamavg / len(players)}\n")
    else: print(f'Failed to balance Results #{j+1}\n')