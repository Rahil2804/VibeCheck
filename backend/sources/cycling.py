from __future__ import annotations

import math
from typing import Any

from backend.snapshot import load_manifest, snapshot_connection
from backend.sources.common import SourceContext, SourceResult


NETWORK_RADIUS_M = 1_000
BIKE_SHARE_RADIUS_M = 800
SOURCE_URL = "https://open.toronto.ca/dataset/major-city-wide-cycling-routes/"


async def fetch_cycling_context(context: SourceContext) -> SourceResult:
    coordinates = context.place.coordinates
    if coordinates is None:
        return SourceResult(
            data={}, message="Cycling access needs resolved coordinates."
        )
    if not _inside_toronto(coordinates.lat, coordinates.lng):
        return SourceResult(
            data={},
            message="Cycling evidence is currently available only inside Toronto.",
            scope="City of Toronto",
            source_url=SOURCE_URL,
        )

    manifest = load_manifest()
    connection = snapshot_connection()
    if connection is None or manifest is None:
        return SourceResult(
            data={},
            message="The bundled Toronto cycling snapshot is unavailable.",
            scope="City of Toronto",
            source_url=SOURCE_URL,
        )
    try:
        segments = _nearby_segments(connection, coordinates.lat, coordinates.lng)
        stations = _nearby_stations(connection, coordinates.lat, coordinates.lng)
        data = score_cycling_access(segments, stations)
        data.update(
            {
                "scope": "City of Toronto",
                "edition": str(
                    manifest.get("edition")
                    or manifest.get("snapshot_id")
                    or "Bundled GTA snapshot"
                ),
            }
        )
        return SourceResult(
            data=data,
            message="Bundled City cycling-network and Bike Share station evidence returned.",
            updated_at=manifest.get("created_at"),
            edition=data["edition"],
            scope=data["scope"],
            source_url=SOURCE_URL,
            stale=bool(manifest.get("stale", False)),
        )
    finally:
        connection.close()


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
    protected_points = min(protected_m / 3_000, 1) * 50
    total_points = min(total_m / 5_000, 1) * 25
    station_points = min(station_count / 5, 1) * 25
    return {
        "score": round(protected_points + total_points + station_points),
        "protected_network_km": round(protected_m / 1_000, 2),
        "total_network_km": round(total_m / 1_000, 2),
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


def _inside_toronto(lat: float, lng: float) -> bool:
    return 43.58 <= lat <= 43.86 and -79.64 <= lng <= -79.11


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
