from backend.models import (
    CoverageLevel,
    CoverageRegion,
    CoverageSummary,
    Place,
    VibeScores,
)
from backend.sources.local import is_gta_place, is_toronto_place


SCORE_LABELS = {
    "walkability": "Walkability",
    "transit_access": "Transit access",
    "affordability": "Rent context",
    "parks_outdoors": "Parks and outdoors",
    "daily_needs": "Daily needs",
    "dining_activity": "Dining and activity",
    "cycling_access": "Cycling access",
}


def build_coverage(place: Place, scores: VibeScores) -> CoverageSummary:
    region = _region(place)
    level = {
        CoverageRegion.TORONTO: CoverageLevel.FULL,
        CoverageRegion.GTA: CoverageLevel.PARTIAL,
        CoverageRegion.OUTSIDE_GTA: CoverageLevel.LIMITED,
    }[region]
    supported = [
        label
        for field, label in SCORE_LABELS.items()
        if getattr(scores, field) is not None
    ]
    unavailable = [
        label for field, label in SCORE_LABELS.items() if getattr(scores, field) is None
    ]
    tier_messages = {
        CoverageRegion.TORONTO: (
            "Toronto is eligible for the deepest local evidence tier."
        ),
        CoverageRegion.GTA: (
            "This location is eligible for the GTA regional evidence tier."
        ),
        CoverageRegion.OUTSIDE_GTA: (
            "Outside the GTA, this is a limited place and nearby-access check."
        ),
    }
    supported_copy = ", ".join(supported) if supported else "no analytical signals"
    unavailable_copy = ", ".join(unavailable) if unavailable else "none"
    return CoverageSummary(
        region=region,
        level=level,
        supported_signals=supported,
        unavailable_signals=unavailable,
        message=(
            f"{tier_messages[region]} Supported now: {supported_copy}. "
            f"Unavailable now: {unavailable_copy}."
        ),
    )


def _region(place: Place) -> CoverageRegion:
    if is_toronto_place(place) or _in_box(place, 43.58, 43.86, -79.64, -79.11):
        return CoverageRegion.TORONTO
    if is_gta_place(place) or _in_box(place, 43.40, 44.25, -80.15, -78.75):
        return CoverageRegion.GTA
    return CoverageRegion.OUTSIDE_GTA


def _in_box(
    place: Place,
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
) -> bool:
    coordinates = place.coordinates
    return bool(
        coordinates
        and min_lat <= coordinates.lat <= max_lat
        and min_lng <= coordinates.lng <= max_lng
    )
