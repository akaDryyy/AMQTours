import os
import json
import re
from collections import defaultdict

import gspread
import numpy as np

from JsonProcessing import get_correct_guess_player_names, normalize_player_name
from TourFunctions import clean_data

JSON_DATA_FIELDS = [
    "songNumber",
    "songInfo.animeNames.english",
    "songInfo.animeNames.romaji",
    "songInfo.artist",
    "songInfo.composerInfo.artistId",
    "songInfo.composerInfo.name",
    "songInfo.arrangerInfo.artistId",
    "songInfo.arrangerInfo.name",
    "songInfo.songName",
    "songInfo.type",
    "songInfo.typeNumber",
    "songInfo.annId",
    "songInfo.annSongId",
    "songInfo.highRisk",
    "songInfo.animeScore",
    "songInfo.animeType",
    "songInfo.vintage",
    "songInfo.animeDifficulty",
    "songInfo.animeTags",
    "songInfo.animeGenre",
    "songInfo.altAnimeNames",
    "songInfo.altAnimeNamesAnswers",
    "songInfo.siteIds.annId",
    "songInfo.siteIds.malId",
    "songInfo.siteIds.kitsuId",
    "songInfo.siteIds.aniListId",
    "songInfo.rebroadcast",
    "songInfo.dub",
    "songInfo.seasonInfo.name",
    "songInfo.seasonInfo.number",
    "songInfo.popularityRank",
    "correctCount",
    "wrongCount",
    "videoUrl",
    "correctGuessPlayers",
    "incorrectGuessPlayers",
    "listStates",
    "codesText",
]

JSON_FILE_NAME_COLUMN_INDEX = 3
JSON_CODES_COLUMN_INDEX = 41
JSON_DATA_COLUMN_FIELDS = [field for field in JSON_DATA_FIELDS if field != "codesText"]
JSON_PACKED_COLUMN_LABELS = ["songLabel"] + JSON_DATA_COLUMN_FIELDS
JSON_CELL_TEXT_LIMIT = 40000

NGM_STATS_SHEET_NAME = "NGM Stats Export v2"
NGM_STATS_SHEET_ID = "1ihfqssregh74curDyvRE0GAFihQfovUAHpYDrtOIrOA"
SHEET_PLAYER_IDS = 1903970832

SERVER_AVERAGE_SHEET_CANDIDATES = {
    "random_fl": ("Random FL (usual)",),
    "watched_fl": ("Watched FL",),
    "watched_op": ("Watched OP",),
    "watched_oped": ("Watched OPED",),
    "watched_in": ("Watched IN",),
    "watched_in_no_chanting": ("Watched IN (-chanting)",),
    "watched_ed": ("Watched ED",),
    "watched_fl_speed": ("Watched 2+8",),
    "watched_fl_5s": ("Watched 5s",),
    "watched_pre_2009": ("Watched -2009",),
    "random_op": ("Random OP",),
    "random_ed": ("Random ED",),
    "random_in": ("Random IN stats",),
    "random_oped": ("Random OPED",),
    "random_chanting": ("Random Chanting",),
}




def get_or_create_worksheet(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except Exception:
        return spreadsheet.add_worksheet(title=title, rows=1000, cols=100)


def get_worksheet_by_ref(spreadsheet, worksheet_ref):
    if isinstance(worksheet_ref, int):
        return spreadsheet.get_worksheet_by_id(worksheet_ref)
    return spreadsheet.worksheet(worksheet_ref)


def append_log_rows(worksheet, rows):
    if not rows:
        return
    max_cols = max(len(row) for row in rows)
    padded_rows = [row + [""] * (max_cols - len(row)) for row in rows]
    existing_values = worksheet.get_all_values()
    start_row = len(existing_values) + 1
    try:
        existing_cols = max((len(row) for row in existing_values), default=0)
        target_rows = max(1, start_row + len(padded_rows) - 1)
        target_cols = max(1, existing_cols, max_cols)
        worksheet.resize(rows=target_rows, cols=target_cols)
    except Exception:
        pass
    worksheet.update(values=padded_rows, range_name=f"A{start_row}")


def log_cell_value(value):
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)


def get_nested_json_value(data, path):
    value = data
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return ""
        value = value[key]
    return value


def normalized_name_for_log(name):
    return str(name).strip().casefold()


def player_identity_for_log(name, alias_to_id):
    normalized = normalize_player_name(name)
    return alias_to_id.get(normalized, normalized)


def get_incorrect_guess_players(song, game_player_names, alias_to_id):
    correct_players = get_correct_guess_player_names(song)
    correct_ids = {player_identity_for_log(player, alias_to_id) for player in correct_players}
    seen_roster_ids = set()
    roster_names = []
    for player_name in game_player_names:
        player_id = player_identity_for_log(player_name, alias_to_id)
        if player_id in seen_roster_ids:
            continue
        seen_roster_ids.add(player_id)
        roster_names.append((player_name, player_id))

    max_incorrect = max(0, 8 - len(correct_ids))
    incorrect_players = [
        player_name for player_name, player_id in roster_names
        if player_id not in correct_ids
    ]
    return incorrect_players[:max_incorrect]


def ordered_song_json_values(song, game_player_names, alias_to_id, codes_text=""):
    incorrect_guess_players = get_incorrect_guess_players(song, game_player_names, alias_to_id)
    values = []
    for field in JSON_DATA_FIELDS:
        if field == "correctCount":
            values.append(len(get_correct_guess_player_names(song)))
        elif field == "wrongCount":
            values.append(len(incorrect_guess_players))
        elif field == "incorrectGuessPlayers":
            values.append(incorrect_guess_players)
        elif field == "codesText":
            values.append(codes_text)
        else:
            values.append(get_nested_json_value(song, field))
    return values


def compact_json_song_record(song_label, song, game_player_names, alias_to_id):
    song_record = {
        "songLabel": song_label,
    }
    for field, value in zip(JSON_DATA_FIELDS, ordered_song_json_values(song, game_player_names, alias_to_id)):
        if field == "codesText":
            continue
        song_record[field] = value
    return song_record


def packed_json_cell(values):
    if not values or all(value == "" for value in values):
        return ""
    return json.dumps(values, ensure_ascii=False)


def build_packed_column_cells(song_records):
    packed_cells = [
        packed_json_cell([song_record.get("songLabel", "") for song_record in song_records])
    ]
    for field in JSON_DATA_COLUMN_FIELDS:
        packed_cells.append(
            packed_json_cell([song_record.get(field, "") for song_record in song_records])
        )
    return packed_cells


def overflowing_packed_columns(packed_cells):
    return [
        label for label, cell in zip(JSON_PACKED_COLUMN_LABELS, packed_cells)
        if len(cell) > JSON_CELL_TEXT_LIMIT
    ]


def split_song_records_for_sheet(song_records, file_name, tour_type, export_time):
    chunks = []
    current_chunk = []

    for song_record in song_records:
        candidate_chunk = current_chunk + [song_record]
        candidate_cells = build_packed_column_cells(candidate_chunk)

        if not overflowing_packed_columns(candidate_cells):
            current_chunk = candidate_chunk
            continue

        if current_chunk:
            chunks.append(build_packed_column_cells(current_chunk))
            current_chunk = [song_record]
        else:
            single_cells = build_packed_column_cells([song_record])
            overflow_columns = ", ".join(overflowing_packed_columns(single_cells)) or "unknown columns"
            print(
                f"Warning: {tour_type} {export_time} {file_name or '[blank json name]'} "
                f"{song_record.get('songLabel', '[unknown song]')} alone exceeds the JsonData limit in: {overflow_columns}."
            )
            chunks.append(single_cells)
            current_chunk = []
            continue

        single_cells = build_packed_column_cells(current_chunk)
        overflow_columns = overflowing_packed_columns(single_cells)
        if overflow_columns:
            print(
                f"Warning: {tour_type} {export_time} {file_name or '[blank json name]'} "
                f"{song_record.get('songLabel', '[unknown song]')} alone exceeds the JsonData limit in: {', '.join(overflow_columns)}."
            )
            chunks.append(single_cells)
            current_chunk = []

    if current_chunk:
        chunks.append(build_packed_column_cells(current_chunk))
    return chunks


def build_compact_json_rows(tour_type, export_time, raw_json_songs, alias_to_id, codes_text):
    songs_by_file = {}
    for song_label, file_name, song, game_player_names in raw_json_songs:
        songs_by_file.setdefault(file_name or "", []).append(
            compact_json_song_record(song_label, song, game_player_names, alias_to_id)
        )

    compact_rows = []
    for file_name, song_records in songs_by_file.items():
        for packed_cells in split_song_records_for_sheet(song_records, file_name, tour_type, export_time):
            compact_row = [tour_type, export_time, packed_cells[0], file_name]
            compact_row.extend(packed_cells[1:])
            compact_row.append(codes_text)
            compact_rows.append(compact_row)
    return compact_rows


def log_export_data(sheet, tour_type, export_time, list_guess_counts, raw_json_songs, alias_to_id, id_to_aliases, codes_text):
    if list_guess_counts:
        list_row = [tour_type, export_time]
        for player_name, guess_counts in sorted(list_guess_counts.items(), key=lambda item: item[0].casefold()):
            list_row.extend([player_name, round(float(np.mean(guess_counts)), 3)])
        list_wks = get_or_create_worksheet(sheet, "ListData")
        append_log_rows(list_wks, [list_row, [""]])

    compact_rows = build_compact_json_rows(tour_type, export_time, raw_json_songs, alias_to_id, codes_text)
    if compact_rows:
        json_wks = get_or_create_worksheet(sheet, "JsonData")
        append_log_rows(json_wks, compact_rows + [[""]])


def get_gspread_client(script_dir):
    parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
    credential_paths = [
        (
            os.path.join(script_dir, "assets", "credentials", "credentials.json"),
            os.path.join(script_dir, "assets", "credentials", "authorized_user.json"),
        ),
        (
            os.path.join(script_dir, "assets", "credentials.json"),
            os.path.join(script_dir, "assets", "authorized_user.json"),
        ),
        (
            os.path.join(parent_dir, "assets", "credentials", "credentials.json"),
            os.path.join(parent_dir, "assets", "credentials", "authorized_user.json"),
        ),
        (
            os.path.join(parent_dir, "credentials", "credentials.json"),
            os.path.join(parent_dir, "credentials", "authorized_user.json"),
        ),
    ]
    credentials_filename, authorized_user_filename = next(
        (
            (credentials, authorized_user)
            for credentials, authorized_user in credential_paths
            if os.path.exists(credentials) and os.path.exists(authorized_user)
        ),
        credential_paths[-1],
    )
    return gspread.oauth(
        credentials_filename=credentials_filename,
        authorized_user_filename=authorized_user_filename
    )


def load_sheet_context(directory, sheet_id, worksheet_ref, is_list, assets_dir=None):
    gc = get_gspread_client(directory)
    if assets_dir is not None:
        sync_chanting_ids_file(gc, assets_dir)

    sheet = gc.open_by_key(sheet_id)
    wks = get_worksheet_by_ref(sheet, worksheet_ref)
    rows_stats = wks.get_all_values()
    wks_ids = sheet.get_worksheet_by_id(SHEET_PLAYER_IDS)
    rows_ids = wks_ids.get_all_values()
    alias_to_id, id_to_aliases = load_player_aliases(gc)

    avg_df = clean_data(rows_ids, rows_stats, 6, 10, is_list)
    avg_df = avg_df.sort_values(["Player ID", "Timestamp"])

    return {
        "gc": gc,
        "sheet": sheet,
        "wks": wks,
        "rows_stats": rows_stats,
        "wks_ids": wks_ids,
        "rows_ids": rows_ids,
        "alias_to_id": alias_to_id,
        "id_to_aliases": id_to_aliases,
        "avg_df": avg_df,
    }


def parse_stat_cell(value, is_percent=False):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        has_percent = text.endswith("%")
        text = text.rstrip("%").replace(",", "")
        try:
            value = float(text)
        except ValueError:
            return None
        if has_percent:
            value /= 100
    elif isinstance(value, (int, float)):
        value = float(value)
    else:
        return None

    if is_percent and value > 1:
        value /= 100
    return value


def average_tour_blocks_from_rows(rows, col_idx, is_percent=False):
    tour_values = []
    tour_averages = []
    value_idx = col_idx - 1
    for row in rows[1:]:
        value = parse_stat_cell(row[value_idx] if len(row) > value_idx else None, is_percent)
        if value is None:
            if tour_values:
                tour_averages.append(float(np.mean(tour_values)))
                tour_values = []
        else:
            tour_values.append(value)
    if tour_values:
        tour_averages.append(float(np.mean(tour_values)))
    return float(np.mean(tour_averages)) if tour_averages else None


def normalize_sheet_title(title):
    return re.sub(r"[^a-z0-9]+", "", str(title).casefold())


def get_stats_worksheet(worksheets, candidates):
    by_title = {normalize_sheet_title(ws.title): ws for ws in worksheets}
    for candidate in candidates:
        worksheet = by_title.get(normalize_sheet_title(candidate))
        if worksheet is not None:
            return worksheet

    normalized_candidates = [normalize_sheet_title(candidate) for candidate in candidates]
    for worksheet in worksheets:
        normalized_title = normalize_sheet_title(worksheet.title)
        if any(candidate in normalized_title for candidate in normalized_candidates):
            return worksheet
    return None


def load_server_average_stats(gc):
    stats = {}
    try:
        stats_sheet = gc.open_by_key(NGM_STATS_SHEET_ID)
        worksheets = stats_sheet.worksheets()
    except Exception:
        return stats

    for mode, candidates in SERVER_AVERAGE_SHEET_CANDIDATES.items():
        try:
            worksheet = get_stats_worksheet(worksheets, candidates)
            if worksheet is None:
                continue
            rows = worksheet.get_all_values()
        except Exception:
            continue
        stats[mode] = {
            "guess_rate": average_tour_blocks_from_rows(rows, 4, is_percent=True),
            "attacker": average_tour_blocks_from_rows(rows, 14),
            "blocker": average_tour_blocks_from_rows(rows, 15),
        }
    return stats


def load_player_aliases(gc):
    try:
        sheet = gc.open_by_key(NGM_STATS_SHEET_ID)
        rows = sheet.get_worksheet_by_id(SHEET_PLAYER_IDS).get_all_values()
    except Exception:
        return {}, defaultdict(set)

    alias_to_id = {}
    id_to_aliases = defaultdict(set)
    for row in rows[1:]:
        if len(row) < 2:
            continue
        player_name, player_id = row[0], row[1]
        if not player_name or not player_id:
            continue
        norm_name = normalize_player_name(player_name)
        alias_to_id[norm_name] = player_id
        id_to_aliases[player_id].add(norm_name)
    return alias_to_id, id_to_aliases


def load_chanting_ids(gc):
    try:
        sheet = gc.open_by_key(NGM_STATS_SHEET_ID)
        rows = sheet.worksheet("MiscData").get_all_values()
    except Exception:
        return set()

    chanting_ids = set()
    for row in rows[1:]:
        if not row:
            continue
        value = str(row[0]).strip()
        if value:
            chanting_ids.add(value)
    return chanting_ids


def sync_chanting_ids_file(gc, assets_dir):
    chanting_ids = load_chanting_ids(gc)
    os.makedirs(assets_dir, exist_ok=True)
    with open(os.path.join(assets_dir, "chanting.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(chanting_ids)))
    return chanting_ids

