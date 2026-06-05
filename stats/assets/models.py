
import base64
import logging
import re
import requests
import subprocess
import sys
from collections import UserList
from dataclasses import _MISSING_TYPE, dataclass, field
from enum import Enum
from pathlib import Path
from typing import List

property_map = {
    'aniListId': "anilist_id",
    'annId': "ann_id",
    'annSongId': "ann_song_id",
    'fileName': "filename",
    'globalPercent': "difficulty",
    'kitsuId': "kitsu_id",
    'fileNameMap': "filename_map",
    'malId': "mal_id",
    'meanVolume': "mean_volume",
    'recentPercent': "recent_difficulty",
    'seasonId': "season_number",
    'songArtistId': "song_artist_id",
    'songId': "song_id",
    'songGroupId': "song_group_id",
    'totalCorrectCount': "correct_count",
    'totalMultipleChoiceCorrectCount': "multiple_choice_correct_count",
    'totalMultipleChoiceWrongCount': "multiple_choice_incorrect_count",
    'totalWrongCount': "incorrect_count",
}

class Base:
    def __init__(self, options = {}):
        # Run factory on fields with no default because we skip __post_init__
        for field in self.__dataclass_fields__.values():
            if isinstance(field.default, _MISSING_TYPE):
                setattr(self, field.name, field.default_factory())
        # Set attributes found in options dict
        for key, value in options.items():
            if key in property_map:
                key = property_map[key]
            if key not in self.__dataclass_fields__:
                continue
            try:
                setattr(self, key, self.__annotations__[key](value))
            except Exception as e:
                logging.warning(f"Could not find attribute: {e}")

class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class SongCategory(Enum):
    UNKNOWN = 0
    INSTRUMENTAL = 1
    CHANTING = 2
    CHARACTER = 3
    STANDARD = 4

    def name(self):
        if self == SongCategory.UNKNOWN:
            return "Unknown"
        if self == SongCategory.INSTRUMENTAL:
            return "Instrumental"
        if self == SongCategory.CHANTING:
            return "Chanting"
        if self == SongCategory.CHARACTER:
            return "Character"
        if self == SongCategory.STANDARD:
            return "Standard"

class Type(Enum):
    OPENING = 1
    ENDING = 2
    INSERT = 3

    def name(self):
        if self == Type.OPENING:
            return "OP"
        if self == Type.ENDING:
            return "ED"
        if self == Type.INSERT:
            return "IN"

class Language(Enum):
    JAPANESE = "JA"
    JAPANESE2 = "JP"
    JAPANESE3 = "Ja"
    ENGLISH = "EN"
    ENGLISH2 = "EEN"

JAPANESE = (Language.JAPANESE, Language.JAPANESE2, Language.JAPANESE3)
ENGLISH = (Language.ENGLISH, Language.ENGLISH2)

class IntList(UserList):
    def __init__(self, integers = []):
        self.data = [int(integer) for integer in integers]

class StrList(UserList):
    def __init__(self, strings = []):
        self.data = [str(string) for string in strings]

class PathList(UserList):
    def __init__(self, paths = []):
        self.data = [Path(path) for path in paths]

class NameList(UserList):
    def __init__(self, names = []):
        self.data = [Name(name) for name in names]

    def name(self, language):
        for name in self.data:
            if name.language in language:
                return name.name
        # We can't find this language, return a default
        return self.data[0].name

class TypeList(UserList):
    def __init__(self, types = []):
        self.data = [Type(type) for type in types]

class SongCategoryList(UserList):
    def __init__(self, song_categories = []):
        self.data = [SongCategory(song_category) for song_category in song_categories]

@dataclass(init=False)
class Artist(Base):
    song_artist_id: int = None
    name: str = None

    @property
    def id(self):
        return self.song_artist_id

    @classmethod
    def from_master_list(cls, master_list, artist_id):
        return cls(master_list['artistMap'][str(artist_id)])

    def all_artists(self):
        yield self

    def contributing_artists(self):
        return
        yield

@dataclass(init=False)
class Group(Base):
    song_group_id: int = None
    name: str = None
    artists: List[Artist] = field(default_factory=list)

    @property
    def id(self):
        return self.song_group_id

    @classmethod
    def from_master_list(cls, master_list, group_id):
        master_group = master_list['groupMap'][str(group_id)]
        group = cls(master_group)
        group.artists = [Artist.from_master_list(master_list, artist_id) for artist_id in master_group['artistMembers']]
        return group

    def all_artists(self):
        yield self
        for artist in self.artists:
            yield artist

    def contributing_artists(self):
        for artist in self.artists:
            yield artist

@dataclass(init=False)
class SongExtendedInfo(Base):
    ann_id: int = None
    song_id: int = None
    ann_song_id: int = None
    difficulty: int = None
    filename_map: dict = field(default_factory=dict)
    mean_volume: int = None
    recent_difficulty: int = None
    correct_count: int = None
    incorrect_count: int = None
    multiple_choice_correct_count: int = None
    multiple_choice_incorrect_count: int = None

@dataclass(init=False)
class Song(Base):
    song_id: int = None
    name: str = None
    category: SongCategory = None
    artist: Artist | Group = None
    composer: Artist | Group = None
    arranger: Artist | Group = None
    extended_info: SongExtendedInfo = None

    @classmethod
    def from_master_list(cls, master_list, song_id):
        master_song = master_list['songMap'][str(song_id)]
        song = cls(master_song)
        if master_song['songArtistId']:
            song.artist = Artist.from_master_list(master_list, master_song['songArtistId'])
        elif master_song['songGroupId']:
            song.artist = Group.from_master_list(master_list, master_song['songGroupId'])
        if master_song['composerArtistId']:
            song.composer = Artist.from_master_list(master_list, master_song['composerArtistId'])
        elif master_song['composerGroupId']:
            song.composer = Group.from_master_list(master_list, master_song['composerGroupId'])
        if master_song['arrangerArtistId']:
            song.arranger = Artist.from_master_list(master_list, master_song['arrangerArtistId'])
        elif master_song['arrangerGroupId']:
            song.arranger = Group.from_master_list(master_list, master_song['arrangerGroupId'])
        return song

@dataclass(init=False)
class Name(Base):
    name: str = None
    language: Language = None

@dataclass(init=False)
class AnimeExtendedInfo(Base):
    ann_id: int = None
    anilist_id: int = None
    mal_id: int = None
    kitsu_id: int = None
    genres: StrList = field(default_factory=StrList)
    tags: StrList = field(default_factory=StrList)

@dataclass(init=False)
class Anime(Base):
    ann_id: int = None
    category: str = None
    year: int = None
    season_number: int = None
    names: NameList = field(default_factory=NameList)
    extended_info: AnimeExtendedInfo = None

@dataclass(init=False)
class SongLink(Base):
    song_id: int = None
    ann_song_id: int = None
    type: Type = None
    number: int = None
    uploaded: bool = None
    rebroadcast: bool = None
    dub: bool = None
    anime: Anime = field(default_factory=Anime)
    song: Song = field(default_factory=Song)
