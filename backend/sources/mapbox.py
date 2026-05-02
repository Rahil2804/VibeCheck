import os
from typing import Any

import httpx

from backend.models import AnalyzeRequest, Coordinates, Place


async def resolve_place(request: AnalyzeRequest) -> Place:
    if request.coordinates is not None:
        return Place(
            label=request.query or _coordinate_label(request.coordinates),
            coordinates=request.coordinates,
        )

    if not request.query:
        raise ValueError("Query or coordinates are required.")

    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        return Place(label=request.query)

    url = "https://api.mapbox.com/search/geocode/v6/forward"
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.get(
            url,
            params={
                "q": request.query,
                "country": "us,ca",
                "limit": 1,
                "access_token": token,
            },
        )
        response.raise_for_status()
        payload = response.json()

    feature = (payload.get("features") or [{}])[0]
    if not feature:
        return Place(label=request.query)

    properties: dict[str, Any] = feature.get("properties") or {}
    coordinates = _coordinates_from_feature(feature)
    context = properties.get("context") or {}
    return Place(
        label=properties.get("full_address") or properties.get("name") or request.query,
        neighborhood=_context_name(context, "neighborhood"),
        city=_context_name(context, "place"),
        state=_context_name(context, "region_code") or _context_name(context, "region"),
        coordinates=coordinates,
    )


def _coordinates_from_feature(feature: dict[str, Any]) -> Coordinates | None:
    geometry = feature.get("geometry") or {}
    raw_coordinates = geometry.get("coordinates") or []
    if len(raw_coordinates) < 2:
        return None
    return Coordinates(lat=raw_coordinates[1], lng=raw_coordinates[0])


def _context_name(context: dict[str, Any], key: str) -> str | None:
    value = context.get(key)
    if isinstance(value, dict):
        return value.get("name") or value.get("short_code")
    if isinstance(value, str):
        return value
    return None


def _coordinate_label(coordinates: Coordinates) -> str:
    return f"{coordinates.lat:.5f}, {coordinates.lng:.5f}"
