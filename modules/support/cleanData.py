from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

def internal_clean_data(idtable, statstable, isWatched):
    # Load alias table
    alias_df = pd.read_csv(idtable)
    alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
    alias_to_id = dict(zip(alias_df["Player Name"], alias_df["Player ID"]))

    df = pd.read_csv(statstable, dtype=str).fillna("")
    df = df.replace(r"^\s*$", pd.NA, regex=True).dropna(how="all")

    df_names = set(df["Player name"].dropna().str.strip().str.lower())
    known_names = set(alias_to_id.keys())
    missing_players = df_names - known_names
    if missing_players:
        print(f"[WARN] Unknown players: {missing_players}. Add to Master Sheet IDs to properly track them.")

    df["Player ID"] = df["Player name"].dropna().str.strip().str.lower().map(alias_to_id)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    cols = ["Rank", "Guess rate", "Usefulness", "erigs", "7/8s", "avg/8", "Lives taken", "Lives saved", 
            "WIN", "LOSE", "TIE", "Total hit"]
    watched_cols = ["Rigs hit", "Rigs", "Rigs missed", "Solo rigs", 
                    "Missed solos", "Lives lost on rigs", "Offlist erigs", "avg/8 of your rigs"]
    
    df[cols] = df[cols].apply(pd.to_numeric, errors="coerce")
    
    if isWatched:
        df[watched_cols] = df[watched_cols].apply(pd.to_numeric, errors="coerce")
        cols.extend(watched_cols)
        df["Offlist hit"] = df["Total hit"] - df["Rigs hit"]
    
    df = df[df["WIN"] + df["LOSE"] + df["TIE"] >= 4]

    return df

def clean_data(idtable, statstable, cleanedStatsYear, maxFallbackWindow, activeTours, tourType):
    df = internal_clean_data(idtable, statstable, tourType.startswith("watched"))

    six_months_ago = datetime.now() - relativedelta(months=maxFallbackWindow)
    year_6m_ago = six_months_ago.year
    month_6m_ago = six_months_ago.month

    year_df = df[
        ((df["Timestamp"].dt.year > year_6m_ago)) |
        ((df["Timestamp"].dt.year == year_6m_ago) & (df["Timestamp"].dt.month >= month_6m_ago))
    ]

    year_df = year_df.sort_values(["Player ID", "Timestamp"])
    year_df.to_csv(cleanedStatsYear, index=False, encoding="utf-8")
    result_df = year_df.groupby("Player ID").tail(activeTours)
    WLT = ["WIN", "LOSE", "TIE"]
    agg_dict = {
        col: "sum" if col in WLT else "max"
        for col in df.columns
        if col != "Player ID"
    }
    df = df.groupby("Player ID").agg(agg_dict).reset_index()
    
    return result_df, df

def mini_clean(idtable, statstable, tourType):
    if tourType.startswith("watched"):
        isWatched=True
    else:
        isWatched=False
    return internal_clean_data(idtable, statstable, isWatched)