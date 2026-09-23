from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx

from backend.models import Coordinates
from backend.source_cache import get_cached_source, set_cached_source
from backend.sources.common import SourceContext, SourceResult
from backend.sources.ontario.toronto_profiles import (
    TORONTO_NEIGHBOURHOODS_URL,
    TORONTO_PROFILE_WORKBOOK_URL,
    lookup_bundled_toronto_profile,
    normalize_toronto_neighbourhood_profile,
)

TORONTO_PARKS_PACKAGE_URL = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show"
    "?id=parks-and-recreation-facilities"
)
TORONTO_RADIUS_KM = 1.5


async def fetch_toronto_context(
    context: SourceContext,
    client: httpx.AsyncClient | None = None,
) -> SourceResult:
    if context.place.coordinates is None:
        return SourceResult(
            data={}, message="Toronto local lookup needs resolved coordinates."
        )

    coordinates = context.place.coordinates
    cache_key = f"toronto:local:2021:{coordinates.lat:.4f}:{coordinates.lng:.4f}"
    cached = get_cached_source(cache_key) if client is None else None
    if cached is not None:
        return SourceResult(
            data=cached["data"],
            message=cached["message"],
            updated_at=cached["updated_at"],
        )

    parks_payload: dict[str, Any] = {}
    profile_data: dict[str, Any] = (
        lookup_bundled_toronto_profile(coordinates) if client is None else {}
    )
    should_close = client is None
    http_client = client or httpx.AsyncClient(timeout=20)
    try:
        try:
            parks_payload = await _download_package_resource(
                http_client,
                TORONTO_PARKS_PACKAGE_URL,
                preferred_formats=("GeoJSON", "JSON"),
                preferred_name="4326.geojson",
            )
        except Exception:
            parks_payload = {}
        if not profile_data:
            try:
                boundaries_response = await http_client.get(TORONTO_NEIGHBOURHOODS_URL)
                boundaries_response.raise_for_status()
                workbook_response = await http_client.get(TORONTO_PROFILE_WORKBOOK_URL)
                workbook_response.raise_for_status()
                profile_data = normalize_toronto_neighbourhood_profile(
                    boundaries_response.json(),
                    workbook_response.content,
                    coordinates,
                )
            except Exception:
                profile_data = {}
    finally:
        if should_close:
            await http_client.aclose()

    amenity_records = (
        parks_payload.get("features", []) if isinstance(parks_payload, dict) else []
    )
    updated_at = datetime.now(UTC).isoformat()
    data = normalize_toronto_open_data(
        [],
        amenity_records,
        context.place.coordinates,
        updated_at=updated_at,
    )
    data.update(profile_data)
    if not _has_meaningful_local_data(data):
        return SourceResult(
            data={},
            message="Toronto open data returned no nearby neighbourhood or parks context.",
            updated_at=updated_at,
        )
    message = _source_message(data)
    if client is None:
        set_cached_source(
            cache_key,
            {"data": data, "message": message, "updated_at": updated_at},
            ttl=timedelta(days=7),
        )
    return SourceResult(data=data, message=message, updated_at=updated_at)


def normalize_toronto_open_data(
    _deferred_permit_records: list[dict[str, Any]],
    amenity_records: list[dict[str, Any]],
    center: Coordinates,
    *,
    updated_at: str,
) -> dict[str, Any]:
    amenities = summarize_amenity_records(
        amenity_records,
        center,
        radius_km=TORONTO_RADIUS_KM,
    )
    return {
        "coverage_area": "Toronto",
        **amenities,
        "summary": "Toronto open data returned nearby parks and recreation context.",
        "updated_at": updated_at,
    }


def summarize_amenity_records(
    records: list[dict[str, Any]],
    center: Coordinates,
    *,
    radius_km: float,
) -> dict[str, Any]:
    nearby = [record for record in records if _is_nearby(record, center, radius_km)]
    parks = [_asset_name(record) for record in nearby if "park" in _record_text(record)]
    community = [
        _asset_name(record)
        for record in nearby
        if "community recreation centre" in _record_text(record)
    ]
    parks_count = len({name for name in parks if name})
    community_count = len({name for name in community if name})
    return {
        "parks_count": parks_count,
        "community_amenities_count": community_count,
        "parks_outdoors": _clamp_score(parks_count * 12 + community_count * 4),
    }


async def _download_package_resource(
    client: httpx.AsyncClient,
    package_url: str,
    *,
    preferred_formats: tuple[str, ...],
    preferred_name: str | None = None,
) -> Any:
    package_response = await client.get(package_url)
    package_response.raise_for_status()
    package_payload = package_response.json()
    resources = package_payload.get("result", {}).get("resources", [])
    resource = _select_resource(
        resources,
        preferred_formats=preferred_formats,
        preferred_name=preferred_name,
    )
    resource_response = await client.get(resource["url"])
    resource_response.raise_for_status()
    return resource_response.json()


def _select_resource(
    resources: list[dict[str, Any]],
    *,
    preferred_formats: tuple[str, ...],
    preferred_name: str | None,
) -> dict[str, Any]:
    normalized_formats = {item.lower() for item in preferred_formats}
    for resource in resources:
        name = str(resource.get("name") or "").lower()
        resource_format = str(resource.get("format") or "").lower()
        if preferred_name and preferred_name.lower() not in name:
            continue
        if resource_format in normalized_formats and resource.get("url"):
            return resource
    for resource in resources:
        resource_format = str(resource.get("format") or "").lower()
        if resource_format in normalized_formats and resource.get("url"):
            return resource
    raise ValueError(
        f"No Toronto resource found for formats: {', '.join(preferred_formats)}"
    )


def _is_nearby(record: dict[str, Any], center: Coordinates, radius_km: float) -> bool:
    coordinates = _record_coordinates(record)
    if coordinates is None:
        return False
    return _distance_km(center, coordinates) <= radius_km


def _record_coordinates(record: dict[str, Any]) -> Coordinates | None:
    geometry = record.get("geometry")
    if isinstance(geometry, dict):
        raw = geometry.get("coordinates")
        pair = _coordinate_pair(raw)
        if pair is not None:
            lng = _to_float(pair[0])
            lat = _to_float(pair[1])
            if lat is not None and lng is not None:
                return Coordinates(lat=lat, lng=lng)

    lat = _first_float(record, ("LATITUDE", "latitude", "Lat", "lat", "Y"))
    lng = _first_float(record, ("LONGITUDE", "longitude", "Lon", "lng", "X"))
    if lat is None or lng is None:
        return None
    return Coordinates(lat=lat, lng=lng)


def _coordinate_pair(raw: Any) -> list[Any] | None:
    if not isinstance(raw, list) or len(raw) == 0:
        return None
    if len(raw) < 2:
        first = raw[0]
        return first if isinstance(first, list) and len(first) >= 2 else None
    if all(not isinstance(item, list) for item in raw[:2]):
        return raw
    first = raw[0]
    if isinstance(first, list) and len(first) >= 2:
        return first
    return None


def _first_float(record: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _to_float(record.get(key))
        if value is not None:
            return value
    return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in record.values():
        if isinstance(value, dict):
            parts.extend(str(item) for item in value.values())
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def _asset_name(record: dict[str, Any]) -> str:
    properties = record.get("properties")
    if isinstance(properties, dict):
        return str(
            properties.get("AssetName")
            or properties.get("ASSET_NAME")
            or properties.get("asset_name")
            or ""
        )
    return str(
        record.get("AssetName")
        or record.get("ASSET_NAME")
        or record.get("asset_name")
        or ""
    )


def _distance_km(start: Coordinates, end: Coordinates) -> float:
    earth_radius_km = 6371.0
    lat1 = radians(start.lat)
    lat2 = radians(end.lat)
    delta_lat = radians(end.lat - start.lat)
    delta_lng = radians(end.lng - start.lng)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lng / 2) ** 2
    return 2 * earth_radius_km * asin(sqrt(value))


def _clamp_score(value: int | float) -> int:
    return max(0, min(100, int(value)))


def _has_meaningful_local_data(data: dict[str, Any]) -> bool:
    return bool(data.get("neighbourhood_id")) or any(
        int(data.get(key, 0) or 0) > 0
        for key in (
            "parks_count",
            "community_amenities_count",
        )
    )


def _source_message(data: dict[str, Any]) -> str:
    park_count = int(data.get("parks_count", 0) or 0)
    amenity_count = int(data.get("community_amenities_count", 0) or 0)
    has_profile = bool(data.get("neighbourhood_id"))
    if has_profile and (park_count or amenity_count):
        return "Toronto open data returned 2021 neighbourhood and nearby parks context."
    if has_profile:
        return "Toronto open data returned 2021 neighbourhood context."
    if park_count or amenity_count:
        return "Toronto open data returned nearby parks context."
    return "Toronto open data returned local signals."
