from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

def is_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def internal_clean_data(idtable, statstable, hasExtraColumn):
    # Load alias table
    alias_df = pd.read_csv(idtable)
    alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
    alias_to_id = dict(zip(alias_df["Player Name"], alias_df["Player ID"]))

    raw_lines = pd.read_csv(statstable, header=None, dtype=str).fillna("").values.tolist()
    if hasExtraColumn:
        raw_lines = [row for row in raw_lines if row[0].strip() != ""]
        processed_lines = []
        for row in raw_lines:
            if not is_date(row[0].strip()):
                row = row[1:]
            processed_lines.append(row)
    else:
        processed_lines = raw_lines
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

    return df

def clean_data(idtable, statstable, cleanedStatsYear, monthWindow, maxFallbackWindow, pastTours, activeTours, hasExtraColumn):
    df = internal_clean_data(idtable, statstable, hasExtraColumn)

    six_months_ago = datetime.now() - relativedelta(months=maxFallbackWindow)
    year_6m_ago = six_months_ago.year
    month_6m_ago = six_months_ago.month

    year_df = df[
        ((df["Tournament Date"].dt.year > year_6m_ago)) |
        ((df["Tournament Date"].dt.year == year_6m_ago) & (df["Tournament Date"].dt.month >= month_6m_ago))
    ]

    year_df = year_df.sort_values(["Player ID", "Tournament Date"])
    # Save 2025 stats for future
    year_df.to_csv(cleanedStatsYear, index=False, encoding="utf-8")
    # Sort by Player ID and Tournament Date
    df = df.sort_values(["Player ID", "Tournament Date"])

    two_months_ago = datetime.now() - relativedelta(months=monthWindow)
    year_2m_ago = two_months_ago.year
    month_2m_ago = two_months_ago.month

    timely_df = df[
        ((df["Tournament Date"].dt.year > year_2m_ago)) |
        ((df["Tournament Date"].dt.year == year_2m_ago) & (df["Tournament Date"].dt.month >= month_2m_ago))
    ]
    
    timely_counts = timely_df.groupby("Player ID").size()

    enough_ids = timely_counts[timely_counts >= pastTours].index
    not_enough_ids = timely_counts[timely_counts < pastTours].index

    result_df = timely_df[timely_df["Player ID"].isin(enough_ids)]
    result_df = result_df.groupby("Player ID").tail(activeTours)
    fallback_df = (
        year_df[year_df["Player ID"].isin(not_enough_ids)]
        .groupby("Player ID", group_keys=False)
        .tail(pastTours)
    )

    final_df = pd.concat([result_df, fallback_df], ignore_index=True)

    return final_df

def mini_clean(idtable, statstable, hasExtraColumn):
    return internal_clean_data(idtable, statstable, hasExtraColumn=hasExtraColumn)