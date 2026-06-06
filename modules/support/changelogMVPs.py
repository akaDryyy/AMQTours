def makeChangelog(rank_dict, old_elos, changelog_path):
    old_by_id = {id_val: (name, elo) for (id_val, name), elo in old_elos.items()}

    elo_diff = {}

    for (p_id, p_name), new_elo in rank_dict.items():
        if p_id in old_by_id:
            old_name, old_elo = old_by_id[p_id]

            old_elo_f = float(old_elo)
            new_elo_f = float(new_elo)
            diff = round(new_elo_f - old_elo_f, 3)

            if abs(diff) >= 0.15:
                elo_diff[(p_id, p_name)] = {
                    "initial rank": round(old_elo_f, 3),
                    "new rank": round(new_elo_f, 3),
                    "rating_change": diff,
                }

    elo_diff_str = "\n".join(
        f"{name}, old rank: {data['initial rank']}, new rank: {data['new rank']}, diff: {data['rating_change']}"
        for (pid, name), data in sorted(
            elo_diff.items(), key=lambda x: -x[1]["rating_change"]
        )
    )

    with open(changelog_path, "w") as f:
        f.write(elo_diff_str)

def makeMVPs(last_tour_dict, old_old_elos, mvps_path):
    old_by_id = {p_id: old_elo for (p_id, name), old_elo in old_old_elos.items()}

    diff = {}
    for (p_id, p_name), new_elo in last_tour_dict.items():
        old_elo = old_by_id.get(p_id, new_elo)

        diff[(p_id, p_name)] = {
            "old": old_elo,
            "new": new_elo,
            "diff": round(new_elo - old_elo, 3),
        }

    sorted_diff = sorted(
        diff.items(), key=lambda item: item[1]["diff"], reverse=True
    )
    top_3 = sorted_diff[:3]

    with open(mvps_path, "w", encoding="utf-8") as f:
        f.write("# Full PV List:\n")
        for (pid, name), data in sorted_diff:
            f.write(
                f"ID: {pid} | {name} played like a {data['new']}. (Current rank {data['old']}, Δ{data['diff']})\n"
            )

        f.write("\n# MVPS:\n")
        (f_id, f_name), fpdata = top_3[0]
        (s_id, s_name), spdata = top_3[1]
        (t_id, t_name), tpdata = top_3[2]

        f.write(
            f":first_place: {f_name}. Played like a {fpdata['new']} rank (Current Rank: {fpdata['old']}, Δ{fpdata['diff']})\n"
        )
        f.write(
            f":second_place: ID: {s_name}. Played like a {spdata['new']} rank (Current Rank: {spdata['old']}, Δ{spdata['diff']})\n"
        )
        f.write(
            f":third_place: ID: {t_name}. Played like a {tpdata['new']} rank (Current Rank: {tpdata['old']}, Δ{tpdata['diff']})\n"
        )