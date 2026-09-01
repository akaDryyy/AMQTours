from __future__ import annotations

from pathlib import Path

from modules.support.readCredentials import readCredentials
from modules.support.readElos import load_alias_table, load_elos, normalize_player_id, normalize_player_name, save_elos


class MissingDraftElosError(ValueError):
    def __init__(self, names):
        self.names = names
        super().__init__("Missing Watched Elo for: " + ", ".join(names))


class MissingDraftPlayerIdsError(ValueError):
    def __init__(self, names):
        self.names = names
        super().__init__("Missing player IDs for: " + ", ".join(names))


def _store_config(tour):
    config = tour.get("draft_elo_store")
    if not config:
        raise ValueError(f"{tour['label']} is missing draft_elo_store configuration.")
    return config


def _worksheet(tour):
    config = _store_config(tour)
    gc = readCredentials(tour["state_path"])
    sheet = gc.open_by_key(config["spreadsheet_id"])
    return sheet.get_worksheet_by_id(config["worksheet_id"])


def _columns(config):
    return (
        int(config.get("name_column", 4)),
        int(config.get("id_column", 5)),
        int(config.get("elo_column", 6)),
        int(config.get("first_row", 2)),
    )


def _column_letter(column):
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _read_store(tour):
    config = _store_config(tour)
    name_column, id_column, elo_column, first_row = _columns(config)
    rows = _worksheet(tour).get_all_values()
    entries = {}
    for row_index, row in enumerate(rows[first_row - 1:], start=first_row):
        def value(column):
            return row[column - 1].strip() if len(row) >= column else ""

        player_id = normalize_player_id(value(id_column))
        if not player_id:
            continue
        try:
            elo = float(value(elo_column))
        except ValueError:
            continue
        entries[player_id] = {
            "row": row_index,
            "name": normalize_player_name(value(name_column)),
            "elo": elo,
        }
    return entries


def _id_lookup(ids_path):
    aliases = load_alias_table(ids_path)
    return dict(zip(aliases["Player Name"], aliases["Player ID"]))


def _save_local_elos(tour, entries):
    state_path = Path(tour["state_path"])
    state_path.mkdir(parents=True, exist_ok=True)
    values = {
        (player_id, entry["name"] or player_id): entry["elo"]
        for player_id, entry in entries.items()
    }
    save_elos(values, state_path / "elos.json", state_path / "ids.csv", key_format="composite")
    return values


def _write_store_entries(tour, entries):
    """Keep the Draft table compact in D:F even when other sheet columns have data below it."""
    config = _store_config(tour)
    name_column, id_column, elo_column, first_row = _columns(config)
    worksheet = _worksheet(tour)
    ordered_entries = sorted(entries.items(), key=lambda item: item[1].get("row", float("inf")))
    first_column = _column_letter(name_column)
    last_column = _column_letter(elo_column)
    updates = []
    previous_rows = set()

    for offset, (player_id, entry) in enumerate(ordered_entries):
        row_index = first_row + offset
        if "row" in entry:
            previous_rows.add(entry["row"])
        updates.append({
            "range": f"{first_column}{row_index}:{last_column}{row_index}",
            "values": [[entry["name"], player_id, entry["elo"]]],
        })
        entry["row"] = row_index

    for row_index in previous_rows - {entry["row"] for entry in entries.values()}:
        updates.append({
            "range": f"{first_column}{row_index}:{last_column}{row_index}",
            "values": [["", "", ""]],
        })

    if updates:
        worksheet.batch_update(updates, value_input_option="RAW")


def sync_draft_elos(tour):
    """Load the shared Draft sheet into the local Elo file used by the UI and scraper."""
    entries = _read_store(tour)
    _save_local_elos(tour, entries)
    return {entry["name"]: entry["elo"] for entry in entries.values() if entry["name"]}


def assign_draft_elos(tour, player_entries, manual_ratings, watched_elos):
    """Register missing Draft players from Watched Elo or supplied manual Elo values."""
    state_path = Path(tour["state_path"])
    ids_path = state_path / "ids.csv"
    name_to_id = _id_lookup(ids_path)
    entries = _read_store(tour)
    missing_ids, missing_elos = [], []
    new_entries = {}

    for name, pasted_rank in player_entries:
        normalized_name = normalize_player_name(name)
        player_id = name_to_id.get(normalized_name)
        if not player_id:
            missing_ids.append(name)
            continue
        if player_id in entries:
            continue
        elo = watched_elos.get(player_id)
        if elo is None:
            elo = manual_ratings.get(normalized_name, pasted_rank)
        if elo is None:
            missing_elos.append(name)
            continue
        new_entries[player_id] = {"name": normalized_name, "elo": float(elo)}

    if missing_ids:
        raise MissingDraftPlayerIdsError(missing_ids)

    if new_entries:
        entries.update(new_entries)

    if entries:
        _write_store_entries(tour, entries)

    _save_local_elos(tour, entries)
    if missing_elos:
        raise MissingDraftElosError(missing_elos)
    return len(new_entries), len(entries)


def write_draft_elo_values(directory, store_config, elos_path):
    """Write updated scraper ratings back to the Draft sheet's Elo column only."""
    directory = Path(directory)
    gc = readCredentials(directory)
    sheet = gc.open_by_key(store_config["spreadsheet_id"])
    worksheet = sheet.get_worksheet_by_id(store_config["worksheet_id"])
    name_column, id_column, elo_column, first_row = _columns(store_config)
    ids_path = directory / "ids.csv"
    ratings = load_elos(elos_path, ids_path, key_format="composite")
    ratings_by_id = {normalize_player_id(player_id): float(elo) for (player_id, _name), elo in ratings.items()}
    rows = worksheet.get_all_values()
    updates = []
    for row_index, row in enumerate(rows[first_row - 1:], start=first_row):
        player_id = normalize_player_id(row[id_column - 1] if len(row) >= id_column else "")
        if player_id in ratings_by_id:
            updates.append({
                "range": f"{_column_letter(elo_column)}{row_index}",
                "values": [[ratings_by_id[player_id]]],
            })
    if updates:
        worksheet.batch_update(updates, value_input_option="RAW")
    return len(updates)
