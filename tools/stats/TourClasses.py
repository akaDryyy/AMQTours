from __future__ import annotations
from dataclasses import *
from typing import List, Optional, Dict, Any
from math import comb
from collections import Counter
from TourFunctions import *

@dataclass
class Player:
    name: str
    player_id: int
    player_team: str = ""
    rank: float = 0
    GR: float = 0
    OPGR: float = 0
    EDGR: float = 0
    INGR: float = 0
    usefulness: float = 0
    erigs: int = 0
    eggs: int = 0
    erigsmissed: int = 0
    avgoutof: float = 0
    avgDifficultyHit: float = 0
    OP: int = 0
    ED: int = 0
    IN: int = 0
    list_hit: int = 0
    list_miss: int = 0
    low_count_hits: int = 0
    totalSongsPlayed: int = 0
    totalSongsHit: int = 0
    avgDifficultyPlayed: float = 0
    OPplayed: int = 0
    EDplayed: int = 0
    INplayed: int = 0
    rigAmount: int = 0
    soloRigs: int = 0
    avgoutofRigs: float = 0
    SKILLISSUE: int = 0
    OFFLIST: float = 0.0
    ONLIST: float = 0.0
    RIGPERC: float = 0.0

    WIN: int = 0 
    LOSE: int = 0
    TIE: int = 0
    WLT: str = ""

    AVGGR: float = 0.0
    AVGUF: float = 0.0
    AVGOP: float = 0.0
    AVGED: float = 0.0
    AVGIN: float = 0.0

    DELTAGR: float = 0.0
    DELTAUF: float = 0.0
    DELTAOP: float = 0.0
    DELTAED: float = 0.0
    DELTAIN: float = 0.0

    livesTaken: int = 0
    livesSaved: int = 0
    livesLostOnRig: int = 0
    livesTakenOfflist: int = 0
    erigsTakenOfflist: int = 0
    avgVintagePlayed: float = 0.0
    avgVintageHit: float = 0.0
    avgVintageRig: float = 0.0
    avgVintageString: str = ""
    avgVintageHitString: str = ""
    avgVintageRigString: str = ""

    def __repr__(self):
        return (f"Name={self.name}, Rank={self.rank}, GR={self.GR}%, OPGR={self.OPGR}%, EDGR={self.EDGR}%, INGR={self.INGR}%, UF={self.usefulness}, "
                f"ERIGS={self.erigs}, EGGS={self.eggs}, AVG/8={self.avgoutof}, avgDiffHit={self.avgDifficultyHit}, avgDiffPlayed={self.avgDifficultyPlayed}, Low Count Hits={self.low_count_hits}, "
                f"List Hit={self.list_hit}, List Miss={self.list_miss}, Solo Rigs={self.soloRigs}, Rigs/8={self.avgoutofRigs}, Correct Count={self.totalSongsHit}, Song Count={self.totalSongsPlayed}, "
                f"Lives Taken={self.livesTaken}, Lives Saved={self.livesSaved}, avg Vintage Played={self.avgVintageString}, avg Vintage Hit={self.avgVintageHitString}, "
                f"SKILL ISSUE={self.SKILLISSUE}, WIN={self.WIN}, LOSE={self.LOSE}, TIE={self.TIE}, "
                f"ΔGR={self.DELTAGR}%, ΔUF={self.DELTAUF}, ΔOP={self.DELTAOP}%, ΔED={self.DELTAED}%, ΔIN={self.DELTAIN}%")

    def vintage_to_str(self, vintage: float) -> str:
        year = int(vintage)
        frac = vintage - year
        if frac < 0.25:
            season = "Winter"
        elif frac < 0.50:
            season = "Spring"
        elif frac < 0.75:
            season = "Summer"
        else:
            season = "Fall"

        return f"{season} {year}"

    def add(self, field: str, n=1):
        setattr(self, field, getattr(self, field) + n)

    def add_song(self, song: Song):
        self.songsHit.append(song)

    def set_averages(self, df):
        self.AVGGR = get_stat(df, self.player_id, "Guess rate")
        self.AVGGR = round(self.AVGGR, 3)
        self.AVGUF = get_stat(df, self.player_id, "Usefulness")
        self.AVGUF = round(self.AVGUF, 3)
        self.AVGOP = get_stat(df, self.player_id, "OP guess rate")
        self.AVGOP = round(self.AVGOP, 3)
        self.AVGED = get_stat(df, self.player_id, "ED guess rate")
        self.AVGED = round(self.AVGED, 3)
        self.AVGIN = get_stat(df, self.player_id, "IN guess rate")
        self.AVGIN = round(self.AVGIN, 3)

    def post_process(self, AVGRANK, WLTcheck=True):
        self.GR = round(self.totalSongsHit / self.totalSongsPlayed, 5) if self.totalSongsPlayed else 0.0
        self.GR = round(100*self.GR, 3)
        self.OPGR = round(self.OP / self.OPplayed, 5) if self.OPplayed else 0.0
        self.OPGR = round(100*self.OPGR, 3)
        self.EDGR = round(self.ED / self.EDplayed, 5) if self.EDplayed else 0.0
        self.EDGR = round(100*self.EDGR, 3)
        self.INGR = round(self.IN / self.INplayed, 5) if self.INplayed else 0.0
        self.INGR = round(100*self.INGR, 3)
        self.avgDifficultyPlayed = round(self.avgDifficultyPlayed / self.totalSongsPlayed, 3) if self.totalSongsPlayed else 0.0
        self.avgDifficultyHit = round(self.avgDifficultyHit / self.totalSongsHit, 3) if self.totalSongsHit else 0.0
        self.avgoutof = round(self.avgoutof / self.totalSongsHit, 3) if self.totalSongsHit else 0.0
        self.usefulness = round(self.usefulness, 3)
        self.avgoutofRigs = round(self.avgoutofRigs / self.rigAmount, 3) if self.rigAmount else 0.0
        self.avgVintagePlayed = round(self.avgVintagePlayed / self.totalSongsPlayed, 3) if self.totalSongsPlayed else 0.0
        self.avgVintageString = self.vintage_to_str(self.avgVintagePlayed)
        self.avgVintageHit = round(self.avgVintageHit / self.totalSongsHit, 3) if self.totalSongsHit else 0.0
        self.avgVintageHitString = self.vintage_to_str(self.avgVintageHit)
        self.avgVintageRig = round(self.avgVintageRig / self.rigAmount, 3) if self.rigAmount else 0.0
        self.avgVintageRigString = self.vintage_to_str(self.avgVintageRig)
        self.usefulness = round(self.usefulness * AVGRANK * 2 / self.totalSongsPlayed, 3)
        self.DELTAGR = round(self.GR - self.AVGGR, 3) if self.AVGGR > 0.0 else 0.0
        self.DELTAUF = round(self.usefulness - self.AVGUF, 3) if self.AVGUF > 0.0 else 0.0
        self.DELTAOP = round(self.OPGR - self.AVGOP, 3) if self.AVGOP > 0.0 else 0.0
        self.DELTAED = round(self.EDGR - self.AVGED, 3) if self.AVGED > 0.0 else 0.0
        self.DELTAIN = round(self.INGR - self.AVGIN, 3) if self.AVGIN > 0.0 else 0.0
        self.OFFLIST = round(100 * (self.totalSongsHit - self.list_hit) / (self.totalSongsPlayed - self.rigAmount), 3) if self.totalSongsPlayed else 0.0
        self.ONLIST = round(100 * self.list_hit / self.rigAmount, 3) if self.rigAmount > 0 else 0.0
        self.RIGPERC = round(100* self.rigAmount  / self.totalSongsPlayed, 3) if self.totalSongsPlayed else 0.0
        if (self.WIN + self.LOSE + self.TIE) == 0 and WLTcheck:
            print(self.name)
            input("W-L-T check failed. The sub might have been incorrectly reported on the challonge. Ping the current host to fix. Press anything to exit.")
            exit()
        self.WLT = f"{self.WIN}-{self.LOSE}-{self.TIE}"

@dataclass
class PlayerDB:
    players: List[Player] = field(default_factory=list)
    _players_by_name: Dict[str, Player] = field(init=False, repr=False)
    _players_by_id: Dict[int, Player] = field(init=False, repr=False)

    def build_lookups(self):
        self._players_by_name = {p.name.lower(): p for p in self.players}
        self._players_by_id = {p.player_id: p for p in self.players}

    def add_player(self, player: Player):
        self.players.append(player)
    
    def lookup_player_name(self, name: str) -> Optional[Player]:
        return self._players_by_name.get(name.lower())

    def lookup_player_id(self, player_id: int) -> Optional[Player]:
        return self._players_by_id.get(player_id)
      
@dataclass
class Team:
    team_string: str
    players: List[Player] = field(default_factory=list)
    subs: List[Player] = field(default_factory=list)

    def add_player(self, player: Player):
        self.players.append(player)
        player.player_team = self.team_string

    def add_sub(self, sub: Player):
        self.subs.append(sub)
        sub.player_team = self.team_string

    def get_team_size(self):
        return(len(self.players))

    # Function used to obtain the Player object in team given an alias
    def lookup_player(self, player: Player) -> Optional[Player]:
        for p in self.players:
            if p.player_id == player.player_id:
                return p
        for p in self.subs:
            if p.player_id == player.player_id:
                return p
        return None

@dataclass
class TeamDB:
    teams: List[Team] = field(default_factory=list)
    subs: List[Player] = field(default_factory=list)
    
    def add_team(self, team: Team):
        self.teams.append(team)
    
    def add_sub(self, sub: Player):
        self.subs.append(sub)

    def add_sub_by_position(self, position: int, sub: Player):
        for team in self.teams:
            if team.position == position:
                team.add_sub(sub)
                break

    # Function used to obtain the Player object in team given an alias
    def lookup_player(self, player: Player) -> Optional[Player]:
        for team in self.teams:
            p = team.lookup_player(player)
            if p:
                return p
        for sub in self.subs:
            if sub.player_id == player.player_id:
                return sub
        print("Player not found")
        return None

    def get_team_by_player(self, player: Player) -> Optional[Team]:
        for team in self.teams:
            if team.lookup_player(player):
                return team
        print(f"{player.name} was not found inside any team. {player.name} might be a sub.")
        return None

@dataclass
class Song:
    data: Any

    anime_name: str = ""
    anime_id: int = 0
    video_id: str = ""
    vintage: float = 0.0
    artist: str = ""
    composerID: int = 0
    composer: str = ""
    arrangerID: int = 0
    arranger: str = ""
    song_title: str = ""
    song_type: str = ""
    anime_type: str = ""
    song_difficulty: float = 0.0
    rebroadcast: bool = False
    playerHit: List[Player] = field(default_factory=list)
    playerRig : List[Player] = field(default_factory=list)

    season_value = {
        "Winter": 0.0,
        "Spring": 0.25,
        "Summer": 0.50,
        "Fall":   0.75
    }

    def __post_init__(self):
        actions = {
            1: "OP",
            2: "ED",
            3: "IN"
        }
        self.anime_name = self.data["songInfo"]["animeNames"]["english"]
        self.anime_id = (
            self.data["songInfo"]["siteIds"]["malId"]
            or self.data["songInfo"]["siteIds"]["annId"]
        )
        self.video_id = self.data['videoUrl'].split('/')[-1].split('.')[0]
        self.set_vintage(self.data["songInfo"]["vintage"])
        self.artist = self.data["songInfo"]["artist"]
        composer_info = self.data.get("songInfo", {}).get("composerInfo") or {}
        self.composerID = composer_info.get("artistId")
        self.composer = composer_info.get("name")
        arranger_info = self.data.get("songInfo", {}).get("arrangerInfo") or {}
        self.arrangerID = arranger_info.get("artistId")
        self.arranger = arranger_info.get("name")
        self.song_title = self.data["songInfo"]["songName"]
        self.song_type = actions.get(self.data["songInfo"]["type"])
        self.anime_type = self.data["songInfo"]["animeType"]
        song_diff = self.data["songInfo"]["animeDifficulty"]
        self.song_difficulty = round(
            0.0 if isinstance(song_diff, str) and song_diff.lower() == "unrated" else float(song_diff),
            3
        )
        self.rebroadcast = bool(self.data["songInfo"]["rebroadcast"])

    def set_vintage(self, song_vintage):
        # season = song_vintage["key"].split(".")[-1].title()
        # year = int(song_vintage["data"]["year"])
        season, year = song_vintage.split()
        self.vintage = float(year) + float(self.season_value[season])
        

    def add_guesser(self, guesser: Player):
        self.playerHit.append(guesser)

    def add_rig(self, rig: Player):
        self.playerRig.append(rig)

@dataclass
class SongDB:
    songs: List[Song] = field(default_factory=list)
    _songs_by_id: Dict[str, Song] = field(init=False, repr=False)
    _songs_by_anime_id: Dict[str, Song] = field(init=False, repr=False)
    opedin: dict = field(default_factory=dict)
    decades: dict = field(default_factory=dict)
    formats: dict = field(default_factory=dict)
    diffs: dict = field(default_factory=dict)
    rbs: List[Song] = field(default_factory=list)
    topComposer: List[Song] = field(default_factory=list)
    topArranger: List[Song] = field(default_factory=list)
    topArtist: List[Song] = field(default_factory=list)
    topAnimeID: List[Song] = field(default_factory=list)
    topVideoID: List[Song] = field(default_factory=list)
    songsAmount: int = 0

    def build_lookups(self):
        self._songs_by_id = {s.video_id: s for s in self.songs}
        self._songs_by_anime_id = {s.anime_id: s for s in self.songs}

    def add_song(self, song: Song):
        self.songs.append(song)

    def lookup_song_id(self, video_id: str) -> Optional[Song]:
        return self._songs_by_id.get(video_id)
    
    def post_process(self):
        self.songsAmount = len(self.songs)
        for song in self.songs:
            vintage = song.vintage
            decade = int((vintage // 10) * 10)
            key = f"{decade}"
            self.decades.setdefault(key, []).append(song)

            format = song.anime_type
            key = f"{format}"
            self.formats.setdefault(key, []).append(song)

            songdiff = song.song_difficulty
            diff = int((songdiff // 10) * 10)
            key = f"{diff}"
            self.diffs.setdefault(key, []).append(song)

            if song.rebroadcast:
                self.rbs.append(song)

            songtype = song.song_type
            key = f"{songtype}"
            self.opedin.setdefault(key, []).append(song)

        countComposer = Counter(
            s.composerID for s in self.songs if s.composerID
        )
        countArranger = Counter(
            s.arrangerID for s in self.songs if s.arrangerID
        )
        countArtist = Counter(
            s.artist for s in self.songs if s.artist
        )
        countVideoID = Counter(
            s.video_id for s in self.songs if s.video_id
        )
        countAnimeID = Counter(
            s.anime_id for s in self.songs if s.anime_id
        )
        
        top_comp, _ = countComposer.most_common(1)[0]
        top_arr, _ = countArranger.most_common(1)[0]
        top_art, _ = countArtist.most_common(1)[0]
        top_videoID, _ = countVideoID.most_common(1)[0]
        top_animeID, _ = countAnimeID.most_common(1)[0]

        self.topComposer = [
            s for s in self.songs if s.composerID == top_comp
        ]
        self.topArranger = [
            s for s in self.songs if s.arrangerID == top_arr
        ]
        self.topArtist = [
            s for s in self.songs if s.artist == top_art
        ]
        self.topVideoID = [
            s for s in self.songs if s.video_id == top_videoID
        ]
        self.topAnimeID = [
            s for s in self.songs if s.anime_id == top_animeID
        ]

        order = ["OP", "ED", "IN"]
        self.opedin = {k: self.opedin[k] for k in order if k in self.opedin}

@dataclass
class Game:
    id: str
    players: List[Player] = field(default_factory=list)
    songs: List[Song] = field(default_factory=list)
    OP: int = 0
    ED: int = 0
    IN: int = 0
    difficulty: float = 0.0
    vintage: float = 0.0

    def add_song(self, song: Song):
        self.songs.append(song)

    def add(self, field: str, n=1):
        setattr(self, field, getattr(self, field) + n)

@dataclass
class TourGames:
    games: List[Game] = field(default_factory=list)

    def add_game(self, game: Game):
        self.games.append(game)

@dataclass
class Usefulness:
    teamsize: int
    teamavg: float

    def get_usefulness(self, amtcorrect):
        UF = 0
        for i in range(self.teamsize):
            UF += comb(2*self.teamsize-(i+2), amtcorrect-1) / comb(2*self.teamsize-1, amtcorrect-1)
        return UF / self.teamsize