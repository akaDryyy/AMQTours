import ast
from collections import Counter
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ortools.sat.python import cp_model

from data import utils
from modules.support.ortoolsLPProblem import LPProblem, TeamSolverError, integerize_ratings


class TeamSolverTests(unittest.TestCase):
    def setUp(self):
        self.players = [(f"player{i}", float(i)) for i in range(8)]

    def test_preserves_exact_decimals_when_they_fit(self):
        ratings, scaled = integerize_ratings([("a", "1.23456789"), ("b", "-2.34567891")], team_count=2)
        self.assertEqual(ratings, {"a": Decimal("1.23456789"), "b": Decimal("-2.34567891")})
        self.assertEqual(scaled, {"a": 123456789, "b": -234567891})

    def test_float_tail_averages_form_valid_teams(self):
        rates = [58.153999999999996, 73.15457142857143, 8.407142857142858, 60.0] * 6
        players = [(f"player{i}", rate) for i, rate in enumerate(rates)]
        solution = LPProblem(players, 4, [], [], 1, 3, separateT1=True)[0]
        self.assertEqual(set(solution), {name for name, _ in players})
        self.assertEqual(Counter(solution.values()), {i: 4 for i in range(6)})
        top_players = sorted(players, key=lambda p: p[1], reverse=True)[:6]
        self.assertEqual(len({solution[name] for name, _ in top_players}), 6)

    def test_adaptive_scaling_keeps_original_values_and_high_precision(self):
        players = [(f"player{i}", 58.153999999999996 + i) for i in range(32)]
        originals, scaled = integerize_ratings(players, team_count=8)
        self.assertEqual(originals["player0"], Decimal("58.153999999999996"))
        self.assertLess(sum(abs(v) for v in scaled.values()) * 40 + 256, 1 << 63)
        scale = Decimal(scaled["player1"] - scaled["player0"])
        self.assertGreaterEqual(scale, 10**9)
        self.assertLess(abs(Decimal(scaled["player0"]) / scale - originals["player0"]), Decimal("1e-9"))

    def test_zero_and_negative_values_are_supported(self):
        solution = LPProblem([("a", -2.5), ("b", 0), ("c", 0), ("d", 2.5)], 2, [], [], 1, 2)[0]
        self.assertEqual(Counter(solution.values()), {0: 2, 1: 2})
        totals = [sum(v for n, v in [("a", -2.5), ("b", 0), ("c", 0), ("d", 2.5)] if solution[n] == team) for team in (0, 1)]
        self.assertEqual(totals, [0, 0])

    def test_whitelist_blacklist_and_t1_constraints_are_preserved(self):
        solution = LPProblem(self.players, 4, [("player0", "player7")], [("player0", "player1")], 1, 2, True)[0]
        self.assertEqual(solution["player0"], solution["player1"])
        self.assertNotEqual(solution["player0"], solution["player7"])
        self.assertNotEqual(solution["player6"], solution["player7"])

    def test_conflicting_top_player_request_explains_failure(self):
        with self.assertRaisesRegex(TeamSolverError, "No valid teams.*Separate T1s"):
            LPProblem(self.players, 4, [], [("player6", "player7")], 1, 2, True)

    def test_conflicting_whitelist_blacklist_explains_failure(self):
        pair = [("player0", "player1")]
        with self.assertRaisesRegex(TeamSolverError, "No valid teams.*blacklist"):
            LPProblem(self.players, 4, pair, pair, 1, 2)

    def test_timeout_is_distinct_from_infeasible_constraints(self):
        with patch.object(cp_model.CpSolver, "Solve", return_value=cp_model.UNKNOWN):
            with self.assertRaisesRegex(TeamSolverError, "15-second limit"):
                LPProblem(self.players, 4, [], [], 1, 15)

    def test_invalid_model_status_is_reported(self):
        with patch.object(cp_model.CpSolver, "Solve", return_value=cp_model.MODEL_INVALID):
            with self.assertRaisesRegex(TeamSolverError, "MODEL_INVALID"):
                LPProblem(self.players, 4, [], [], 1, 2)

    def test_no_more_solutions_keeps_the_first_solution(self):
        solutions = LPProblem([("a", 1), ("b", 2)], 2, [], [], 2, 2)
        self.assertEqual(solutions, [{"a": 0, "b": 0}])

    def test_bad_team_sizes_are_reported(self):
        for players, size in [(self.players, 0), (self.players, 3), ([], 4)]:
            with self.subTest(size=size, players=len(players)):
                with self.assertRaisesRegex(TeamSolverError, "complete teams"):
                    LPProblem(players, size, [], [], 1, 2)

    def test_out_of_range_and_nonfinite_ratings_are_reported(self):
        with self.assertRaisesRegex(TeamSolverError, "too large"):
            integerize_ratings([("a", "1e30")])
        for value in [float("nan"), float("inf"), "invalid"]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Invalid rating"):
                    integerize_ratings([("a", value)])

    def test_team_creation_handles_empty_solver_result(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "ids.csv").write_text("Player Name,Player ID\n", encoding="utf-8")
            with patch.object(utils, "LPProblem", return_value=[]):
                with self.assertRaisesRegex(TeamSolverError, "No valid teams were returned"):
                    utils.create_teams(directory, self.players, 4, [], [], True)

    def test_ui_reports_known_solver_failure_without_traceback(self):
        root = Path(__file__).resolve().parents[1]
        module = ast.parse((root / "AMQ Host Script.py").read_text(encoding="utf-8"))
        host_class = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "AMQTourUI")
        method = next(node for node in host_class.body if isinstance(node, ast.FunctionDef) and node.name == "solve_in_background")
        namespace = {
            "MissingRatingsError": type("MissingRatingsError", (Exception,), {}),
            "MissingGuessRatesError": type("MissingGuessRatesError", (Exception,), {}),
            "TeamSolverError": TeamSolverError,
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), "solver_ui", "exec"), namespace)
        host = Mock()
        host.solve_selected_tour.side_effect = TeamSolverError("No valid teams satisfy the current requests.")
        host.after.side_effect = lambda _delay, callback: callback()
        namespace["solve_in_background"](host, {"tour_id": "watched_0_100_op"})
        host.finish_solver.assert_called_once_with(error="No valid teams satisfy the current requests.")


if __name__ == "__main__":
    unittest.main()
