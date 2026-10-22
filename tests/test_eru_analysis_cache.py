import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from modules.main.eruAnalysis import Condition, EruAnalysisService, Filters, unpack_row


class Worksheet:
    row_count = 20

    def __init__(self):
        self.headers = ["Tour Type", '["songNumber"]', '["Vintage"]', '["Tags"]', '["Genres"]', '["correctGuessPlayers"]', '["incorrectGuessPlayers"]']
        self.data = [self.row()]
        self.requests = []

    @staticmethod
    def row(correct=True):
        return ["Watched FL", "[1]", '["2020"]', '[["Isekai"]]', '[["Fantasy"]]',
                '[["Player"]]' if correct else '[[]]', '[[]]' if correct else '[["Player"]]']

    def row_values(self, row):
        return self.headers

    def batch_get(self, ranges):
        self.requests.extend(ranges)
        columns = []
        for cell_range in ranges:
            column, start, end = re.fullmatch(r"([A-Z])(\d+):[A-Z](\d+)", cell_range).groups()
            index = ord(column) - ord("A")
            columns.append([[self.data[row - 2][index]] if 0 <= row - 2 < len(self.data) else [] for row in range(int(start), int(end) + 1)])
        return columns


class EruCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.worksheet = Worksheet()
        self.ids = [["name", "id"], ["Player", "1"]]
        ids_sheet = SimpleNamespace(get_all_values=lambda: self.ids)
        sheet = SimpleNamespace(get_worksheet_by_id=lambda gid: self.worksheet if gid == 711415473 else ids_sheet)
        client = SimpleNamespace(set_timeout=lambda _: None, open_by_key=lambda _: sheet)
        credentials = patch("modules.support.readCredentials.readCredentials", return_value=client)
        credentials.start()
        self.addCleanup(credentials.stop)
        self.service = EruAnalysisService(self.root)

    def test_restart_and_append_only_calculation(self):
        filters = Filters("watched")
        self.service.load(force=False)
        self.assertEqual(self.service.calculate(filters)[0]["id:1"], [1, 1])
        resumed = EruAnalysisService(self.root)
        self.worksheet.requests.clear()
        with patch("modules.main.eruAnalysis.unpack_row", wraps=unpack_row) as parser:
            resumed.load(force=False)
            parser.assert_not_called()
        self.assertEqual(resumed.calculate(filters)[0]["id:1"], [1, 1])
        self.assertEqual(resumed.last_processed_songs, 0)
        self.assertIn("A2:A20", self.worksheet.requests)
        self.worksheet.data.append(self.worksheet.row(correct=False))
        resumed.load(force=False)
        self.assertEqual(resumed.calculate(filters)[0]["id:1"], [2, 1])
        self.assertEqual(resumed.last_processed_songs, 1)

    def test_filter_change_uses_cached_songs(self):
        self.service.load(force=False)
        self.service.calculate(Filters("watched"))
        before = list(self.worksheet.requests)
        self.service.calculate(Filters("watched", tags=frozenset(["Isekai"]), match_mode="AND"))
        self.assertEqual(self.service.last_processed_songs, 1)
        self.assertEqual(before, self.worksheet.requests)

    def test_condition_links_have_separate_cached_results(self):
        self.service.load(force=False)
        first = Filters("watched", conditions=(Condition("genres", "Fantasy"), Condition("tags", "Missing", "OR")))
        second = Filters("watched", conditions=(Condition("genres", "Fantasy"), Condition("tags", "Missing", "AND")))
        self.assertEqual(self.service.calculate(first)[1], 1)
        self.assertEqual(self.service.calculate(second)[1], 0)
        self.assertEqual(self.service.calculate(first)[1], 1)
        self.assertEqual(self.service.last_processed_songs, 0)

    def test_tail_edit_and_alias_changes_rebuild(self):
        self.service.load(force=False)
        self.service.calculate(Filters("watched"))
        generation = self.service.metadata["generation"]
        self.worksheet.data[0] = self.worksheet.row(correct=False)
        self.service.load(force=False)
        self.assertNotEqual(generation, self.service.metadata["generation"])
        self.assertEqual(self.service.calculate(Filters("watched"))[0]["id:1"], [1, 0])
        self.ids[1][1] = "2"
        self.service.load(force=False)
        self.assertEqual(self.service.calculate(Filters("watched"))[0], {"id:2": [1, 0]})

    def test_force_refresh_rebuilds_historical_edits(self):
        self.worksheet.data.append(self.worksheet.row())
        self.service.load(force=False)
        self.service.calculate(Filters("watched"))
        self.worksheet.data[0] = self.worksheet.row(correct=False)
        self.service.load(force=True)
        self.assertEqual(self.service.calculate(Filters("watched"))[0]["id:1"], [2, 1])
        self.assertEqual(self.service.last_processed_songs, 2)

    def test_automatic_scan_detects_historical_correction(self):
        self.worksheet.data.extend([self.worksheet.row(), self.worksheet.row()])
        self.service.load(force=False)
        self.service.calculate(Filters("watched"))
        self.worksheet.data[0] = self.worksheet.row(correct=False)
        with patch("modules.main.eruAnalysis.unpack_row", wraps=unpack_row) as parser:
            self.service.load(force=False)
            self.assertEqual(parser.call_count, 1)
        self.assertEqual(self.service.calculate(Filters("watched"))[0]["id:1"], [3, 2])

    def test_automatic_scan_fills_earlier_gap(self):
        self.worksheet.data = [self.worksheet.row(), [""] * 7, self.worksheet.row()]
        self.service.load(force=False)
        self.service.calculate(Filters("watched"))
        self.worksheet.data[1] = self.worksheet.row(correct=False)
        self.service.load(force=False)
        self.assertEqual(self.service.calculate(Filters("watched"))[0]["id:1"], [3, 2])

    def test_automatic_scan_detects_deleted_records(self):
        self.worksheet.data.extend([self.worksheet.row(), self.worksheet.row()])
        self.service.load(force=False)
        self.service.calculate(Filters("watched"))
        self.worksheet.data[0] = [""] * 7
        self.service.load(force=False)
        self.assertEqual(self.service.calculate(Filters("watched"))[0]["id:1"], [2, 2])

    def test_automatic_scan_recovers_pre_manifest_cache(self):
        self.service.load(force=False)
        self.service.calculate(Filters("watched"))
        self.service.metadata.pop("rows")
        self.service.save_cache(songs=True)
        resumed = EruAnalysisService(self.root)
        resumed.load(force=False)
        self.assertEqual(resumed.calculate(Filters("watched"))[0]["id:1"], [1, 1])
        self.assertIn("rows", resumed.metadata)

    def test_corrupt_cache_falls_back_to_sheet(self):
        self.service.cache_dir.mkdir(parents=True)
        (self.service.cache_dir / "songs.json.gz").write_bytes(b"not gzip")
        self.service.load(force=False)
        self.assertEqual(len(self.service.songs), 1)

    def test_failed_sync_preserves_previous_cache(self):
        self.service.load(force=False)
        self.service.calculate(Filters("watched"))
        self.worksheet.data.append(self.worksheet.row())
        with patch.object(self.worksheet, "batch_get", side_effect=RuntimeError("Offline")):
            with self.assertRaises(RuntimeError):
                self.service.load(force=False)
        self.assertEqual(len(self.service.songs), 1)
        restored = EruAnalysisService(self.root)
        restored.restore_cache()
        self.assertEqual(len(restored.songs), 1)


if __name__ == "__main__":
    unittest.main()
