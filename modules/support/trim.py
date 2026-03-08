import pandas as pd

def trim(group):
    n = len(group)
    if n < 10:
        return pd.Series({
            "avg_gr": group["guess rate"].mean(),
            "avg_uf": group["usefulness"].mean(),
            "count": n
        })
    else:
        trimmed_gr = group["guess rate"].sort_values()#.iloc[1:-1]
        trimmed_uf = group["usefulness"].sort_values()#.iloc[1:-1]
        return pd.Series({
            "avg_gr": trimmed_gr.mean(),
            "avg_uf": trimmed_uf.mean(),
            "count": n
        })
    
def get_tiers(tourType):
    if tourType.startswith("watched"):
        tiers = {
            "Tier1": ["GuessRate"],
            "Tier2": ["LivesTaken", "erigs", "avg8"]#, "SoloRigs", "rigs8"],
            # "Tier3": ["Rigs", "LivesSaved", "OfflistErigs", "RigsHit", "OfflistHit"],
            # "Tier4": ["LivesLostOnRigs", "RigsMissed", "MissedSolos", "Seven8"]
        }

        tier_weights = {
            "Tier1": 0.35,
            "Tier2": 0.65
        }
    else:
        tiers = {
            "Tier1": ["GuessRate"],
            "Tier2": ["LivesTaken", "erigs", "avg8"]
            # "Tier3": ["LivesSaved"],
            # "Tier4": ["Seven8"]
        }

        tier_weights = {
            "Tier1": 0.35,
            "Tier2": 0.65
        }

    return tiers, tier_weights

def get_normalization_spec(full_stats, tourType):
    if tourType.startswith("watched"):
        normalization_spec = {
            "GuessRate": {
                "min": 0,
                "max": 100,
                "direction": "max"
            },
            "LivesTaken": {
                "min": 0,
                "max": full_stats["Lives taken"].max(),
                "direction": "max"
            },
            "avg8": {
                "min": 1,
                "max": 8,
                "direction": "min"
            },
            "erigs": {
                "min": 0,
                "max": full_stats["erigs"].max(),
                "direction": "max"
            }
            # ,
            # "LivesSaved": {
            #     "min": 0,
            #     "max": full_stats["Lives saved"].max(),
            #     "direction": "max"
            # },
            # "MissedSolos": {
            #     "min": 0,
            #     "max": full_stats["Missed solos"].max(),
            #     "direction": "min"
            # },
            # "SoloRigs": {
            #     "min": 0,
            #     "max": full_stats["Solo rigs"].max(),
            #     "direction": "max"
            # },
            # "OfflistErigs": {
            #     "min": 0,
            #     "max": full_stats["Offlist erigs"].max(),
            #     "direction": "max"
            # },
            # "LivesLostOnRigs": {
            #     "min": 0,
            #     "max": full_stats["Lives lost on rigs"].max(),
            #     "direction": "min"
            # },
            # "rigs8": {
            #     "min": 1,
            #     "max": 8,
            #     "direction": "min"
            # },
            # "Rigs": {
            #     "min": 0,
            #     "max": full_stats["Rigs"].max(),
            #     "direction": "max"
            # },
            # "RigsHit": {
            #     "min": 0,
            #     "max": full_stats["Rigs hit"].max(),
            #     "direction": "max"
            # },
            # "OfflistHit": {
            #     "min": 0,
            #     "max": full_stats["Offlist hit"].max(),
            #     "direction": "max"
            # },
            # "RigsMissed": {
            #     "min": 0,
            #     "max": full_stats["Rigs missed"].max(),
            #     "direction": "min"
            # },
            # "Seven8": {
            #     "min": 0,
            #     "max": full_stats["7/8s"].max(),
            #     "direction": "min"
            # }
        }
    else:
        normalization_spec = {
            "GuessRate": {
                "min": 0,
                "max": 100,
                "direction": "max"
            },
            "LivesTaken": {
                "min": 0,
                "max": full_stats["Lives taken"].max(),
                "direction": "max"
            },
            "avg8": {
                "min": 1,
                "max": 8,
                "direction": "min"
            },
            "erigs": {
                "min": 0,
                "max": full_stats["erigs"].max(),
                "direction": "max"
            }
            # "LivesSaved": {
            #     "min": 0,
            #     "max": full_stats["Lives saved"].max(),
            #     "direction": "max"
            # },
            # "Seven8": {
            #     "min": 0,
            #     "max": full_stats["7/8s"].max(),
            #     "direction": "min"
            # }
        }

    return normalization_spec