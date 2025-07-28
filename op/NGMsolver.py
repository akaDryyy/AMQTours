from pulp import *
import argparse, json, os
from copy import deepcopy

blacklist_path = os.path.abspath(os.path.join(os.pardir, "blacklist.json"))
whitelist_path = os.path.abspath(os.path.join(os.pardir, "whitelist.json"))
aliases_path = os.path.abspath(os.path.join(os.pardir, "aliases.txt"))
ranks_path = os.path.abspath("ops_TL.txt")
players_path = os.path.abspath("players.txt")
codes_path = os.path.abspath("codes.txt")
team_size = 4
max_solutions = 5
optimal_value = None
think_time = 15000
found_solutions = []

parser = argparse.ArgumentParser(description="AMQ Tours")
parser.add_argument('--size', '-s',
                    help="Define the size of each team",
                    default=4,
                    required=False)
parser.add_argument('--thinktime', '-t',
                    help="Define how long should the script take to find solutions. Less think time might result in less team options provided.",
                    default=15000,
                    required=False)
args = parser.parse_args()
if args.size:
    team_size = int(args.size)
if args.thinktime:
    think_time = args.thinktime

# Obtain the players
ranks = {}
def process_rank(line):
    rank, rank_players = line.split(':', 2)
    rank = float(rank)
    for player in rank_players.split(','):
        ranks[player.strip().lower()] = rank

with open(ranks_path, 'r') as file:
    for line in file.readlines():
        process_rank(line)

ranks = {player: rank for player, rank in ranks.items()}

aliases = {}
with open(aliases_path, 'r', encoding='utf-8') as f:
    for line in f:
        alias_list = [name.strip() for name in line.strip().split('\t') if name.strip()]
        resolved_name = next((a for a in alias_list if a.lower() in ranks), alias_list[0])
        for alias in alias_list:
            aliases[alias.lower()] = resolved_name

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
for s in range(max_solutions):
    prob.solve(PULP_CBC_CMD(maxNodes=think_time))

    if prob.status != 1:
        break

    # Store the value of the optimal objective
    if optimal_value is None:
        optimal_value = value(prob.objective)
    elif abs(value(prob.objective) - optimal_value) > 1e-5:
        break  # This solution is worse

    # Get current solution
    solution = {}
    for name in p_names:
        for p in range(k):
            if value(x[name][p]) == 1:
                solution[name] = p

    found_solutions.append(deepcopy(solution))

    # Add exclusion constraint: prevent same assignment
    prob += lpSum([x[name][p] for name, p in solution.items()]) <= len(p_names) - 1

for idx, sol in enumerate(found_solutions, 1):
    print(f"\n### Solution {idx} ###")
    team_map = [[] for _ in range(k)]
    for name, p in sol.items():
        team_map[p].append((name, p_values[name]))

    for i, team in enumerate(team_map):
        members = " ".join(f"{n} ({v:.1f})" for n, v in sorted(team, key=lambda x: x[1], reverse=True))
        total = sum(v for _, v in team)
        print(f"{members} | Total = {total:.1f}")
    

def generate_codes(txtvar):
    txtvar += "\n[Challonge](YOUR_CHALLONGE_URL)\n"
    txtvar += "```e0g0z211111101100000z21000000000z11111111111100k051o000000f11100k012r02i0a46533a11002s0111111111001e0111002s01a111111111102a11111111111i01k903-11111--```\n"
    txtvar += """Distribution of guesses:
≥9: 4 guesses
5-8: 3 guesses
1-4: 2 guesses
0: 1 guess
"""
    return txtvar

def get_guess(val):
    if val >= 9:
        return '4'
    elif val >= 5:
        return '3'
    elif val >= 1:
        return '2'
    else:
        return '1'

txtvar = ""

header = f"{'#'*25} Challonge {'#'*25}\n"
print(header)
txtvar += header
txtvar += "\n"

for idx, sol in enumerate(found_solutions, 1):
    sol_msg = f"### Solution {idx} ###\n\n"
    print(sol_msg)
    txtvar += sol_msg
    team_map = [[] for _ in range(k)]
    for name, p in sol.items():
        team_map[p].append((name, p_values[name]))

    for i, team in enumerate(team_map):
        members = " ".join(f"{n} ({v:.1f})" for n, v in sorted(team, key=lambda x: x[1], reverse=True))
        total = sum(v for _, v in team)
        team_msg = f"{members}\n"
        print(team_msg)
        txtvar += team_msg
    txtvar += "\n"
    print()

txtvar += "\n"
print()

header = f"{'#'*25} Discord {'#'*25}\n"
print(header)
txtvar += header
txtvar += "\n"
for idx, sol in enumerate(found_solutions, 1):
    sol_msg = f"### Solution {idx} ###\n\n"
    print(sol_msg)
    txtvar += sol_msg
    team_map = [[] for _ in range(k)]
    for name, p in sol.items():
        team_map[p].append((name, p_values[name]))
    avg = 0
    for i, team in enumerate(team_map):
        members = " ".join(f"{n} ({v:.1f})" for n, v in sorted(team, key=lambda x: x[1], reverse=True))
        guess_str = "".join(get_guess(val) for _, val in sorted(team, key=lambda x: x[1], reverse=True))
        total = sum(v for _, v in team)
        team_msg = f"{members} | Total = {total:.1f} | Guesses = [{guess_str}]\n"
        print(team_msg)
        txtvar += team_msg
        avg += round(total, 4)
    txtvar += "\n"
    print()

footer = f"Average: {round(avg / k, 4)}\n"
print(footer)
txtvar += footer

final_code = generate_codes(txtvar)

with open(codes_path, "w", encoding="utf-8") as f:
    f.write(final_code)

reset_whitelist = """[
    ["playerA", "playerB"],
    ["playerC", "playerD"]
]"""

with open(whitelist_path, "w") as f:
    f.write(reset_whitelist)