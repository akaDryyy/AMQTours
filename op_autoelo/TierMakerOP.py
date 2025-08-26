import pandas as pd
import numpy as np
import os
import json
import gspread
import csv
import shutil
import argparse
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta

idtable = os.path.abspath("id_stats.csv")
statstable = os.path.abspath("op_stats.csv")
statstable_tminus1 = os.path.abspath("op_stats_tminus1.csv")
GR_weight = 0.35
UF_weight = 0.65
past_tours = 10
# Year from which we start considering potentially usable data points
chosen_year = 2025
# Window of months to draw data points from
month_window = 2
# Do not go further than 6 months to gather data
max_fallback_window = 6
cleanedstats = os.path.abspath("op_clean.csv")
cleanedstats_chosen_year = os.path.abspath("op_clean_year.csv")
jsonstats = os.path.abspath("op_elos.json")
txtstats = os.path.abspath("op_TL.txt")
changelog = os.path.abspath("changelog.txt")
mvp = os.path.abspath("mvps.txt")

def clean_data(idtable, statstable):
    # Load alias table
    alias_df = pd.read_csv(idtable)
    alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
    alias_to_id = dict(zip(alias_df["Player Name"], alias_df["Player ID"]))

    # Read raw CSV as a list of rows (not yet parsed by header)
    raw_lines = pd.read_csv(statstable, header=None, dtype=str).fillna("").values.tolist()
    
    # Prepare
    parsed_rows = []
    current_date = None
    columns = ["player name", "guess rate", "usefulness", "avg diff", "erigs", "avg /8 correct", "OP guess rate", "ED guess rate", "IN guess rate"]

    # Parse manually
    for row in raw_lines:
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
    # Save 2025 stats for future
    year_df.to_csv(cleanedstats_chosen_year, index=False, encoding="utf-8")

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
        trimmed_gr = group["guess rate"].sort_values().iloc[1:-1]
        trimmed_uf = group["usefulness"].sort_values().iloc[1:-1]
        return pd.Series({
            "avg_gr": trimmed_gr.mean(),
            "avg_uf": trimmed_uf.mean(),
            "count": n
        })

def compute_rank_scores(df, gr_max=100, uf_max=30, alpha=3.75, midpoint=0.33, max_score=25):
    """
    Compute a smoothed rank score for players based on guess rate and usefulness.

    Parameters:
        df (pd.DataFrame): DataFrame with 'guess rate' and 'usefulness' columns.
        gr_max (float): Max value to normalize guess rate (default: 100%).
        uf_max (float): Max value to normalize usefulness (default: 30).
        alpha (float): Controls steepness of sigmoid (higher = steeper).
        midpoint (float): Sigmoid center (default: 0.5 = average players).
        max_score (float): Maximum output score (default: 25).

    Returns:
        pd.DataFrame: DataFrame with avg_gr, avg_uf, norm_gr, norm_Uf, raw_score and elo columns.
    """

    # Normalize guess rate and usefulness
    df["norm_gr"] = df["avg_gr"] / gr_max
    df["norm_uf"] = df["avg_uf"] / uf_max

    # Clip values to avoid weird outliers
    df["norm_gr"] = df["norm_gr"].clip(0, 1)
    df["norm_uf"] = df["norm_uf"].clip(0, 1)

    # Combine into a single raw score (equal weighting)
    df["raw_score"] = GR_weight * df["norm_gr"] + UF_weight * df["norm_uf"]

    # Apply sigmoid transformation
    df["elo"] = max_score / (1 + np.exp(-alpha * (df["raw_score"] - midpoint)))
    return df

# Find MVPs
def mini_clean(idtable, statstable):
    # Load alias table
    alias_df = pd.read_csv(idtable)
    alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
    alias_to_id = dict(zip(alias_df["Player Name"], alias_df["Player ID"]))

    # Read raw CSV as a list of rows (not yet parsed by header)
    raw_lines = pd.read_csv(statstable, header=None, dtype=str).fillna("").values.tolist()
    
    # Prepare
    parsed_rows = []
    current_date = None
    columns = ["player name", "guess rate", "usefulness", "avg diff", "erigs", "avg /8 correct", "OP guess rate", "ED guess rate", "IN guess rate", "rigs", "rigs hit", "correct count", "song count", "Rigs missed", "Offlist GR"]

    # Parse manually
    for row in raw_lines:
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

    return df

def main():
    parser = argparse.ArgumentParser(description="AMQ Tours")
    parser.add_argument('--keep', '-k', action='store_true',
                        help="Keep the current CSVs for stats, used for when doing changelogs one at the time after not running the script for multiple tours",
                        required=False)
    args = parser.parse_args()

    if not args.keep:
        DIRECTORY = os.path.dirname(__file__)
        sheet_name = "ngm stats"
        tab_id_stats = 1315204448
        tab_id_ids = 220350629

        gc = gspread.oauth(
            credentials_filename=os.path.join(DIRECTORY, 'credentials', 'credentials.json'),
            authorized_user_filename=os.path.join(DIRECTORY, 'credentials', 'authorized_user.json')
        )
        sheet = gc.open(sheet_name)
        wks = sheet.get_worksheet_by_id(tab_id_stats)
        wks_ids = sheet.get_worksheet_by_id(tab_id_ids)

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
    player_stats = clean_stats.groupby("Player ID").apply(trim, include_groups=False).reset_index()
    final_ranks = compute_rank_scores(player_stats, uf_max=(clean_stats["usefulness"].max()))
    ids = pd.read_csv(idtable)
    ids = ids.drop_duplicates(subset='Player ID', keep='first')
    final_ranks = final_ranks.merge(ids[['Player ID', 'Player Name']], on='Player ID', how='left')
    new_order = ['Player ID', 'Player Name', 'elo', 'avg_gr', 'avg_uf', 'count', 'norm_gr', 'norm_uf', 'raw_score']
    final_ranks = final_ranks[new_order]
    final_ranks = final_ranks.sort_values(by='elo', ascending=False)
    print(final_ranks)
    rank_dict = dict(zip(final_ranks['Player Name'], final_ranks['elo'].round(3)))

    with open(jsonstats, 'r') as f:
        old_elos = json.load(f)
        old_old_elos = old_elos

    with open(jsonstats, 'w') as f:
        json.dump(rank_dict, f, indent=4)

    score_to_players = defaultdict(list)
    for player, score in rank_dict.items():
        score_to_players[round(score, 3)].append(player)

    with open(txtstats, "w") as f:
        for score in sorted(score_to_players.keys(), reverse=True):
            players = ", ".join(score_to_players[score])
            f.write(f"{score}: {players}\n")

    elo_diff = {
        player: {
            "initial rank": round(float(old_elos[player]), 3),
            "new rank": round(float(rank_dict[player]), 3),
            "rating_change": round(float(rank_dict[player]) - float(old_elos[player]), 3)
        }
        for player in old_elos
        if player in rank_dict and float(rank_dict[player]) - float(old_elos[player]) != 0
    }

    elo_diff_str = "\n".join(
        f"{player}, old rank: {data['initial rank']}, new rank: {data['new rank']}, diff: {data['rating_change']}"
        for player, data in sorted(
            elo_diff.items(), key=lambda x: -x[1]["rating_change"]
        )
    )

    with open(changelog, "w") as f:
        f.write(elo_diff_str)
    clean_stats_tnow = mini_clean(idtable, statstable)
    clean_stats_tminus1 = mini_clean(idtable, statstable_tminus1)
    last_tour = clean_stats_tnow.merge(clean_stats_tminus1, how='outer', indicator=True).query('_merge == "left_only"')
    if not last_tour.empty:
        player_stats_tour = last_tour.groupby("Player ID").apply(trim, include_groups=False).reset_index()
        last_tour_ranks = compute_rank_scores(player_stats_tour, uf_max=(clean_stats["usefulness"].max()))
        last_tour_ranks = last_tour_ranks.merge(ids[['Player ID', 'Player Name']], on='Player ID', how='left')
        last_tour_ranks = last_tour_ranks[new_order]
        last_tour_ranks = last_tour_ranks.sort_values(by='elo', ascending=False)
        last_tour_dict = dict(zip(last_tour_ranks['Player Name'], last_tour_ranks['elo'].round(3)))

        diff = {}
        for player, new_elo in last_tour_dict.items():
            old_elo = old_old_elos.get(player)
            if old_elo is None:
                old_elo = new_elo
            diff[player] = {
                'old': old_elo,
                'new': new_elo,
                'diff': round(new_elo - old_elo, 3)
            }

        sorted_diff = sorted(diff.items(), key=lambda item: item[1]['diff'], reverse=True)
        top_3 = sorted_diff[:3]

        with open(mvp, "w", encoding="utf-8") as f:
            f.write("# Full PV List:\n")
            for player, data in sorted_diff:
                f.write(f"{player} played like a {data['new']}. (Current rank {data['old']}, Δ{data['diff']})\n")
            f.write("\n# MVPS:\n")
            first, fpdata = top_3[0]
            second, spdata = top_3[1]
            third, tpdata = top_3[2]
            f.write(f":first_place: {first}. Played like a {fpdata['new']} rank (Current Rank: {fpdata['old']}, Δ{fpdata['diff']})\n")
            f.write(f":second_place: {second}. Played like a {spdata['new']} rank (Current Rank: {spdata['old']}, Δ{spdata['diff']})\n")
            f.write(f":third_place: {third}. Played like a {tpdata['new']} rank (Current Rank: {tpdata['old']}, Δ{tpdata['diff']})\n")

    # Latest tour will be the new most recent one afterwards
    shutil.copyfile(statstable, statstable_tminus1)

if __name__ == '__main__':
    main()