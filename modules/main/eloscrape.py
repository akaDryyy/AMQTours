import sys
import json
import asyncio
import trueskill
import dateutil.parser as dp
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
import os
from urllib.parse import urlsplit, urlunsplit
from modules.support.saveElos import saveElos
from modules.support.getAliases import *
from modules.support.getTourlist import getTourlist
from modules.support.readCredentials import readCredentials
from modules.support.inhouseData import load_inhouse_tours
from modules.support.readElos import (
    normalize_player_id,
    normalize_player_name,
    parse_composite_key,
    save_elos,
)

class EloScrape:
    def __init__(
            self, 
            directory, 
            tabEloStorage, 
            tabEloStorageCell, 
            sheetName, 
            mu, 
            sigma, 
            beta, 
            tau, 
            draw_probability,
            cache_mode=None,
            inhouse_type=None,
            min_games=3,
            external_elo_store=None):
        """
        directory = Directory where the file you are calling from resides
        tabEloStorage = GID of the Elo Storage tab
        tabEloStorageCell = Cell where to store elo
        sheetName = Name of the spreadsheet
        Trueskill parameters:
        mu = mean rating
        sigma = initial uncertainty of a new player's rating -- recommended to be mu/3 in docs but redefined below since most people are relatively well rated to start (?)
        beta = rating difference at which the higher-rated player has a ~76% chance of winning // initial 2
        tau = change this to increase/decrease how much a regular player's rating is likely to swing // initial 0.04
        draw_probability = based on jan-jul 2024 results -- no clue what this means
        """
        self.directory = directory
        self.tabEloStorage = tabEloStorage
        self.tabEloStorageCell = tabEloStorageCell
        self.sheetName = sheetName
        self.mu = mu
        self.sigma = sigma
        self.beta = beta
        self.tau = tau
        self.draw_probability = draw_probability
        self.cache_mode = cache_mode
        self.inhouse_type = inhouse_type
        self.min_games = max(1, int(min_games))
        self.external_elo_store = external_elo_store

        self.ALIASES_PATH = os.path.abspath(os.path.join(self.directory, os.pardir, os.pardir, "aliases.txt"))
        self.TOURLIST_PATH = os.path.join(self.directory, "tourlist.txt")
        self.ELOS = os.path.join(self.directory, "elos.json")
        self.ELOS_HISTORY = os.path.join(self.directory, "elo_history.json")
        self.ELOS_HISTORY_LATEST = os.path.join(self.directory, "elo_history_latest.json")
        self.ELOSCRAPE_STATE = os.path.join(self.directory, "eloscrape_state.json")
        self.ELOS_ADJUSTED_TL = os.path.join(self.directory, "elo_adjusted_tl.txt")
        self.ELOS_ADJUSTED_TL_FINEGRAINED = os.path.join(self.directory, "elo_adjusted_tl_finegrained.txt")
        self.IDTABLE = os.path.join(self.directory, "ids.csv")
        self.MATCH_BACKLOG = os.path.join(self.directory, "match_backlog.json")
        self.PROXY_SERVER = '' # get from tsui if necessary
        self.TEAMSIZE = 4
        self.SHEET_CACHE_VERSION = "1"
        self.CACHE_WORKBOOK = "NGM Stats Export v2"
        self.CACHE_SHEET = "Cache"
        self.SUBSTITUTE_CACHE_SUFFIX = "__substitutes"
        self.CACHE_HEADERS = [
            "cache_version", "mode", "tour_id", "tour_url", "time", "round",
            "player1_id", "player1_display", "player2_id", "player2_display",
            "winner_id", "loser_id", "player1_score", "player2_score", "match_count"
        ]

    async def eloscrape(
            self,
            saveToSheet=True,
            tourlist_cell=None,
            backlog_cell=None,
            progress_callback=None,
            force_refresh_tour_ids=None,
            force_refresh_tour_urls=None,
            ignore_sheet_cache=False,
        ):  
        trueskill.setup(
            mu=self.mu,
            sigma=self.sigma, 
            beta=self.beta, 
            tau=self.tau, 
            draw_probability=self.draw_probability,
            backend='mpmath')

        def report_progress(percent, message=""):
            if progress_callback:
                progress_callback(max(0, min(100, percent)), message)

        tzd = {}
        def init_timezones():
            tz_str = '''-12 Y
            -11 X NUT SST
            -10 W CKT HAST HST TAHT TKT
            -9 V AKST GAMT GIT HADT HNY
            -8 U AKDT CIST HAY HNP PST PT
            -7 T HAP HNR MST PDT
            -6 S CST EAST GALT HAR HNC MDT
            -5 R CDT COT EASST ECT EST ET HAC HNE PET
            -4 Q AST BOT CLT COST EDT FKT GYT HAE HNA PYT
            -3 P ADT ART BRT CLST FKST GFT HAA PMST PYST SRT UYT WGT
            -2 O BRST FNT PMDT UYST WGST
            -1 N AZOT CVT EGT IST
            0 Z EGST GMT UTC WET WT
            1 A CET DFT WAT WEDT WEST
            2 B CAT CEDT CEST EET SAST WAST
            3 C EAT EEDT EEST IDT MSK
            4 D AMT AZT GET GST KUYT MSD MUT RET SAMT SCT
            5 E AMST AQTT AZST HMT MAWT MVT PKT TFT TJT TMT UZT YEKT
            6 F ALMT BIOT BTT IOT KGT NOVT OMST YEKST
            7 G CXT DAVT HOVT ICT KRAT NOVST OMSST THA WIB
            8 H ACT AWST BDT BNT CAST HKT IRKT KRAST MYT PHT SGT ULAT WITA WST
            9 I AWDT IRKST JST KST PWT TLT WDT WIT YAKT
            10 K AEST ChST PGT VLAT YAKST YAPT
            11 L AEDT LHDT MAGT NCT PONT SBT VLAST VUT
            12 M ANAST ANAT FJT GILT MAGST MHT NZST PETST PETT TVT WFT
            13 FJST NZDT
            11.5 NFT
            10.5 ACDT LHST
            9.5 ACST
            6.5 CCT MMT
            5.75 NPT
            5.5 SLT
            4.5 AFT IRDT
            3.5 IRST
            -2.5 HAT NDT
            -3.5 HNT NST NT
            -4.5 HLV VET
            -9.5 MART MIT'''

            for tz_descr in map(str.split, tz_str.split('\n')):
                tz_offset = int(float(tz_descr[0]) * 3600)
                for tz_code in tz_descr[1:]:
                    tzd[tz_code] = tz_offset

        def start_time(tag):
            return tag.name == 'div' and tag.has_attr('class') and 'start-time' in tag['class']

        def display_name_for_key(player_key, fallback=None):
            player_key = str(player_key)
            if player_key.startswith("name:"):
                return normalize_player_name(player_key[5:])
            all_names = getAliasesAllNames(aliases, player_key)
            if all_names:
                return normalize_player_name(all_names[0])
            return normalize_player_name(fallback if fallback is not None else player_key)

        def register_player_key(player_key, display_name=None):
            player_key = str(player_key)
            player_names.setdefault(player_key, display_name_for_key(player_key, display_name))
            return player_key

        def player_identity(player_name):
            player_name = normalize_player_name(player_name)
            player_id = normalize_player_id(getAliasesID(aliases, player_name))
            if player_id is None:
                return register_player_key(f"name:{player_name}", player_name)
            return register_player_key(player_id, player_name)

        def state_player_identity(player_key, state_version):
            parsed = parse_composite_key(player_key)
            if parsed is not None:
                player_id, player_name = parsed
                return register_player_key(player_id, player_name)
            if int(state_version or 1) >= 2:
                player_key = str(player_key)
                if not player_key.startswith("name:"):
                    player_key = normalize_player_id(player_key) or player_key
                return register_player_key(player_key)
            return player_identity(player_key)

        def get_players(teamstr, elos, teamid):
            player_strs = teamstr.rstrip(')').split(') ')
            players = {}
            rounds_played = {
                teamid: {}
            }
            for player_str in player_strs:
                if '(' not in player_str:
                    continue
                player, rank = player_str.split(' (')
                player = player.strip().lower()
                if '[' in player:
                    player, rounds_played_str = player.split(' [')
                    player = player.strip().lower()
                    player_key = player_identity(player)
                    rounds_played[teamid][player_key] = json.loads('[' + rounds_played_str)
                else:
                    player_key = player_identity(player)
                if player_key in elos:
                    players[player_key] = elos[player_key]
                else:
                    players[player_key] = trueskill.Rating(mu=float(rank))
                    
            return players, rounds_played

        def handle_subs(team, rounds_played, round, teamid):
            team_rounds = rounds_played.get(teamid, {})
            if len(team) == self.TEAMSIZE and not team_rounds:
                return team

            new_team = {}
            for player, rating in team.items():
                if player in team_rounds and round not in team_rounds[player]:
                    print(f'deleting {player_names.get(player, player)} in round {round}')
                    continue
                new_team[player] = rating
            return new_team

        class ChallongeFetchError(RuntimeError):
            pass

        async def parse_challonge_html(text, url):
            store_marker = "['TournamentStore'] = "
            theme_marker = "; window._initialStoreState['ThemeStore'] = "
            if store_marker not in text or theme_marker not in text:
                preview = BeautifulSoup(text[:500], 'lxml').get_text(" ", strip=True)
                preview = preview[:180] if preview else "empty page"
                raise ChallongeFetchError(
                    f"Could not read Challonge match data for {url}. "
                    f"Challonge returned a page without tournament data: {preview}"
                )

            match_info_str = text.split(store_marker, 1)[1].split(theme_marker, 1)[0]
            try:
                match_info = json.loads(match_info_str)
            except json.JSONDecodeError as exc:
                raise ChallongeFetchError(f"Could not parse Challonge match data for {url}: {exc}") from exc
            
            search = BeautifulSoup(text, 'lxml')
            time_tag = search.find(start_time)
            if time_tag is None or time_tag.string is None:
                raise ChallongeFetchError(f"Could not find start time on Challonge page for {url}.")
            time_str = time_tag.string.strip()
            match_info['time'] = dp.parse(time_str, tzinfos=tzd)
            
            return match_info

        def mode_key():
            return self.cache_mode or os.path.basename(os.path.normpath(self.directory))

        def substitute_mode_key(current_mode):
            return f"{current_mode}{self.SUBSTITUTE_CACHE_SUFFIX}"

        def normalize_challonge_link(url):
            url = str(url or "").strip()
            if not url:
                return ""
            parsed = urlsplit(url if "://" in url else f"https://{url}")
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            path = parsed.path.rstrip("/")
            return urlunsplit((parsed.scheme.lower() or "https", netloc, path, "", ""))

        def tour_id_from_url(url):
            return normalize_challonge_link(url).rstrip("/").split("/")[-1]

        def cache_value(value):
            if value is None:
                return ""
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return str(value)

        def cache_id(value):
            if value is None or value == "":
                return None
            return str(value)

        def cache_score(scores, player_id):
            if not isinstance(scores, dict):
                return ""
            for key in (player_id, str(player_id)):
                if key in scores:
                    return cache_value(scores[key])
            try:
                numeric_key = int(player_id)
                if numeric_key in scores:
                    return cache_value(scores[numeric_key])
            except (TypeError, ValueError):
                pass
            return ""

        def normalize_match(match):
            player1 = match.get("player1") or {}
            player2 = match.get("player2") or {}
            player1_id = cache_id(player1.get("id"))
            player2_id = cache_id(player2.get("id"))
            scores = match.get("scores", {})
            return {
                "round": int(match.get("round")),
                "player1": {
                    "id": player1_id,
                    "display_name": player1.get("display_name", ""),
                },
                "player2": {
                    "id": player2_id,
                    "display_name": player2.get("display_name", ""),
                },
                "winner_id": cache_id(match.get("winner_id")),
                "loser_id": cache_id(match.get("loser_id")),
                "scores": {
                    player1_id: cache_score(scores, player1_id),
                    player2_id: cache_score(scores, player2_id),
                },
            }

        def normalize_tour(match_info, tour_id, tour_url):
            return {
                "tour_id": tour_id,
                "tour_url": normalize_challonge_link(tour_url),
                "time": match_info["time"],
                "matches_by_round": {
                    str(round_key): [normalize_match(match) for match in round_info]
                    for round_key, round_info in match_info["matches_by_round"].items()
                },
            }

        def display_has_substitute(display_name):
            return "[" in str(display_name) and "]" in str(display_name)

        def tour_has_substitutes(tour):
            for matches in tour.get("matches_by_round", {}).values():
                for match in matches:
                    for side in ("player1", "player2"):
                        if display_has_substitute((match.get(side) or {}).get("display_name", "")):
                            return True
            return False

        def load_eloscrape_state(challonges):
            if not os.path.exists(self.ELOSCRAPE_STATE):
                return {}, [], challonges

            try:
                with open(self.ELOSCRAPE_STATE, encoding="utf-8") as f:
                    state = json.load(f)
            except (OSError, json.JSONDecodeError):
                return {}, [], challonges

            state_version = state.get("version")
            if state_version not in (1, 2):
                return {}, [], challonges

            current_ids = [tour["tour_id"] for tour in challonges]
            processed_ids = state.get("tour_ids", [])
            if not processed_ids or current_ids[:len(processed_ids)] != processed_ids:
                return {}, [], challonges
            if len(processed_ids) > len(current_ids):
                return {}, [], challonges

            ratings = {}
            for player, value in state.get("ratings", {}).items():
                try:
                    player_key = state_player_identity(player, state_version)
                    ratings[player_key] = trueskill.Rating(mu=float(value["mu"]), sigma=float(value["sigma"]))
                except (KeyError, TypeError, ValueError):
                    return {}, [], challonges

            for player, display_name in state.get("rating_names", {}).items():
                player_key = state_player_identity(player, state_version)
                player_names[player_key] = normalize_player_name(display_name)

            history = state.get("elo_history", [])
            if not isinstance(history, list):
                history = []

            return ratings, history, challonges[len(processed_ids):]

        def save_eloscrape_state(challonges, ratings, history):
            state = {
                "version": 2,
                "tour_ids": [tour["tour_id"] for tour in challonges],
                "ratings": {
                    player: {"mu": rating.mu, "sigma": rating.sigma}
                    for player, rating in ratings.items()
                },
                "rating_names": {
                    player: player_names.get(player, display_name_for_key(player))
                    for player in ratings
                },
                "elo_history": history,
            }
            with open(self.ELOSCRAPE_STATE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent="\t")

        def save_latest_elo_history(history):
            if not history:
                return
            with open(self.ELOS_HISTORY_LATEST, "w", encoding="utf-8") as f:
                json.dump(history[-1], f, indent="\t")

        def tour_match_count(tour):
            return sum(len(matches) for matches in tour["matches_by_round"].values())

        def open_sheet_cache():
            gc = readCredentials(self.directory)
            sheet = gc.open(self.CACHE_WORKBOOK)
            try:
                wks = sheet.worksheet(self.CACHE_SHEET)
            except Exception:
                wks = sheet.add_worksheet(title=self.CACHE_SHEET, rows=1000, cols=len(self.CACHE_HEADERS))

            values = wks.get_all_values()
            if not values:
                for column, header in enumerate(self.CACHE_HEADERS, start=1):
                    wks.update_cell(1, column, header)
                return wks, {header: index for index, header in enumerate(self.CACHE_HEADERS)}, []

            headers = values[0]
            if not any(headers):
                for column, header in enumerate(self.CACHE_HEADERS, start=1):
                    wks.update_cell(1, column, header)
                return wks, {header: index for index, header in enumerate(self.CACHE_HEADERS)}, values[1:]

            missing_headers = [header for header in self.CACHE_HEADERS if header not in headers]
            if missing_headers:
                for offset, header in enumerate(missing_headers, start=len(headers) + 1):
                    wks.update_cell(1, offset, header)
                headers = headers + missing_headers

            return wks, {header: headers.index(header) for header in self.CACHE_HEADERS}, values[1:]

        def read_cell(row, headers, name):
            index = headers[name]
            return row[index] if index < len(row) else ""

        def column_letter(index):
            letters = ""
            while index:
                index, remainder = divmod(index - 1, 26)
                letters = chr(65 + remainder) + letters
            return letters

        def backfill_cache_links(wks, rows, headers, current_mode, url_by_tour_id):
            tour_url_column = column_letter(headers["tour_url"] + 1)
            updates = []
            for row_index, row in enumerate(rows, start=2):
                if read_cell(row, headers, "cache_version") != self.SHEET_CACHE_VERSION:
                    continue
                if read_cell(row, headers, "mode") != current_mode:
                    continue
                if read_cell(row, headers, "tour_url"):
                    continue

                tour_url = url_by_tour_id.get(read_cell(row, headers, "tour_id"))
                if tour_url:
                    updates.append({
                        "range": f"{tour_url_column}{row_index}",
                        "values": [[tour_url]],
                    })

            for start in range(0, len(updates), 500):
                batch = updates[start:start + 500]
                try:
                    wks.batch_update(batch, value_input_option="RAW")
                except TypeError:
                    wks.batch_update(batch)
            return len(updates)

        def load_sheet_cache(rows, headers, current_mode):
            cached_by_id = {}
            cached_by_url = {}

            latest_blocks = {}
            current_block_key = None
            current_block_start = None
            for row_index, row in enumerate(rows):
                if read_cell(row, headers, "cache_version") != self.SHEET_CACHE_VERSION:
                    current_block_key = None
                    current_block_start = None
                    continue
                if read_cell(row, headers, "mode") != current_mode:
                    current_block_key = None
                    current_block_start = None
                    continue

                tour_id = read_cell(row, headers, "tour_id")
                if not tour_id:
                    current_block_key = None
                    current_block_start = None
                    continue
                tour_url = normalize_challonge_link(read_cell(row, headers, "tour_url"))
                cache_key = tour_url if tour_url else tour_id
                if cache_key != current_block_key:
                    current_block_key = cache_key
                    current_block_start = row_index
                latest_blocks[cache_key] = (current_block_start, row_index)

            for row_index, row in enumerate(rows):
                if read_cell(row, headers, "cache_version") != self.SHEET_CACHE_VERSION:
                    continue
                if read_cell(row, headers, "mode") != current_mode:
                    continue

                tour_id = read_cell(row, headers, "tour_id")
                if not tour_id:
                    continue
                tour_url = normalize_challonge_link(read_cell(row, headers, "tour_url"))
                cache_key = tour_url if tour_url else tour_id
                block = latest_blocks.get(cache_key)
                if not block or not (block[0] <= row_index <= block[1]):
                    continue

                cache_bucket = cached_by_url if tour_url else cached_by_id
                tour = cache_bucket.setdefault(cache_key, {
                    "tour_id": tour_id,
                    "tour_url": tour_url,
                    "time": dp.parse(read_cell(row, headers, "time")),
                    "matches_by_round": {},
                    "_cache_match_keys": set(),
                })
                expected_match_count = read_cell(row, headers, "match_count")
                if expected_match_count:
                    try:
                        tour["_expected_match_count"] = max(
                            int(tour.get("_expected_match_count", 0)),
                            int(expected_match_count),
                        )
                    except ValueError:
                        pass

                player1_id = cache_id(read_cell(row, headers, "player1_id"))
                player2_id = cache_id(read_cell(row, headers, "player2_id"))
                round_number = int(read_cell(row, headers, "round"))
                match_key = (
                    round_number,
                    player1_id,
                    player2_id,
                    cache_id(read_cell(row, headers, "winner_id")),
                    cache_id(read_cell(row, headers, "loser_id")),
                    read_cell(row, headers, "player1_score"),
                    read_cell(row, headers, "player2_score"),
                )
                if match_key in tour["_cache_match_keys"]:
                    continue
                tour["_cache_match_keys"].add(match_key)
                match = {
                    "round": round_number,
                    "player1": {
                        "id": player1_id,
                        "display_name": read_cell(row, headers, "player1_display"),
                    },
                    "player2": {
                        "id": player2_id,
                        "display_name": read_cell(row, headers, "player2_display"),
                    },
                    "winner_id": cache_id(read_cell(row, headers, "winner_id")),
                    "loser_id": cache_id(read_cell(row, headers, "loser_id")),
                    "scores": {
                        player1_id: read_cell(row, headers, "player1_score"),
                        player2_id: read_cell(row, headers, "player2_score"),
                    },
                }
                tour["matches_by_round"].setdefault(str(round_number), []).append(match)
            return cached_by_id, cached_by_url

        def cache_rows_for_tour(tour, current_mode):
            rows = []
            match_count = tour_match_count(tour)
            for round_key in tour["matches_by_round"]:
                for match in tour["matches_by_round"][round_key]:
                    player1 = match["player1"]
                    player2 = match["player2"]
                    player1_id = cache_id(player1["id"])
                    player2_id = cache_id(player2["id"])
                    scores = match.get("scores", {})
                    rows.append([
                        self.SHEET_CACHE_VERSION,
                        current_mode,
                        tour["tour_id"],
                        tour.get("tour_url", ""),
                        cache_value(tour["time"]),
                        match["round"],
                        player1_id,
                        player1.get("display_name", ""),
                        player2_id,
                        player2.get("display_name", ""),
                        cache_value(match.get("winner_id")),
                        cache_value(match.get("loser_id")),
                        cache_score(scores, player1_id),
                        cache_score(scores, player2_id),
                        match_count,
                    ])
            return rows

        def append_sheet_cache(wks, tours, current_mode):
            rows = []
            for tour in tours:
                rows.extend(cache_rows_for_tour(tour, current_mode))
            for start in range(0, len(rows), 500):
                batch = rows[start:start + 500]
                try:
                    wks.append_rows(batch, value_input_option="RAW")
                except AttributeError:
                    for row in batch:
                        wks.append_row(row, value_input_option="RAW")
                except TypeError:
                    try:
                        wks.append_rows(batch)
                    except AttributeError:
                        for row in batch:
                            wks.append_row(row)
            return len(rows)

        def delete_sheet_cache_rows(wks, rows, headers, current_modes, tour_ids=None, tour_urls=None):
            if isinstance(current_modes, str):
                current_modes = {current_modes}
            else:
                current_modes = set(current_modes)
            tour_ids = {str(tour_id).strip().lower() for tour_id in (tour_ids or []) if str(tour_id).strip()}
            tour_urls = {normalize_challonge_link(url) for url in (tour_urls or []) if str(url).strip()}
            if not tour_ids and not tour_urls:
                return rows, 0

            kept_rows = []
            rows_to_delete = []
            for sheet_row_index, row in enumerate(rows, start=2):
                if read_cell(row, headers, "cache_version") != self.SHEET_CACHE_VERSION:
                    kept_rows.append(row)
                    continue
                if read_cell(row, headers, "mode") not in current_modes:
                    kept_rows.append(row)
                    continue

                row_tour_id = read_cell(row, headers, "tour_id").strip().lower()
                row_tour_url = normalize_challonge_link(read_cell(row, headers, "tour_url"))
                if row_tour_id in tour_ids or row_tour_url in tour_urls:
                    rows_to_delete.append(sheet_row_index)
                else:
                    kept_rows.append(row)

            for row_index in reversed(rows_to_delete):
                try:
                    wks.delete_rows(row_index)
                except Exception:
                    try:
                        wks.delete_row(row_index)
                    except Exception:
                        pass
            return kept_rows, len(rows_to_delete)

        def cached_tour_is_complete(tour):
            expected_match_count = tour.get("_expected_match_count")
            if not expected_match_count:
                return True
            return tour_match_count(tour) >= int(expected_match_count)

        async def get_challonge_info(session, url):
            url = normalize_challonge_link(url)
            tour_id = tour_id_from_url(url)
            resp = await session.get(url)
            status_code = getattr(resp, "status_code", None)
            if status_code and status_code >= 400:
                raise ChallongeFetchError(f"Could not fetch {url}: HTTP {status_code}.")
            match_info = await parse_challonge_html(resp.text, url)
            
            return normalize_tour(match_info, tour_id, url)


        async def load_inhouse_backlog():
            if self.inhouse_type:
                return load_inhouse_tours(self.directory, self.inhouse_type)

            if not os.path.exists(self.MATCH_BACKLOG):
                return []

            with open(self.MATCH_BACKLOG, encoding="utf-8") as f:
                backlog = json.load(f)

            tours = []
            for event in backlog:
                team1_id = "team1"
                team2_id = "team2"
                team1 = event["teams"][team1_id]
                team2 = event["teams"][team2_id]
                matches_by_round = {}

                for match in event["matches"]:
                    winner = match.get("winner")
                    if winner == team1_id:
                        winner_id = team1_id
                        loser_id = team2_id
                    elif winner == team2_id:
                        winner_id = team2_id
                        loser_id = team1_id
                    else:
                        winner_id = None
                        loser_id = None

                    round_key = str(match["round"])
                    matches_by_round.setdefault(round_key, []).append({
                        "round": match["round"],
                        "player1": {"id": team1_id, "display_name": team1["display_name"]},
                        "player2": {"id": team2_id, "display_name": team2["display_name"]},
                        "winner_id": winner_id,
                        "loser_id": loser_id,
                        "scores": {
                            team1_id: match["team1_score"],
                            team2_id: match["team2_score"],
                        },
                    })

                tours.append({
                    "tour_id": event["tour_id"],
                    "time": dp.parse(event["time"]),
                    "matches_by_round": matches_by_round,
                })

            return tours

        init_timezones()

        aliases = getAliasesDF(self.IDTABLE)
        player_names = {}
        current_mode = mode_key()
        substitute_cache_mode = substitute_mode_key(current_mode)
        report_progress(2, "Reading sheet cache")
        cache_wks, cache_headers, cache_values = open_sheet_cache()
        force_refresh_tour_ids = {
            str(tour_id).strip().lower()
            for tour_id in (force_refresh_tour_ids or [])
            if str(tour_id).strip()
        }
        force_refresh_tour_urls = {
            normalize_challonge_link(url)
            for url in (force_refresh_tour_urls or [])
            if str(url).strip()
        }
        if force_refresh_tour_ids or force_refresh_tour_urls:
            cache_values, deleted_rows = delete_sheet_cache_rows(
                cache_wks,
                cache_values,
                cache_headers,
                {current_mode, substitute_cache_mode},
                force_refresh_tour_ids,
                force_refresh_tour_urls,
            )
            if deleted_rows:
                report_progress(6, f"Cleared {deleted_rows} stale cache row(s)")
        if ignore_sheet_cache:
            cached_tours_by_id, cached_tours_by_url = {}, {}
            substitute_tours_by_id, substitute_tours_by_url = {}, {}
            report_progress(8, "Ignoring old sheet cache")
        else:
            cached_tours_by_id, cached_tours_by_url = load_sheet_cache(cache_values, cache_headers, current_mode)
            substitute_tours_by_id, substitute_tours_by_url = load_sheet_cache(cache_values, cache_headers, substitute_cache_mode)
        report_progress(8, "Loaded sheet cache")

        if not self.inhouse_type:
            tourlist = [normalize_challonge_link(url) for url in getTourlist(self.TOURLIST_PATH)]
            url_by_tour_id = {tour_id_from_url(url): url for url in tourlist}
            backfilled_links = backfill_cache_links(cache_wks, cache_values, cache_headers, current_mode, url_by_tour_id)
            if backfilled_links:
                report_progress(10, f"Backfilled {backfilled_links} cache links")
            for tour_id, url in url_by_tour_id.items():
                if tour_id in cached_tours_by_id:
                    cached_tours_by_id[tour_id]["tour_url"] = url
                    cached_tours_by_url[url] = cached_tours_by_id[tour_id]
                if tour_id in substitute_tours_by_id:
                    substitute_tours_by_id[tour_id]["tour_url"] = url
                    substitute_tours_by_url[url] = substitute_tours_by_id[tour_id]
        
        # comment this out if tsui is asleep
        # only use if having issues w/ curl-cffi
        # tourlist = [PROXY_SERVER + tour for tour in tourlist]
        if self.inhouse_type:
            backlog_tours = await load_inhouse_backlog()
            missing_tours = [tour for tour in backlog_tours if tour["tour_id"] not in cached_tours_by_id]
            report_progress(18, f"{len(missing_tours)} missing in-house cache event(s)")
            written_rows = append_sheet_cache(cache_wks, missing_tours, current_mode)
            if written_rows:
                report_progress(25, f"Wrote {written_rows} cache rows")
            for tour in missing_tours:
                cached_tours_by_id[tour["tour_id"]] = tour
            challonges = [cached_tours_by_id[tour["tour_id"]] for tour in backlog_tours if tour["tour_id"] in cached_tours_by_id]
            report_progress(35, "Prepared cached matches")
        else:
            missing_urls = []
            ordered_cache = {}
            for url in tourlist:
                tour = substitute_tours_by_url.get(url)
                if tour is None:
                    tour = substitute_tours_by_id.get(tour_id_from_url(url))
                    if tour is not None and not tour.get("tour_url"):
                        tour["tour_url"] = url
                if tour is None:
                    tour = cached_tours_by_url.get(url)
                if tour is None:
                    tour = cached_tours_by_id.get(tour_id_from_url(url))
                    if tour is not None and not tour.get("tour_url"):
                        tour["tour_url"] = url
                if tour is None or not cached_tour_is_complete(tour):
                    missing_urls.append(url)
                else:
                    ordered_cache[url] = tour
            async with AsyncSession(impersonate='chrome123', max_clients=2) as session:
                try:
                    missing_tours = []
                    missing_total = len(missing_urls)
                    if missing_total == 0:
                        report_progress(35, "All Challonges already cached")
                    else:
                        report_progress(10, f"{missing_total} missing Challonge cache(s)")
                    fetch_tasks = [asyncio.create_task(get_challonge_info(session, url)) for url in missing_urls]
                    for missing_index, task in enumerate(asyncio.as_completed(fetch_tasks), start=1):
                        missing_tours.append(await task)
                        fetch_progress = 10 + (25 * missing_index / missing_total)
                        report_progress(fetch_progress, "Caching missing Challonges")
                    report_progress(38, "Saving missing cache rows")
                    written_rows = append_sheet_cache(cache_wks, missing_tours, current_mode)
                    if written_rows:
                        report_progress(40, f"Wrote {written_rows} cache rows")
                    substitute_tours = [tour for tour in missing_tours if tour_has_substitutes(tour)]
                    substitute_rows = append_sheet_cache(cache_wks, substitute_tours, substitute_cache_mode)
                    if substitute_rows:
                        report_progress(41, f"Wrote {substitute_rows} substitute cache rows")
                    for tour in missing_tours:
                        cached_tours_by_id[tour["tour_id"]] = tour
                        cached_tours_by_url[tour["tour_url"]] = tour
                        if tour_has_substitutes(tour):
                            substitute_tours_by_id[tour["tour_id"]] = tour
                            substitute_tours_by_url[tour["tour_url"]] = tour
                        ordered_cache[tour["tour_url"]] = tour
                    challonges = [
                        ordered_cache[url]
                        for url in tourlist
                        if url in ordered_cache
                    ]
                    challonges.sort(key=lambda tour:tour['time'].timestamp())
                    report_progress(42, "Prepared cached matches")
                except ChallongeFetchError:
                    raise
                except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ChallongeFetchError(f"Could not process Challonge cache for {current_mode}: {exc}") from exc

        elos, elo_history_list, challonges_to_process = load_eloscrape_state(challonges)
        
        match_count = 0
        draw_count = 0
        last_rounds_played = {}
        total_challonges = len(challonges_to_process)
        if self.inhouse_type and total_challonges == 0:
            save_eloscrape_state(challonges, elos, elo_history_list)
            save_latest_elo_history(elo_history_list)
            report_progress(100, "No new in-house results")
            return
        if not self.inhouse_type and total_challonges == 0:
            save_eloscrape_state(challonges, elos, elo_history_list)
            save_latest_elo_history(elo_history_list)
            report_progress(100, "No new Challonges")
            return
        for tour_index, tour in enumerate(challonges_to_process, start=1):
            played_rounds = {
                match.get("round")
                for matches in tour["matches_by_round"].values()
                for match in matches
            }
            if len(played_rounds) < self.min_games:
                report_progress(
                    42 + (50 * tour_index / total_challonges),
                    f"Skipped a {len(played_rounds)}-round event (minimum: {self.min_games})",
                )
                continue

            teams = {}
            rounds_played = {}
            elo_history = {
                'tour_id': tour['tour_id'],
                'time': tour['time'].isoformat(sep=' '),
                'results': {},
                'teams': {},
                'players': {}
            }
            rounds = tour['matches_by_round']
            for round_info in rounds.values():
                for match in round_info:
                    match_count += 1
                    team1_id = match['player1']['id']
                    team2_id = match['player2']['id']
                    
                    # add teams to tour 
                    if team1_id not in teams:
                        team1, team1_rounds = get_players(match['player1']['display_name'], elos, team1_id)
                        teams[team1_id] = team1
                        rounds_played.update(team1_rounds)
                        teamstr = ''
                        team_initial_rating = 0
                        for player, rating in team1.items(): 
                            elo_history['players'][player] = rating.mu
                            if player in team1_rounds and 1 not in team1_rounds[player]:
                                continue
                            teamstr += f'{player_names.get(player, player)} ({rating.mu:.2f}) '
                            team_initial_rating += rating.mu 
                        teamstr += f'= {team_initial_rating:.2f}'
                        elo_history['results'][team1_id] = {
                            'teamstr': teamstr,
                            'win': 0,
                            'loss': 0,
                            'draw': 0
                            }
                    if team2_id not in teams:
                        team2, team2_rounds = get_players(match['player2']['display_name'], elos, team2_id)
                        teams[team2_id] = team2
                        rounds_played.update(team2_rounds)
                        teamstr = ''
                        team_initial_rating = 0
                        for player, rating in team2.items(): 
                            elo_history['players'][player] = rating.mu
                            if player in team2_rounds and 1 not in team2_rounds[player]:
                                continue
                            teamstr += f'{player_names.get(player, player)} ({rating.mu:.2f}) '
                            team_initial_rating += rating.mu 
                        teamstr += f'= {team_initial_rating:.2f}'
                        elo_history['results'][team2_id] = {
                            'teamstr': teamstr,
                            'win': 0,
                            'loss': 0,
                            'draw': 0
                            }
                    
                    # calc rating changes 
                    if not match['winner_id']:
                        draw_count += 1
                        team1 = handle_subs(teams[team1_id], rounds_played, match['round'], team1_id)
                        team2 = handle_subs(teams[team2_id], rounds_played, match['round'], team2_id)
                        new_ratings = trueskill.rate([team1, team2], ranks=[0,0])
                        teams[team1_id].update(new_ratings[0])
                        teams[team2_id].update(new_ratings[1])
                        elo_history['results'][team1_id]['draw'] += 1
                        elo_history['results'][team2_id]['draw'] += 1
                    else:
                        winner_id = match['winner_id']
                        loser_id = match['loser_id']
                        winner_team = handle_subs(teams[winner_id], rounds_played, match['round'], winner_id)
                        loser_team = handle_subs(teams[loser_id], rounds_played, match['round'], loser_id)
                        new_ratings = trueskill.rate([winner_team, loser_team])
                        teams[winner_id].update(new_ratings[0])
                        teams[loser_id].update(new_ratings[1])
                        elo_history['results'][winner_id]['win'] += 1
                        elo_history['results'][loser_id]['loss'] += 1
                        
            elo_history['player'] = {}
            for team_id, team in teams.items():
                team_dict = elo_history['results'][team_id]
                teamstr = team_dict['teamstr']
                elo_history['teams'][teamstr] = f"{team_dict['win']}W {team_dict['loss']}L {team_dict['draw']}D"
                for player, rating in team.items():
                    display_name = player_names.get(player, player)
                    elo_history['player'][display_name] = f"initial elo: {elo_history['players'][player]:.3f}, new elo: {rating.mu:.3f}, rating change: {rating.mu - elo_history['players'][player]:.3f}"
                elos.update(team)
            del elo_history['results']
            del elo_history['players']
            elo_history_list.append(elo_history)
            last_rounds_played = rounds_played
            if total_challonges:
                report_progress(42 + (50 * tour_index / total_challonges), "Calculating ratings")
        
        print(last_rounds_played)
        report_progress(94, "Saving local elo files")
        
        elos_print = {
            (player, player_names.get(player, display_name_for_key(player))): round(rating.mu, 3)
            for player, rating in sorted(elos.items(), key=lambda elo: elo[1].mu, reverse=True)
        }
        save_elos(elos_print, self.ELOS, self.IDTABLE, key_format="composite")
        
        with open(self.ELOS_HISTORY, 'w', encoding='utf-8') as f:
            json.dump(elo_history_list, f, indent='\t')
        save_eloscrape_state(challonges, elos, elo_history_list)

        if not elo_history_list:
            report_progress(100, "Done")
            return
            
        save_latest_elo_history(elo_history_list)
        
        tierlist = {}
        for (_player, display_name), rating in elos_print.items():
            rating_int = int(round(rating))
            if rating_int not in tierlist:
                tierlist[rating_int] = [(display_name, rating)]
            else:
                tierlist[rating_int].append((display_name, rating))
        
        with open(self.ELOS_ADJUSTED_TL, 'w', encoding='utf-8') as f:
            tiers = sorted(list(tierlist.keys()), reverse=True)
            for tier in tiers:
                f.write(f'{tier}: {", ".join([player for player, _rating in tierlist[tier]])}\n')
        
        with open(self.ELOS_ADJUSTED_TL_FINEGRAINED, 'w', encoding='utf-8') as f:
            tiers = sorted(list(tierlist.keys()), reverse=True)
            for tier in tiers:
                f.write(f'{tier}: {", ".join([f"{player} ({rating})" for player, rating in tierlist[tier]])}\n')

        if saveToSheet:
            report_progress(97, "Saving elos to sheet")
            saveElos(self.directory, self.tabEloStorage, self.sheetName, self.tabEloStorageCell, self.ELOS, tourlist_path=self.TOURLIST_PATH, tourlist_cell=tourlist_cell, backlog_path=self.MATCH_BACKLOG, backlog_cell=backlog_cell)
            if self.external_elo_store:
                from modules.main.draftElo import write_draft_elo_values

                write_draft_elo_values(self.directory, self.external_elo_store, self.ELOS)
        report_progress(100, "Done")
