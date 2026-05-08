from __future__ import annotations

from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx

from backend.models import Coordinates
from backend.sources.common import SourceContext, SourceResult


TORONTO_PERMITS_PACKAGE_URL = (
    "https://open.toronto.ca/api/3/action/package_show"
    "?id=building-permits-active-permits"
)
TORONTO_PARKS_PACKAGE_URL = (
    "https://open.toronto.ca/api/3/action/package_show"
    "?id=parks-and-recreation-facilities"
)
TORONTO_RADIUS_KM = 1.5
MAJOR_PERMIT_KEYWORDS = ("new building", "demolition", "addition")


async def fetch_toronto_context(context: SourceContext) -> SourceResult:
    if context.place.coordinates is None:
        return SourceResult(data={}, message="Toronto local lookup needs resolved coordinates.")

    async with httpx.AsyncClient(timeout=8) as client:
        permits_payload = await _download_package_resource(
            client,
            TORONTO_PERMITS_PACKAGE_URL,
            preferred_formats=("JSON",),
        )
        parks_payload = await _download_package_resource(
            client,
            TORONTO_PARKS_PACKAGE_URL,
            preferred_formats=("GeoJSON", "JSON"),
            preferred_name="4326.geojson",
        )

    permit_records = (
        permits_payload
        if isinstance(permits_payload, list)
        else permits_payload.get("records", [])
    )
    amenity_records = (
        parks_payload.get("features", []) if isinstance(parks_payload, dict) else []
    )
    updated_at = datetime.now(UTC).isoformat()
    data = normalize_toronto_open_data(
        permit_records,
        amenity_records,
        context.place.coordinates,
        updated_at=updated_at,
    )
    if not _has_meaningful_local_data(data):
        return SourceResult(
            data={},
            message="Toronto open data returned no nearby development or parks signals.",
            updated_at=updated_at,
        )
    return SourceResult(
        data=data,
        message="Toronto open data returned development and parks signals.",
        updated_at=updated_at,
    )


def normalize_toronto_open_data(
    permit_records: list[dict[str, Any]],
    amenity_records: list[dict[str, Any]],
    center: Coordinates,
    *,
    updated_at: str,
) -> dict[str, Any]:
    permits = summarize_permit_records(
        permit_records,
        center,
        radius_km=TORONTO_RADIUS_KM,
    )
    amenities = summarize_amenity_records(
        amenity_records,
        center,
        radius_km=TORONTO_RADIUS_KM,
    )
    return {
        "coverage_area": "Toronto",
        **permits,
        **amenities,
        "summary": "Toronto open data returned nearby development and parks/amenity signals.",
        "updated_at": updated_at,
    }


def summarize_permit_records(
    records: list[dict[str, Any]],
    center: Coordinates,
    *,
    radius_km: float,
) -> dict[str, Any]:
    nearby = [record for record in records if _is_nearby(record, center, radius_km)]
    major = [record for record in nearby if _is_major_permit(record)]
    development_activity = _clamp_score(len(nearby) * 12 + len(major) * 8)
    trajectory_signal = "uncertain"
    if development_activity >= 50 or len(major) >= 3:
        trajectory_signal = "rising"
    elif nearby:
        trajectory_signal = "stable"
    return {
        "development_activity": development_activity,
        "recent_permits_count": len(nearby),
        "major_project_count": len(major),
        "trajectory_signal": trajectory_signal,
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
    raise ValueError(f"No Toronto resource found for formats: {', '.join(preferred_formats)}")


def _is_nearby(record: dict[str, Any], center: Coordinates, radius_km: float) -> bool:
    coordinates = _record_coordinates(record)
    if coordinates is None:
        return False
    return _distance_km(center, coordinates) <= radius_km


def _record_coordinates(record: dict[str, Any]) -> Coordinates | None:
    geometry = record.get("geometry")
    if isinstance(geometry, dict):
        raw = geometry.get("coordinates")
        if isinstance(raw, list) and len(raw) >= 2:
            lng = _to_float(raw[0])
            lat = _to_float(raw[1])
            if lat is not None and lng is not None:
                return Coordinates(lat=lat, lng=lng)

    lat = _first_float(record, ("LATITUDE", "latitude", "Lat", "lat", "Y"))
    lng = _first_float(record, ("LONGITUDE", "longitude", "Lon", "lng", "X"))
    if lat is None or lng is None:
        return None
    return Coordinates(lat=lat, lng=lng)


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


def _is_major_permit(record: dict[str, Any]) -> bool:
    text = _record_text(record)
    return any(keyword in text for keyword in MAJOR_PERMIT_KEYWORDS)


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
        return str(properties.get("AssetName") or properties.get("asset_name") or "")
    return str(record.get("AssetName") or record.get("asset_name") or "")


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
    return any(
        int(data.get(key, 0) or 0) > 0
        for key in (
            "recent_permits_count",
            "major_project_count",
            "parks_count",
            "community_amenities_count",
        )
    )
