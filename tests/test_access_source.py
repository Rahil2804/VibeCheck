from unittest.mock import AsyncMock, Mock
from datetime import timedelta

import httpx
import pytest

from backend.models import AnalyzeRequest, Coordinates, Place
from backend.sources.access import (
    ACCESS_RADIUS_METERS,
    _should_cool_down,
    build_overpass_query,
    fetch_access_context,
    normalize_access_payload,
)
from backend.source_cache import set_cached_source
from backend.sources.common import SourceContext


def _element(element_id: int, tags: dict[str, str], element_type: str = "node") -> dict:
    return {
        "type": element_type,
        "id": element_id,
        "lat": 43.654,
        "lon": -79.401,
        "tags": tags,
    }


def test_normalize_access_payload_counts_supported_categories_and_scores_dense_area():
    payload = {
        "elements": [
            _element(1, {"shop": "supermarket"}),
            _element(2, {"shop": "convenience"}),
            _element(3, {"amenity": "pharmacy"}),
            _element(4, {"amenity": "library"}),
            _element(5, {"amenity": "restaurant"}),
            _element(6, {"amenity": "restaurant"}),
            _element(7, {"amenity": "cafe"}),
            _element(8, {"amenity": "bar"}),
            _element(9, {"highway": "bus_stop"}),
            _element(10, {"public_transport": "station"}),
            _element(11, {"railway": "subway_entrance"}),
            _element(12, {"leisure": "park"}, element_type="way"),
            _element(13, {"leisure": "playground"}, element_type="relation"),
            _element(14, {"amenity": "community_centre"}),
        ]
    }

    access = normalize_access_payload(payload)

    assert access["nearby_categories"] == {
        "groceries": 2,
        "pharmacies": 1,
        "restaurants": 2,
        "cafes": 1,
        "bars": 1,
        "transit": 3,
        "parks": 2,
        "libraries": 1,
        "community": 1,
    }
    assert access["daily_needs"] >= 70
    assert access["food_social"] >= 65
    assert access["transit_access"] >= 60
    assert access["parks_outdoors"] >= 60
    assert access["walkability"] >= 70
    assert "public POI signals" in access["summary"]


def test_normalize_access_payload_dedupes_same_osm_element():
    payload = {
        "elements": [
            _element(1, {"amenity": "restaurant"}),
            _element(1, {"amenity": "restaurant"}),
            _element(2, {"amenity": "restaurant"}),
        ]
    }

    access = normalize_access_payload(payload)

    assert access["nearby_categories"]["restaurants"] == 2
    assert access["food_social"] > 50


def test_normalize_access_payload_accepts_way_center_and_ignores_unknown_tags():
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 20,
                "center": {"lat": 43.65, "lon": -79.4},
                "tags": {"landuse": "recreation_ground"},
            },
            _element(21, {"shop": "clothes"}),
        ]
    }

    access = normalize_access_payload(payload)

    assert access["nearby_categories"]["parks"] == 1
    assert access["nearby_categories"]["groceries"] == 0


def test_normalize_access_payload_returns_low_scores_for_successful_empty_query():
    access = normalize_access_payload({"elements": []})

    assert access["nearby_categories"]["groceries"] == 0
    assert access["nearby_categories"]["transit"] == 0
    assert access["daily_needs"] == 30
    assert access["transit_access"] == 30
    assert access["food_social"] == 30
    assert access["parks_outdoors"] == 30
    assert access["walkability"] == 30


def test_normalize_access_payload_rejects_invalid_payload_shape():
    with pytest.raises(ValueError, match="Overpass payload missing elements list"):
        normalize_access_payload({"unexpected": []})


def _context_with_coordinates() -> SourceContext:
    place = Place(
        label="Kensington Market, Toronto, ON",
        city="Toronto",
        state="ON",
        coordinates=Coordinates(lat=43.654, lng=-79.401),
    )
    return SourceContext(request=AnalyzeRequest(query=place.label), place=place)


def test_build_overpass_query_is_bounded_to_radius_and_tags():
    query = build_overpass_query(lat=43.654, lng=-79.401)

    assert f"around:{ACCESS_RADIUS_METERS},43.654,-79.401" in query
    assert "[out:json][timeout:6]" in query
    assert "supermarket|convenience|grocery" in query
    assert "pharmacy|library|restaurant|cafe|bar|pub|fast_food" in query
    assert "bus_stop" in query
    assert "recreation_ground" in query
    assert "out geom tags;" in query
    assert 'highway="cycleway"' in query
    assert 'amenity="bicycle_parking"' in query


@pytest.mark.asyncio
async def test_fetch_access_context_returns_empty_without_coordinates():
    place = Place(label="Toronto, ON", city="Toronto", state="ON")
    context = SourceContext(request=AnalyzeRequest(query=place.label), place=place)

    result = await fetch_access_context(context)

    assert result.data == {}
    assert result.message == "Access lookup needs resolved coordinates."


@pytest.mark.asyncio
async def test_fetch_access_context_uses_http_client_and_returns_source_result():
    payload = {
        "elements": [
            _element(1, {"shop": "supermarket"}),
            _element(2, {"amenity": "pharmacy"}),
            _element(3, {"highway": "bus_stop"}),
            _element(4, {"leisure": "park"}),
        ]
    }

    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.post.return_value = response

    result = await fetch_access_context(_context_with_coordinates(), client=client)

    assert result.data["nearby_categories"]["groceries"] == 1
    assert result.data["nearby_categories"]["transit"] == 1
    assert result.data["walkability"] > 30
    assert result.message == result.data["summary"]
    assert result.updated_at is not None
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_access_context_uses_secondary_endpoint_after_406():
    request = httpx.Request("POST", "https://overpass-api.de/api/interpreter")
    rejected = Mock()
    rejected.raise_for_status.side_effect = httpx.HTTPStatusError(
        "not acceptable",
        request=request,
        response=httpx.Response(406, request=request),
    )
    accepted = Mock()
    accepted.raise_for_status.return_value = None
    accepted.json.return_value = {"elements": [_element(1, {"shop": "supermarket"})]}
    client = AsyncMock()
    client.post.side_effect = [rejected, accepted]

    result = await fetch_access_context(_context_with_coordinates(), client=client)

    assert result.data["nearby_categories"]["groceries"] == 1
    assert client.post.await_count == 2


@pytest.mark.parametrize(
    ("status", "expected"),
    [(400, False), (406, True), (429, True), (500, True), (503, True)],
)
def test_overpass_endpoint_cooldown_statuses(status, expected):
    request = httpx.Request("POST", "https://example.test")
    error = httpx.HTTPStatusError(
        "failed",
        request=request,
        response=httpx.Response(status, request=request),
    )

    assert _should_cool_down(error) is expected


def test_overpass_timeout_triggers_endpoint_cooldown():
    assert _should_cool_down(httpx.ReadTimeout("timed out")) is True


@pytest.mark.asyncio
async def test_fetch_access_context_uses_seven_day_stale_cache_on_total_failure(
    monkeypatch,
    tmp_path,
):
    database = tmp_path / "cache.sqlite"
    monkeypatch.setenv("SQLITE_PATH", str(database))
    context = _context_with_coordinates()
    cache_key = "osm:neighbourhood:v2:43.6540:-79.4010"
    cached_data = normalize_access_payload(
        {"elements": [_element(1, {"shop": "supermarket"})]}
    )
    set_cached_source(
        cache_key,
        {
            "data": {"access": cached_data, "cycling": {}},
            "message": cached_data["summary"],
            "updated_at": "2026-09-15T00:00:00+00:00",
            "source_url": "https://overpass-api.de/api/interpreter",
        },
        ttl=timedelta(hours=-1),
        db_path=database,
    )
    client = AsyncMock()
    client.post.side_effect = [
        httpx.ReadTimeout("primary timeout"),
        httpx.ReadTimeout("secondary timeout"),
    ]
    monkeypatch.setattr(httpx, "AsyncClient", Mock(return_value=client))

    result = await fetch_access_context(context)

    assert result.stale is True
    assert result.data == cached_data
    assert "last successful OSM" in result.message
    assert client.post.await_count == 2
