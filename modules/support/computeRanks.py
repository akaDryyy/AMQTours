import numpy as np

def spread_lower_tail(elo, knee=9.0, gamma=1.6, cap=25.0):
        """
        - elo: array/Series of current scores
        - knee: values >= knee are left unchanged
        - gamma > 1 spreads values in [0, knee) downward (more variety in 0–8)
        - cap: optional max to clip at the top end
        """
        elo = np.asarray(elo, dtype=float)
        below = elo < knee
        out = elo.copy()
        # map [0, knee) -> [0, knee) with f(0)=0, f(knee)=knee
        out[below] = knee * (elo[below] / knee) ** gamma
        if cap is not None:
            out = np.clip(out, 0, cap)
        return out

def compute_ranks(df, gr_max=100, uf_max=30, alpha=3.75, midpoint=0.30, min_score=0, max_score=25, GR_weight=0.35, spread=False):
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

    # Normalize guess rate and usefulness
    df["norm_gr"] = df["avg_gr"] / gr_max
    df["norm_uf"] = df["avg_uf"] / uf_max

    # Clip values to avoid weird outliers
    df["norm_gr"] = df["norm_gr"].clip(0, 1)
    df["norm_uf"] = df["norm_uf"].clip(0, 1)

    # Combine into a single raw score (equal weighting)
    UF_weight = 1 - GR_weight
    df["raw_score"] = GR_weight * df["norm_gr"] + UF_weight * df["norm_uf"]

    # Apply sigmoid transformation
    sigmoid_vals = 1 / (1 + np.exp(-alpha * (df["raw_score"] - midpoint)))
    df["elo"] = min_score + (max_score - min_score) * sigmoid_vals

    if spread:
        df["elo"] = spread_lower_tail(df["elo"], knee=9.0, gamma=1.6, cap=max_score)

    return df