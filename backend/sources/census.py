from datetime import timedelta
from typing import Any

import httpx

from backend.census_bundle import (
    STATCAN_CENSUS_PROFILE_URL,
    lookup_bundled_census_subdivision,
)
from backend.source_cache import get_cached_source, set_cached_source
from backend.sources.common import SourceContext, SourceResult
from backend.sources.ontario.toronto_profiles import (
    TORONTO_PROFILE_WORKBOOK_URL,
    lookup_bundled_toronto_profile,
)

CENSUS_YEAR = 2021
BOUNDARY_QUERY_URL = (
    "https://geo.statcan.gc.ca/geo_wa/rest/services/2021/"
    "Digital_boundary_files/MapServer/12/query"
)
CSD_BOUNDARY_QUERY_URL = (
    "https://geo.statcan.gc.ca/geo_wa/rest/services/2021/"
    "Digital_boundary_files/MapServer/9/query"
)
CENSUS_PROFILE_URL = "https://www12.statcan.gc.ca/rest/census-recensement/CPR2021.json"


async def fetch_census_context(
    context: SourceContext,
    client: httpx.AsyncClient | None = None,
) -> SourceResult:
    coordinates = context.place.coordinates
    if coordinates is None:
        return SourceResult(
            data={}, message="Statistics Canada lookup needs resolved coordinates."
        )

    if (
        context.geography is not None
        and context.geography.is_toronto
        and client is None
    ):
        bundled = lookup_bundled_toronto_profile(coordinates)
        if bundled:
            return SourceResult(
                data={
                    **bundled,
                    "census_year": CENSUS_YEAR,
                    "geographic_scope": "Toronto neighbourhood",
                },
                message="Bundled Toronto 2021 Census neighbourhood context returned.",
                updated_at="2021",
                edition="2021 Census",
                scope=bundled.get("neighbourhood_name") or "City of Toronto",
                source_url=TORONTO_PROFILE_WORKBOOK_URL,
            )
    if context.geography is not None and context.geography.is_gta and client is None:
        bundled = lookup_bundled_census_subdivision(coordinates)
        if bundled:
            return SourceResult(
                data=bundled,
                message="Bundled Statistics Canada 2021 census-subdivision context returned.",
                updated_at="2021",
                edition="2021 Census",
                scope=bundled.get("census_subdivision_name"),
                source_url=STATCAN_CENSUS_PROFILE_URL,
            )
        return SourceResult(
            data={},
            message=(
                "The bundled Statistics Canada GTA context does not cover this coordinate."
            ),
            edition="2021 Census",
            scope=context.geography.census_subdivision_name or "Greater Toronto Area",
        )

    point_key = f"statcan:2021:v2:point:{coordinates.lat:.5f}:{coordinates.lng:.5f}"
    cached = get_cached_source(point_key)
    if cached is not None and client is None:
        return SourceResult(
            data=cached["data"],
            message=cached["message"],
            updated_at=cached.get("updated_at"),
        )

    should_close = client is None
    http_client = client or httpx.AsyncClient(timeout=12, follow_redirects=True)
    try:
        geography_response = await http_client.get(
            BOUNDARY_QUERY_URL,
            params={
                "geometry": f"{coordinates.lng},{coordinates.lat}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "DAUID,DGUID",
                "returnGeometry": "false",
                "f": "json",
            },
        )
        geography_response.raise_for_status()
        geography = normalize_geography_response(_response_json(geography_response))
        if geography is None:
            return SourceResult(
                data={},
                message="Statistics Canada found no 2021 dissemination area for this point.",
            )
        try:
            csd_response = await http_client.get(
                CSD_BOUNDARY_QUERY_URL,
                params={
                    "geometry": f"{coordinates.lng},{coordinates.lat}",
                    "geometryType": "esriGeometryPoint",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "CSDUID,CSDNAME,CSDTYPE,DGUID",
                    "returnGeometry": "false",
                    "f": "json",
                },
            )
            csd_response.raise_for_status()
            csd = normalize_csd_response(_response_json(csd_response)) or {}
        except httpx.HTTPError:
            csd = {}
        profile_key = f"statcan:2021:v2:profile:{geography['dguid']}"
        cached_profile = get_cached_source(profile_key) if client is None else None
        if cached_profile is None:
            profile_response = await http_client.get(
                CENSUS_PROFILE_URL,
                params={
                    "lang": "E",
                    "dguid": geography["dguid"],
                    "topic": "0",
                    "notes": "0",
                    "stat": "0",
                },
            )
            profile_response.raise_for_status()
            data = {
                **geography,
                **csd,
                **normalize_census_profile(_response_json(profile_response)),
                "census_year": CENSUS_YEAR,
                "geographic_scope": "2021 dissemination area",
            }
            if client is None:
                set_cached_source(profile_key, data, ttl=None)
        else:
            data = cached_profile
    finally:
        if should_close:
            await http_client.aclose()

    message = "Statistics Canada 2021 dissemination-area context returned."
    if client is None:
        set_cached_source(
            point_key,
            {"data": data, "message": message},
            ttl=timedelta(days=365),
        )
    return SourceResult(data=data, message=message, updated_at="2021")


def normalize_geography_response(payload: dict[str, Any]) -> dict[str, str] | None:
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        return None
    attributes = features[0].get("attributes", {})
    dauid = attributes.get("DAUID")
    dguid = attributes.get("DGUID")
    if not dauid or not dguid:
        return None
    return {"dauid": str(dauid), "dguid": str(dguid)}


def normalize_csd_response(payload: dict[str, Any]) -> dict[str, str] | None:
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        return None
    attributes = features[0].get("attributes", {})
    csduid = attributes.get("CSDUID")
    csd_name = attributes.get("CSDNAME")
    if not csduid or not csd_name:
        return None
    output = {"csduid": str(csduid), "csd_name": str(csd_name)}
    if attributes.get("CSDTYPE"):
        output["csd_type"] = str(attributes["CSDTYPE"])
    return output


def normalize_census_profile(payload: Any) -> dict[str, int | float]:
    rows = _profile_rows(payload)
    output: dict[str, int | float] = {}
    wanted = {
        "population density per square kilometre": "population_density",
        "median monthly shelter costs for rented dwellings ($)": (
            "median_renter_shelter_cost"
        ),
        "% of tenant households spending 30% or more of its income on shelter costs": (
            "renter_cost_burden_percent"
        ),
    }
    for row in rows:
        normalized = {str(key).lower(): value for key, value in row.items()}
        label = (
            str(
                normalized.get("characteristic_name")
                or normalized.get("characteristic")
                or normalized.get("member_name")
                or ""
            )
            .strip()
            .lower()
        )
        field = wanted.get(label)
        if field is None:
            continue
        value = _number(
            normalized.get("c1_count_total")
            or normalized.get("total")
            or normalized.get("value")
        )
        if value is not None:
            output[field] = value
    return output


def _response_json(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "").casefold()
    final_url = str(response.url).casefold()
    if "text/html" in content_type or "srvmsg" in final_url:
        raise RuntimeError("Statistics Canada returned an HTML error page.")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Statistics Canada returned a non-JSON response.") from exc


def _profile_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("DATA", "data", "rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _number(value: Any) -> int | float | None:
    if value in (None, "", "x", "F", ".."):
        return None
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number
