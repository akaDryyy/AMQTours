from __future__ import annotations

import re
from pathlib import Path


class MissingRatingsError(ValueError):
    def __init__(self, names):
        self.names = names
        super().__init__("Missing rating for: " + ", ".join(names))


def normalize_alias_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_alias_ratings(ratings: dict[str, float], aliases_path: str | Path) -> dict[str, tuple[str, float]]:
    alias_ratings = {}
    aliases_path = Path(aliases_path)
    if aliases_path.exists():
        for line in aliases_path.read_text(encoding="utf-8").splitlines():
            names = [name.strip().lower() for name in line.split("\t") if name.strip()]
            resolved_name = next((name for name in names if name in ratings), None)
            if resolved_name:
                for alias in names:
                    alias_ratings[alias] = (resolved_name, ratings[resolved_name])

    normalized = {}
    for name, rating in ratings.items():
        key = normalize_alias_key(name)
        if key not in normalized:
            normalized[key] = (name, rating)
        else:
            normalized[key] = None

    for key, value in normalized.items():
        if value is not None:
            alias_ratings.setdefault(key, value)

    return alias_ratings


def resolve_rating_name(name: str, ratings: dict[str, float], alias_ratings: dict[str, tuple[str, float]]):
    if name in ratings:
        return name, ratings[name]
    if name in alias_ratings:
        return alias_ratings[name]

    normalized_name = normalize_alias_key(name)
    if normalized_name in alias_ratings:
        return alias_ratings[normalized_name]
    return None


def resolve_player_ratings(
    tour,
    player_entries,
    manual_ratings,
    aliases_path: str | Path,
    allow_missing=False,
):
    from utils import get_elos

    ratings = {name.lower(): float(rating) for name, rating in get_elos(tour["state_path"]).items()}
    alias_ratings = build_alias_ratings(ratings, aliases_path)
    players = []
    missing = []
    for name, pasted_rank in player_entries:
        if name in manual_ratings:
            rating_name = name
            rating = manual_ratings[name]
        elif pasted_rank is not None:
            rating_name = name
            rating = pasted_rank
        else:
            resolved = resolve_rating_name(name, ratings, alias_ratings)
            if resolved:
                rating_name, rating = resolved
            else:
                if allow_missing:
                    players.append((name, 0.0))
                    continue
                missing.append(name)
                continue
        players.append((rating_name, float(rating)))

    if missing:
        raise MissingRatingsError(missing)
    return players
