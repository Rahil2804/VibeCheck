from typing import Any

from backend.models import SourceName, VibeScores

ScoreSupport = dict[str, list[str]]


def resolve_vibe_scores(source_data: dict[SourceName, dict[str, Any]]) -> VibeScores:
    access = source_data.get(SourceName.ACCESS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    local = source_data.get(SourceName.LOCAL, {})
    transit = source_data.get(SourceName.TRANSIT, {})
    cycling = source_data.get(SourceName.CYCLING, {})
    return VibeScores(
        walkability=_optional_score(access, "walkability"),
        transit_access=_first_score(
            _optional_score(transit, "score"),
            _optional_score(access, "transit_access"),
        ),
        affordability=(
            _optional_score(housing, "affordability")
            if housing.get("benchmark_matches_preference", True)
            else None
        ),
        parks_outdoors=_best_score(
            _optional_score(access, "parks_outdoors"),
            _optional_score(local, "parks_outdoors"),
        ),
        daily_needs=_optional_score(access, "daily_needs"),
        dining_activity=_optional_score(access, "food_social"),
        # Noise and sentiment are deliberately not inferred from Reddit or amenity proxies.
        quiet=None,
        social_scene=None,
        cycling_access=_optional_score(cycling, "score"),
    )


def resolve_score_support(
    source_data: dict[SourceName, dict[str, Any]],
) -> ScoreSupport:
    access = source_data.get(SourceName.ACCESS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    local = source_data.get(SourceName.LOCAL, {})
    transit = source_data.get(SourceName.TRANSIT, {})
    cycling = source_data.get(SourceName.CYCLING, {})
    transit_support = _field_if_present(transit, SourceName.TRANSIT, "score")
    if not transit_support:
        transit_support = _field_if_present(access, SourceName.ACCESS, "transit_access")
    return {
        "walkability": _field_if_present(access, SourceName.ACCESS, "walkability"),
        "transit_access": transit_support,
        "affordability": (
            _field_if_present(housing, SourceName.HOUSING, "affordability")
            if housing.get("benchmark_matches_preference", True)
            else []
        ),
        "parks_outdoors": [
            *_field_if_present(access, SourceName.ACCESS, "parks_outdoors"),
            *_field_if_present(local, SourceName.LOCAL, "parks_outdoors"),
        ],
        "daily_needs": _field_if_present(access, SourceName.ACCESS, "daily_needs"),
        "dining_activity": _field_if_present(access, SourceName.ACCESS, "food_social"),
        "quiet": [],
        "social_scene": [],
        "cycling_access": _field_if_present(cycling, SourceName.CYCLING, "score"),
    }


def _field_if_present(
    data: dict[str, Any], source: SourceName, field: str
) -> list[str]:
    return [f"{source.value}.{field}"] if data.get(field) is not None else []


def _optional_score(data: dict[str, Any], key: str) -> int | None:
    raw = data.get(key)
    if not isinstance(raw, int | float) or isinstance(raw, bool):
        return None
    return max(0, min(100, int(raw)))


def _best_score(*scores: int | None) -> int | None:
    available = [score for score in scores if score is not None]
    return max(available) if available else None


def _first_score(*scores: int | None) -> int | None:
    return next((score for score in scores if score is not None), None)
