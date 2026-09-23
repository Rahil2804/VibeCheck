from __future__ import annotations

import json
from typing import Any

from backend.models import Coordinates
from backend.snapshot import snapshot_connection
from backend.sources.ontario.toronto_profiles import geometry_contains

STATCAN_CENSUS_PROFILE_URL = (
    "https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/"
    "download-telecharger/comp/getFile.cfm?LANG=E&GEONO=005&FILETYPE=CSV"
)
STATCAN_CSD_BOUNDARY_URL = (
    "https://geo.statcan.gc.ca/geo_wa/rest/services/2021/"
    "Digital_boundary_files/MapServer/9"
)


def lookup_bundled_census_subdivision(point: Coordinates) -> dict[str, Any]:
    """Resolve a point against the bundled official GTA Census subdivisions."""
    connection = snapshot_connection()
    if connection is None:
        return {}
    try:
        rows = connection.execute(
            """
            SELECT geography_id, geography_name, geography_type, geometry_json,
                   population_density, median_renter_shelter_cost,
                   renter_cost_burden_percent
            FROM census_subdivisions
            """
        ).fetchall()
    except Exception:
        return {}
    finally:
        connection.close()
    for row in rows:
        geometry = json.loads(row["geometry_json"])
        if not geometry_contains(geometry, point):
            continue
        return {
            "census_subdivision_id": str(row["geography_id"]),
            "census_subdivision_name": str(row["geography_name"]),
            "census_subdivision_type": row["geography_type"],
            "population_density": row["population_density"],
            "median_renter_shelter_cost": row["median_renter_shelter_cost"],
            "renter_cost_burden_percent": row["renter_cost_burden_percent"],
            "census_year": 2021,
            "geographic_scope": "2021 census subdivision",
        }
    return {}
