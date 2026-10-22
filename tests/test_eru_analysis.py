import json
import unittest

from modules.main.eruAnalysis import (
    Condition, Filters, PlayerIdentities, calculate, column_letter, condition_expression, eru_list,
    header_columns, player_names, unpack_row,
)


class EruAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.identities = PlayerIdentities(
            [["Player Name", "Player ID"], ["Main_Name", "1"], ["OldName", "1"], ["Other", "2"]],
            ["Main_Name\tAnotherAlias"],
        )

    def row(self, **changes):
        row = {
            "mode": "Watched FL", "songs": "[1, 2, 3]",
            "year": '["Spring 2000", "Winter 2020", "unknown"]',
            "tags": '[["Isekai"], ["School"], []]',
            "genres": '[["Fantasy"], ["Drama"], ["Fantasy"]]',
            "correct": '[["OldName", "Main_Name"], [{"name": "Other", "answerTime": 3.1}], []]',
            "wrong": '[["AnotherAlias", "Other"], ["mainname"], ["OldName", "Other"]]',
        }
        row.update(changes)
        return row

    def test_all_encounters_and_aliases(self):
        songs = unpack_row(self.row(), self.identities)
        totals, count, mode_count = calculate(songs, Filters("watched"))
        self.assertEqual(totals, {"id:1": [3, 1], "id:2": [3, 1]})
        self.assertEqual((count, mode_count), (3, 3))

    def test_inclusive_or_does_not_double_count_overlap(self):
        songs = unpack_row(self.row(), self.identities)
        totals, count, _ = calculate(songs, Filters("watched", frozenset(["isekai"]), frozenset(["Fantasy"])))
        self.assertEqual(count, 2)
        self.assertEqual(totals["id:1"], [2, 1])

    def test_genre_only_and_tag_only(self):
        songs = unpack_row(self.row(), self.identities)
        self.assertEqual(calculate(songs, Filters("watched", genres=frozenset(["Drama"])))[0]["id:2"], [1, 1])
        self.assertEqual(calculate(songs, Filters("watched", tags=frozenset(["School", "Isekai"])))[1], 2)

    def test_and_requires_every_selected_genre_and_tag(self):
        songs = unpack_row(self.row(), self.identities)
        self.assertEqual(calculate(songs, Filters("watched", frozenset(["Isekai"]), frozenset(["Fantasy"]), match_mode="AND"))[1], 1)
        self.assertEqual(calculate(songs, Filters("watched", tags=frozenset(["School", "Isekai"]), match_mode="AND"))[1], 0)
        self.assertEqual(calculate(songs, Filters("watched", genres=frozenset(["Fantasy"]), match_mode="AND"))[1], 2)
        self.assertEqual(calculate(songs, Filters("watched", match_mode="AND"))[1], 3)

    def test_mixed_links_and_visible_expression(self):
        conditions = (Condition("genres", "Fantasy"), Condition("tags", "Isekai", "AND"), Condition("tags", "School", "OR"))
        songs = unpack_row(self.row(), self.identities)
        totals, count, _ = calculate(songs, Filters("watched", conditions=conditions))
        self.assertEqual(count, 2)
        self.assertEqual(totals["id:1"], [2, 1])
        self.assertEqual(condition_expression(conditions), '(Genre "Fantasy" AND Tag "Isekai") OR Tag "School"')

    def test_and_precedence_not_left_to_right(self):
        conditions = (Condition("genres", "Fantasy"), Condition("tags", "School", "OR"), Condition("tags", "Missing", "AND"))
        songs = unpack_row(self.row(), self.identities)
        self.assertEqual(calculate(songs, Filters("watched", conditions=conditions))[1], 2)
        self.assertEqual(condition_expression(conditions), 'Genre "Fantasy" OR (Tag "School" AND Tag "Missing")')

    def test_conditions_validate_and_empty_matches_all(self):
        for args in (("year", "2000"), ("genres", ""), ("tags", "Isekai", "XOR")):
            with self.assertRaises(ValueError):
                Condition(*args)
        self.assertEqual(condition_expression(()), "All songs")
        self.assertEqual(calculate(unpack_row(self.row(), self.identities), Filters("watched", conditions=()))[1], 3)

    def test_year_inclusive_and_unknown_year_excluded(self):
        songs = unpack_row(self.row(), self.identities)
        self.assertEqual(calculate(songs, Filters("watched", start_year=2000, end_year=2020))[1], 2)
        self.assertEqual(calculate(songs, Filters("watched", end_year=2000))[1], 1)
        self.assertEqual(calculate(songs, Filters("watched", start_year=2020))[1], 1)

    def test_modes_do_not_leak(self):
        songs = unpack_row(self.row(), self.identities)
        for mode in ("usual", "watched_draft", "watched_house", "watched_0_100"):
            self.assertEqual(calculate(songs, Filters(mode)), ({}, 0, 0))

    def test_export_replaces_ranks_keeps_order_and_unknown_zero(self):
        text = "AnotherAlias (Anything Goes), Other (SS-), NewPlayer (None), MAINNAME (C+)"
        self.assertEqual(eru_list(text, {"id:1": [3, 1], "id:2": [4, 3]}, self.identities),
                         "AnotherAlias (33.33), Other (75.00), NewPlayer (0.00), MAINNAME (33.33)")

    def test_empty_and_bad_player_list_rejected(self):
        for text in ("", "Bad (Rank", "Bad (Rank) junk"):
            with self.assertRaises(ValueError):
                eru_list(text, {}, self.identities)

    def test_scalar_legacy_rows(self):
        row = self.row(songs="1", year="1999", tags='["Isekai"]', genres='["Fantasy"]', correct='["OldName"]', wrong='["Other"]')
        songs = unpack_row(row, self.identities)
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0].year, 1999)
        self.assertEqual(songs[0].correct, frozenset(["id:1"]))

    def test_blank_optional_metadata(self):
        songs = unpack_row(self.row(tags="", genres="", year=""), self.identities)
        self.assertEqual(calculate(songs, Filters("watched"))[1], 3)
        self.assertEqual(calculate(songs, Filters("watched", genres=frozenset(["Fantasy"])))[1], 0)

    def test_misaligned_row_rejected(self):
        with self.assertRaises(ValueError):
            unpack_row(self.row(year='["2000"]'), self.identities)

    def test_name_objects_and_dicts(self):
        self.assertEqual(player_names([{"player": {"username": "One"}}, "Two"]), ["One", "Two"])
        self.assertEqual(player_names({"One": {"answerTime": 3.0}}), ["One"])

    def test_ambiguous_normalization_does_not_merge_players(self):
        ids = PlayerIdentities([["name", "id"], ["a_b", "1"], ["a-b", "2"]])
        self.assertEqual(ids.resolve("ab"), "name:ab")
        self.assertEqual(ids.resolve("a_b"), "id:1")

    def test_conflicting_alias_group_does_not_merge_ids(self):
        ids = PlayerIdentities([["name", "id"], ["one", "1"], ["two", "2"]], ["one\ttwo\tthird"])
        self.assertEqual(ids.resolve("third"), "name:third")

    def test_repeated_song_is_separate_encounter(self):
        songs = unpack_row(self.row(), self.identities)
        self.assertEqual(calculate(songs + songs, Filters("watched"))[0]["id:1"], [6, 2])

    def test_filters_validation(self):
        for kwargs in ({"mode": ""}, {"mode": "watched", "start_year": 999}, {"mode": "watched", "start_year": 2020, "end_year": 2000}):
            with self.assertRaises(ValueError):
                Filters(**kwargs)

    def test_header_mapping_and_sheet_column_letters(self):
        headers = ["Tour Type"] + [json.dumps([name]) for name in ("songNumber", "Vintage", "Tags", "Genres", "correctGuessPlayers", "incorrectGuessPlayers")]
        self.assertEqual(header_columns(headers)["correct"], 5)
        self.assertEqual(column_letter(38), "AM")
        with self.assertRaises(ValueError):
            header_columns(["Wrong schema"])


if __name__ == "__main__":
    unittest.main()
