from __future__ import annotations


ERU_RATE_OPTIONS = ("Average GR", "OP", "ED", "IN", "OPED", "EDIN", "OPIN")
ERU_RATE_COLUMNS = {
    "Average GR": ("Guess rate",),
    "OP": ("OP guess rate",),
    "ED": ("ED guess rate",),
    "IN": ("IN guess rate",),
    "OPED": ("OP guess rate", "ED guess rate"),
    "EDIN": ("ED guess rate", "IN guess rate"),
    "OPIN": ("OP guess rate", "IN guess rate"),
}


def eru_fallback_config(tour):
    """Return the fallback tour and rate source allowed for a selected Eru tour."""
    tour_id = tour["id"]
    excluded = {"usual", "watched", "usual_house", "watched_house", "random_chanting", "watched_x_2009", "watched_2_8", "watched_5s"}
    if tour_id in excluded:
        return None
    if "oped" in tour_id:
        rate_source = "OPED"
    elif "ins" in tour_id:
        rate_source = "IN"
    elif tour_id.endswith("_op"):
        rate_source = "OP"
    elif tour_id.endswith("_ed"):
        rate_source = "ED"
    else:
        rate_source = "Average GR"
    if tour["group"] == "Random":
        return {"tour_id": "usual", "rate_source": rate_source, "label": "Attempt to use Usual stats for players without data"}
    if tour["group"] == "Watched":
        return {"tour_id": "watched", "rate_source": rate_source, "label": "Attempt to use Watched stats for players without data"}
    return None


class MissingGuessRatesError(ValueError):
    def __init__(self, names):
        self.names = names
        super().__init__(
            "Missing guess-rate data for: "
            + ", ".join(names)
            + ". Enter a manual guess rate for these players, then try Eru Mode again."
        )


def _player_rate_averages(player_stats, idtable, rate_source):
    import pandas as pd

    columns = ERU_RATE_COLUMNS.get(rate_source)
    if columns is None:
        raise ValueError(f"Unknown Eru guess-rate source: {rate_source}")
    aliases = pd.read_csv(idtable, dtype=str).fillna("")
    aliases["Player Name"] = aliases["Player Name"].str.strip().str.lower()
    player_ids = dict(zip(aliases["Player Name"], aliases["Player ID"].str.strip()))
    stats = player_stats.copy()
    stats["Player ID"] = stats["Player ID"].astype(str).str.strip()
    averages = {}
    for player_id, group in stats.groupby("Player ID"):
        values = []
        for column in columns:
            if column not in group:
                values = []
                break
            value = pd.to_numeric(group[column], errors="coerce").mean()
            if pd.isna(value):
                values = []
                break
            values.append(float(value))
        if values:
            averages[str(player_id)] = sum(values) / len(values)
    return player_ids, averages


def player_guess_rates(names, player_stats, idtable, rate_source="Average GR", fallback=None, manual_rates=None):
    """Resolve rates from the primary source, an allowed fallback, then manual values."""
    player_ids, averages = _player_rate_averages(player_stats, idtable, rate_source)
    fallback_ids, fallback_averages = ({}, {})
    if fallback is not None:
        fallback_stats, fallback_idtable, fallback_source = fallback
        fallback_ids, fallback_averages = _player_rate_averages(fallback_stats, fallback_idtable, fallback_source)
    manual_rates = {name.strip().lower(): float(value) for name, value in (manual_rates or {}).items()}

    rates, missing = {}, []
    for name in names:
        normalized_name = name.strip().lower()
        player_id = player_ids.get(normalized_name)
        guess_rate = averages.get(player_id)
        if guess_rate is None:
            guess_rate = fallback_averages.get(fallback_ids.get(normalized_name))
        if guess_rate is None:
            guess_rate = manual_rates.get(normalized_name)
        if guess_rate is None:
            missing.append(name)
        else:
            rates[name] = float(guess_rate)
    if missing:
        raise MissingGuessRatesError(missing)
    return rates


def guess_gr(thresholds, avg_gr):
    if avg_gr:
        for threshold, result in thresholds:
            if avg_gr >= threshold:
                return result
    return "x"


def player_average_gr(name, player_stats, idtable):
    import pandas as pd

    try:
        alias_df = pd.read_csv(idtable)
        alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
        player_id = alias_df.loc[alias_df["Player Name"] == name, "Player ID"].iloc[0]
        avg_gr = player_stats.loc[player_stats["Player ID"] == player_id, "Guess rate"].mean()
        if pd.isna(avg_gr):
            avg_gr = None
    except IndexError:
        avg_gr = None
    return avg_gr


def get_guess_watched_ui(name, player_stats, idtable, oneg, twog, threeg, fourg):
    avg_gr = player_average_gr(name, player_stats, idtable)
    return guess_gr([(fourg, "5"), (threeg, "4"), (twog, "3"), (oneg, "2"), (-float("inf"), "1")], avg_gr)


def get_guess_random_ui(name, player_stats, idtable, oneg, twog, threeg):
    avg_gr = player_average_gr(name, player_stats, idtable)
    return guess_gr([(threeg, "4"), (twog, "3"), (oneg, "2"), (-float("inf"), "1")], avg_gr)


def get_guess_watched_28_ui(name, player_stats, idtable, zerog, oneg, twog, threeg, fourg):
    avg_gr = player_average_gr(name, player_stats, idtable)
    return guess_gr([(fourg, "5"), (threeg, "4"), (twog, "3"), (oneg, "2"), (zerog, "1"), (-float("inf"), "0")], avg_gr)


GUESS_HANDLERS = {
    "random": get_guess_random_ui,
    "random5g": get_guess_watched_ui,
    "watched": get_guess_watched_ui,
    "watched_28": get_guess_watched_28_ui,
}
