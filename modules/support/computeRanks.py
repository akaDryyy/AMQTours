import numpy as np

def normalize_stats(df, normalization_specs):
    df_norm = df.copy()

    for column in normalization_specs:
        spec = normalization_specs[column]
        min_val = spec.get("min", 0)
        max_val = spec.get("max", 1)
        direction = spec.get("direction", "max")
        
        norm = (df_norm[column] - min_val) / (max_val - min_val)
        norm = norm.clip(0, 1)

        if direction == "min":
            norm = 1 - norm
        
        df_norm[column] = norm
    
    return df_norm

def compute_rank_scores(df, alpha, midpoint, minRating, maxRating):
    df["ELO"] = maxRating / (1 + np.exp(-alpha * (df["RANK"] - midpoint)))
    return df

def compute_ranks(clean_stats, full_stats, normalization_spec, tiers, tier_weights, 
                  alpha=3.75, midpoint=0.4, minRating=0, maxRating=25,
                  full=True, path=None, isWatched = True, wrpath=None):
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
    if isWatched:
        player_stats = (
            clean_stats
            .groupby("Player ID", as_index=False)
            .agg(
                PlayerName=("Player name", "last"),
                GuessRate=("Guess rate", "mean"),
                erigs=("erigs", "mean"),
                Seven8=("7/8s", "mean"),
                avg8=("avg/8", "mean"),
                LivesTaken=("Lives taken", "mean"),
                LivesSaved=("Lives saved", "mean"),
                WIN=("WIN", "sum"),
                LOSE=("LOSE", "sum"),
                TIE=("TIE", "sum"),
                RigsHit=("Rigs hit", "mean"),
                OfflistHit=("Offlist hit", "mean"),
                Rigs=("Rigs", "mean"),
                RigsMissed=("Rigs missed", "mean"),
                SoloRigs=("Solo rigs", "mean"),
                MissedSolos=("Missed solos", "mean"),
                LivesLostOnRigs=("Lives lost on rigs", "mean"),
                OfflistErigs=("Offlist erigs", "mean"),
                rigs8=("avg/8 of your rigs", "mean"),
                Samples=("Usefulness", "size")
            )
        )
    else:
        player_stats = (
        clean_stats
        .groupby("Player ID", as_index=False)
        .agg(
            PlayerName=("Player name", "last"),
            GuessRate=("Guess rate", "mean"),
            erigs=("erigs", "mean"),
            Seven8=("7/8s", "mean"),
            avg8=("avg/8", "mean"),
            LivesTaken=("Lives taken", "mean"),
            LivesSaved=("Lives saved", "mean"),
            WIN=("WIN", "sum"),
            LOSE=("LOSE", "sum"),
            TIE=("TIE", "sum"),
            Samples=("Usefulness", "size")
        )
    )

    if full:
        player_stats = player_stats.round(3)
        player_stats.to_csv(path, index=False, encoding="utf-8")

    stats = list(normalization_spec.keys())
    weights = {}
    for tier_name, stat_list in tiers.items():
        n = len(stat_list)
        for stat in stat_list:
            weights[stat] = tier_weights[tier_name] / n

    final_ranks = normalize_stats(player_stats, normalization_spec)
    final_ranks["RANK"]  = final_ranks.apply(lambda row: sum(row[stat]*weights[stat] for stat in stats), axis=1)
    final_ranks["WIN"] = final_ranks["Player ID"].map(full_stats.set_index("Player ID")["WIN"])
    final_ranks["LOSE"] = final_ranks["Player ID"].map(full_stats.set_index("Player ID")["LOSE"])
    final_ranks["TIE"] = final_ranks["Player ID"].map(full_stats.set_index("Player ID")["TIE"])
    final_ranks["WINSTREAK"] = final_ranks["Player ID"].map(player_stats.set_index("Player ID")["WIN"])
    final_ranks["LOSESTREAK"] = final_ranks["Player ID"].map(player_stats.set_index("Player ID")["LOSE"])
    final_ranks["TIESTREAK"] = final_ranks["Player ID"].map(player_stats.set_index("Player ID")["TIE"])
    final_ranks.insert(2, "RANK", final_ranks.pop("RANK"))
    final_ranks = compute_rank_scores(final_ranks, alpha, midpoint, minRating, maxRating)
    final_ranks.insert(2, "ELO", final_ranks.pop("ELO"))
    
    if full:
        final_ranks = final_ranks.round(3)
        final_ranks.to_csv(wrpath, index=False, encoding="utf-8")

    # WR + Streak accounting
    final_ranks["PALL"] = final_ranks["WIN"] + final_ranks["LOSE"] + final_ranks["TIE"]
    final_ranks["PRECENT"] = final_ranks["WINSTREAK"] + final_ranks["LOSESTREAK"] + final_ranks["TIESTREAK"]
    final_ranks["WR"] = (final_ranks["WIN"] + 0.5 * final_ranks["TIE"]) / final_ranks["PALL"]
    final_ranks["STREAK"] = (final_ranks["WINSTREAK"] + 0.5 * final_ranks["TIESTREAK"]) / final_ranks["PRECENT"]
    final_ranks["DELTAWR"] =  final_ranks["STREAK"] - final_ranks["WR"]
    final_ranks["WR MODIFIER"] = np.where(
        final_ranks["PALL"] > 30,
        final_ranks["WR"] - 0.5,
        0.0
    )
    final_ranks["STREAK MODIFIER"] = 0.5 * np.maximum(0, final_ranks["DELTAWR"]) ** 2
    confidence = np.log1p(final_ranks["PALL"]) / np.log1p(final_ranks["PALL"].max())
    final_ranks["STREAK MODIFIER"] *= confidence
    final_ranks["WR MODIFIER"] *= confidence
    final_ranks["FINALELO"] = final_ranks["ELO"] * (1 + final_ranks["WR MODIFIER"] + final_ranks["STREAK MODIFIER"])
    final_ranks.insert(3, "STREAK MODIFIER", final_ranks.pop("STREAK MODIFIER"))
    final_ranks.insert(3, "WR MODIFIER", final_ranks.pop("WR MODIFIER"))
    final_ranks.insert(3, "FINALELO", final_ranks.pop("FINALELO"))
    final_ranks = final_ranks.round(3)
    final_ranks = final_ranks.sort_values(by='ELO', ascending=False)

    return final_ranks