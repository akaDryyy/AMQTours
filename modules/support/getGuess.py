import pandas as pd

def guess_gr(thresholds, avg_gr):
    for threshold, result in thresholds:
        if avg_gr >= threshold:
            return result

def make_guess_function(thresholds):
    def guess(val):
        for threshold, result in thresholds:
            if val >= threshold:
                return result
    return guess

def get_guess_usual_gr(name, player_stats, idtable, oneg, twog, threeg):
    try:
        alias_df = pd.read_csv(idtable)
        alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
        player_id = alias_df.loc[alias_df["Player Name"] == name, 'Player ID'].iloc[0]
        avg_gr = player_stats.loc[player_stats["Player ID"] == player_id, 'avg_gr'].iloc[0]
    except IndexError:
        avg_gr = float(input(f"{name} not found. Give initial gr% (Example: 75 = 75%): "))
    return guess_gr([
        (threeg, '4'),
        (twog, '3'),
        (oneg, '2'),
        (-float('inf'), '1')
    ], avg_gr)

get_guess_usual = make_guess_function([
    (9, '4'),
    (5.75, '3'),
    (3.5, '2'),
    (-float('inf'), '1')
])

get_guess_old_usual = make_guess_function([
    (8.5, '4'),
    (4.5, '3'),
    (0.5, '2'),
    (-float('inf'), '1')
])

get_guess_watched = make_guess_function([
    (8.75, '5'),
    (8, '4'),
    (7, '3'),
    (6, '2'),
    (-float('inf'), '1')
])

get_guess_watched_in = make_guess_function([
    (11, '5'),
    (9, '4'),
    (7, '3'),
    (-float('inf'), '2')
])

get_guess_watched_cl = make_guess_function([
    (8.75, '5'),
    (8, '4'),
    (7, '3'),
    (6, '2'),
    (-float('inf'), '1')
])

get_guess_watched_5s = make_guess_function([
    (10.5, '5'),
    (7.5, '4'),
    (6, '3'),
    (3.5, '2'),
    (-float('inf'), '1')
])

get_guess_old_watched = make_guess_function([
    (8.5, '5'),
    (7, '4'),
    (5.5, '3'),
    (3.5, '2'),
    (-float('inf'), '1')
])
    
get_guess_op = make_guess_function([
    (10, '4'),
    (8, '3'),
    (5.5, '2'),
    (-float('inf'), '1')
])
    
get_guess_op_old = make_guess_function([
    (9, '4'),
    (5, '3'),
    (1, '2'),
    (-float('inf'), '1')
])

get_guess_ed = make_guess_function([
    (10, '4'),
    (8, '3'),
    (5.5, '2'),
    (-float('inf'), '1')
])
  
get_guess_ed_old = make_guess_function([
    (9, '4'),
    (5, '3'),
    (1, '2'),
    (-float('inf'), '1')
])

get_guess_in = make_guess_function([
    (10, '4'),
    (8, '3'),
    (5.5, '2'),
    (-float('inf'), '1')
])
  
get_guess_in_old = make_guess_function([
    (9, '4'),
    (5, '3'),
    (1, '2'),
    (-float('inf'), '1')
])

get_guess_cl = make_guess_function([
    (10, '4'),
    (6, '3'),
    (3.5, '2'),
    (-float('inf'), '1')
])