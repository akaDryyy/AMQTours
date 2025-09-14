import os
import json

oldmonth = os.path.abspath("2025-08-01.json")
newmonth = os.path.abspath("2025-09-01.json")
changelog = os.path.abspath("monthly_improvements.txt")
changelogdelta = os.path.abspath("monthly_improvements_deltas.txt")

with open(oldmonth, 'r') as f:
    old_elos = json.load(f)

with open(newmonth, 'r') as f:
    new_elos = json.load(f)

elo_diff = {
        player: {
            "initial rank": round(float(old_elos[player]), 3),
            "new rank": round(float(new_elos[player]), 3),
            "rating_change": round(float(new_elos[player]) - float(old_elos[player]), 3)
        }
        for player in old_elos
        if player in new_elos and float(new_elos[player]) - float(old_elos[player]) != 0
    }

elo_diff_str = "\n".join(
    f"{player}, Last month elo: {data['initial rank']}, this month elo: {data['new rank']}, diff: {data['rating_change']}"
    for player, data in sorted(
        elo_diff.items(), key=lambda x: -x[1]["initial rank"]
    )
)

elo_diff_str_delta = "\n".join(
    f"{player}, Last month elo: {data['initial rank']}, this month elo: {data['new rank']}, diff: {data['rating_change']}"
    for player, data in sorted(
        elo_diff.items(), key=lambda x: -x[1]["rating_change"]
    )
)

with open(changelog, "w") as f:
    f.write(elo_diff_str)

with open(changelogdelta, "w") as f:
    f.write(elo_diff_str_delta)