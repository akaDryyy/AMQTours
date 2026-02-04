from pulp import *
from copy import deepcopy

def LPProblem(players, team_size, blacklist, whitelist, max_solutions, think_time):
    found_solutions = []
    optimal_value = None
    nums = [val for _, val in players]
    # Number of teams
    k = int(len(nums) / team_size)
    p_names = [p[0] for p in players]
    p_values = {p[0]: p[1] for p in players}

    # LP Problem
    prob = LpProblem("TeamPartitions", LpMinimize)

    # Decision variables: x[name][partition] = 1 if player is in that partition
    x = LpVariable.dicts("assign", (p_names, range(k)), 0, 1, LpBinary)

    # Variables for max and min partition sums
    z = LpVariable("max_sum", lowBound=0)
    y = LpVariable("min_sum", lowBound=0)

    # Constraint: Each player assigned to one partition
    for name in p_names:
        prob += lpSum(x[name][p] for p in range(k)) == 1

    # Constraint: Each partition gets exact group size
    for p in range(k):
        prob += lpSum(x[name][p] for name in p_names) == team_size

    # Constraint: Blacklisted pairs not in the same partition
    for a, b in blacklist:
        if a in p_names and b in p_names:
            for p in range(k):
                prob += x[a][p] + x[b][p] <= 1
        else:
            pass

    # Constraint: Whitelisted pairs in the same partition
    for a, b in whitelist:
        if a in p_names and b in p_names:
            for p in range(k):
                prob += x[a][p] == x[b][p], f"whitelist_same_partition_{a}_{b}_{p}"
        else:
            pass

    # Partition totals
    totals = [lpSum(x[name][p] * p_values[name] for name in p_names) for p in range(k)]

    for total in totals:
        prob += z >= total
        prob += y <= total

    # Objective: minimize max_sum - min_sum
    prob += z - y

    # Solve. Edit maxNodes to reduce thinking time
    for s in range(max_solutions):
        prob.solve(PULP_CBC_CMD(maxNodes=think_time))

        if prob.status != 1:
            break

        # Store the value of the optimal objective
        if optimal_value is None:
            optimal_value = value(prob.objective)
        elif abs(value(prob.objective) - optimal_value) > 1e-5:
            break  # This solution is worse

        # Get current solution
        solution = {}
        for name in p_names:
            for p in range(k):
                if value(x[name][p]) == 1:
                    solution[name] = p

        found_solutions.append(deepcopy(solution))

        # Add exclusion constraint: prevent same assignment
        prob += lpSum([x[name][p] for name, p in solution.items()]) <= len(p_names) - 1

    return found_solutions