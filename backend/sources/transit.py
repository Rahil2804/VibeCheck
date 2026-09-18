from __future__ import annotations

import math
from datetime import date
from typing import Any

from backend.snapshot import load_manifest, snapshot_connection
from backend.sources.common import SourceContext, SourceResult


NORMAL_STOP_RADIUS_M = 800
RAPID_STOP_RADIUS_M = 1_200
RAPID_ROUTE_TYPES = {0, 1, 2}
SOURCE_URL = "https://www.metrolinx.com/en/about-us/open-data"


async def fetch_transit_context(context: SourceContext) -> SourceResult:
    coordinates = context.place.coordinates
    if coordinates is None:
        return SourceResult(
            data={}, message="Scheduled transit needs resolved coordinates."
        )

    manifest = load_manifest()
    connection = snapshot_connection()
    if connection is None or manifest is None:
        return SourceResult(
            data={},
            message="The bundled scheduled-transit snapshot is unavailable; OSM may be used as fallback.",
        )
    try:
        covered_agencies = _covered_agencies(
            connection, coordinates.lat, coordinates.lng
        )
        if not covered_agencies:
            return SourceResult(
                data={},
                message="This location is outside the six-agency scheduled-transit snapshot.",
                edition=_edition(manifest),
                scope="TTC, GO/UP, MiWay, Brampton Transit, YRT, and Durham Region Transit",
                source_url=SOURCE_URL,
            )
        expired = _expired_agencies(connection, covered_agencies)
        usable_agencies = [
            agency for agency in covered_agencies if agency not in expired
        ]
        if not usable_agencies:
            return SourceResult(
                data={},
                message="Scheduled transit feeds covering this point are expired; OSM fallback is labelled separately.",
                edition=_edition(manifest),
                scope=", ".join(covered_agencies),
                source_url=SOURCE_URL,
                stale=True,
            )

        rows = _nearby_service(
            connection, coordinates.lat, coordinates.lng, usable_agencies
        )
        data = score_scheduled_transit(rows, covered_agencies=usable_agencies)
        data["edition"] = _edition(manifest)
        data["scope"] = ", ".join(usable_agencies)
        return SourceResult(
            data=data,
            message=(
                "Bundled regular-weekday GTFS schedule evidence returned."
                if rows
                else "The snapshot covers this point and confirms no qualifying nearby scheduled service."
            ),
            updated_at=manifest.get("created_at"),
            edition=_edition(manifest),
            scope=data["scope"],
            source_url=SOURCE_URL,
            stale=bool(expired),
        )
    finally:
        connection.close()


def score_scheduled_transit(
    rows: list[dict[str, Any]],
    *,
    covered_agencies: list[str] | None = None,
) -> dict[str, Any]:
    eligible = []
    for row in rows:
        distance = float(row["distance_m"])
        route_type = int(row.get("route_type", 3))
        regional = bool(row.get("is_regional"))
        if distance <= NORMAL_STOP_RADIUS_M or (
            distance <= RAPID_STOP_RADIUS_M
            and (route_type in RAPID_ROUTE_TYPES or regional)
        ):
            eligible.append(row)

    if not eligible:
        return {
            "score": 0,
            "scheduled_departures_per_hour": 0.0,
            "nearby_route_count": 0,
            "nearby_stop_count": 0,
            "nearby_routes": [],
            "agencies": covered_agencies or [],
            "nearest_stop_distance_m": None,
            "rapid_or_regional_access": False,
            "service_date": None,
        }

    deduplicated: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in eligible:
        key = (
            str(row.get("agency", "")),
            str(row.get("route_id", "")),
            str(row.get("direction_id", "")),
        )
        current = deduplicated.get(key)
        if current is None or float(row.get("departures_per_hour", 0)) > float(
            current.get("departures_per_hour", 0)
        ):
            deduplicated[key] = row

    services = list(deduplicated.values())
    frequency = round(
        sum(float(row.get("departures_per_hour", 0)) for row in services), 1
    )
    routes = sorted(
        {
            str(row.get("route_name") or row.get("route_id"))
            for row in services
            if row.get("route_name") or row.get("route_id")
        }
    )
    agencies = sorted({str(row.get("agency")) for row in services if row.get("agency")})
    nearest = min(float(row["distance_m"]) for row in eligible)
    rapid = any(
        int(row.get("route_type", 3)) in RAPID_ROUTE_TYPES
        or bool(row.get("is_regional"))
        for row in eligible
    )

    proximity_points = 25 if nearest <= 400 else 18 if nearest <= 800 else 10
    frequency_points = min(frequency / 20, 1) * 40
    diversity_points = min(len(routes) / 6, 1) * 25
    rapid_points = 10 if rapid else 0
    score = round(proximity_points + frequency_points + diversity_points + rapid_points)
    service_dates = sorted(
        {str(row["service_date"]) for row in eligible if row.get("service_date")}
    )
    return {
        "score": max(0, min(100, score)),
        "scheduled_departures_per_hour": frequency,
        "nearby_route_count": len(routes),
        "nearby_stop_count": len(
            {str(row["stop_key"]) for row in eligible if row.get("stop_key")}
        ),
        "nearby_routes": routes,
        "agencies": agencies,
        "nearest_stop_distance_m": round(nearest),
        "rapid_or_regional_access": rapid,
        "service_date": service_dates[-1] if service_dates else None,
    }


def _covered_agencies(connection: Any, lat: float, lng: float) -> list[str]:
    rows = connection.execute(
        """
        SELECT agency FROM feed_status
        WHERE min_lat <= ? AND max_lat >= ? AND min_lng <= ? AND max_lng >= ?
        ORDER BY agency
        """,
        (lat, lat, lng, lng),
    ).fetchall()
    return [str(row["agency"]) for row in rows]


def _expired_agencies(connection: Any, agencies: list[str]) -> set[str]:
    placeholders = ",".join("?" for _ in agencies)
    rows = connection.execute(
        f"SELECT agency, feed_end_date FROM feed_status WHERE agency IN ({placeholders})",
        agencies,
    ).fetchall()
    today = date.today().isoformat()
    return {
        str(row["agency"])
        for row in rows
        if row["feed_end_date"] and str(row["feed_end_date"]) < today
    }


def _nearby_service(
    connection: Any,
    lat: float,
    lng: float,
    agencies: list[str],
) -> list[dict[str, Any]]:
    lat_delta = RAPID_STOP_RADIUS_M / 111_320
    lng_delta = RAPID_STOP_RADIUS_M / (111_320 * max(math.cos(math.radians(lat)), 0.2))
    placeholders = ",".join("?" for _ in agencies)
    rows = connection.execute(
        f"""
        SELECT * FROM transit_stop_service
        WHERE agency IN ({placeholders})
          AND stop_lat BETWEEN ? AND ?
          AND stop_lng BETWEEN ? AND ?
        """,
        [*agencies, lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta],
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["distance_m"] = _distance_m(lat, lng, row["stop_lat"], row["stop_lng"])
        if item["distance_m"] <= RAPID_STOP_RADIUS_M:
            output.append(item)
    return output


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


def _edition(manifest: dict[str, Any]) -> str:
    return str(
        manifest.get("edition") or manifest.get("snapshot_id") or "Bundled GTA snapshot"
    )
