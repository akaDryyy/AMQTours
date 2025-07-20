import json

try:
    with open('elos.json', 'r', encoding='utf-8') as f:
        PLAYER_LIST = json.load(f)
except:
    PLAYER_LIST = {}

try:
    with open('historical_tourcount.json', 'r', encoding='utf-8') as f:
        HISTORICAL_TOURCOUNT = json.load(f)
except:
    HISTORICAL_TOURCOUNT = {}    

try:
    with open('elo_history.json', 'r', encoding='utf-8') as f:
        ELO_HISTORY = json.load(f)
except:
    ELO_HISTORY = {}


aliases = {}
with open('aliases.txt', 'r', encoding='utf-8') as f:
    for line in f:
        alias_list = line.split('\t')
        main_name = alias_list[0].strip().lower()
        for alias in alias_list:
            aliases[alias.strip().lower()] = main_name

players = {}
for player in HISTORICAL_TOURCOUNT:
    if player in aliases:
        players[aliases[player]] = HISTORICAL_TOURCOUNT.get(player, 0)
    else:
        players[player] = HISTORICAL_TOURCOUNT.get(player, 0)

for player in PLAYER_LIST:
    if player not in players:
        players[player] = 0


for tour in ELO_HISTORY:
    for item in tour:
        if item == 'player':
            for player in tour.get(item):
                if player in aliases:
                    players[aliases[player]] += 1
                else:
                    players[player] += 1

with open('new_tourcount.json', 'w', encoding='utf-8') as f:
    tour_count = {k: v for k, v in sorted(players.items(), key=lambda item: item[1], reverse=True)}
    json.dump(tour_count, f, indent='\t')