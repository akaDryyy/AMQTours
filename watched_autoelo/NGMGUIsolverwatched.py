from pulp import *
import argparse, json, os
import pandas as pd
from copy import deepcopy
from collections import defaultdict
from gooey import Gooey
from TierMakerWatched import trim, compute_rank_scores

@Gooey(show_success_modal=False)
def main():
    blacklist_path = os.path.abspath(os.path.join(os.pardir, "blacklist.json"))
    whitelist_path = os.path.abspath(os.path.join(os.pardir, "whitelist.json"))
    aliases_path = os.path.abspath(os.path.join(os.pardir, "aliases.txt"))
    ranks_path = os.path.abspath("ranks.txt")
    elo_path = os.path.abspath("watched_elos.json")
    txtelo_path = os.path.abspath("watched_TL.txt")
    players_path = os.path.abspath("players.txt")
    codes_path = os.path.abspath("codes.txt")
    watched_data_fallback = os.path.abspath("watched_clean.csv")
    watched_data_fallback_year = os.path.abspath("watched_clean_year.csv")
    idtable = os.path.abspath("id_stats.csv")
    team_size = 4
    gamemode = "40"
    max_solutions = 1
    optimal_value = None
    think_time = 25000
    found_solutions = []

    parser = argparse.ArgumentParser(description="AMQ Tours")
    parser.add_argument('--size', '-s',
                        help="Define the size of each team",
                        default=4,
                        required=False)
    parser.add_argument('--mode', '-m', 
                        choices=['30', '35', '40', '45', '50'],
                        default='40',
                        required=False,
                        help="Define the tour difficulty range")
    parser.add_argument('--thinktime', '-t',
                        help="Define how long should the script take to find solutions. Less think time might result in less team options provided.",
                        default=15000,
                        required=False)
    args = parser.parse_args()
    if args.size:
        team_size = int(args.size)
    if args.mode:
        gamemode = args.mode
    if args.thinktime:
        think_time = args.thinktime

    # Obtain the players
    ranks = {}
    post_ranks_fixup = {}
    def process_rank(line):
        rank, rank_players = line.split(':', 2)
        rank = float(rank)
        for player in rank_players.split(','):
            ranks[player.strip().lower()] = rank
            if player.strip() != '':
                post_ranks_fixup[player.strip()] = rank

    with open(ranks_path, 'r') as file:
        for line in file.readlines():
            process_rank(line)

    with open(elo_path, 'r') as f:
        raw_ranks = json.load(f)
        cleaned_ranks = {k.strip().lower(): v for k, v in raw_ranks.items()}
        ranks.update(cleaned_ranks)

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
            player = player.lower()
            player_key = player.lower()
            if player_key in ranks:
                new_player = {player: ranks[player_key]}
                players.update(new_player)
            # Check aliases
            elif player_key in aliases:
                main_name = aliases[player_key]
                main_name = main_name.strip().lower()
                if main_name in ranks:
                    players[player] = ranks[main_name]
                else:
                    print(f"[WARN] Alias '{player}' maps to '{main_name}', but '{main_name}' not in ranks. Press Enter to continue.")
            else:
                # Not in current elo, check if new player or stats exist for them
                alias_df = pd.read_csv(idtable)
                alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
                alias_to_id = dict(zip(alias_df["Player Name"], alias_df["Player ID"]))
                if player_key in alias_to_id:
                    player_id = alias_to_id[player_key]
                else:
                    player_id = None
                # If player found, generate the elo
                if player_id:
                    df = pd.read_csv(watched_data_fallback_year)
                    df = df[df['Player ID'] == player_id]
                    # Reset in case need to grab multiple IDs 
                    player_id = None
                    if not df.empty:
                        player_stats = df.groupby("Player ID").apply(trim, include_groups=False).reset_index()
                        clean_fb = pd.read_csv(watched_data_fallback)
                        final_df = compute_rank_scores(df=player_stats, uf_max=(clean_fb["usefulness"].max()))
                        alias_df = alias_df.drop_duplicates(subset='Player ID', keep='first')
                        final_df = final_df.merge(alias_df[['Player ID', 'Player Name']], on='Player ID', how='left')
                        rank_dict = dict(zip(final_df['Player Name'], final_df['elo'].round(3)))
                        ranks.update(rank_dict)
                        raw_ranks.update(rank_dict)
                        players[player] = ranks[list(rank_dict.keys())[0]]
                    else:
                        print(f"[WARN] Player '{player}' was found in ranks but has no data in the past months. Manually add to ranks.txt. Press Enter to exit.")
                        exit()
                else:
                    print(f"[WARN] Player '{player}' not found in ranks or aliases. Manually add to ranks.txt. Press Enter to exit.")
                    exit()  
                        
    players = dict(sorted(((k.lower(), v) for k, v in players.items()), key=lambda x: x[1], reverse=True))
    players = list(players.items())
    raw_ranks.update(post_ranks_fixup)
    raw_ranks = dict(sorted(raw_ranks.items(), key=lambda x: -x[1]))
    score_to_players = defaultdict(list)
    for player_to_append, score in raw_ranks.items():
        score_to_players[round(score, 3)].append(player_to_append)

    with open(elo_path, "w") as f:
        json.dump(raw_ranks, f, indent=4)
    with open(txtelo_path, "w") as f:
        for score in sorted(score_to_players.keys(), reverse=True):
            string_players = ", ".join(score_to_players[score])
            f.write(f"{score}: {string_players}\n")

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
            members = " ".join(f"{n} ({v:.3f})" for n, v in sorted(team, key=lambda x: x[1], reverse=True))
            total = sum(v for _, v in team)
            print(f"{members} | Total = {total:.3f}")
        

    def generate_codes(gamemode, txtvar):
        txtvar += "\n[Challonge](YOUR_CHALLONGE_URL)\n"
        match gamemode:
            case "30":
                txtvar += "```e0g0z21111100130z000011110000000z11111111111100k051o000000f11100k012r02i0a46533a11002s0111111111000u0111002s01a111111111102a11111111111i01k903-11111--```\n"
            case "35":
                txtvar += "```e0g0z21111100130z000011110000000z11111111111100k051o000000f11100k012r02i0a46533a11002s0111111111000z0111002s01a111111111102a11111111111i01k903-11111--```\n"
            case "40":
                txtvar += "```e0g0z21111100130z000011110000000z11111111111100k051o000000f11100k012r02i0a46533a11002s011111111100140111002s01a111111111102a11111111111i01k803-11111--```\n"
            case "45":
                txtvar += "```e0g0z21111100130z000011110000000z11111111111100k051o000000f11100k012r02i0a46533a11002s011111111100190111002s01a111111111102a11111111111i01k903-11111--```\n"
            case "50":
                txtvar += "```e0g0z21111100130z000011110000000z11111111111100k051o000000f11100k012r02i0a46533a11002s0111111111001e0111002s01a111111111102a11111111111i01k903-11111--```\n"
        txtvar += """Distribution of guesses:
    ≥8.75: 5 guesses
    8-8.74: 4 guesses
    7-7.99: 3 guesses
    6-6.99: 2 guesses
    ≤5.99: 1 guess
    """
        return txtvar

    def get_guess(val):
        if val >= 8.75:
            return '5'
        elif val >= 8:
            return '4'
        elif val >= 7:
            return '3'
        elif val >= 6:
            return '2'
        else:
            return '1'

    txtvar = ""

    # header = f"{'#'*25} Challonge {'#'*25}\n"
    # print(header)
    # txtvar += header
    # txtvar += "\n"

    # for idx, sol in enumerate(found_solutions, 1):
    #     sol_msg = f"### Solution {idx} ###\n\n"
    #     print(sol_msg)
    #     txtvar += sol_msg
    #     team_map = [[] for _ in range(k)]
    #     for name, p in sol.items():
    #         team_map[p].append((name, p_values[name]))

    #     for i, team in enumerate(team_map):
    #         members = " ".join(f"{n} ({v:.3f})" for n, v in sorted(team, key=lambda x: x[1], reverse=True))
    #         total = sum(v for _, v in team)
    #         team_msg = f"{members}\n"
    #         print(team_msg)
    #         txtvar += team_msg
    #     txtvar += "\n"
    #     print()

    # txtvar += "\n"
    # print()

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
            members = " ".join(f"{n} ({v:.3f})" for n, v in sorted(team, key=lambda x: x[1], reverse=True))
            guess_str = "".join(get_guess(val) for _, val in sorted(team, key=lambda x: x[1], reverse=True))
            total = sum(v for _, v in team)
            team_msg = f"{members} | Total = {total:.3f} | Guesses = [{guess_str}]\n"
            print(team_msg)
            txtvar += team_msg
            avg += round(total, 4)
        txtvar += "\n"
        print()

    footer = f"Average: {round(avg / k, 4)}\n"
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

if __name__ == '__main__':
    main()