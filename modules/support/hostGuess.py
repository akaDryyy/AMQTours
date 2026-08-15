from __future__ import annotations


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
