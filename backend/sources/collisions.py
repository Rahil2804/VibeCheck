from __future__ import annotations

import math
from typing import Any

from backend.snapshot import load_manifest, partition_is_stale, snapshot_connection
from backend.sources.common import SourceContext, SourceResult

RADIUS_M = 1_000
MAX_MAP_POINTS = 100
ALL_COLLISIONS_URL = "https://open.toronto.ca/dataset/traffic-collisions/"
KSI_COLLISIONS_URL = (
    "https://open.toronto.ca/dataset/"
    "motor-vehicle-collisions-involving-killed-or-seriously-injured-persons/"
)


async def fetch_collision_context(context: SourceContext) -> SourceResult:
    coordinates = context.place.coordinates
    if coordinates is None:
        return SourceResult(
            data={},
            message="Collision history needs resolved coordinates.",
            scope="City of Toronto",
            source_url=ALL_COLLISIONS_URL,
        )
    if not (context.geography and context.geography.is_toronto):
        return SourceResult(
            data={},
            message="Reported collision history is currently available only inside Toronto.",
            scope="City of Toronto",
            source_url=ALL_COLLISIONS_URL,
        )

    manifest = load_manifest()
    connection = snapshot_connection()
    if manifest is None or connection is None:
        return SourceResult(
            data={},
            message="The bundled Toronto collision snapshot is unavailable.",
            scope="City of Toronto",
            source_url=ALL_COLLISIONS_URL,
        )
    try:
        baseline = _nearby_rows(
            connection,
            "toronto_collisions",
            coordinates.lat,
            coordinates.lng,
        )
        severe = _nearby_rows(
            connection,
            "toronto_ksi_collisions",
            coordinates.lat,
            coordinates.lng,
        )
        partitions = manifest.get("partitions", {})
        baseline_partition = partitions.get("collisions_all", {})
        ksi_partition = partitions.get("collisions_ksi", {})
        stale = partition_is_stale(
            manifest, "collisions_all", "collisions_ksi"
        )
        severe = sorted(
            severe,
            key=lambda row: (str(row.get("occurred_at") or ""), row["collision_id"]),
            reverse=True,
        )
        collision_context = {
            "radius_m": RADIUS_M,
            "baseline_period_start": str(
                baseline_partition.get("data_start") or _minimum_date(connection, "toronto_collisions")
            ),
            "baseline_period_end": str(
                baseline_partition.get("data_through") or _maximum_date(connection, "toronto_collisions")
            ),
            "total_collisions": len(baseline),
            "injury_collisions": _count_flag(baseline, "injury"),
            "fatal_collisions": _count_flag(baseline, "fatal"),
            "pedestrian_involved_collisions": _count_flag(
                baseline, "pedestrian_involved"
            ),
            "cyclist_involved_collisions": _count_flag(
                baseline, "cyclist_involved"
            ),
            "ksi_period_start": str(
                ksi_partition.get("data_start") or _minimum_date(connection, "toronto_ksi_collisions")
            ),
            "ksi_period_end": str(
                ksi_partition.get("data_through") or _maximum_date(connection, "toronto_ksi_collisions")
            ),
            "ksi_collisions": len(severe),
            "ksi_fatal_collisions": _count_flag(severe, "fatal"),
            "ksi_pedestrian_involved_collisions": _count_flag(
                severe, "pedestrian_involved"
            ),
            "ksi_cyclist_involved_collisions": _count_flag(
                severe, "cyclist_involved"
            ),
            "severe_events": [
                {
                    "collision_id": row["collision_id"],
                    "occurred_at": row["occurred_at"],
                    "latitude": row["lat"],
                    "longitude": row["lng"],
                    "fatal": bool(row["fatal"]),
                    "pedestrian_involved": bool(row["pedestrian_involved"]),
                    "cyclist_involved": bool(row["cyclist_involved"]),
                    "other_road_user_involved": bool(
                        row["other_road_user_involved"]
                    ),
                }
                for row in severe[:MAX_MAP_POINTS]
            ],
            "scope": "Reported collisions within 1 km in the City of Toronto",
            "edition": str(manifest.get("snapshot_id") or "Bundled GTA snapshot"),
            "stale": stale,
            "baseline_source_url": ALL_COLLISIONS_URL,
            "ksi_source_url": KSI_COLLISIONS_URL,
        }
        return SourceResult(
            data={"collision_context": collision_context},
            message=(
                "Bundled Toronto reported-collision history returned. Counts describe "
                "recorded events, not the probability that a location is safe or unsafe."
            ),
            updated_at=_latest_retrieval(baseline_partition, ksi_partition),
            edition=collision_context["edition"],
            scope=collision_context["scope"],
            source_url=ALL_COLLISIONS_URL,
            stale=stale,
        )
    finally:
        connection.close()


def _nearby_rows(
    connection: Any, table: str, lat: float, lng: float
) -> list[dict[str, Any]]:
    lat_delta = RADIUS_M / 111_320
    lng_delta = RADIUS_M / (
        111_320 * max(math.cos(math.radians(lat)), 0.2)
    )
    rows = connection.execute(
        f"""
        SELECT * FROM {table}
        WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?
        """,
        (lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta),
    ).fetchall()
    return [
        dict(row)
        for row in rows
        if _distance_m(lat, lng, float(row["lat"]), float(row["lng"])) <= RADIUS_M
    ]


def _count_flag(rows: list[dict[str, Any]], field: str) -> int:
    return sum(bool(row.get(field)) for row in rows)


def _minimum_date(connection: Any, table: str) -> str:
    value = connection.execute(f"SELECT MIN(occurred_at) FROM {table}").fetchone()[0]
    return str(value or "unavailable")[:10]


def _maximum_date(connection: Any, table: str) -> str:
    value = connection.execute(f"SELECT MAX(occurred_at) FROM {table}").fetchone()[0]
    return str(value or "unavailable")[:10]


def _latest_retrieval(*partitions: Any) -> str | None:
    values = [
        str(item.get("retrieved_at"))
        for item in partitions
        if isinstance(item, dict) and item.get("retrieved_at")
    ]
    return max(values) if values else None


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
