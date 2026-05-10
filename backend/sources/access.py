from typing import Any

LOW_SCORE = 30

CATEGORY_KEYS = (
    "groceries",
    "pharmacies",
    "restaurants",
    "cafes",
    "bars",
    "transit",
    "parks",
    "libraries",
    "community",
)


async def fetch_access_context() -> dict[str, Any]:
    return {
        "walkability": 50,
        "transit_access": 50,
        "daily_needs": 50,
        "food_social": 50,
        "parks_outdoors": 50,
        "nearby_categories": {
            "groceries": 0,
            "parks": 0,
            "restaurants": 0,
            "transit": 0,
        },
    }


def normalize_access_payload(payload: dict[str, Any]) -> dict[str, Any]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass payload missing elements list")

    categories = _empty_categories()
    seen: set[tuple[str, int]] = set()

    for element in elements:
        if not isinstance(element, dict):
            continue
        element_type = str(element.get("type", "node"))
        element_id = element.get("id")
        if not isinstance(element_id, int):
            continue
        identity = (element_type, element_id)
        if identity in seen:
            continue
        seen.add(identity)

        tags = element.get("tags")
        if not isinstance(tags, dict):
            continue
        for category in _categories_for_tags(tags):
            categories[category] += 1

    daily_needs = _score_daily_needs(categories)
    food_social = _score_food_social(categories)
    transit_access = _score_count(categories["transit"], useful=4, dense=12)
    parks_outdoors = _score_count(categories["parks"], useful=2, dense=6)
    walkability = _weighted_score(
        daily_needs=daily_needs,
        food_social=food_social,
        transit_access=transit_access,
        parks_outdoors=parks_outdoors,
        community_count=categories["community"] + categories["libraries"],
    )

    return {
        "walkability": walkability,
        "transit_access": transit_access,
        "daily_needs": daily_needs,
        "food_social": food_social,
        "parks_outdoors": parks_outdoors,
        "nearby_categories": categories,
        "summary": _summary(categories),
    }


def _empty_categories() -> dict[str, int]:
    return {key: 0 for key in CATEGORY_KEYS}


def _categories_for_tags(tags: dict[str, Any]) -> list[str]:
    categories: list[str] = []
    shop = tags.get("shop")
    amenity = tags.get("amenity")
    highway = tags.get("highway")
    public_transport = tags.get("public_transport")
    railway = tags.get("railway")
    leisure = tags.get("leisure")
    landuse = tags.get("landuse")

    if shop in {"supermarket", "convenience", "grocery"}:
        categories.append("groceries")
    if amenity == "pharmacy":
        categories.append("pharmacies")
    if amenity == "library":
        categories.append("libraries")
    if amenity == "restaurant":
        categories.append("restaurants")
    if amenity in {"cafe", "fast_food"}:
        categories.append("cafes")
    if amenity in {"bar", "pub"}:
        categories.append("bars")
    if (
        highway == "bus_stop"
        or public_transport in {"platform", "station"}
        or railway in {"station", "subway_entrance", "tram_stop"}
    ):
        categories.append("transit")
    if leisure in {"park", "garden", "playground", "recreation_ground"}:
        categories.append("parks")
    if landuse == "recreation_ground":
        categories.append("parks")
    if amenity in {"community_centre", "townhall", "clinic", "doctors"}:
        categories.append("community")

    return categories


def _score_daily_needs(categories: dict[str, int]) -> int:
    weighted_count = (
        categories["groceries"] * 2
        + categories["pharmacies"] * 2
        + categories["libraries"]
        + categories["community"]
    )
    return _score_count(weighted_count, useful=4, dense=12)


def _score_food_social(categories: dict[str, int]) -> int:
    weighted_count = categories["restaurants"] + categories["cafes"] + categories["bars"]
    return _score_count(weighted_count, useful=4, dense=20)


def _score_count(count: int, *, useful: int, dense: int) -> int:
    if count <= 0:
        return LOW_SCORE
    if count >= dense:
        return 88
    if count >= useful:
        return 70 + min(15, int((count - useful) * 15 / max(dense - useful, 1)))
    return 40 + int(count * 30 / useful)


def _weighted_score(
    *,
    daily_needs: int,
    food_social: int,
    transit_access: int,
    parks_outdoors: int,
    community_count: int,
) -> int:
    score = int(
        daily_needs * 0.35
        + food_social * 0.25
        + transit_access * 0.2
        + parks_outdoors * 0.15
        + min(8, community_count * 2)
    )
    return max(LOW_SCORE, _clamp(score))


def _summary(categories: dict[str, int]) -> str:
    found = [label for label, count in categories.items() if count > 0]
    if not found:
        return "Public POI query returned no nearby everyday destination signals."
    return f"Nearby public POI signals found {', '.join(found)} within the access radius."


def _clamp(score: int) -> int:
    return max(0, min(100, score))
