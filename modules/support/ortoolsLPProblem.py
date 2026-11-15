from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from heapq import nlargest
from itertools import combinations
from os import cpu_count

from ortools.sat.python import cp_model


class TeamSolverError(ValueError):
    """A team solve failed with an actionable explanation for the host."""


def integerize_ratings(players, team_count=1):
    """Preserve decimals where possible without overflowing CP-SAT's domains."""
    ratings = {}
    decimal_places = 0
    for name, rating in players:
        try:
            value = Decimal(str(rating))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Invalid rating for {name}: {rating!r}") from exc
        if not value.is_finite():
            raise ValueError(f"Invalid rating for {name}: {rating!r}")
        ratings[name] = value
        decimal_places = max(decimal_places, max(0, -value.as_tuple().exponent))

    # CP-SAT checks all variable domains, not just individual coefficients.
    # Leave room for team totals, min/max totals, and constraint arithmetic.
    safe_total = ((1 << 63) - 1 - len(ratings) * team_count) // (4 * (team_count + 2))
    magnitude = sum(abs(value) for value in ratings.values())
    if magnitude > safe_total:
        raise TeamSolverError("Ratings are too large for team balancing. Check the entered values.")
    if magnitude:
        decimal_places = min(decimal_places, max(0, Decimal(safe_total).adjusted() - magnitude.adjusted()))
    else:
        decimal_places = 0
    while True:
        scaled_ratings = {
            name: int(value.scaleb(decimal_places).to_integral_value(rounding=ROUND_HALF_EVEN))
            for name, value in ratings.items()
        }
        if sum(abs(value) for value in scaled_ratings.values()) <= safe_total:
            break
        decimal_places -= 1
    return ratings, scaled_ratings


def LPProblem(players, team_size, blacklist, whitelist, max_solutions, time_limit_seconds, separateT1=False):
    found_solutions = []
    if not players or team_size <= 0 or len(players) % team_size:
        raise TeamSolverError("Add enough players to form complete teams of the selected size.")
    k = len(players) // team_size

    p_names = [name for name, _rating in players]
    p_values, scaled_values = integerize_ratings(players, team_count=k)
    model = cp_model.CpModel()
    assignments = {
        (name, team): model.NewBoolVar(f"assign_{name}_{team}")
        for name in p_names
        for team in range(k)
    }

    for name in p_names:
        model.Add(sum(assignments[name, team] for team in range(k)) == 1)
    for team in range(k):
        model.Add(sum(assignments[name, team] for name in p_names) == team_size)

    for first, second in blacklist:
        if first in p_values and second in p_values:
            for team in range(k):
                model.Add(assignments[first, team] + assignments[second, team] <= 1)

    if separateT1:
        top_players = nlargest(k, p_values, key=p_values.get)
        for first, second in combinations(top_players, 2):
            for team in range(k):
                model.Add(assignments[first, team] + assignments[second, team] <= 1)

    for first, second in whitelist:
        if first in p_values and second in p_values:
            for team in range(k):
                model.Add(assignments[first, team] == assignments[second, team])

    lower_total = sum(value for value in scaled_values.values() if value < 0)
    upper_total = sum(value for value in scaled_values.values() if value > 0)
    totals = []
    for team in range(k):
        total = model.NewIntVar(lower_total, upper_total, f"total_{team}")
        model.Add(total == sum(assignments[name, team] * scaled_values[name] for name in p_names))
        totals.append(total)

    maximum_total = model.NewIntVar(lower_total, upper_total, "max_sum")
    minimum_total = model.NewIntVar(lower_total, upper_total, "min_sum")
    model.AddMaxEquality(maximum_total, totals)
    model.AddMinEquality(minimum_total, totals)
    model.Minimize(maximum_total - minimum_total)

    validation_error = model.Validate()
    if validation_error:
        raise TeamSolverError(f"The team solver rejected the rating model: {validation_error}")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = min(8, cpu_count() or 1)
    optimal_value = None

    for _ in range(max_solutions):
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if not found_solutions:
                if status == cp_model.INFEASIBLE:
                    raise TeamSolverError(
                        "No valid teams satisfy the current requests. Check whitelist/team requests, "
                        "blacklist restrictions, and Separate T1s."
                    )
                if status == cp_model.UNKNOWN:
                    raise TeamSolverError(
                        f"No teams were found within the {float(time_limit_seconds):g}-second limit. "
                        "Try again or relax team requests/Separate T1s."
                    )
                raise TeamSolverError(f"Team balancing failed ({solver.StatusName(status)}). Check the entered ratings and team settings.")
            break

        current_value = solver.Value(maximum_total) - solver.Value(minimum_total)
        if optimal_value is None:
            optimal_value = current_value
            model.Add(maximum_total - minimum_total == optimal_value)
        elif current_value != optimal_value:
            break

        solution = {}
        for name in p_names:
            for team in range(k):
                if solver.Value(assignments[name, team]):
                    solution[name] = team
                    break
        found_solutions.append(solution)
        model.Add(sum(assignments[name, team] for name, team in solution.items()) <= len(p_names) - 1)

    return found_solutions
