from pulp import *
import pandas as pd
import argparse, json, os, gspread, csv
from datetime import datetime
from dateutil.relativedelta import relativedelta
from gooey import Gooey

@Gooey(show_success_modal=False)
def main():
    blacklist_path = os.path.abspath(os.path.join(os.pardir, "blacklist.json"))
    whitelist_path = os.path.abspath(os.path.join(os.pardir, "whitelist.json"))
    aliases_path = os.path.abspath(os.path.join(os.pardir, "aliases.txt"))
    ranks_path = os.path.abspath("ranks.txt")
    elo_path = os.path.abspath("elos.json")
    players_path = os.path.abspath("players.txt")
    codes_path = os.path.abspath("codes.txt")
    think_time = 25000

    idtable = os.path.abspath("id_stats.csv")
    statstable = os.path.abspath("usual_stats.csv")
    cleanedstats = os.path.abspath("usual_clean.csv")
    cleanedavgs = os.path.abspath("usual_avgs.csv")
    max_fallback_window = 6
    month_window = 2
    past_tours = 10
    active_tours = 10

    #Guess Count Thresholds
    one_guess_percent = 8
    two_guess_percent = 19
    three_guess_percent = 28

    parser = argparse.ArgumentParser(description="AMQ Tours")
    parser.add_argument('--size', '-s',
                        help="Define the size of each team",
                        default=4,
                        required=False)
    parser.add_argument('--mode', '-m', 
                        choices=['usual', 'quag'],
                        default='usual',
                        required=False,
                        help="Define the tour mode, currently usual or quag")
    args = parser.parse_args()
    if args.size:
        team_size = int(args.size)
    if args.mode:
        gamemode = args.mode

    # Obtain last n tours for the guess thresholds
    def is_date(value):
            try:
                datetime.strptime(value, "%Y-%m-%d")
                return True
            except ValueError:
                return False

    def clean_data(idtable, statstable):
        # Load alias table
        alias_df = pd.read_csv(idtable)
        alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
        alias_to_id = dict(zip(alias_df["Player Name"], alias_df["Player ID"]))

        # Read raw CSV as a list of rows (not yet parsed by header)
        raw_lines = pd.read_csv(statstable, header=None, dtype=str).fillna("").values.tolist()
        raw_lines = [row for row in raw_lines if row[0].strip() != ""]
        processed_lines = []
        for row in raw_lines:
            if not is_date(row[0].strip()):
                row = row[1:]
            processed_lines.append(row)
        # Prepare
        parsed_rows = []
        current_date = None
        columns = ["Player name", "guess rate", "usefulness", "avg diff", "erigs", "avg /8 correct", "OP guess rate", "ED guess rate", "IN guess rate"]

        # Parse manually
        for row in processed_lines:
            # Skip completely empty rows
            if all(cell.strip() == "" for cell in row):
                continue

            first_cell = row[0].strip()
            
            # Check if the row is a tournament date
            if first_cell and all(cell.strip() == "" for cell in row[1:]):
                current_date = first_cell
                continue

            # Skip rows without tournament date assigned yet
            if current_date is None:
                continue

            # Normalize name
            player_name = first_cell.strip().lower()
            player_id = alias_to_id.get(player_name)

            if not player_id:
                print(f"[WARN] Unknown player alias: {player_name}")
                continue

            # Pad short rows with empty strings
            while len(row) < len(columns):
                row.append("")

            parsed_rows.append([current_date, player_id] + row[0:len(columns)])

        # Final DataFrame
        final_columns = ["Tournament Date", "Player ID"] + columns[0:]
        df = pd.DataFrame(parsed_rows, columns=final_columns)
        df["guess rate"] = pd.to_numeric(df["guess rate"], errors='coerce')
        df["usefulness"] = pd.to_numeric(df["usefulness"], errors='coerce')
        df = df.dropna(subset=["usefulness", "guess rate"])
        df = df[df["usefulness"].astype(str).str.strip() != ""]

        # Ensure the Tournament Date is a datetime object
        df["Tournament Date"] = pd.to_datetime(df["Tournament Date"], errors="coerce")
        # Drop invalid dates
        df = df.dropna(subset=["Tournament Date"])

        six_months_ago = datetime.now() - relativedelta(months=max_fallback_window)
        year_6m_ago = six_months_ago.year
        month_6m_ago = six_months_ago.month

        year_df = df[
            ((df["Tournament Date"].dt.year > year_6m_ago)) |
            ((df["Tournament Date"].dt.year == year_6m_ago) & (df["Tournament Date"].dt.month >= month_6m_ago))
        ]

        year_df = year_df.sort_values(["Player ID", "Tournament Date"])

        # Sort by Player ID and Tournament Date
        df = df.sort_values(["Player ID", "Tournament Date"])

        two_months_ago = datetime.now() - relativedelta(months=month_window)
        year_2m_ago = two_months_ago.year
        month_2m_ago = two_months_ago.month

        timely_df = df[
            ((df["Tournament Date"].dt.year > year_2m_ago)) |
            ((df["Tournament Date"].dt.year == year_2m_ago) & (df["Tournament Date"].dt.month >= month_2m_ago))
        ]
        
        timely_counts = timely_df.groupby("Player ID").size()

        enough_ids = timely_counts[timely_counts >= past_tours].index
        not_enough_ids = timely_counts[timely_counts < past_tours].index

        result_df = timely_df[timely_df["Player ID"].isin(enough_ids)]
        result_df = result_df.groupby("Player ID").tail(active_tours)
        fallback_df = (
            year_df[year_df["Player ID"].isin(not_enough_ids)]
            .groupby("Player ID", group_keys=False)
            .tail(past_tours)
        )

        final_df = pd.concat([result_df, fallback_df], ignore_index=True)

        return final_df

    def trim(group):
        n = len(group)
        if n < 10:
            return pd.Series({
                "avg_gr": group["guess rate"].mean(),
                "avg_uf": group["usefulness"].mean(),
                "count": n
            })
        else:
            trimmed_gr = group["guess rate"].sort_values()#.iloc[1:-1]
            trimmed_uf = group["usefulness"].sort_values()#.iloc[1:-1]
            return pd.Series({
                "avg_gr": trimmed_gr.mean(),
                "avg_uf": trimmed_uf.mean(),
                "count": n
            })

    DIRECTORY = os.path.dirname(os.path.dirname(__file__))
    sheet_name = "ngm stats"
    tab_id_stats = 0
    tab_id_ids = 220350629
    tab_elo_storage = 716533894
    gc = gspread.oauth(
        credentials_filename=os.path.join(DIRECTORY, 'credentials', 'credentials.json'),
        authorized_user_filename=os.path.join(DIRECTORY, 'credentials', 'authorized_user.json')
    )
    sheet = gc.open(sheet_name)
    wks = sheet.get_worksheet_by_id(tab_id_stats)
    wks_ids = sheet.get_worksheet_by_id(tab_id_ids)
    wks_storage = sheet.get_worksheet_by_id(tab_elo_storage)

    rows = wks.get_all_values()
    with open(statstable, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    rows_ids = wks_ids.get_all_values()
    with open(idtable, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows_ids)

    clean_stats = clean_data(idtable, statstable)
    clean_stats = clean_stats.sort_values(["Player ID", "Tournament Date"])
    clean_stats.to_csv(cleanedstats, index=False, encoding="utf-8")
    player_stats = clean_stats.groupby(["Player ID", "Player name"]).apply(trim, include_groups=False).reset_index()
    player_stats['Player name'] = player_stats['Player name'].str.lower()
    player_stats.to_csv(cleanedavgs, index=False, encoding="utf-8")

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
    ≥28% = 4 guesses
    20% - 28% = 3 guesses
    12% - 20% = 2 guesses
    <12% = 1 guess
    """

        return txtvar

    def get_guess(name, player_stats):
        try:
            alias_df = pd.read_csv(idtable)
            alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
            player_id = alias_df.loc[alias_df["Player Name"] == name, 'Player ID'].iloc[0]
            avg_gr = player_stats.loc[player_stats["Player ID"] == player_id, 'avg_gr'].iloc[0]
        except IndexError:
            avg_gr = float(input(f"{name} not found. Give initial gr% (Example: 75 = 75%): "))
        if avg_gr >= three_guess_percent:
            return '4'
        elif avg_gr >= two_guess_percent:
            return '3'
        elif avg_gr >= one_guess_percent:
            return '2'
        else:
            return '1'

    txtvar = ""

    # header = f"{'#'*25} Challonge {'#'*25}\n"
    # print(header)
    # txtvar += header
    # txtvar += "\n"
    # for idx, (group, total) in enumerate(sorted_parts, 1):
    #     members = " ".join(f"{name} ({val:.3f})" for name, val in sorted(group, key=lambda x: x[1], reverse=True))
    #     line = f"{members}\n"
    #     print(line, end="")
    #     txtvar += line

    # txtvar += "\n"
    # print()

    header = f"{'#'*25} Discord {'#'*25}\n"
    print(header)
    txtvar += header
    txtvar += "\n"
    avg = 0
    for idx, (group, total) in enumerate(sorted_parts, 1):
        members = " ".join(f"{name} ({val:.3f})" for name, val in sorted(group, key=lambda x: x[1], reverse=True))
        guess_str = "".join(get_guess(name, player_stats) for name, _ in sorted(group, key=lambda x: x[1], reverse=True))
        avg += round(total, 4)
        line = f"{members} | Total = {round(total, 3)} | Guesses = [{guess_str}]\n"
        print(line, end="")
        txtvar += line
    footer = f"\nAverage: {round(avg / k, 4)}\n"
    print(footer)
    txtvar += footer
    print("#"*50)
    print("Open `codes.txt` for all the information")
    print("#"*50)

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