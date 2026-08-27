import os
import json
import re
from collections import Counter, defaultdict
from html import escape
from shutil import which

import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import messagebox, ttk

from JsonProcessing import *
from SheetTransmission import *
from TourClasses import *
from TourFunctions import *

try:
    from html2image import Html2Image
    from PIL import Image
except ImportError:
    Html2Image = None
    Image = None

EXCLUDED_TAGS = {
    "Female Protagonist", "Male Protagonist", "Primarily Female Cast", 
    "Primarily Male Cast", "School", "Heterosexual", "Primarily Teen Cast",
    "Ensemble Cast"
}


def extract_year(vintage_str):
    if not vintage_str: return None
    years = re.findall(r'\d{4}', str(vintage_str))
    if not years: return None
    year_val = float(years[0])
    season_map = {"winter": 0.00, "spring": 0.25, "summer": 0.50, "fall": 0.75}
    v_lower = str(vintage_str).lower()
    decimal = 0.0
    for season, val in season_map.items():
        if season in v_lower:
            decimal = val
            break
    return year_val + decimal


def get_browser():
    browser_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        which("chrome"),
        which("msedge"),
    ]
    return next((path for path in browser_paths if path and os.path.exists(path)), None)


def trim_bottom_white(path_in):
    if Image is None:
        return
    img = Image.open(path_in).convert("RGBA")
    arr = np.array(img)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    non_white = np.any(rgb < 250, axis=2) & (alpha > 0)
    rows = np.where(non_white.any(axis=1))[0]
    if len(rows):
        img.crop((0, 0, img.width, rows[-1] + 8)).save(path_in)


def pct_text(value):
    return "N/A" if value is None or pd.isna(value) else f"{value:.2%}"


def pct_text_with_fraction(value, fraction_string):
    return f"({pct_text(value)}, {fraction_string})"


def number_text(value, _ignore=None):
    decimals = 2
    text = "N/A" if value is None or pd.isna(value) else f"{value:.{decimals}f}"
    return f"({text})"


def medal_html(index):
    return ["&#x1F947;", "&#x1F948;", "&#x1F949;"][index]


def ranked_list_html(title, rows, formatter):
    lines = []
    if len(rows[0]) == 2:
        rows = [x + (None,) for x in rows]
    for i, (name, value, details) in enumerate(rows[:3]):
        lines.append(f"<div>{medal_html(i)} {escape(str(name))} {formatter(value, details)}</div>")
    while len(lines) < 3:
        lines.append("<div>&nbsp;</div>")
    return f"""
        <div class="podium">
            <div class="section-title">{escape(title)}</div>
            {''.join(lines)}
        </div>
    """


def line_plot_html(title, value, min_value, max_value, left_label, right_label, value_label, points=None, extra_marker=None):
    if value is None or max_value == min_value:
        pct = 0
    else:
        pct = max(0, min(100, ((value - min_value) / (max_value - min_value)) * 100))
    marker_html = ""
    stat_items = [f"<span><b>Tour Average</b><br>{value_label}</span>"]
    if extra_marker and extra_marker.get("value") is not None and max_value != min_value:
        marker_pct = max(0, min(100, ((extra_marker["value"] - min_value) / (max_value - min_value)) * 100))
        marker_html = f"""
            <div class="scale-marker server" style="left:{marker_pct}%"></div>
        """
        stat_items.append(f'<span class="server-stat"><b>Server Average</b><br>{pct_text(extra_marker["value"])}</span>')
    dots = []
    for name, point_value in points or []:
        if point_value is None or max_value == min_value:
            continue
        point_pct = max(1.5, min(98.5, ((point_value - min_value) / (max_value - min_value)) * 100))
        dots.append(f'<div class="plot-dot" style="left:{point_pct}%" title="{escape(str(name))}"></div>')
    return f"""
        <div class="scale-block">
            <div class="metric-line"><b>{escape(title)}</b></div>
            <div class="scale line-scale">
                {''.join(dots)}
                <div class="scale-marker tour" style="left:{pct}%"></div>
                {marker_html}
            </div>
            <div class="scale-labels">
                <span>{escape(left_label)}</span>
                <span>{escape(right_label)}</span>
            </div>
            <div class="avg-stats">{"".join(stat_items)}</div>
        </div>
    """


def hero_chart_html(title, rows, average_value, server_average=None):
    rows = rows or []
    max_value = max([value for _, _, value in rows] + [average_value or 0, server_average or 0, 1])
    avg_pct = max(0, min(100, ((average_value or 0) / max_value) * 100))
    server_pct = max(0, min(100, ((server_average or 0) / max_value) * 100))
    server_guide = ""
    server_axis = ""
    if server_average is not None:
        server_guide = f'<div class="guide server-guide" style="left:{server_pct}%"></div>'
        server_axis = f'<span class="axis-label server-axis"><b>Server Average</b><br>{number_text(server_average)}</span>'
    html_rows = []
    for tier, name, value in rows:
        width = max(2, min(100, (value / max_value) * 100)) if max_value else 0
        html_rows.append(f"""
            <div class="hero-row">
                <div class="tier">{escape(str(tier))}</div>
                <div class="hero-name">{escape(str(name))}</div>
                <div class="hero-bar-wrap"><div class="hero-bar" style="width:{width}%"></div></div>
                <div class="hero-value">{value}</div>
            </div>
        """)
    if not html_rows:
        html_rows.append('<div class="empty-note">No team data</div>')
    return f"""
        <div class="hero-chart">
            <div class="chart-title">{escape(title)}</div>
            <div class="hero-plot">
                <div class="hero-guides">
                    <div class="guide tour-guide" style="left:{avg_pct}%"></div>
                    {server_guide}
                </div>
                {''.join(html_rows)}
            </div>
            <div class="chart-axis">
                <span class="axis-label tour-axis"><b>Tour Average</b><br>{number_text(average_value)}</span>
                {server_axis}
            </div>
        </div>
    """


def save_extra_stats_image(data, output_dir, filename):
    if Html2Image is None:
        raise RuntimeError("html2image is not installed. Install it to export the Extra Stats PNG.")

    chanting_html = ""
    if data["has_chanting"]:
        chanting_html = f"""
            <div class="chanting">
                <div class="boxed-title">CHANTING STATS</div>
                <div class="two-col-row"><span>Total chanting songs played</span><span>{data['chanting_total']}</span></div>
                <div class="two-col-row"><span>Average chanting guess rate</span><span>{pct_text(data['chanting_gr'])}</span></div>
                <div class="chant-lists">
                    {ranked_list_html("Top 3 Chanting Lovers", data["chanting_lovers"], pct_text_with_fraction)}
                    {ranked_list_html("Top 3 Chanting Haters", data["chanting_haters"], pct_text_with_fraction)}
                </div>
            </div>
        """

    answer_time_html = ""
    if data.get("answer_time_tryhards") or data.get("answer_time_ballscratchers"):
        answer_time_html = f"""
            <div class="answer-time">
                <div class="boxed-title">ANSWER TIME STATS</div>
                <div class="chant-lists">
                    {ranked_list_html("Top 3 Tryhards", data.get("answer_time_tryhards", []), number_text)}
                    {ranked_list_html("Top 3 Ballscratchers", data.get("answer_time_ballscratchers", []), number_text)}
                </div>
            </div>
        """

    server_marker = None
    if data["server_average_gr"] is not None:
        server_marker = {
            "value": data["server_average_gr"],
            "label": f"Server Average\n{pct_text(data['server_average_gr'])}",
        }

    right_only = data.get("right_only", False)
    dashboard_class = "dashboard right-only" if right_only else "dashboard"
    left_html = ""
    if not right_only:
        left_html = f"""
        <div class="left">
            {line_plot_html("Tour Average GR", data["tour_average_gr"], 0, 1, "0%", "100%", pct_text(data["tour_average_gr"]), data["gr_points"], server_marker)}
            <div class="boxed-title">WATCHED STATS</div>
            {line_plot_html("", data["watched_average"], 0, 8, "0.0", "8.0", number_text(data["watched_average"]), data["difficulty_points"])}
            <div class="podium-grid">
                {ranked_list_html("Top 3 Easiest Lists", data["easiest_lists"], number_text)}
                {ranked_list_html("Top 3 Hardest Lists", data["hardest_lists"], number_text)}
            </div>
            {line_plot_html("", data["vintage_average"], data["vintage_min"], data["vintage_max"], number_text(data["vintage_min"]), number_text(data["vintage_max"]), number_text(data["vintage_average"]), data["vintage_points"])}
            <div class="podium-grid">
                {ranked_list_html("Top 3 Zoomer Lists", data["zoomer_lists"], number_text)}
                {ranked_list_html("Top 3 Boomer Lists", data["boomer_lists"], number_text)}
            </div>
            <div class="summary-table">
                <div class="two-col-row"><span>Most 2/8s</span><span>{escape(data["most_two_eighths"])}</span></div>
                <div class="two-col-row"><span>Highest GR with no erig</span><span>{escape(data["best_no_erig"])}</span></div>
                <div class="two-col-row"><span>&nbsp;</span><span>&nbsp;</span></div>
                <div class="two-col-row"><span>Top erig misser</span><span>{escape(data["top_erig_misser"])}</span></div>
                <div class="two-col-row"><span>Top reverse erig collector</span><span>{escape(data["top_reverse_erig"])}</span></div>
            </div>
        </div>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        background: white;
        color: black;
        font-family: Helvetica, Arial, sans-serif;
        font-size: 18px;
    }}
    .dashboard {{
        width: 1220px;
        min-height: 980px;
        padding: 0;
        display: grid;
        grid-template-columns: 530px 620px;
        gap: 36px;
    }}
    .dashboard.right-only {{
        width: 620px;
        grid-template-columns: 620px;
        gap: 0;
    }}
    .left, .right {{ position: relative; }}
    .metric-line {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        padding: 8px 18px 0 4px;
    }}
    .scale-block {{ margin-bottom: 18px; position: relative; }}
    .scale {{
        height: 44px;
        margin: 0 16px 0 6px;
        position: relative;
        overflow: visible;
    }}
    .line-scale::before {{
        content: "";
        position: absolute;
        left: 0;
        right: 0;
        top: 50%;
        border-top: 5px solid black;
        transform: translateY(-50%);
    }}
    .plot-dot {{
        position: absolute;
        top: 50%;
        width: 3px;
        height: 20px;
        transform: translate(-50%, -50%);
        border-radius: 0;
        background: #ed1c24;
        border: 0;
        box-shadow: none;
    }}
    .scale-marker {{
        position: absolute;
        top: 3px;
        bottom: 3px;
        width: 2px;
        background: black;
    }}
    .scale-marker.server {{
        width: 2px;
        background: #2563eb;
    }}
    .marker-label {{
        position: absolute;
        top: 47px;
        transform: translateX(-50%);
        text-align: center;
        white-space: pre;
        font-size: 16px;
        font-weight: bold;
    }}
    .server-label {{ color: #1d4ed8; }}
    .scale-labels {{
        position: relative;
        height: 22px;
        display: flex;
        justify-content: space-between;
        padding: 0 0 0 8px;
        font-size: 16px;
        font-weight: bold;
        margin-top: -2px;
    }}
    .avg-stats {{
        display: flex;
        gap: 28px;
        align-items: flex-start;
        margin: 0 0 10px 8px;
        font-size: 16px;
        font-weight: normal;
        line-height: 1.2;
    }}
    .avg-stats span {{
        text-align: left;
    }}
    .avg-stats b {{
        font-weight: bold;
    }}
    .server-stat {{ color: #1d4ed8; }}
    .boxed-title {{
        border: 2px solid black;
        height: 31px;
        line-height: 28px;
        padding-left: 5px;
        font-size: 23px;
        font-weight: bold;
        margin: 8px 0 10px;
    }}
    .podium-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        border-left: 1px solid #ccc;
        border-top: 1px solid #ccc;
    }}
    .podium {{
        min-height: 116px;
        border-right: 1px solid #ccc;
        border-bottom: 1px solid #ccc;
        padding: 0 4px 5px;
    }}
    .section-title {{
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 4px;
    }}
    .podium div:not(.section-title) {{
        line-height: 25px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-family: Helvetica, Arial, sans-serif;
    }}
    .summary-table {{
        border-left: 1px solid #ccc;
        border-top: 1px solid #ccc;
        margin-top: 12px;
        font-size: 20px;
    }}
    .summary-table .two-col-row {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        border-bottom: 1px solid #ccc;
    }}
    .summary-table span {{
        padding: 4px;
        border-right: 1px solid #ccc;
    }}
    .summary-table span:first-child {{ font-weight: bold; }}
    .hero-chart {{
        height: 202px;
        border-top: 1px solid #ccc;
        margin-bottom: 10px;
        padding-top: 0;
    }}
    .chart-title {{
        height: 27px;
        border: 2px solid black;
        padding-left: 14px;
        font-weight: bold;
        line-height: 24px;
    }}
    .hero-plot {{
        margin-top: 0;
        position: relative;
        padding-top: 0;
    }}
    .hero-guides {{
        position: absolute;
        left: 147px;
        right: 45px;
        top: 0;
        bottom: 0;
        pointer-events: none;
        z-index: 3;
    }}
    .hero-row {{
        display: grid;
        grid-template-columns: 31px 116px 1fr 45px;
        height: 30px;
        align-items: center;
        font-weight: bold;
    }}
    .tier, .hero-name {{
        height: 30px;
        line-height: 29px;
        border-left: 1px solid black;
        border-bottom: 1px solid black;
        padding-left: 5px;
    }}
    .hero-name {{ border-right: 1px solid black; }}
    .hero-bar-wrap {{
        height: 30px;
        position: relative;
        border-bottom: 1px solid black;
        border-right: 1px solid black;
    }}
    .hero-bar {{
        height: 29px;
        background: #ed1c24;
        border-right: 2px solid black;
    }}
    .hero-value {{
        text-align: right;
        padding-right: 8px;
        font-family: Helvetica, Arial, sans-serif;
    }}
    .guide {{
        position: absolute;
        top: 0;
        bottom: 0;
        width: 2px;
        background: black;
        pointer-events: none;
    }}
    .server-guide {{
        background: #2563eb;
        width: 2px;
    }}
    .chart-axis {{
        height: 32px;
        display: flex;
        gap: 18px;
        align-items: flex-start;
        padding-left: 0;
        font-size: 16px;
        font-weight: bold;
    }}
    .axis-label {{
        min-width: 126px;
        text-align: center;
        line-height: 1.15;
        background: white;
    }}
    .server-axis {{ color: #1d4ed8; }}
    .chanting, .answer-time {{
        margin-top: 18px;
        width: 620px;
    }}
    .chanting .boxed-title, .answer-time .boxed-title {{ margin-bottom: 0; }}
    .two-col-row {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        min-height: 30px;
        border-left: 1px solid #ccc;
        border-bottom: 1px solid #ccc;
    }}
    .two-col-row span {{
        padding: 4px 6px;
        border-right: 1px solid #ccc;
    }}
    .chant-lists {{
        margin-top: 28px;
        display: grid;
        grid-template-columns: 1fr 1fr;
        border-left: 1px solid #ccc;
        border-top: 1px solid #ccc;
    }}
    .empty-note {{ padding: 12px; color: #555; }}
</style>
</head>
<body>
    <div class="{dashboard_class}">
        {left_html}
        <div class="right">
            {hero_chart_html("Top Attacker", data["top_attackers"], data["attacker_average"], data["server_attacker_average"])}
            {hero_chart_html("Top Blocker", data["top_blockers"], data["blocker_average"], data["server_blocker_average"])}
            {chanting_html}
            {answer_time_html}
        </div>
    </div>
</body>
</html>
"""

    hti = Html2Image(
        size=(620 if right_only else 1228, 1120),
        browser_executable=get_browser(),
        custom_flags=[
            "--headless=new",
            "--hide-scrollbars",
            "--disable-gpu",
            "--force-device-scale-factor=1",
        ],
        output_path=output_dir
    )
    hti.screenshot(html_str=html, save_as=filename)
    save_path = os.path.join(output_dir, filename)
    trim_bottom_white(save_path)
    return save_path


class SubSelectionDialog(tk.Toplevel):
    def __init__(self, parent, missing_roster):
        super().__init__(parent)
        self.title("Substitute Resolution")
        self.result = None
        tk.Label(self, text="Multiple roster members are missing.\nWhich player is being replaced by the substitute?", 
                 font=("Arial", 10), padx=20, pady=10).pack()
        self.listbox = tk.Listbox(self, height=len(missing_roster))
        self.listbox.pack(padx=20, pady=5, fill=tk.X)
        for m in missing_roster: self.listbox.insert(tk.END, m)
        ttk.Button(self, text="Confirm", command=self.on_confirm).pack(pady=10)
        self.grab_set(); self.wait_window()
        
    def on_confirm(self):
        sel = self.listbox.curselection()
        if sel: self.result = self.listbox.get(sel[0]); self.destroy()


class ManualMatchDialog(tk.Toplevel):
    def __init__(self, parent, unknown_name, available_pool):
        super().__init__(parent)
        self.title("Manual Match Required")
        self.result = None
        ttk.Label(self, text=f"Could not find match for: '{unknown_name}'", font=("Arial", 10, "bold")).pack(pady=10)
        self.listbox = tk.Listbox(self, height=15); self.listbox.pack(padx=10, fill=tk.BOTH)
        for name in sorted(available_pool): self.listbox.insert(tk.END, name)
        ttk.Button(self, text="Match Selected", command=self.on_match).pack(pady=10)
        self.grab_set(); self.wait_window()

    def on_match(self):
        sel = self.listbox.curselection()
        if sel: self.result = self.listbox.get(sel[0]); self.destroy()


def export_extra_stats_screenshot(server_average_mode, gc=None, ask_cleanup=False, teamDB=None):
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(script_dir, "assets")
    json_dir = os.path.join(script_dir, "jsons")
    os.makedirs(assets_dir, exist_ok=True)
    if tk._default_root is None:
        root = tk.Tk()
        root.withdraw()
    
    json_paths = []
    while True:
        if os.path.exists(json_dir) and os.path.isdir(json_dir):
            json_paths = [os.path.join(json_dir, f) for f in os.listdir(json_dir) if f.endswith(".json")]
        
        if json_paths:
            break
        else:
            retry = messagebox.askyesno("Missing Files", "There is no jsons folder detected or there are no JSON files in the folder. Lock in and press yes to re-run the script")
            if not retry:
                return

    all_known_players = set()
    for path in json_paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f); songs = data.get("songs", [])
                for s in songs:
                    for p in get_correct_guess_player_names(s): all_known_players.add(p)
                    for answer_name, _ in get_answer_time_entries(s): all_known_players.add(answer_name)
                    for ls in get_list_state_entries(s):
                        if isinstance(ls, dict) and ls.get("name"):
                            all_known_players.add(ls["name"])
        except: continue

    raw_assignments = {}
    team_rosters = defaultdict(set)
    t1_lookup = {}
    use_teams = False
    team_size_for_extra = 4
    server_average_gr = None
    if gc is None:
        try:
            gc = get_gspread_client(script_dir)
        except Exception as exc:
            print(f"Extra stats screenshot skipped: could not authorize Google Sheets access: {exc}")
            return None

    chanting_ids = load_chanting_ids(gc)
    alias_to_id, id_to_aliases = load_player_aliases(gc)

    codes_path = find_codes_path(script_dir)
    codes_valid = False
    if os.path.exists(codes_path):
        with open(codes_path, "r", encoding="utf-8") as f:
            if f.read().strip():
                codes_valid = True

    if not codes_valid:
        if not messagebox.askyesno("Codes Missing", "codes.txt is missing or empty, skip team assignment phase?"):
            return
    else:
        with open(codes_path, "r", encoding="utf-8") as f:
            content = f.read()
        for line in content.strip().split('\n'):
            if line.lower().startswith(("average", "avg")):
                avg_match = re.search(r"(-?\d+(?:\.\d+)?)", line)
                if avg_match:
                    server_average_gr = float(avg_match.group(1))
                    if server_average_gr > 1:
                        server_average_gr /= 100

        if teamDB is not None and getattr(teamDB, "teams", None):
            use_teams = True
            team_size_for_extra = teamDB.teams[0].get_team_size() if teamDB.teams else team_size_for_extra
            for t_idx, team in enumerate(teamDB.teams, 1):
                for i, player in enumerate(team.players):
                    tier = f"T{i+1}"
                    raw_assignments[player.name] = (t_idx, tier)
                    team_rosters[t_idx].add(player.name)
                    if tier == "T1":
                        t1_lookup[t_idx] = player.name
                for sub in team.subs:
                    raw_assignments[sub.name] = (t_idx, "Sub")
                    team_rosters[t_idx].add(sub.name)
        else:
            all_teams_data = []
            for line in content.strip().split('\n'):
                lower = line.lower()
                if lower.startswith(("average", "avg", "sub")) or line.startswith("http"):
                    continue
                matches = re.findall(r'([^\s(]+)\s*\([\d.]+\)', line)
                if matches:
                    all_teams_data.append(matches)

            if all_teams_data:
                use_teams = True
                team_size_for_extra = len(all_teams_data[0])
                available = list(all_known_players)
                for t_idx, members in enumerate(all_teams_data, 1):
                    for i, p_in in enumerate(members):
                        tier = f"T{i+1}"
                        match = resolve_player_name(p_in, available, alias_to_id, id_to_aliases)
                        if not match:
                            d = ManualMatchDialog(None, p_in, available)
                            match = d.result
                        if match:
                            raw_assignments[match] = (t_idx, tier)
                            team_rosters[t_idx].add(match)
                            if match in available:
                                available.remove(match)
                            if tier == "T1":
                                t1_lookup[t_idx] = match

    roster_name_pool = list(raw_assignments.keys())

    def extra_player_name(name):
        if not use_teams:
            return name
        return resolve_player_name(name, roster_name_pool, alias_to_id, id_to_aliases) or name

    correct_counts, song_participation = defaultdict(int), defaultdict(int)
    erigs_counts, player_reverse_erigs = defaultdict(int), defaultdict(int)
    player_two_eighths, player_points, player_blocks = defaultdict(int), defaultdict(int), defaultdict(int)
    player_type_correct, player_type_seen = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    player_rigs, player_rigs_hit = defaultdict(int), defaultdict(int)
    all_song_vintages, all_song_difficulties = [], []
    total_correct_answers_sum, total_erigs = 0, 0
    genre_counter, tag_counter = Counter(), Counter()
    player_list_vintages, player_list_correct_counts = defaultdict(list), defaultdict(list) 
    player_missed_erigs, watched_only_valid = defaultdict(int), False
    team_correct_per_song = defaultdict(list)
    team_onlist_synergy, team_offlist_synergy, team_shared_rig_pct = defaultdict(list), defaultdict(list), defaultdict(list)
    
    total_songs_played = 0
    total_chanting_songs = 0
    player_chanting_correct = defaultdict(int)
    player_chanting_seen = defaultdict(int)
    chanting_correct_sum = 0
    player_answer_times = defaultdict(list)

    for path in json_paths:
        with open(path, encoding="utf-8") as f: data = json.load(f); songs = data.get("songs", [])
        if not songs: continue
        
        raw_file_players = set()
        for song in songs:
            for p in get_correct_guess_player_names(song):
                raw_file_players.add(extra_player_name(p))
            for answer_name, _ in get_answer_time_entries(song):
                raw_file_players.add(extra_player_name(answer_name))
            for ls in get_list_state_entries(song):
                if isinstance(ls, dict) and ls.get("name"):
                    raw_file_players.add(extra_player_name(ls["name"]))
        
        final_file_members = set(raw_file_players)
        if use_teams:
            teams_in_file = set(raw_assignments[p][0] for p in raw_file_players if p in raw_assignments)
            for t_id in teams_in_file:
                roster = team_rosters[t_id]
                seen_on_team = [p for p in roster if p in raw_file_players]
                missing = [p for p in roster if p not in raw_file_players]
                needed = max(0, team_size_for_extra - len(seen_on_team))
                if needed and missing:
                    if len(missing) == needed:
                        final_file_members.update(missing)
                    else:
                        remaining = missing[:]
                        for _ in range(needed):
                            if not remaining:
                                break
                            if len(remaining) == 1:
                                final_file_members.add(remaining[0])
                                break
                            d = SubSelectionDialog(None, remaining)
                            if d.result:
                                final_file_members.add(d.result)
                                remaining.remove(d.result)
                            else:
                                break

        apply_rev = (len(final_file_members) % 2 == 0)
        max_songs = max(s.get("songNumber", 0) for s in songs)
        type_totals_this_file = defaultdict(int)

        for song in songs:
            total_songs_played += 1
            si = song.get("songInfo", {}); st = si.get("type")
            
            # Using annSongId for chanting matching
            ann_song_id = str(si.get("annSongId"))
            
            is_chanting = ann_song_id in chanting_ids
            if is_chanting: total_chanting_songs += 1

            if st in [1, 2, 3]: type_totals_this_file[st] += 1
            if isinstance(si.get("animeGenre"), list): genre_counter.update(si.get("animeGenre"))
            if isinstance(si.get("animeTags"), list):
                tag_counter.update([t for t in si.get("animeTags") if t not in EXCLUDED_TAGS])

            correct = {extra_player_name(name) for name in get_correct_guess_player_names(song)}
            ls = get_list_state_entries(song); total_correct_answers_sum += len(correct)
            if is_chanting: chanting_correct_sum += len(correct)
            for answer_name, answer_time in get_answer_time_entries(song):
                answer_name = extra_player_name(answer_name)
                matched_answer_name = answer_name if answer_name in final_file_members else resolve_player_name(answer_name, final_file_members, alias_to_id, id_to_aliases)
                if matched_answer_name:
                    player_answer_times[matched_answer_name].append(answer_time)

            year, diff = extract_year(si.get("vintage")), si.get("animeDifficulty")
            if isinstance(diff, (int, float)): all_song_difficulties.append(diff)
            if year is not None: all_song_vintages.append(year)
            
            song_riggers = {extra_player_name(p["name"]) for p in ls if isinstance(p, dict) and p.get("name")}
            
            if use_teams:
                teams_in_this_file = list(set(raw_assignments[p][0] for p in raw_file_players if p in raw_assignments))
                if len(teams_in_this_file) == 2:
                    tA, tB = teams_in_this_file[0], teams_in_this_file[1]
                    for cur_t, opp_t in [(tA, tB), (tB, tA)]:
                        cur_correct = correct.intersection(team_rosters[cur_t])
                        opp_correct = correct.intersection(team_rosters[opp_t])
                        if not opp_correct:
                            for p in cur_correct: player_points[p] += 1
                        if len(cur_correct) == 1 and len(opp_correct) > 0:
                            player_blocks[list(cur_correct)[0]] += 1

                for t_id in teams_in_this_file:
                    roster = team_rosters[t_id]
                    correct_on_team = correct.intersection(roster)
                    team_correct_per_song[t_id].append(len(correct_on_team) / float(team_size_for_extra or 1))
                    team_riggers = song_riggers.intersection(roster)
                    if team_riggers:
                        team_onlist_synergy[t_id].append(len(correct_on_team) / float(team_size_for_extra or 1))
                        team_shared_rig_pct[t_id].append((len(team_riggers) - 1) / float(max(team_size_for_extra - 1, 1)))
                    else: team_offlist_synergy[t_id].append(len(correct_on_team) / float(team_size_for_extra or 1))

            if len(correct) == 2:
                for p in correct: player_two_eighths[p] += 1
            elif len(correct) == 1: 
                total_erigs += 1; erigs_counts[list(correct)[0]] += 1
            if apply_rev and len(final_file_members - correct) == 1:
                player_reverse_erigs[list(final_file_members - correct)[0]] += 1

            for name in final_file_members:
                if name in correct:
                    correct_counts[name] += 1
                    if st in [1, 2, 3]: player_type_correct[name][st] += 1
                    if is_chanting: player_chanting_correct[name] += 1
                if is_chanting: player_chanting_seen[name] += 1

            if ls:
                watched_only_valid = True
                for p in ls:
                    if not isinstance(p, dict) or not p.get("name"):
                        continue
                    n = extra_player_name(p["name"]); player_rigs[n] += 1
                    if n in correct: player_rigs_hit[n] += 1
                    if year is not None: player_list_vintages[n].append(year)
                    player_list_correct_counts[n].append(len(correct))
                    if len(correct) == 0: player_missed_erigs[n] += 1

        for name in final_file_members:
            song_participation[name] += max_songs
            for t in [1, 2, 3]: player_type_seen[name][t] += type_totals_this_file[t]

    p_rows = []
    for name in song_participation:
        total, correct = song_participation[name], correct_counts[name]
        t_id, tier = raw_assignments.get(name, ("Unassigned", "N/A"))
        t_name = t1_lookup.get(t_id, "Unknown")
        p_rows.append({
            "Team": t_name, "Tier": tier, "Player": name, 
            "Guess Rate": correct/total if total else 0, "Erigs 🔫": erigs_counts[name],
            "Points": player_points[name], "Blocks": player_blocks[name],
            "2/8s": player_two_eighths[name], "Rev. Erigs": player_reverse_erigs[name],
            "Song Count": total,
            "OP GR": player_type_correct[name][1]/player_type_seen[name][1] if player_type_seen[name][1] else np.nan,
            "ED GR": player_type_correct[name][2]/player_type_seen[name][2] if player_type_seen[name][2] else np.nan,
            "IN GR": player_type_correct[name][3]/player_type_seen[name][3] if player_type_seen[name][3] else np.nan,
            "Rigs": player_rigs[name], "Rigs Missed": player_rigs[name]-player_rigs_hit[name],
            "Onlist GR": player_rigs_hit[name]/player_rigs[name] if player_rigs[name] else np.nan,
            "Offlist GR": (correct-player_rigs_hit[name])/(total-player_rigs[name]) if (total-player_rigs[name]) else np.nan
        })
    df_ps = pd.DataFrame(p_rows).sort_values("Guess Rate", ascending=False)
    total_participation = sum(song_participation.values())
    avg_tour_gr = total_correct_answers_sum / total_participation if total_participation else 0

    df_tour = pd.DataFrame([
        ["Average Vintage", round(np.mean(all_song_vintages), 2) if all_song_vintages else "N/A"],
        ["Average Difficulty", round(np.mean(all_song_difficulties), 2) if all_song_difficulties else "N/A"],
        ["Average GR", f"{avg_tour_gr:.2%}"],
        ["Total Erigs", total_erigs],
        ["Total Rev. Erigs", sum(player_reverse_erigs.values())],
        ["Most Popular Genre", f"{genre_counter.most_common(1)[0][0]} ({genre_counter.most_common(1)[0][1]})" if genre_counter else "N/A"],
        ["Most Popular Tag", f"{tag_counter.most_common(1)[0][0]} ({tag_counter.most_common(1)[0][1]})" if tag_counter else "N/A"],
    ], columns=["TOUR STATS", ""])

    team_stat_rows, team_meta = [], []
    if use_teams:
        for t_id in sorted(team_correct_per_song.keys()):
            t_name = t1_lookup.get(t_id, f"Team {t_id}"); roster = team_rosters[t_id]
            t_v = [v for p in roster for v in player_list_vintages[p]]
            t_d = [v for p in roster for v in player_list_correct_counts[p]]
            team_stat_rows.append({"TEAM STATS": t_name, "Avg. Correct": np.mean(team_correct_per_song[t_id]), "Onlist Synergy": np.mean(team_onlist_synergy[t_id]) if team_onlist_synergy[t_id] else 0, "Offlist Synergy": np.mean(team_offlist_synergy[t_id]) if team_offlist_synergy[t_id] else 0, "Shared Rigs": np.mean(team_shared_rig_pct[t_id]) if team_shared_rig_pct[t_id] else 0})
            team_meta.append({"name": t_name, "erigs": sum(erigs_counts[p] for p in roster), "vintage": np.mean(t_v) if t_v else 0, "diff": np.mean(t_d) if t_d else 0})
    
    df_team_stats = pd.DataFrame(team_stat_rows)
    if not df_team_stats.empty:
        df_team_stats = df_team_stats.sort_values("Avg. Correct", ascending=False)

    tier_hero_rows = []
    tier_attackers, tier_blockers = {}, {}
    tier_order = []
    if use_teams:
        tier_order = sorted(
            {attr[1] for attr in raw_assignments.values()},
            key=lambda tier: (0, int(tier[1:])) if str(tier).startswith("T") and str(tier)[1:].isdigit() else (1, str(tier)),
        )
        for tier in tier_order:
            tp = [p for p, attr in raw_assignments.items() if attr[1] == tier]
            if tp:
                bp = max(tp, key=lambda x: player_points[x]); bb = max(tp, key=lambda x: player_blocks[x])
                tier_attackers[tier] = (bp, player_points[bp])
                tier_blockers[tier] = (bb, player_blocks[bb])
                tier_hero_rows.append([tier, f"{bp} ({player_points[bp]})", f"{bb} ({player_blocks[bb]})"])
    df_tier_heroes = pd.DataFrame(tier_hero_rows, columns=["Tier", "Top Attacker", "Top Blocker"])

    plist = list(song_participation.keys())
    diff_data = [(n, np.mean(player_list_correct_counts[n])) for n in plist if player_list_correct_counts[n]]
    vint_data = [(n, np.mean(player_list_vintages[n])) for n in plist if player_list_vintages[n]]
    all_list_correct_counts = [v for values in player_list_correct_counts.values() for v in values]
    all_list_vintages = [v for values in player_list_vintages.values() for v in values]

    no_erig_pool = [n for n in plist if erigs_counts[n] == 0]
    best_no_erig = sorted(no_erig_pool, key=lambda x: (correct_counts[x]/song_participation[x]), reverse=True)[0] if no_erig_pool else "N/A"
    best_no_erig_gr = f"{correct_counts[best_no_erig]/song_participation[best_no_erig]:.2%}" if no_erig_pool else "N/A"
    p_28 = sorted(plist, key=lambda x: player_two_eighths[x], reverse=True)[0] if plist else "N/A"
    m_miss = max(player_missed_erigs, key=player_missed_erigs.get) if player_missed_erigs else "N/A"
    m_rev = max(player_reverse_erigs, key=player_reverse_erigs.get) if player_reverse_erigs else "N/A"

    chan_pct = total_chanting_songs / total_songs_played if total_songs_played else 0
    avg_chan_gr = (chanting_correct_sum / (total_chanting_songs * len(song_participation))) if (total_chanting_songs and song_participation) else 0
    chan_plist = [n for n in song_participation.keys() if player_chanting_seen[n] > 0]
    chan_rates = [(n, player_chanting_correct[n]/player_chanting_seen[n], f"{player_chanting_correct[n]}/{player_chanting_seen[n]}") for n in chan_plist]
    answer_time_rates = [
        (name, float(np.mean(times)))
        for name, times in player_answer_times.items()
        if times
    ]
    server_average_stats = load_server_average_stats(gc)
    selected_server_stats = server_average_stats.get(server_average_mode, {})
    image_server_gr = selected_server_stats.get("guess_rate")
    if image_server_gr is None:
        image_server_gr = server_average_gr
    image_server_attacker = selected_server_stats.get("attacker")
    image_server_blocker = selected_server_stats.get("blocker")
    vintage_min = min([v for _, v in vint_data]) if vint_data else 0
    vintage_max = max([v for _, v in vint_data]) if vint_data else 1
    if vintage_min == vintage_max:
        vintage_min -= 1
        vintage_max += 1

    extra_image_data = {
        "tour_average_gr": avg_tour_gr,
        "server_average_gr": image_server_gr,
        "gr_points": [(row["Player"], row["Guess Rate"]) for row in p_rows],
        "watched_average": np.mean(all_list_correct_counts) if all_list_correct_counts else None,
        "difficulty_points": diff_data,
        "easiest_lists": sorted(diff_data, key=lambda x: x[1], reverse=True)[:3],
        "hardest_lists": sorted(diff_data, key=lambda x: x[1])[:3],
        "vintage_average": np.mean(all_list_vintages) if all_list_vintages else None,
        "vintage_min": vintage_min,
        "vintage_max": vintage_max,
        "vintage_points": vint_data,
        "zoomer_lists": sorted(vint_data, key=lambda x: x[1], reverse=True)[:3],
        "boomer_lists": sorted(vint_data, key=lambda x: x[1])[:3],
        "most_two_eighths": f"{p_28} ({player_two_eighths[p_28]})" if p_28 != "N/A" else "N/A",
        "best_no_erig": f"{best_no_erig} ({best_no_erig_gr})" if no_erig_pool else "N/A",
        "top_erig_misser": f"{m_miss} ({player_missed_erigs.get(m_miss, 0)})" if m_miss != "N/A" else "N/A",
        "top_reverse_erig": f"{m_rev} ({player_reverse_erigs.get(m_rev, 0)})" if m_rev != "N/A" else "N/A",
        "top_attackers": [(tier, tier_attackers[tier][0], tier_attackers[tier][1]) for tier in tier_order if tier in tier_attackers],
        "top_blockers": [(tier, tier_blockers[tier][0], tier_blockers[tier][1]) for tier in tier_order if tier in tier_blockers],
        "attacker_average": np.mean([player_points[n] for n in plist]) if plist else 0,
        "blocker_average": np.mean([player_blocks[n] for n in plist]) if plist else 0,
        "server_attacker_average": image_server_attacker,
        "server_blocker_average": image_server_blocker,
        "has_chanting": total_chanting_songs != 0,
        "right_only": server_average_mode.startswith("random"),
        "chanting_total": f"{total_chanting_songs} ({chan_pct:.2%})",
        "chanting_gr": avg_chan_gr,
        "chanting_lovers": sorted(chan_rates, key=lambda x: x[1], reverse=True)[:3],
        "chanting_haters": sorted(chan_rates, key=lambda x: x[1])[:3],
        "answer_time_tryhards": sorted(answer_time_rates, key=lambda x: x[1])[:3],
        "answer_time_ballscratchers": sorted(answer_time_rates, key=lambda x: x[1], reverse=True)[:3],
    }

    image_name = "Stats4.png"
    image_status = f"Extra stats image exported to {image_name}."
    try:
        save_extra_stats_image(extra_image_data, script_dir, image_name)
    except Exception as exc:
        image_status = f"Extra stats image could not be exported: {exc}"
        print(image_status)
        return None

    print(image_status)
    if ask_cleanup and messagebox.askyesno("Success", f"{image_status}\nDo you want to delete all processed JSON files?"):
        for path in json_paths:
            try:
                os.remove(path)
            except Exception:
                pass
        messagebox.showinfo("Cleanup", "JSON files deleted.")
    return os.path.join(script_dir, image_name)

