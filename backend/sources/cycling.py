from __future__ import annotations

import math
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from backend.geography import resolve_geography
from backend.models import CyclingEvidenceMethod
from backend.snapshot import load_manifest, snapshot_connection
from backend.sources.common import SourceContext, SourceResult
from backend.sources.osm import (
    CYCLING_RADIUS_METERS,
    OSM_SOURCE_URL,
    fetch_osm_context,
    score_cycling_lengths,
)

NETWORK_RADIUS_M = CYCLING_RADIUS_METERS
BIKE_SHARE_RADIUS_M = 800
SOURCE_URL = "https://open.toronto.ca/dataset/major-city-wide-cycling-routes/"
OFFICIAL_NETWORK_STALE_AFTER = timedelta(days=90)


async def fetch_cycling_context(
    context: SourceContext,
    client: httpx.AsyncClient | None = None,
) -> SourceResult:
    coordinates = context.place.coordinates
    if coordinates is None:
        return SourceResult(
            data={}, message="Cycling access needs resolved coordinates."
        )

    geography = context.geography or resolve_geography(context.place)
    if geography.is_toronto:
        official = _official_toronto_context(context)
        if official is not None:
            return official
    return await _osm_fallback(context, client=client)


def _official_toronto_context(context: SourceContext) -> SourceResult | None:
    coordinates = context.place.coordinates
    if coordinates is None:
        return None
    manifest = load_manifest()
    if manifest is None:
        return None
    connection = None
    try:
        connection = snapshot_connection()
        if connection is None:
            return None
        segments = _nearby_segments(connection, coordinates.lat, coordinates.lng)
        stations = _nearby_stations(connection, coordinates.lat, coordinates.lng)
        data = score_cycling_access(segments, stations)
    except (OSError, sqlite3.Error):
        return None
    finally:
        if connection is not None:
            connection.close()

    updated_at = _source_retrieved_at(manifest, "Toronto cycling network")
    stale = _is_stale(updated_at, OFFICIAL_NETWORK_STALE_AFTER)
    edition = str(
        manifest.get("edition")
        or manifest.get("snapshot_id")
        or "Bundled GTA snapshot"
    )
    data.update(
        {
            "scope": "City of Toronto",
            "edition": edition,
            "method": CyclingEvidenceMethod.TORONTO_OFFICIAL.value,
            "fallback": False,
            "network_radius_m": NETWORK_RADIUS_M,
            "bicycle_parking_locations": None,
            "updated_at": updated_at,
            "source_url": SOURCE_URL,
        }
    )
    return SourceResult(
        data=data,
        message=(
            "Bundled City cycling-network evidence returned; Bike Share station locations are context only."
        ),
        updated_at=updated_at,
        edition=edition,
        scope="City of Toronto",
        source_url=SOURCE_URL,
        stale=stale,
        fallback=False,
    )


async def _osm_fallback(
    context: SourceContext,
    *,
    client: httpx.AsyncClient | None,
) -> SourceResult:
    result = await fetch_osm_context(context, client=client)
    data = dict(result.data.get("cycling", {}))
    if not data:
        return SourceResult(
            data={},
            message="OpenStreetMap cycling evidence was unavailable.",
            scope="Mapped cycling infrastructure near this address",
            source_url=OSM_SOURCE_URL,
            stale=bool(result.stale),
            fallback=True,
        )
    data.update(
        {
            "scope": "OpenStreetMap mapped cycling infrastructure",
            "edition": "OpenStreetMap live proximity query",
            "method": CyclingEvidenceMethod.OSM_FALLBACK.value,
            "fallback": True,
            "bike_share_stations": None,
            "updated_at": result.updated_at,
            "source_url": OSM_SOURCE_URL,
        }
    )
    has_network = bool(data.get("total_network_km"))
    return SourceResult(
        data=data,
        message=(
            "Using stale cached OpenStreetMap cycling evidence because live endpoints are unavailable."
            if result.stale
            else "OpenStreetMap returned mapped cycling infrastructure near this address."
            if has_network
            else "OpenStreetMap returned no mapped qualifying cycling infrastructure within 1 km."
        ),
        updated_at=result.updated_at,
        edition=data["edition"],
        scope=data["scope"],
        source_url=OSM_SOURCE_URL,
        stale=bool(result.stale),
        fallback=True,
    )


def score_cycling_access(
    segments: list[dict[str, Any]],
    stations: list[dict[str, Any]],
) -> dict[str, Any]:
    nearby_segments = [
        segment
        for segment in segments
        if float(segment.get("distance_m", NETWORK_RADIUS_M + 1)) <= NETWORK_RADIUS_M
    ]
    protected_m = sum(
        float(segment.get("length_m", 0))
        for segment in nearby_segments
        if bool(segment.get("protected"))
    )
    total_m = sum(float(segment.get("length_m", 0)) for segment in nearby_segments)
    station_count = sum(
        1
        for station in stations
        if float(station.get("distance_m", BIKE_SHARE_RADIUS_M + 1))
        <= BIKE_SHARE_RADIUS_M
    )
    protected_km = protected_m / 1_000
    total_km = total_m / 1_000
    return {
        "score": score_cycling_lengths(protected_km, total_km),
        "protected_network_km": round(protected_km, 2),
        "total_network_km": round(total_km, 2),
        "bike_share_stations": station_count,
    }


def _nearby_segments(connection: Any, lat: float, lng: float) -> list[dict[str, Any]]:
    rows = _bounded_rows(connection, "cycling_segments", lat, lng, NETWORK_RADIUS_M)
    output = []
    for row in rows:
        item = dict(row)
        item["distance_m"] = _distance_m(lat, lng, row["center_lat"], row["center_lng"])
        output.append(item)
    return output


def _nearby_stations(connection: Any, lat: float, lng: float) -> list[dict[str, Any]]:
    rows = _bounded_rows(
        connection, "bike_share_stations", lat, lng, BIKE_SHARE_RADIUS_M
    )
    output = []
    for row in rows:
        item = dict(row)
        item["distance_m"] = _distance_m(lat, lng, row["lat"], row["lng"])
        output.append(item)
    return output


def _bounded_rows(
    connection: Any,
    table: str,
    lat: float,
    lng: float,
    radius_m: int,
) -> list[Any]:
    lat_field = "center_lat" if table == "cycling_segments" else "lat"
    lng_field = "center_lng" if table == "cycling_segments" else "lng"
    lat_delta = radius_m / 111_320
    lng_delta = radius_m / (111_320 * max(math.cos(math.radians(lat)), 0.2))
    return connection.execute(
        f"""
        SELECT * FROM {table}
        WHERE {lat_field} BETWEEN ? AND ? AND {lng_field} BETWEEN ? AND ?
        """,
        (lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta),
    ).fetchall()


def _source_retrieved_at(manifest: dict[str, Any], source_name: str) -> str | None:
    for source in manifest.get("sources", []):
        if isinstance(source, dict) and source.get("name") == source_name:
            value = source.get("retrieved_at")
            return str(value) if value else None
    value = manifest.get("created_at")
    return str(value) if value else None


def _is_stale(value: str | None, max_age: timedelta) -> bool:
    if not value:
        return True
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp < datetime.now(UTC) - max_age


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
