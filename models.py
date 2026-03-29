from pydantic import BaseModel
from typing import List
from enum import Enum

class Player(BaseModel):
    name: str
    rating: float

class Players(BaseModel):
    players: List[Player]

class Team(BaseModel):
    player1: str
    player2: str

class WhiteList(BaseModel):
    teams: List[Team]

class TourType(str, Enum):
    RANDOM = "random"
    RANDOM_15S = "random 15s"
    WATCHED = "watched"
    RANDOM_OP = "random op"
    RANDOM_ED = "random ed"
    RANDOM_INS = "random ins"
    RANDOM_CL = "random cl"
    WATCHED_INS = "watched ins"
    WATCHED_5S = "watched 5s"

class Tour(BaseModel):
    type: TourType

class Challonge(BaseModel):
    challonge: str