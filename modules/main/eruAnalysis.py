"""Read-only, song-level Eru analysis of the stats export's JsonData sheet."""
from __future__ import annotations

import json
import gzip
import hashlib
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from modules.support.playerRatings import normalize_alias_key


SHEET_ID = "1ihfqssregh74curDyvRE0GAFihQfovUAHpYDrtOIrOA"
MODE_LABELS = {
    "usual": ("Random FL",),
    "watched": ("Watched FL",),
    "watched_0_100": ("Watched 0-100 FL", "Watched FL 0-100"),
    "watched_0_100_op": ("Watched OP 0-100", "Watched 0-100 OP"),
    "watched_op": ("Watched OP",),
    "watched_ed": ("Watched ED",),
    "watched_ins": ("Watched IN",),
    "watched_ins_no_chanting": ("Watched IN (-chanting)",),
    "watched_oped": ("Watched OPED",),
    "watched_x_2009": ("Watched -2009",),
    "watched_2_8": ("Watched FL 2+8s", "Watched 2+8"),
    "watched_5s": ("Watched FL 5s", "Watched 5s"),
    "random_op": ("Random OP",),
    "random_ed": ("Random ED",),
    "random_ins": ("Random IN",),
    "random_oped": ("Random OPED",),
    "random_chanting": ("Random Chanting",),
    # Never substitute base-mode records for a mode without its own label.
    "usual_house": ("Usual In-House", "Random In-House"),
    "watched_house": ("Watched In-House",),
    "watched_draft": ("Watched Draft",),
}
FIELD_HEADERS = {
    "mode": ("Tour Type",),
    "songs": ("songNumber",),
    "year": ("Vintage", "songInfo.vintage"),
    "tags": ("Tags", "songInfo.animeTags"),
    "genres": ("Genres", "songInfo.animeGenre"),
    "correct": ("correctGuessPlayers",),
    "wrong": ("incorrectGuessPlayers",),
}


def key(value):
    return str(value).strip().casefold()


class PlayerIdentities:
    def __init__(self, id_rows, alias_lines=()):
        self.ids = {}
        self.names = {}
        for row in id_rows[1:]:
            if len(row) < 2 or not str(row[0]).strip() or not str(row[1]).strip():
                continue
            name, player_id = str(row[0]).strip(), str(row[1]).strip()
            if re.fullmatch(r"\d+\.0+", player_id):
                player_id = player_id.split(".")[0]
            identity = "id:" + player_id
            self.ids[key(name)] = identity
            self.names.setdefault(identity, name)
        for line in alias_lines:
            aliases = [name.strip() for name in line.split("\t") if name.strip()]
            known = {self.ids[key(name)] for name in aliases if key(name) in self.ids}
            if not aliases or len(known) > 1:
                continue
            identity = next(iter(known), "name:" + key(aliases[0]))
            self.names.setdefault(identity, aliases[0])
            for name in aliases:
                self.ids.setdefault(key(name), identity)
        self.normalized = {}
        for name, identity in self.ids.items():
            normalized = normalize_alias_key(name)
            if normalized:
                previous = self.normalized.setdefault(normalized, identity)
                if previous != identity:
                    self.normalized[normalized] = None

    def resolve(self, name):
        name = str(name).strip().replace("\\_", "_")
        identity = self.ids.get(key(name)) or self.normalized.get(normalize_alias_key(name))
        return identity or "name:" + key(name)

    def register(self, name):
        identity = self.resolve(name)
        self.names.setdefault(identity, str(name).strip())
        return identity


@dataclass(frozen=True)
class Song:
    mode: str
    year: int | None
    tags: frozenset[str]
    genres: frozenset[str]
    correct: frozenset[str]
    encountered: frozenset[str]


@dataclass(frozen=True)
class Condition:
    field: str
    value: str
    link: str = "OR"

    def __post_init__(self):
        if self.field not in {"genres", "tags"} or not self.value.strip():
            raise ValueError("Choose a genre or tag for each condition.")
        if self.link not in {"AND", "OR"}:
            raise ValueError("Each condition must be linked with AND or OR.")


def condition_groups(conditions):
    """Split OR alternatives into AND groups (standard Boolean precedence)."""
    groups = []
    for condition in conditions:
        if not groups or condition.link == "OR":
            groups.append([])
        groups[-1].append(condition)
    return groups


def condition_expression(conditions):
    groups = []
    for group in condition_groups(conditions):
        text = " AND ".join(f"{'Genre' if item.field == 'genres' else 'Tag'} {json.dumps(item.value, ensure_ascii=False)}" for item in group)
        groups.append(f"({text})" if len(group) > 1 else text)
    return " OR ".join(groups) or "All songs"


@dataclass(frozen=True)
class Filters:
    mode: str
    tags: frozenset[str] = frozenset()
    genres: frozenset[str] = frozenset()
    start_year: int | None = None
    end_year: int | None = None
    match_mode: str = "OR"
    conditions: tuple[Condition, ...] = ()

    def __post_init__(self):
        if self.mode not in MODE_LABELS:
            raise ValueError("Select a tour type.")
        if self.match_mode not in {"AND", "OR"}:
            raise ValueError("Select AND or OR for genre/tag matching.")
        for year in (self.start_year, self.end_year):
            if year is not None and not 1000 <= year <= 9999:
                raise ValueError("Enter a four-digit release year or leave it empty.")
        if self.start_year is not None and self.end_year is not None and self.start_year > self.end_year:
            raise ValueError("The start year must not be after the end year.")


def parse_cell(value):
    if not isinstance(value, str):
        return value
    return json.loads(value) if value.strip().startswith(("[", "{")) else value


def header_columns(headers):
    decoded = []
    for header in headers:
        value = parse_cell(header)
        decoded.append(key(value[0] if isinstance(value, list) and len(value) == 1 else value))
    result = {}
    for field, alternatives in FIELD_HEADERS.items():
        result[field] = next((decoded.index(key(name)) for name in alternatives if key(name) in decoded), None)
    missing = [name for name, index in result.items() if index is None]
    if missing:
        raise ValueError("JsonData is missing required columns: " + ", ".join(missing))
    return result


def text_list(value):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("Expected a JSON list")
    if any(not isinstance(item, str) for item in value):
        raise ValueError("Expected names as strings")
    return [item.strip() for item in value if item.strip()]


def player_names(value):
    # AMQ exports use either names or objects carrying name and answerTime.
    def name_from(entry):
        if isinstance(entry, str):
            return entry.strip()
        if isinstance(entry, dict):
            for field in ("name", "playerName", "username", "amqName", "player"):
                name = name_from(entry.get(field))
                if name:
                    return name
        return ""

    if value in (None, ""):
        return []
    if isinstance(value, dict):
        return [name_from(entry) or str(name).strip() for name, entry in value.items()]
    if not isinstance(value, list):
        raise ValueError("Expected a player list")
    names = [name_from(entry) for entry in value]
    if any(not name for name in names):
        raise ValueError("Unrecognized player entry")
    return names


def unpack_row(row, identities):
    mode = key(row.get("mode", ""))
    if not mode:
        return []
    cells = {field: parse_cell(row.get(field, "")) for field in FIELD_HEADERS if field != "mode"}
    packed = isinstance(cells["songs"], list)
    count = len(cells["songs"]) if packed else 1
    if packed:
        for field, values in cells.items():
            if values == "":
                cells[field] = [""] * count
            elif not isinstance(values, list) or len(values) != count:
                raise ValueError(f"Misaligned {field} column")
    result = []
    for i in range(count):
        values = {field: value[i] if packed else value for field, value in cells.items()}
        correct = frozenset(identities.register(name) for name in player_names(values["correct"]))
        wrong = frozenset(identities.register(name) for name in player_names(values["wrong"]))
        year_match = re.search(r"(?<!\d)(\d{4})(?!\d)", str(values["year"]))
        result.append(Song(
            mode, int(year_match[1]) if year_match else None,
            frozenset(text_list(values["tags"])), frozenset(text_list(values["genres"])),
            correct, correct | wrong,
        ))
    return result


def calculate(songs, filters):
    modes = {key(label) for label in MODE_LABELS[filters.mode]}
    tags, genres = {key(tag) for tag in filters.tags}, {key(genre) for genre in filters.genres}
    groups = [[(item.field, key(item.value)) for item in group] for group in condition_groups(filters.conditions)]
    totals = defaultdict(lambda: [0, 0])
    matched_songs = 0
    mode_songs = 0
    for song in songs:
        if song.mode not in modes:
            continue
        mode_songs += 1
        if groups:
            values = {"tags": set(map(key, song.tags)), "genres": set(map(key, song.genres))}
            if not any(all(value in values[field] for field, value in group) for group in groups):
                continue
        elif tags or genres:
            song_tags, song_genres = set(map(key, song.tags)), set(map(key, song.genres))
            matches = (tags <= song_tags and genres <= song_genres) if filters.match_mode == "AND" else bool(tags & song_tags or genres & song_genres)
            if not matches:
                continue
        if filters.start_year is not None and (song.year is None or song.year < filters.start_year):
            continue
        if filters.end_year is not None and (song.year is None or song.year > filters.end_year):
            continue
        matched_songs += 1
        for identity in song.encountered:
            totals[identity][0] += 1
            totals[identity][1] += identity in song.correct
    return dict(totals), matched_songs, mode_songs


def eru_list(text, totals, identities):
    players = []
    for entry in re.split(r"[,\n]+", text):
        entry = entry.strip()
        if not entry:
            continue
        match = re.fullmatch(r"([^()]+?)(?:\s*\([^()]*\))?", entry)
        if not match:
            raise ValueError(f"Invalid player entry: {entry}")
        name = match[1].strip().replace("\\_", "_")
        encounters, correct = totals.get(identities.resolve(name), (0, 0))
        rate = 100 * correct / encounters if encounters else 0
        players.append(f"{name} ({rate:.2f})")
    if not players:
        raise ValueError("Enter at least one player.")
    return ", ".join(players)


def column_letter(index):
    result = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


class EruAnalysisService:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.songs = None
        self.identities = None
        self.skipped_rows = []
        self.cache_dir = self.project_root / "data" / "cache" / "eru_analysis"
        self.metadata = {}
        self.results = {}
        self.cache_warning = ""
        self.cached_names = {}
        self.last_processed_songs = 0

    @staticmethod
    def digest(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def restore_cache(self):
        try:
            with gzip.open(self.cache_dir / "songs.json.gz", "rt", encoding="utf-8") as stream:
                cache = json.load(stream)
            if cache["version"] != 1:
                return
            songs = [Song(mode, year, frozenset(tags), frozenset(genres), frozenset(correct), frozenset(encountered))
                     for mode, year, tags, genres, correct, encountered in cache["songs"]]
            self.metadata = cache["metadata"]
            self.cached_names = cache["names"]
            self.skipped_rows = cache["skipped_rows"]
            self.songs = songs
        except (OSError, EOFError, ValueError, KeyError, TypeError):
            return
        try:
            saved = json.loads((self.cache_dir / "results.json").read_text(encoding="utf-8"))
            if saved["generation"] == self.metadata.get("generation"):
                self.results = saved["results"]
        except (OSError, ValueError, KeyError, TypeError):
            self.results = {}

    def save_cache(self, songs=False):
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            if songs:
                data = {
                    "version": 1, "metadata": self.metadata, "names": self.identities.names,
                    "skipped_rows": self.skipped_rows,
                    "songs": [(s.mode, s.year, sorted(s.tags), sorted(s.genres), sorted(s.correct), sorted(s.encountered)) for s in self.songs],
                }
                temporary = self.cache_dir / "songs.json.gz.tmp"
                with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=1) as stream:
                    json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
                temporary.replace(self.cache_dir / "songs.json.gz")
            temporary = self.cache_dir / "results.json.tmp"
            temporary.write_text(json.dumps({"generation": self.metadata.get("generation"), "results": self.results}), encoding="utf-8")
            temporary.replace(self.cache_dir / "results.json")
            self.cache_warning = ""
        except OSError as exc:
            self.cache_warning = f"Local cache could not be saved: {exc}"

    @staticmethod
    def read_rows(worksheet, indices, start, end):
        fields = list(indices)
        ranges = [f"{column_letter(indices[field])}{start}:{column_letter(indices[field])}{end}" for field in fields]
        columns = worksheet.batch_get(ranges)
        return [{field: column[offset][0] if offset < len(column) and column[offset] else ""
                 for field, column in zip(fields, columns)} for offset in range(end - start + 1)]

    def load(self, progress=lambda message: None, force=True):
        from modules.support.readCredentials import readCredentials

        if not force and self.songs is None:
            progress("Reading local Eru cache...")
            self.restore_cache()
        progress("Connecting to JsonData...")
        client = readCredentials(self.project_root)
        client.set_timeout(90)
        sheet = client.open_by_key(SHEET_ID)
        worksheet = sheet.get_worksheet_by_id(711415473)
        headers = worksheet.row_values(1)
        indices = header_columns(headers)
        id_rows = sheet.get_worksheet_by_id(1903970832).get_all_values()
        alias_path = self.project_root / "data" / "aliases.txt"
        aliases = alias_path.read_text(encoding="utf-8").splitlines() if alias_path.exists() else []
        identities = PlayerIdentities(id_rows, aliases)
        alias_digest = self.digest([id_rows, aliases])
        reusable = (not force and self.songs is not None and self.metadata.get("headers") == headers
                    and self.metadata.get("aliases") == alias_digest and isinstance(self.metadata.get("rows"), dict))
        previous_rows = self.metadata.get("rows", {}) if reusable else {}
        last_row = self.metadata.get("last_row", 1) if reusable else 1
        if reusable:
            for identity, name in (self.identities.names if self.identities else self.cached_names).items():
                identities.names.setdefault(identity, name)
        songs, skipped, manifest = [], [], {}
        append_only = reusable
        updated_rows = 0
        # Fetch only the seven needed columns, in bounded batches; never fetch videos/codes.
        # Verify all rows so edits, deletions and gaps in older tours are detected too.
        for start in range(2, worksheet.row_count + 1, 1000):
            end = min(start + 999, worksheet.row_count)
            progress(f"Reading JsonData rows {start:,}-{end:,} / {worksheet.row_count:,}...")
            for offset, row in enumerate(self.read_rows(worksheet, indices, start, end)):
                if not row.get("mode", "").strip():
                    continue
                number = start + offset
                old = previous_rows.get(str(number))
                entry = {"digest": self.digest(row), "start": len(songs)}
                if old and old["digest"] == entry["digest"]:
                    songs.extend(self.songs[old["start"]:old["start"] + old["count"]])
                    if old.get("error"):
                        entry["error"] = old["error"]
                else:
                    updated_rows += 1
                    if number <= last_row:
                        append_only = False
                    try:
                        songs.extend(unpack_row(row, identities))
                    except (ValueError, TypeError, KeyError) as exc:
                        entry["error"] = str(exc)
                entry["count"] = len(songs) - entry["start"]
                manifest[str(number)] = entry
                if entry.get("error"):
                    skipped.append((number, entry["error"]))
        if previous_rows.keys() - manifest.keys():
            append_only = False
        metadata = {
            "generation": self.metadata["generation"] if append_only else uuid.uuid4().hex,
            "headers": headers, "aliases": alias_digest, "rows": manifest,
            "last_row": max(map(int, manifest), default=1),
        }
        self.songs, self.identities, self.skipped_rows = songs, identities, skipped
        changed = metadata != self.metadata
        self.metadata = metadata
        if not append_only:
            self.results = {}
        if changed:
            progress("Saving local Eru cache...")
            self.save_cache(songs=True)
        progress(f"Verified {len(manifest):,} rows; updated {updated_rows:,}. Cached {len(songs):,} songs.")
        return len(songs)

    def calculate(self, filters):
        signature = self.digest([filters.mode, sorted(filters.tags), sorted(filters.genres), filters.start_year, filters.end_year, filters.match_mode,
                                 [(item.field, item.value, item.link) for item in filters.conditions]])
        saved = self.results.get(signature, {})
        processed = saved.get("processed", 0)
        if processed > len(self.songs):
            saved, processed = {}, 0
        self.last_processed_songs = len(self.songs) - processed
        if saved and processed == len(self.songs):
            return saved["totals"], saved["matching"], saved["mode_songs"]
        added, matching, mode_songs = calculate(self.songs[processed:], filters)
        totals = {identity: list(counts) for identity, counts in saved.get("totals", {}).items()}
        for identity, (count, correct) in added.items():
            current = totals.setdefault(identity, [0, 0])
            current[0] += count
            current[1] += correct
        matching += saved.get("matching", 0)
        mode_songs += saved.get("mode_songs", 0)
        self.results[signature] = {"processed": len(self.songs), "totals": totals, "matching": matching, "mode_songs": mode_songs}
        self.save_cache()
        return totals, matching, mode_songs

    def choices(self, field):
        return sorted({value for song in self.songs or () for value in getattr(song, field)}, key=str.casefold)
