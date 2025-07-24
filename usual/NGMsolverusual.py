from pulp import *
import argparse, json, os

blacklist_path = os.path.abspath(os.path.join(os.pardir, "blacklist.json"))
whitelist_path = os.path.abspath(os.path.join(os.pardir, "whitelist.json"))
alises_path = os.path.abspath(os.path.join(os.pardir, "aliases.txt"))
ranks_path = os.path.abspath("ranks.txt")
elo_path = os.path.abspath("elos.json")
players_path = os.path.abspath("players.txt")
codes_path = os.path.abspath("codes.txt")
think_time = 25000

parser = argparse.ArgumentParser(description="AMQ Tours")
parser.add_argument('--size', '-s',
                    help="Define the size of each team",
                    required=False)
parser.add_argument('--mode', '-m', 
                    choices=['usual', 'quag'],
                    required=False,
                    help="Define the tour mode, currently usual or quag")
args = parser.parse_args()
if args.size:
    team_size = int(args.size)
else:
    team_size = 4
if args.mode:
    gamemode = args.mode
else:
    gamemode = "usual"

# Obtain the players
ranks = {}
def process_rank(line):
    rank, rank_players = line.split(':', 2)
    rank = float(rank)
    for player in rank_players.split(','):
        player_guesscount = player.rsplit(' [',2)
        playername = player_guesscount[0]
        ranks[playername.strip().lower()] = rank

with open(ranks_path, 'r') as file:
    for line in file.readlines():
        process_rank(line)

with open(elo_path, 'r') as f:
    ranks.update(json.load(f))

ranks = {player: rank for player, rank in ranks.items()}

aliases = {}
with open(alises_path, 'r', encoding='utf-8') as f:
    # tab-separated list of aliases, where every line has all names of one player 
    # first of each line should be the main name (current bot name)
    for line in f:
        alias_list = line.split('\t')
        main_name = alias_list[0].strip().lower()
        for alias in alias_list:
            aliases[alias.strip().lower()] = main_name

players = {}
with open(players_path, 'r') as file:
    for player in file.read().split(','):
        player = player.strip().split(' (')[0]
        player = player.strip()
        player_key = player.lower()
        if player_key in ranks:
            new_player = {player: ranks[player_key]}
            players.update(new_player)
        # Check aliases
        elif player_key in aliases:
            main_name = aliases[player_key]
            if main_name in ranks:
                players[player] = ranks[main_name]
            else:
                input(f"[WARN] Alias '{player}' maps to '{main_name}', but '{main_name}' not in ranks. Press Enter to continue.")
        else:
            input(f"[WARN] Player '{player}' not found in ranks or aliases. Press Enter to continue.")

players = dict(sorted(((k.lower(), v) for k, v in players.items()), key=lambda x: x[1], reverse=True))
players = list(players.items())

with open(blacklist_path, "r") as f:
    blacklist = json.load(f)
blacklist = [[a.lower(), b.lower()] for a, b in blacklist]
with open(whitelist_path, "r") as f:
    whitelist = json.load(f)
whitelist = [[a.lower(), b.lower()] for a, b in whitelist]

nums = [val for _, val in players]
n = len(nums)
# Number of teams
k = int(len(nums) / team_size)
p_names = [p[0] for p in players]
p_values = {p[0]: p[1] for p in players}

# LP Problem
prob = LpProblem("TeamPartitions", LpMinimize)

# Decision variables: x[name][partition] = 1 if player is in that partition
x = LpVariable.dicts("assign", (p_names, range(k)), 0, 1, LpBinary)

# Variables for max and min partition sums
z = LpVariable("max_sum", lowBound=0)
y = LpVariable("min_sum", lowBound=0)

# Constraint: Each player assigned to one partition
for name in p_names:
    prob += lpSum(x[name][p] for p in range(k)) == 1

# Constraint: Each partition gets exact group size
for p in range(k):
    prob += lpSum(x[name][p] for name in p_names) == team_size

# Constraint: Blacklisted pairs not in the same partition
for a, b in blacklist:
    if a in p_names and b in p_names:
        for p in range(k):
            prob += x[a][p] + x[b][p] <= 1
    else:
        pass

# Constraint: Whitelisted pairs in the same partition
for a, b in whitelist:
    if a in p_names and b in p_names:
        for p in range(k):
            prob += x[a][p] == x[b][p], f"whitelist_same_partition_{a}_{b}_{p}"
    else:
        pass

# Partition totals
totals = [lpSum(x[name][p] * p_values[name] for name in p_names) for p in range(k)]

for total in totals:
    prob += z >= total
    prob += y <= total

# Objective: minimize max_sum - min_sum
prob += z - y

# Solve. Edit maxNodes to reduce thinking time
prob.solve(PULP_CBC_CMD(maxNodes=think_time))

# Collect partitions safely
partitions = [[] for _ in range(k)]
totals = [0] * k

for i in range(n):
    player_name = players[i][0]
    for j in range(k):
        var = x.get(player_name, {}).get(j)
        if var and value(var) == 1:
            partitions[j].append((player_name, nums[i]))
            totals[j] += nums[i]

# Sort partitions by total value descending
sorted_parts = sorted(zip(partitions, totals), key=lambda x: x[1], reverse=True)

def generate_codes(gamemode, txtvar):
    txtvar += "\n[Challonge](YOUR_CHALLONGE_URL)\n"
    match gamemode:
        case "usual":
            txtvar += "```e0g0z211111101100000z11110000000z11111111111100k051o000000f11100k012r02i0a46533a11002s0111111111002s0111002s01a111111111102a11111111111i01k903-11111--```\n"
        case "quag":
            txtvar += "```e0g0z211111101100000z11110000000z11111111111100f051o000000f11100k012r02i0a46533a11002s0111111111002s0111002s01a111111111102a11111111111i01k903-11111--```\n"
    txtvar += """Random NGMC guess distributions:
≥8.5: 4 guesses
4.5-8.49: 3 guesses
0.5-4.49: 2 guesses
≤0.49: 1 guess
"""

    return txtvar

def get_guess(val):
    if val >= 8.5:
        return '4'
    elif val >= 4.5:
        return '3'
    elif val >= 0.5:
        return '2'
    else:
        return '1'

txtvar = ""

header = f"{'#'*25} Challonge {'#'*25}\n"
print(header)
txtvar += header
txtvar += "\n"
for idx, (group, total) in enumerate(sorted_parts, 1):
    members = " ".join(f"{name} ({val:.3f})" for name, val in sorted(group, key=lambda x: x[1], reverse=True))
    line = f"{members}\n"
    print(line, end="")
    txtvar += line

txtvar += "\n"
print()

header = f"{'#'*25} Discord {'#'*25}\n"
print(header)
txtvar += header
txtvar += "\n"
avg = 0
for idx, (group, total) in enumerate(sorted_parts, 1):
    members = " ".join(f"{name} ({val:.3f})" for name, val in sorted(group, key=lambda x: x[1], reverse=True))
    guess_str = "".join(get_guess(val) for _, val in sorted(group, key=lambda x: x[1], reverse=True))
    avg += round(total, 4)
    line = f"{members} | Total = {round(total, 3)} | Guesses = [{guess_str}]\n"
    print(line, end="")
    txtvar += line
footer = f"\nAverage: {round(avg / k, 4)}\n"
print(footer)
txtvar += footer

final_code = generate_codes(gamemode, txtvar)

with open(codes_path, "w", encoding="utf-8") as f:
    f.write(final_code)

reset_whitelist = """[
    ["playerA", "playerB"],
    ["playerC", "playerD"]
]"""

with open(whitelist_path, "w") as f:
    f.write(reset_whitelist)