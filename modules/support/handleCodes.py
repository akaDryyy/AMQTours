def handleCodes(
        foundSolutions,
        p_values,
        k,
        get_guesses,
        kwargs_guesses=None,
        get_codes=None,
        gamemode=None,
        gr_based=False
        ):
    
    for idx, sol in enumerate(foundSolutions, 1):
        print(f"\n### Solution {idx} ###")
        team_map = [[] for _ in range(k)]
        for name, p in sol.items():
            team_map[p].append((name, p_values[name]))

        for i, team in enumerate(team_map):
            members = " ".join(f"{n} ({v:.3f})" for n, v in sorted(team, key=lambda x: x[1], reverse=True))
            total = sum(v for _, v in team)
            print(f"{members} | Total = {total:.3f}")

    txtvar = ""

    header = f"{'#'*25} Discord {'#'*25}\n"
    print(header)
    txtvar += header
    txtvar += "\n"
    for idx, sol in enumerate(foundSolutions, 1):
        sol_msg = f"### Solution {idx} ###\n\n"
        print(sol_msg)
        txtvar += sol_msg
        team_map = [[] for _ in range(k)]
        for name, p in sol.items():
            team_map[p].append((name, p_values[name]))
        avg = 0
        for i, team in enumerate(team_map):
            members = " ".join(f"{n} ({v:.3f})" for n, v in sorted(team, key=lambda x: x[1], reverse=True))
            if gr_based:
                guess_str = "".join(get_guesses(name, **kwargs_guesses) for name, _ in sorted(team, key=lambda x: x[1], reverse=True))
            else:
                guess_str = "".join(get_guesses(val) for _, val in sorted(team, key=lambda x: x[1], reverse=True))
            total = sum(v for _, v in team)
            team_msg = f"{members} | Total = {total:.3f} | Guesses = [{guess_str}]\n"
            print(team_msg)
            txtvar += team_msg
            avg += round(total, 4)
        txtvar += "\n"
        print()

    try:
        footer = f"Average: {round(avg / k, 4)}\n"
    except UnboundLocalError:
        input("Someone is missing their rating. Try to add to ranks.txt and run again. Press Enter to exit.")
        exit()
    print(footer)
    txtvar += footer

    if gamemode:
        final_code = get_codes(gamemode, txtvar)
    else:
        final_code = get_codes(txtvar)

    return final_code