from __future__ import annotations

import asyncio
import math
import re
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any

import httpx

from backend.source_cache import (
    get_cached_source,
    get_stale_cached_source,
    set_cached_source,
)
from backend.sources.common import SourceContext, SourceResult

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
OVERPASS_USER_AGENT = "VibeCheck/1.0 (+https://github.com/Rahil2804/VibeCheck)"
ACCESS_RADIUS_METERS = 1_200
CYCLING_RADIUS_METERS = 1_000
BICYCLE_PARKING_RADIUS_METERS = 800
OVERPASS_TIMEOUT_SECONDS = 6
ENDPOINT_COOLDOWN_SECONDS = 60
LOW_SCORE = 30
OSM_CACHE_VERSION = "v2"
OSM_SOURCE_URL = "https://www.openstreetmap.org/copyright"

_UNHEALTHY_UNTIL: dict[str, float] = {}
_INFLIGHT: dict[str, asyncio.Task[SourceResult]] = {}

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

_CYCLEWAY_VALUES = {"track", "lane", "shared_lane", "share_busway"}
_BLOCKED_BICYCLE_ACCESS = {"no", "private", "dismount"}
_VALUE_SPLIT = re.compile(r"[;|]")


async def fetch_osm_context(
    context: SourceContext,
    client: httpx.AsyncClient | None = None,
    *,
    use_cache: bool = True,
) -> SourceResult:
    coordinates = context.place.coordinates
    if coordinates is None:
        return SourceResult(
            data={}, message="OpenStreetMap lookup needs resolved coordinates."
        )

    cache_key = _cache_key(coordinates.lat, coordinates.lng)
    if client is not None:
        return await _fetch_live(
            context,
            client=client,
            cache_key=cache_key,
            use_cache=False,
        )

    if use_cache:
        cached = get_cached_source(cache_key)
        if cached is not None:
            return _cached_result(cached)

    task = _INFLIGHT.get(cache_key)
    if task is None:
        task = asyncio.create_task(
            _fetch_live(
                context,
                client=None,
                cache_key=cache_key,
                use_cache=use_cache,
            )
        )
        _INFLIGHT[cache_key] = task
    try:
        return await asyncio.shield(task)
    finally:
        if task.done() and _INFLIGHT.get(cache_key) is task:
            _INFLIGHT.pop(cache_key, None)


async def _fetch_live(
    context: SourceContext,
    *,
    client: httpx.AsyncClient | None,
    cache_key: str,
    use_cache: bool,
) -> SourceResult:
    coordinates = context.place.coordinates
    if coordinates is None:
        return SourceResult(data={})

    query = build_overpass_query(lat=coordinates.lat, lng=coordinates.lng)
    should_close = client is None
    http_client = client or httpx.AsyncClient(
        timeout=3.5,
        follow_redirects=True,
        headers={"User-Agent": OVERPASS_USER_AGENT, "Accept": "application/json"},
    )
    try:
        now = monotonic()
        endpoints = tuple(
            endpoint
            for endpoint in OVERPASS_URLS
            if _UNHEALTHY_UNTIL.get(endpoint, 0) <= now
        )
        last_error: Exception | None = None
        data: dict[str, Any] | None = None
        endpoint_used: str | None = None
        for endpoint in endpoints:
            try:
                response = await http_client.post(endpoint, data={"data": query})
                response.raise_for_status()
                data = normalize_osm_payload(
                    response.json(),
                    lat=coordinates.lat,
                    lng=coordinates.lng,
                )
                endpoint_used = endpoint
                _UNHEALTHY_UNTIL.pop(endpoint, None)
                break
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if client is None and _should_cool_down(exc):
                    _UNHEALTHY_UNTIL[endpoint] = (
                        monotonic() + ENDPOINT_COOLDOWN_SECONDS
                    )
        if data is None:
            stale = (
                get_stale_cached_source(cache_key, max_stale=timedelta(days=6))
                if client is None and use_cache
                else None
            )
            if stale is not None:
                return SourceResult(
                    data=stale["data"],
                    message=(
                        "Using the last successful OpenStreetMap neighbourhood result "
                        "because live endpoints are unavailable."
                    ),
                    updated_at=stale["updated_at"],
                    source_url=stale.get("source_url") or OSM_SOURCE_URL,
                    stale=True,
                )
            if last_error is not None:
                raise last_error
            raise RuntimeError("No Overpass endpoint returned usable data.")
    finally:
        if should_close:
            await http_client.aclose()

    checked_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    result = SourceResult(
        data=data,
        message="OpenStreetMap neighbourhood evidence returned.",
        updated_at=checked_at,
        source_url=OSM_SOURCE_URL,
    )
    if client is None and use_cache:
        set_cached_source(
            cache_key,
            {
                "data": data,
                "message": result.message,
                "updated_at": checked_at,
                "source_url": OSM_SOURCE_URL,
                "endpoint": endpoint_used,
            },
            ttl=timedelta(hours=24),
        )
    return result


def _cached_result(cached: dict[str, Any]) -> SourceResult:
    return SourceResult(
        data=cached["data"],
        message=cached.get("message"),
        updated_at=cached.get("updated_at"),
        source_url=cached.get("source_url") or OSM_SOURCE_URL,
    )


def _cache_key(lat: float, lng: float) -> str:
    return f"osm:neighbourhood:{OSM_CACHE_VERSION}:{lat:.4f}:{lng:.4f}"


def _should_cool_down(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if not isinstance(exc, httpx.HTTPStatusError):
        return False
    status = exc.response.status_code
    return status in {406, 429} or status >= 500


def build_overpass_query(*, lat: float, lng: float) -> str:
    access = f"around:{ACCESS_RADIUS_METERS},{lat},{lng}"
    cycling = f"around:{CYCLING_RADIUS_METERS},{lat},{lng}"
    parking = f"around:{BICYCLE_PARKING_RADIUS_METERS},{lat},{lng}"
    cycle_values = "^(track|lane|shared_lane|share_busway)$"
    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT_SECONDS}];
(
  node({access})[shop~"^(supermarket|convenience|grocery)$"];
  way({access})[shop~"^(supermarket|convenience|grocery)$"];
  node({access})[amenity~"^(pharmacy|library|restaurant|cafe|bar|pub|fast_food|community_centre|townhall|clinic|doctors)$"];
  way({access})[amenity~"^(pharmacy|library|restaurant|cafe|bar|pub|fast_food|community_centre|townhall|clinic|doctors)$"];
  node({access})[highway="bus_stop"];
  node({access})[public_transport~"^(platform|station)$"];
  node({access})[railway~"^(station|subway_entrance|tram_stop)$"];
  way({access})[leisure~"^(park|garden|playground|recreation_ground)$"];
  relation({access})[leisure~"^(park|garden|playground|recreation_ground)$"];
  way({access})[landuse="recreation_ground"];
  relation({access})[landuse="recreation_ground"];
  way({cycling})[highway="cycleway"];
  way({cycling})[highway="path"][bicycle="designated"];
  way({cycling})[cycleway~"{cycle_values}"];
  way({cycling})["cycleway:left"~"{cycle_values}"];
  way({cycling})["cycleway:right"~"{cycle_values}"];
  way({cycling})["cycleway:both"~"{cycle_values}"];
  way({cycling})[bicycle_road="yes"];
  way({cycling})[cyclestreet="yes"];
  node({parking})[amenity="bicycle_parking"];
);
out geom tags;
""".strip()


def normalize_osm_payload(
    payload: dict[str, Any], *, lat: float, lng: float
) -> dict[str, Any]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass payload missing elements list")
    return {
        "access": normalize_access_payload(payload),
        "cycling": normalize_cycling_payload(payload, lat=lat, lng=lng),
    }


def normalize_access_payload(payload: dict[str, Any]) -> dict[str, Any]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass payload missing elements list")

    categories = {key: 0 for key in CATEGORY_KEYS}
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
        "summary": _access_summary(categories),
    }


def normalize_cycling_payload(
    payload: dict[str, Any], *, lat: float, lng: float
) -> dict[str, Any]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass payload missing elements list")

    seen_ways: set[int] = set()
    seen_parking: set[int] = set()
    mapped_way_count = 0
    protected_m = 0.0
    total_m = 0.0
    for element in elements:
        if not isinstance(element, dict):
            continue
        element_id = element.get("id")
        tags = element.get("tags")
        if not isinstance(element_id, int) or not isinstance(tags, dict):
            continue
        if (
            element.get("type") == "node"
            and tags.get("amenity") == "bicycle_parking"
        ):
            node_lat = _number(element.get("lat"))
            node_lng = _number(element.get("lon"))
            if (
                node_lat is not None
                and node_lng is not None
                and _distance_m(lat, lng, node_lat, node_lng)
                <= BICYCLE_PARKING_RADIUS_METERS
            ):
                seen_parking.add(element_id)
            continue
        if element.get("type") != "way" or element_id in seen_ways:
            continue
        if not _is_cycling_way(tags):
            continue
        seen_ways.add(element_id)
        length = _geometry_length_inside_radius(
            element.get("geometry"),
            center_lat=lat,
            center_lng=lng,
            radius_m=CYCLING_RADIUS_METERS,
        )
        if length <= 0:
            continue
        mapped_way_count += 1
        total_m += length
        if _is_protected_or_separated(tags):
            protected_m += length

    protected_km = protected_m / 1_000
    total_km = total_m / 1_000
    return {
        "score": score_cycling_lengths(protected_km, total_km),
        "protected_network_km": round(protected_km, 2),
        "total_network_km": round(total_km, 2),
        "bicycle_parking_locations": len(seen_parking),
        "mapped_cycling_ways": mapped_way_count,
        "network_radius_m": CYCLING_RADIUS_METERS,
    }


def score_cycling_lengths(protected_km: float, total_km: float) -> int:
    protected_points = min(max(protected_km, 0) / 3, 1) * 67
    total_points = min(max(total_km, 0) / 5, 1) * 33
    return round(protected_points + total_points)


def _is_cycling_way(tags: dict[str, Any]) -> bool:
    if str(tags.get("bicycle", "")).casefold() in _BLOCKED_BICYCLE_ACCESS:
        return False
    highway = str(tags.get("highway", "")).casefold()
    if highway == "crossing" or highway.endswith("_link"):
        return False
    if highway == "cycleway":
        return True
    if highway == "path" and str(tags.get("bicycle", "")).casefold() == "designated":
        return True
    if str(tags.get("bicycle_road", "")).casefold() == "yes":
        return True
    if str(tags.get("cyclestreet", "")).casefold() == "yes":
        return True
    return bool(_cycleway_values(tags) & _CYCLEWAY_VALUES)


def _is_protected_or_separated(tags: dict[str, Any]) -> bool:
    highway = str(tags.get("highway", "")).casefold()
    if highway == "cycleway":
        return True
    if highway == "path" and str(tags.get("bicycle", "")).casefold() == "designated":
        return True
    return "track" in _cycleway_values(tags)


def _cycleway_values(tags: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both"):
        raw = tags.get(key)
        if raw is None:
            continue
        values.update(
            value.strip().casefold()
            for value in _VALUE_SPLIT.split(str(raw))
            if value.strip()
        )
    return values


def _geometry_length_inside_radius(
    geometry: Any, *, center_lat: float, center_lng: float, radius_m: float
) -> float:
    if not isinstance(geometry, list) or len(geometry) < 2:
        return 0.0
    points: list[tuple[float, float]] = []
    cos_lat = max(math.cos(math.radians(center_lat)), 0.01)
    for point in geometry:
        if not isinstance(point, dict):
            continue
        point_lat = _number(point.get("lat"))
        point_lng = _number(point.get("lon"))
        if point_lat is None or point_lng is None:
            continue
        points.append(
            (
                (point_lng - center_lng) * 111_320 * cos_lat,
                (point_lat - center_lat) * 111_320,
            )
        )
    return sum(
        _segment_length_inside_circle(start, end, radius_m)
        for start, end in zip(points, points[1:])
    )


def _segment_length_inside_circle(
    start: tuple[float, float], end: tuple[float, float], radius_m: float
) -> float:
    x1, y1 = start
    dx, dy = end[0] - x1, end[1] - y1
    length = math.hypot(dx, dy)
    if length <= 0:
        return 0.0
    a = dx * dx + dy * dy
    b = 2 * (x1 * dx + y1 * dy)
    c = x1 * x1 + y1 * y1 - radius_m * radius_m
    bounds = [0.0, 1.0]
    discriminant = b * b - 4 * a * c
    if discriminant >= 0:
        root = math.sqrt(discriminant)
        for value in ((-b - root) / (2 * a), (-b + root) / (2 * a)):
            if 0 < value < 1:
                bounds.append(value)
    bounds.sort()
    fraction = 0.0
    for left, right in zip(bounds, bounds[1:]):
        midpoint = (left + right) / 2
        x = x1 + midpoint * dx
        y = y1 + midpoint * dy
        if x * x + y * y <= radius_m * radius_m:
            fraction += right - left
    return length * fraction


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


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
    weighted_count = (
        categories["restaurants"] + categories["cafes"] + categories["bars"]
    )
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
    parks_outdoors: int,
    community_count: int,
) -> int:
    score = int(
        daily_needs * 0.45
        + food_social * 0.30
        + parks_outdoors * 0.20
        + min(5, community_count)
    )
    return max(LOW_SCORE, max(0, min(100, score)))


def _access_summary(categories: dict[str, int]) -> str:
    found = [label for label, count in categories.items() if count > 0]
    if not found:
        return "Public POI query returned no nearby everyday destination signals."
    return (
        f"Nearby public POI signals found {', '.join(found)} within the access radius."
    )
