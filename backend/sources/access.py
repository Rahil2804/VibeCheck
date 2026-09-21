import httpx

from backend.sources.common import SourceContext, SourceResult
from backend.sources.osm import (
    ACCESS_RADIUS_METERS,
    CATEGORY_KEYS,
    ENDPOINT_COOLDOWN_SECONDS,
    LOW_SCORE,
    OVERPASS_TIMEOUT_SECONDS,
    OVERPASS_URLS,
    OVERPASS_USER_AGENT,
    _should_cool_down,
    build_overpass_query,
    fetch_osm_context,
    normalize_access_payload,
)


async def fetch_access_context(
    context: SourceContext,
    client: httpx.AsyncClient | None = None,
    *,
    use_cache: bool = True,
) -> SourceResult:
    if context.place.coordinates is None:
        return SourceResult(
            data={}, message="Access lookup needs resolved coordinates."
        )
    result = await fetch_osm_context(context, client=client, use_cache=use_cache)
    data = result.data.get("access", {})
    return SourceResult(
        data=data,
        message=(
            "Using the last successful OSM access result because live endpoints are unavailable."
            if result.stale
            else data.get("summary")
        ),
        updated_at=result.updated_at,
        scope="OpenStreetMap features within 1.2 km",
        source_url=result.source_url,
        stale=result.stale,
    )


__all__ = [
    "ACCESS_RADIUS_METERS",
    "CATEGORY_KEYS",
    "ENDPOINT_COOLDOWN_SECONDS",
    "LOW_SCORE",
    "OVERPASS_TIMEOUT_SECONDS",
    "OVERPASS_URLS",
    "OVERPASS_USER_AGENT",
    "_should_cool_down",
    "build_overpass_query",
    "fetch_access_context",
    "normalize_access_payload",
]
