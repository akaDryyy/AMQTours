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