def makeChangelog(rank_dict, old_elos, changelo_path):
    elo_diff = {
        player: {
            "initial rank": round(float(old_elos[player]), 3),
            "new rank": round(float(rank_dict[player]), 3),
            "rating_change": round(float(rank_dict[player]) - float(old_elos[player]), 3)
        }
        for player in old_elos
        if player in rank_dict and (abs(float(rank_dict[player]) - float(old_elos[player])) >= 0.01)
    }

    elo_diff_str = "\n".join(
        f"{player}, old rank: {data['initial rank']}, new rank: {data['new rank']}, diff: {data['rating_change']}"
        for player, data in sorted(
            elo_diff.items(), key=lambda x: -x[1]["rating_change"]
        )
    )

    with open(changelo_path, "w") as f:
        f.write(elo_diff_str)

def makeMVPs(last_tour_dict, old_old_elos, mvps_path):
    diff = {}
    for player, new_elo in last_tour_dict.items():
        old_elo = old_old_elos.get(player)
        if old_elo is None:
            old_elo = new_elo
        diff[player] = {
            'old': old_elo,
            'new': new_elo,
            'diff': round(new_elo - old_elo, 3)
        }

    sorted_diff = sorted(diff.items(), key=lambda item: item[1]['diff'], reverse=True)
    top_3 = sorted_diff[:3]

    with open(mvps_path, "w", encoding="utf-8") as f:
        f.write("# Full PV List:\n")
        for player, data in sorted_diff:
            f.write(f"{player} played like a {data['new']}. (Current rank {data['old']}, Δ{data['diff']})\n")
        f.write("\n# MVPS:\n")
        first, fpdata = top_3[0]
        second, spdata = top_3[1]
        third, tpdata = top_3[2]
        f.write(f":first_place: {first}. Played like a {fpdata['new']} rank (Current Rank: {fpdata['old']}, Δ{fpdata['diff']})\n")
        f.write(f":second_place: {second}. Played like a {spdata['new']} rank (Current Rank: {spdata['old']}, Δ{spdata['diff']})\n")
        f.write(f":third_place: {third}. Played like a {tpdata['new']} rank (Current Rank: {tpdata['old']}, Δ{tpdata['diff']})\n")