from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import datetime

from modules.support.changelogMVPs import format_mvps, makeChangelog
from modules.support.cleanData import clean_data, mini_clean
from modules.support.computeRanks import compute_ranks
from modules.support.readElos import load_elos, rank_dict_from_frame, save_elos
from modules.support.trim import get_normalization_spec, get_tiers


def generate_mvps_for_tour(tour: dict, selected_tour_id: str | None = None) -> str:
    state_path = Path(tour["state_path"])
    stats_type = tour.get("solver", {}).get("stats_type", tour.get("tour_type", ""))
    refresh_mode_stats(tour, stats_type)

    statstable = state_path / "stats.csv"
    idtable = state_path / "ids.csv"
    if not statstable.exists():
        raise FileNotFoundError(f"No stats.csv found for {tour['label']}.")
    if not idtable.exists():
        raise FileNotFoundError(f"No ids.csv found for {tour['label']}.")

    tier_cfg = tour.get("tiermaker", {})
    alpha = tier_cfg.get("alpha", 3.75)
    midpoint = tier_cfg.get("midpoint", 0.4 if stats_type.startswith("watched") else 0.33)
    min_rating = tier_cfg.get("min_rating", 0)
    max_rating = tier_cfg.get("max_rating", 25)
    min_games = tier_cfg.get("min_games", 4)

    clean_stats, full_stats = clean_data(
        str(idtable),
        str(statstable),
        str(state_path / "stats_clean_year.csv"),
        maxFallbackWindow=6,
        activeTours=10,
        tourType=stats_type,
        min_games=min_games,
    )
    clean_stats = clean_stats.sort_values(["Player ID", "Timestamp"])
    full_stats = full_stats.sort_values(["Player ID", "Timestamp"])
    clean_stats.to_csv(state_path / "stats_clean.csv", index=False, encoding="utf-8")
    full_stats.to_csv(state_path / "stats_clean_full.csv", index=False, encoding="utf-8")

    tiers, tier_weights = get_tiers(stats_type)
    normalization_spec = get_normalization_spec(full_stats, stats_type)
    history_entry = get_history_entry(state_path, selected_tour_id)
    selection_stats = mini_clean(str(idtable), str(statstable), stats_type, min_games=1)
    selected_stats_timestamp = resolve_selected_stats_timestamp(selection_stats, selected_tour_id, history_entry, idtable)
    last_tour = get_last_tour_stats(
        state_path,
        idtable,
        statstable,
        stats_type,
        selected_tour_id,
        selected_stats_timestamp,
        history_entry,
    )
    if last_tour.empty:
        raise ValueError("No new tour rows found for MVP calculation.")
    selected_stats_timestamp = last_tour["Timestamp"].max()
    old_elos = old_ranks_for_mvp(
        state_path,
        idtable,
        statstable,
        stats_type,
        tiers,
        tier_weights,
        alpha,
        midpoint,
        min_rating,
        max_rating,
        selected_stats_timestamp,
        min_games,
    )
    if old_elos:
        save_elos(old_elos, state_path / "mvp_current_elos.json", key_format="composite")

    last_tour_ranks = compute_ranks(
        last_tour,
        full_stats,
        normalization_spec,
        tiers,
        tier_weights,
        alpha,
        midpoint,
        min_rating,
        max_rating,
        full=False,
        isWatched=stats_type.startswith("watched"),
        isMVP=True,
    )
    last_tour_dict = rank_dict_from_frame(last_tour_ranks)
    output = format_mvps(last_tour_dict, old_elos)
    (state_path / "mvps.txt").write_text(output, encoding="utf-8")
    selected_rank_dict = ranks_through_timestamp(
        state_path,
        idtable,
        statstable,
        stats_type,
        tiers,
        tier_weights,
        alpha,
        midpoint,
        min_rating,
        max_rating,
        selected_stats_timestamp,
        min_games,
    )
    makeChangelog(selected_rank_dict, old_elos, state_path / "changelog.txt")
    return output


def refresh_mode_stats(tour: dict, stats_type: str) -> None:
    solver_cfg = tour.get("solver", {})
    stats_tab = solver_cfg.get("stats_tab")
    tab_ids = tour.get("sheet", {}).get("tab_ids")
    if stats_tab is None or tab_ids is None:
        return

    from utils import get_player_stats

    get_player_stats(
        path=tour["state_path"],
        tabStats=stats_tab,
        tabIDs=tab_ids,
        type=stats_type,
        sheetName=tour.get("sheet", {}).get("stats_sheet_name", tour.get("sheet", {}).get("name", "NGM Stats Export v2")),
        sheetId=tour.get("sheet", {}).get("stats_sheet_id"),
        idsSheetName=tour.get("sheet", {}).get("ids_sheet_name"),
        idsSheetId=tour.get("sheet", {}).get("ids_sheet_id"),
    )


def update_dry_elos_for_tour(tour: dict) -> dict[str, float]:
    if not tour.get("dry_elo"):
        return {}

    state_path = Path(tour["state_path"])
    stats_type = tour.get("solver", {}).get("stats_type", tour.get("tour_type", ""))
    refresh_mode_stats(tour, stats_type)

    idtable = state_path / "ids.csv"
    statstable = state_path / "stats.csv"
    if not idtable.exists():
        raise FileNotFoundError(f"No ids.csv found for {tour['label']}.")
    if not statstable.exists():
        raise FileNotFoundError(f"No stats.csv found for {tour['label']}.")

    elos_path = state_path / "elos.json"
    old_elos = {}
    if elos_path.exists():
        try:
            old_elos = load_elos(elos_path, idtable, key_format="composite")
        except (OSError, json.JSONDecodeError):
            old_elos = {}
    if old_elos:
        save_elos(old_elos, state_path / "mvp_current_elos.json", key_format="composite")

    tier_cfg = tour.get("tiermaker", {})
    alpha = tier_cfg.get("alpha", 3.75)
    midpoint = tier_cfg.get("midpoint", 0.4 if stats_type.startswith("watched") else 0.33)
    min_rating = tier_cfg.get("min_rating", 0)
    max_rating = tier_cfg.get("max_rating", 25)
    min_games = tier_cfg.get("min_games", 4)

    clean_stats, full_stats = clean_data(
        str(idtable),
        str(statstable),
        str(state_path / "stats_clean_year.csv"),
        maxFallbackWindow=6,
        activeTours=10,
        tourType=stats_type,
        min_games=min_games,
    )
    clean_stats = clean_stats.sort_values(["Player ID", "Timestamp"])
    full_stats = full_stats.sort_values(["Player ID", "Timestamp"])
    clean_stats.to_csv(state_path / "stats_clean.csv", index=False, encoding="utf-8")
    full_stats.to_csv(state_path / "stats_clean_full.csv", index=False, encoding="utf-8")

    tiers, tier_weights = get_tiers(stats_type)
    normalization_spec = get_normalization_spec(full_stats, stats_type)
    final_ranks = compute_ranks(
        clean_stats,
        full_stats,
        normalization_spec,
        tiers,
        tier_weights,
        alpha,
        midpoint,
        min_rating,
        max_rating,
        path=state_path / "stats_prenormalized.csv",
        isWatched=stats_type.startswith("watched"),
        wrpath=state_path / "stats_prewinrate.csv",
    )
    final_ranks.to_csv(state_path / "stats_postnormalized.csv", index=False, encoding="utf-8")
    rank_dict = rank_dict_from_frame(final_ranks)
    save_elos(rank_dict, elos_path, key_format="composite")
    makeChangelog(rank_dict, old_elos, state_path / "changelog.txt")

    sheet_cfg = tour.get("sheet", {})
    if sheet_cfg.get("elo_storage_gid") and sheet_cfg.get("elo_storage_cell"):
        from modules.support.saveElos import saveElos

        saveElos(
            str(state_path),
            sheet_cfg["elo_storage_gid"],
            sheet_cfg.get("name", "NGM Stats Export v2"),
            sheet_cfg["elo_storage_cell"],
            str(elos_path),
        )
    return rank_dict


def old_elos_for_mvp(state_path: Path) -> dict[str, float]:
    for filename in ("mvp_current_elos.json", "elos.json"):
        path = state_path / filename
        if not path.exists():
            continue
        try:
            return load_elos(path, state_path / "ids.csv", key_format="composite")
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return {}


def get_last_tour_stats(
    state_path: Path,
    idtable: Path,
    statstable: Path,
    stats_type: str,
    selected_tour_id: str | None = None,
    selected_stats_timestamp=None,
    history_entry: dict | None = None,
) -> pd.DataFrame:
    current_stats = mini_clean(str(idtable), str(statstable), stats_type, min_games=1)
    if selected_stats_timestamp is not None:
        return current_stats[current_stats["Timestamp"] == selected_stats_timestamp]

    history_timestamp = resolve_history_stats_timestamp(current_stats, history_entry, idtable)
    if history_timestamp is not None:
        return current_stats[current_stats["Timestamp"] == history_timestamp]

    tminus_path = state_path / "stats_tminus1.csv"
    if tminus_path.exists():
        previous_stats = mini_clean(str(idtable), str(tminus_path), stats_type, min_games=1)
        last_tour = current_stats.merge(previous_stats, how="outer", indicator=True).query("_merge == 'left_only'")
        last_tour = last_tour.drop(columns=["_merge"])
        if not last_tour.empty:
            return last_tour

    latest_timestamp = current_stats["Timestamp"].max()
    return current_stats[current_stats["Timestamp"] == latest_timestamp]


def resolve_history_stats_timestamp(stats: pd.DataFrame, history_entry: dict | None, idtable: Path):
    timestamp, _matched, _expected = history_stats_timestamp_match(stats, history_entry, idtable)
    return timestamp


def history_stats_timestamp_match(stats: pd.DataFrame, history_entry: dict | None, idtable: Path):
    player_names, player_ids = history_player_keys(history_entry, idtable)
    expected_count = max(len(player_names), len(player_ids))
    if not expected_count:
        return None, 0, 0

    history_stats = filter_stats_to_history_players(stats, history_entry, idtable)
    if history_stats.empty:
        return None, 0, expected_count

    counts = history_stats.groupby("Timestamp").apply(
        lambda group: max(
            group["Player ID"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA}).dropna().nunique(),
            group["Player name"].astype(str).str.strip().str.lower().replace({"": pd.NA}).dropna().nunique(),
        )
    ).sort_values(ascending=False)
    if counts.empty:
        return None, 0, expected_count

    max_count = counts.iloc[0]
    candidates = list(counts[counts == max_count].index)
    event_time = pd.to_datetime(history_entry.get("time") if history_entry else None, errors="coerce", utc=True)
    if pd.isna(event_time):
        return candidates[-1], int(max_count), expected_count

    event_time = event_time.tz_convert("UTC").tz_localize(None)
    timestamp = min(candidates, key=lambda timestamp: abs(pd.Timestamp(timestamp) - event_time))
    return timestamp, int(max_count), expected_count


def filter_stats_to_history_players(stats: pd.DataFrame, history_entry: dict | None, idtable: Path) -> pd.DataFrame:
    player_names, player_ids = history_player_keys(history_entry, idtable)
    if not player_names and not player_ids:
        return stats

    mask = stats["Player name"].astype(str).str.strip().str.lower().isin(player_names)
    if player_ids:
        mask = mask | stats["Player ID"].astype(str).str.strip().isin(player_ids)
    return stats[mask]


def history_player_keys(history_entry: dict | None, idtable: Path) -> tuple[set[str], set[str]]:
    if not history_entry or not history_entry.get("player"):
        return set(), set()

    player_names = {str(name).strip().lower() for name in history_entry["player"] if str(name).strip()}
    player_ids = set()
    try:
        from modules.support.getAliases import getAliasesDF, getAliasesID

        aliases = getAliasesDF(str(idtable))
        for player_name in player_names:
            player_id = getAliasesID(aliases, player_name)
            if player_id is not None:
                player_ids.add(str(player_id).strip())
    except Exception:
        player_ids = set()
    return player_names, player_ids


def parse_selected_timestamp(selected_tour_id: str | None):
    if not selected_tour_id:
        return None
    parsed = pd.to_datetime(selected_tour_id, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed


def load_elo_history(state_path: Path) -> list[dict]:
    history_path = state_path / "elo_history.json"
    if not history_path.exists():
        return []
    try:
        with history_path.open(encoding="utf-8") as f:
            history = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return history if isinstance(history, list) else []


def get_history_entry(state_path: Path, selected_tour_id: str | None) -> dict | None:
    history = load_elo_history(state_path)
    if not history:
        return None
    if selected_tour_id:
        selected_key = str(selected_tour_id).strip().lower()
        for entry in history:
            if str(entry.get("tour_id", "")).strip().lower() == selected_key:
                return entry
        return None
    return history[-1]


def resolve_selected_stats_timestamp(current_stats: pd.DataFrame, selected_tour_id: str | None, history_entry: dict | None, idtable: Path | None = None):
    if history_entry and idtable is not None:
        timestamp, matched_count, expected_count = history_stats_timestamp_match(current_stats, history_entry, idtable)
        required_count = max(1, (expected_count * 3 + 3) // 4)
        if timestamp is not None and matched_count >= required_count:
            return timestamp
        tour_id = history_entry.get("tour_id") or selected_tour_id or "selected tour"
        raise ValueError(
            f"Stats rows for Challonge {tour_id} are not in stats.csv yet. "
            f"Matched {matched_count}/{expected_count} players from the bracket; need at least {required_count}. "
            "Update the stats sheet/export for that tour, then run MVPs again."
        )

    selected_timestamp = parse_selected_timestamp(selected_tour_id)
    if selected_timestamp is not None:
        return selected_timestamp
    if selected_tour_id:
        raise ValueError(f"Could not find Elo history for selected tour {selected_tour_id}. Run eloscrape first.")
    if not history_entry:
        return None

    event_time = pd.to_datetime(history_entry.get("time"), errors="coerce", utc=True)
    if pd.isna(event_time):
        return None
    event_time = event_time.tz_convert("UTC").tz_localize(None)

    timestamps = sorted(
        pd.to_datetime(current_stats["Timestamp"].dropna().drop_duplicates(), errors="coerce")
        .dropna()
        .dt.tz_localize(None)
        .tolist()
    )
    if not timestamps:
        return None
    for timestamp in timestamps:
        if timestamp >= event_time:
            return timestamp
    return timestamps[-1]


def aggregate_full_stats(stats: pd.DataFrame) -> pd.DataFrame:
    WLT = ["WIN", "LOSE", "TIE"]
    agg_dict = {
        col: "sum" if col in WLT else "max"
        for col in stats.columns
        if col != "Player ID"
    }
    return stats.groupby("Player ID").agg(agg_dict).reset_index()


def clean_stats_for_baseline(current_stats: pd.DataFrame, max_fallback_window: int, active_tours: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    six_months_ago = datetime.now() - relativedelta(months=max_fallback_window)
    year_df = current_stats[
        (current_stats["Timestamp"].dt.year > six_months_ago.year)
        | (
            (current_stats["Timestamp"].dt.year == six_months_ago.year)
            & (current_stats["Timestamp"].dt.month >= six_months_ago.month)
        )
    ]
    result_df = year_df.sort_values(["Player ID", "Timestamp"]).groupby("Player ID").tail(active_tours)
    return result_df, aggregate_full_stats(current_stats)


def old_ranks_for_mvp(
    state_path: Path,
    idtable: Path,
    statstable: Path,
    stats_type: str,
    tiers: dict,
    tier_weights: dict,
    alpha: float,
    midpoint: float,
    min_rating: float,
    max_rating: float,
    selected_stats_timestamp,
    min_games: int,
) -> dict[str, float]:
    elos_path = state_path / "elos.json"
    saved_elos = {}
    if elos_path.exists():
        try:
            saved_elos = load_elos(elos_path, idtable, key_format="composite")
        except (OSError, ValueError, json.JSONDecodeError):
            saved_elos = {}
    current_stats = mini_clean(str(idtable), str(statstable), stats_type, min_games=min_games)
    if selected_stats_timestamp is None:
        selected_stats_timestamp = current_stats["Timestamp"].max()
    baseline_stats = current_stats[current_stats["Timestamp"] < selected_stats_timestamp]
    if baseline_stats.empty:
        return saved_elos
    baseline_stats, baseline_full_stats = clean_stats_for_baseline(
        baseline_stats,
        max_fallback_window=6,
        active_tours=10,
    )
    if baseline_stats.empty:
        return saved_elos
    normalization_spec = get_normalization_spec(baseline_full_stats, stats_type)

    baseline_ranks = compute_ranks(
        baseline_stats,
        baseline_full_stats,
        normalization_spec,
        tiers,
        tier_weights,
        alpha,
        midpoint,
        min_rating,
        max_rating,
        full=False,
        isWatched=stats_type.startswith("watched"),
        isMVP=False,
    )
    return rank_dict_from_frame(baseline_ranks)


def ranks_through_timestamp(
    state_path: Path,
    idtable: Path,
    statstable: Path,
    stats_type: str,
    tiers: dict,
    tier_weights: dict,
    alpha: float,
    midpoint: float,
    min_rating: float,
    max_rating: float,
    selected_stats_timestamp,
    min_games: int,
) -> dict[str, float]:
    current_stats = mini_clean(str(idtable), str(statstable), stats_type, min_games=min_games)
    if selected_stats_timestamp is None:
        selected_stats_timestamp = current_stats["Timestamp"].max()
    selected_stats = current_stats[current_stats["Timestamp"] <= selected_stats_timestamp]
    if selected_stats.empty:
        return old_elos_for_mvp(state_path)
    selected_stats, selected_full_stats = clean_stats_for_baseline(
        selected_stats,
        max_fallback_window=6,
        active_tours=10,
    )
    if selected_stats.empty:
        return old_elos_for_mvp(state_path)
    normalization_spec = get_normalization_spec(selected_full_stats, stats_type)

    selected_ranks = compute_ranks(
        selected_stats,
        selected_full_stats,
        normalization_spec,
        tiers,
        tier_weights,
        alpha,
        midpoint,
        min_rating,
        max_rating,
        full=False,
        isWatched=stats_type.startswith("watched"),
        isMVP=False,
    )
    return rank_dict_from_frame(selected_ranks)
