from curl_cffi import requests
from shutil import which
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from html2image import Html2Image
from PIL import Image
import numpy as np
import os

def internal_clean_data(idtable, statstable, isWatched):
    # Load alias table
    headers = idtable[0]
    data = idtable[1:]
    alias_df = pd.DataFrame(data, columns=headers)
    alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
    alias_to_id = dict(zip(alias_df["Player Name"], alias_df["Player ID"]))

    headers = statstable[0]
    data = statstable[1:]
    df = pd.DataFrame(data, columns=headers)
    df = df.replace(r"^\s*$", pd.NA, regex=True).dropna(how="all")
    df_names = set(df["Player name"].dropna().str.strip().str.lower())
    known_names = set(alias_to_id.keys())
    missing_players = df_names - known_names
    if missing_players:
        print(f"[WARN] Unknown players: {missing_players}. Ping a host so that they can be added.")

    df["Player ID"] = df["Player name"].dropna().str.strip().str.lower().map(alias_to_id)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    cols = ["Rank", "Guess rate", "Usefulness", "erigs", "7/8s", "avg/8", "Lives taken", "Lives saved", 
            "WIN", "LOSE", "TIE", "Total hit", "OP guess rate", "ED guess rate", "IN guess rate"]
    watched_cols = ["Rigs hit", "Rigs", "Rigs missed", "Solo rigs", 
                    "Missed solos", "Lives lost on rigs", "Offlist erigs", "avg/8 of your rigs"]
    
    df[cols] = df[cols].apply(pd.to_numeric, errors="coerce")
    
    if isWatched:
        df[watched_cols] = df[watched_cols].apply(pd.to_numeric, errors="coerce")
        cols.extend(watched_cols)
        df["Offlist hit"] = df["Total hit"] - df["Rigs hit"]
    
    df = df[df["WIN"] + df["LOSE"] + df["TIE"] >= 4]
    return df

def clean_data(idtable, statstable, maxFallbackWindow, activeTours, is_list):
    df = internal_clean_data(idtable, statstable, is_list)

    six_months_ago = datetime.now() - relativedelta(months=maxFallbackWindow)
    year_6m_ago = six_months_ago.year
    month_6m_ago = six_months_ago.month

    year_df = df[
        ((df["Timestamp"].dt.year > year_6m_ago)) |
        ((df["Timestamp"].dt.year == year_6m_ago) & (df["Timestamp"].dt.month >= month_6m_ago))
    ]

    year_df = year_df.sort_values(["Player ID", "Timestamp"])
    result_df = year_df.groupby("Player ID").tail(activeTours)
    GR = ["Guess rate", "Usefulness", "OP guess rate", "ED guess rate", "IN guess rate"]
    agg_dict = {
        col: "mean" if col in GR else "max"
        for col in result_df.columns
        if col != "Player ID"
    }
    result_df = result_df.groupby("Player ID").agg(agg_dict).reset_index()
    result_df["Player ID"] = result_df["Player ID"].astype(int)
    
    return result_df

def get_stat(df, player_id, column):
    try:
        filtered = df.loc[df["Player ID"] == player_id, column]
        if filtered.empty:
            return 0.0
    except KeyError:
        return 0.0
    
    return filtered.astype(float).iloc[0]

def download_challonge_page(url: str) -> str:
    try:
        response = requests.get(
            url,
            impersonate="chrome123",
            timeout=20
        )

        response.raise_for_status()

        return response.text

    except Exception as e:
        raise RuntimeError(f"Failed to download Challonge page: {e}")

def get_browser():
    WINDOWS_BROWSERS = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in WINDOWS_BROWSERS:
        if os.path.exists(path):
            return path
    return None
 
def trim_bottom_white(path_in):
    img = Image.open(path_in)
    arr = np.array(img)

    if arr.ndim == 3:
        row_sum = arr.sum(axis=2)
        row_total = row_sum.sum(axis=1)
        white_row_sum = 255 * arr.shape[2] * arr.shape[1]
    else:
        row_total = arr.sum(axis=1)
        white_row_sum = 255 * arr.shape[1]

    last_row = 0
    for i, val in enumerate(row_total):
        if val < white_row_sum:
            last_row = i

    cropped = img.crop((0, 0, img.width, last_row+1))
    cropped.save(path_in)

def autosize_image(df, min_width=800, max_width=4000, min_height=1000, max_height=6000):
    num_cols = len(df.columns)
    avg_col_chars = df.astype(str).apply(lambda col: col.map(len)).mean().max()
    width = int(100 + num_cols * (avg_col_chars * 8 + 40))
    width = max(min_width, min(width, max_width))

    row_height = 35      
    header_height = 90
    padding = 0

    height = header_height + len(df) * row_height + padding
    height = max(min_height, min(height, max_height))

    return width, height

def df_to_png(df, path, filename="table.png", reverse_cols=None, exclude_columns=None, separators=None):
    width, height = autosize_image(df)

    if reverse_cols is None:
        reverse_cols = []

    if separators is None:
        separators = []

    hti = Html2Image(
        size=(width, height),
        browser_executable=get_browser(),
        custom_flags=[
            "--headless=new",
            "--hide-scrollbars",
            "--disable-gpu",
            "--force-device-scale-factor=1",
        ],
        output_path=path
    )

    html = """
    <html>
    <head>
    <style>
        html, body { background-color: white; font-family: Arial; padding: 0; }
        table { border-collapse: collapse; width: 100%; font-size: 15px; }
        th { background-color: #eaeaea; padding: 1px; font-weight: bold; border-bottom: 2px solid #888; text-align: center; }
        td { padding: 1px 1px; text-align: center; border-bottom: 1px solid #ddd; white-space: nowrap; }
        tr:nth-child(even) { background-color: #E8E8E8; }
    </style>
    </head>
    <body>
    <table>
    <thead>
        <tr>
    """

    # Add headers
    for col in df.columns:
        html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"

    # Precompute numeric min/max per column
    numeric_cols = df.select_dtypes(include=["number"]).columns
    if exclude_columns:
        numeric_cols = [c for c in numeric_cols if c not in exclude_columns]

    top3 = {}
    bottom3 = {}

    for col in numeric_cols:
        sorted_vals = df[col].sort_values()

        bottom3[col] = set(sorted_vals.head(3).values)

        top3[col] = set(sorted_vals.tail(3).values)

    for _, row in df.iterrows():
        html += "<tr>"
        for col in df.columns:
            val = row[col]
            style = ""

            if col in numeric_cols:
                try:
                    val_num = float(val)

                    if col in reverse_cols:
                        if val_num in bottom3[col]:
                            style = "background-color:#57bb8a;"
                        elif val_num in top3[col]:
                            style = "background-color:#e67c73;"
                    else:
                        if val_num in top3[col]:
                            style = "background-color:#57bb8a;"
                        elif val_num in bottom3[col]:
                            style = "background-color:#e67c73;" # font-weight:bold;

                except:
                    pass
            
            if col in separators:
                style += "border-right:2px solid black;"

            html += f"<td style='{style}'>{val}</td>"

        html += "</tr>"

    html += "</tbody></table></body></html>"

    hti.screenshot(html_str=html, save_as=filename)

    savepath = os.path.join(path, filename)

    trim_bottom_white(savepath)

def render_songdb_summary_html(songDB) -> str:
    html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {
        font-family: Arial, sans-serif;
        background: white;
        padding: 16px;
        margin: 0;
    }

    .section {
        margin-bottom: 18px;
    }

    .section-title {
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 6px;
        border-bottom: 2px solid #444;
        padding-bottom: 2px;
    }

    .line {
        font-size: 14px;
        margin: 2px 0;
    }

    .examples {
        color: #555;
        font-size: 13px;
        margin-left: 12px;
    }
</style>
</head>
<body>
"""

    html += f"""
<div class="section">
    <div class="section-title">Overview</div>
    <div class="line">Total Songs: <b>{songDB.songsAmount}</b></div>
    <div class="line">Rebroadcasts: <b>{len(songDB.rbs)}</b></div>
</div>
"""

    html += """
<div class="section">
    <div class="section-title">Airing Year Summary</div>
"""
    for decade in sorted(songDB.decades.keys(), key=int):
        songs = songDB.decades[decade]
        songs.sort(key=lambda x: x.anime_id)
        examples = songs[:5]
        count = len(songs)
        pct = round(100 * count / songDB.songsAmount, 3)

        html += f"""
    <div class="line">
        <b>{decade}s</b>: {count} songs ({pct}%)
    </div>
    <div class="examples">
        Examples: {", ".join(ann.anime_name for ann in examples)}
    </div>
"""

    html += "</div>"

    html += """
<div class="section">
    <div class="section-title">Song Type Breakdown</div>
"""
    for songtype, songs in songDB.opedin.items():
        count = len(songs)
        pct = round(100 * count / songDB.songsAmount, 3)
        html += f"""
    <div class="line">
        <b>{songtype}</b>: {count} songs ({pct}%)
    </div>
"""

    html += "</div>"

    html += """
<div class="section">
    <div class="section-title">Format Type Breakdown</div>
"""
    for formattype, songs in songDB.formats.items():
        count = len(songs)
        pct = round(100 * count / songDB.songsAmount, 3)
        html += f"""
    <div class="line">
        <b>{formattype}</b>: {count} songs ({pct}%)
    </div>
"""

    html += "</div>"

    html += """
<div class="section">
    <div class="section-title">Difficulty Breakdown</div>
"""
    for difficulty in sorted(songDB.diffs.keys(), key=int):
        songs = songDB.diffs[difficulty]
        count = len(songs)
        pct = round(100 * count / songDB.songsAmount, 3)

        html += f"""
    <div class="line">
        <b>{difficulty}-{int(difficulty)+9}%</b>: {count} songs ({pct}%)
    </div>
"""

    html += "</div></body></html>"

    return html

def saveSongStats(songDB, path, filename):
    hti = Html2Image(
        size=(1200, 2000),
        browser_executable=get_browser(),
        custom_flags=["--hide-scrollbars"],
        output_path=path
    )

    html = render_songdb_summary_html(songDB)

    hti.screenshot(html_str=html, save_as=filename)

    savepath = os.path.join(path, filename)

    trim_bottom_white(savepath)