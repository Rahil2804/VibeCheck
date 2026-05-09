from typing import Any

from backend.models import SourceName, VibeScores

ScoreSupport = dict[str, list[str]]


def resolve_vibe_scores(source_data: dict[SourceName, dict[str, Any]]) -> VibeScores:
    access = source_data.get(SourceName.ACCESS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    reddit = source_data.get(SourceName.REDDIT, {})
    local = source_data.get(SourceName.LOCAL, {})

    local_parks = _optional_score(local, "parks_outdoors")
    parks_count = _int_from(local, "parks_count")
    amenities_count = _int_from(local, "community_amenities_count")

    walkability = _score_from(access, "walkability", 50)
    local_walkability = _local_walkability_score(local_parks, parks_count, amenities_count)
    if local_walkability is not None:
        walkability = max(walkability, local_walkability)

    quiet = _score_from(reddit, "quiet", 50)
    local_quiet = _local_quiet_score(local_parks, parks_count)
    if local_quiet is not None:
        quiet = max(quiet, local_quiet)

    social_scene = _score_from(reddit, "social_scene", 50)
    local_social = _local_social_score(amenities_count)
    if local_social is not None:
        social_scene = max(social_scene, local_social)

    return VibeScores(
        walkability=walkability,
        transit_access=_score_from(access, "transit_access", 50),
        affordability=_score_from(housing, "affordability", 50),
        quiet=quiet,
        social_scene=social_scene,
        parks_outdoors=local_parks,
    )


def resolve_score_support(source_data: dict[SourceName, dict[str, Any]]) -> ScoreSupport:
    access = source_data.get(SourceName.ACCESS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    reddit = source_data.get(SourceName.REDDIT, {})
    local = source_data.get(SourceName.LOCAL, {})
    scores = resolve_vibe_scores(source_data)

    base_walkability = _score_from(access, "walkability", 50)
    base_quiet = _score_from(reddit, "quiet", 50)
    base_social_scene = _score_from(reddit, "social_scene", 50)

    support: ScoreSupport = {
        "walkability": _field_if_present(access, SourceName.ACCESS, "walkability"),
        "transit_access": _field_if_present(access, SourceName.ACCESS, "transit_access"),
        "affordability": _field_if_present(housing, SourceName.HOUSING, "affordability"),
        "quiet": _field_if_present(reddit, SourceName.REDDIT, "quiet"),
        "social_scene": _field_if_present(reddit, SourceName.REDDIT, "social_scene"),
        "parks_outdoors": _field_if_present(local, SourceName.LOCAL, "parks_outdoors"),
    }

    if (
        scores.walkability > base_walkability
        and _optional_score(local, "parks_outdoors") is not None
    ):
        support["walkability"].extend(
            [
                "local.parks_outdoors",
                "local.parks_count",
                "local.community_amenities_count",
            ]
        )
    if scores.quiet > base_quiet and _optional_score(local, "parks_outdoors") is not None:
        support["quiet"].extend(["local.parks_outdoors", "local.parks_count"])
    if (
        scores.social_scene > base_social_scene
        and _int_from(local, "community_amenities_count") > 0
    ):
        support["social_scene"].append("local.community_amenities_count")

    return {key: _dedupe(fields) for key, fields in support.items()}


def _local_walkability_score(
    local_parks: int | None,
    parks_count: int,
    amenities_count: int,
) -> int | None:
    if local_parks is None:
        return None
    lift = max(local_parks - 50, 0) * 0.35
    destination_lift = min(6, parks_count + amenities_count)
    return _clamp(int(50 + lift + destination_lift))


def _local_quiet_score(local_parks: int | None, parks_count: int) -> int | None:
    if local_parks is None:
        return None
    lift = max(local_parks - 50, 0) * 0.2
    park_lift = min(4, parks_count // 2)
    return _clamp(int(50 + lift + park_lift))


def _local_social_score(amenities_count: int) -> int | None:
    if amenities_count <= 0:
        return None
    return _clamp(50 + min(16, amenities_count * 4))


def _field_if_present(data: dict[str, Any], source: SourceName, field: str) -> list[str]:
    return [f"{source.value}.{field}"] if data.get(field) is not None else []


def _optional_score(data: dict[str, Any], key: str) -> int | None:
    raw = data.get(key)
    if not isinstance(raw, int | float):
        return None
    return _clamp(int(raw))


def _score_from(data: dict[str, Any], key: str, default: int) -> int:
    raw = data.get(key, default)
    if not isinstance(raw, int | float):
        return default
    return _clamp(int(raw))


def _int_from(data: dict[str, Any], key: str) -> int:
    raw = data.get(key, 0)
    return raw if isinstance(raw, int) else 0


def _clamp(score: int) -> int:
    return max(0, min(100, score))


def _dedupe(fields: list[str]) -> list[str]:
    deduped: list[str] = []
    for field in fields:
        if field not in deduped:
            deduped.append(field)
    return deduped
