import asyncio
from unittest.mock import Mock

import pytest

from backend.models import AnalyzeRequest, Coordinates, GeographyContext, Place
from backend.sources import cycling as cycling_source
from backend.sources.access import fetch_access_context
from backend.sources.common import SourceContext, SourceResult
from backend.sources.cycling import fetch_cycling_context
from backend.sources.osm import (
    _INFLIGHT,
    _UNHEALTHY_UNTIL,
    normalize_cycling_payload,
    score_cycling_lengths,
)


@pytest.fixture(autouse=True)
def _reset_osm_process_state():
    _INFLIGHT.clear()
    _UNHEALTHY_UNTIL.clear()
    yield
    _INFLIGHT.clear()
    _UNHEALTHY_UNTIL.clear()


def _way(
    element_id: int,
    tags: dict[str, str],
    geometry: list[dict[str, float]] | None = None,
) -> dict:
    return {
        "type": "way",
        "id": element_id,
        "tags": tags,
        "geometry": (
            geometry
            if geometry is not None
            else [
                {"lat": 0.0, "lon": 0.0},
                {"lat": 0.0, "lon": 0.004},
            ]
        ),
    }


def _context(*, label: str = "Ottawa, Ontario") -> SourceContext:
    place = Place(
        label=label,
        city="Ottawa",
        state="Ontario",
        coordinates=Coordinates(lat=0.0, lng=0.0),
    )
    return SourceContext(
        request=AnalyzeRequest(query=label),
        place=place,
        geography=GeographyContext(
            country="Canada",
            province="Ontario",
            is_toronto=False,
            is_gta=False,
            resolution="place context",
        ),
    )


def test_osm_cycling_normalizes_supported_tags_and_counts_each_way_once():
    payload = {
        "elements": [
            _way(1, {"highway": "cycleway"}),
            _way(2, {"highway": "path", "bicycle": "designated"}),
            _way(3, {"highway": "residential", "cycleway:right": "lane"}),
            _way(4, {"highway": "secondary", "cycleway:left": "track"}),
            _way(5, {"highway": "residential", "cyclestreet": "yes"}),
            _way(3, {"highway": "residential", "cycleway:right": "lane"}),
            {
                "type": "node",
                "id": 100,
                "lat": 0.001,
                "lon": 0.001,
                "tags": {"amenity": "bicycle_parking"},
            },
        ]
    }

    context = normalize_cycling_payload(payload, lat=0.0, lng=0.0)

    assert context["mapped_cycling_ways"] == 5
    assert context["bicycle_parking_locations"] == 1
    assert context["protected_network_km"] > 1.3
    assert context["total_network_km"] > context["protected_network_km"]
    assert context["score"] > 0


def test_osm_cycling_excludes_access_blocks_duplicates_and_routing_only_tags():
    payload = {
        "elements": [
            _way(1, {"highway": "primary", "cycleway": "separate"}),
            _way(2, {"highway": "primary", "cycleway": "shoulder"}),
            _way(3, {"highway": "cycleway", "bicycle": "private"}),
            _way(4, {"highway": "crossing", "cycleway": "lane"}),
            _way(5, {"highway": "primary_link", "cycleway": "lane"}),
            _way(6, {"highway": "cycleway"}, geometry=[]),
        ]
    }

    context = normalize_cycling_payload(payload, lat=0.0, lng=0.0)

    assert context["mapped_cycling_ways"] == 0
    assert context["protected_network_km"] == 0
    assert context["total_network_km"] == 0
    assert context["score"] == 0


def test_osm_cycling_clips_geometry_to_one_kilometre_circle():
    payload = {
        "elements": [
            _way(
                1,
                {"highway": "cycleway"},
                geometry=[
                    {"lat": 0.0, "lon": -0.02},
                    {"lat": 0.0, "lon": 0.02},
                ],
            )
        ]
    }

    context = normalize_cycling_payload(payload, lat=0.0, lng=0.0)

    assert context["protected_network_km"] == pytest.approx(2.0, abs=0.02)
    assert context["total_network_km"] == pytest.approx(2.0, abs=0.02)
    assert context["score"] == 58


def test_common_cycling_formula_caps_protected_and_total_components():
    assert score_cycling_lengths(0, 0) == 0
    assert score_cycling_lengths(3, 5) == 100
    assert score_cycling_lengths(30, 50) == 100


@pytest.mark.asyncio
async def test_non_toronto_cycling_returns_labelled_osm_fallback_and_real_zero():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"elements": []}
    class Client:
        async def post(self, *_args, **_kwargs):
            return response

    client = Client()
    result = await fetch_cycling_context(_context(), client=client)

    assert result.fallback is True
    assert result.stale is False
    assert result.data["score"] == 0
    assert result.data["method"] == "osm_fallback"
    assert "no mapped qualifying" in result.message.lower()


@pytest.mark.asyncio
async def test_canonical_toronto_geography_prefers_official_evidence(monkeypatch):
    context = _context(label="79 Thorncliffe Park Drive, East York")
    context = SourceContext(
        request=context.request,
        place=context.place,
        geography=context.geography.model_copy(update={"is_toronto": True}),
    )
    official = SourceResult(
        data={"score": 75},
        message="Official Toronto evidence returned.",
    )
    monkeypatch.setattr(
        cycling_source,
        "_official_toronto_context",
        lambda _context: official,
    )

    result = await fetch_cycling_context(context)

    assert result is official


@pytest.mark.asyncio
async def test_unreadable_toronto_partition_still_uses_osm_fallback(monkeypatch):
    context = _context(label="79 Thorncliffe Park Drive, East York")
    context = SourceContext(
        request=context.request,
        place=context.place,
        geography=context.geography.model_copy(update={"is_toronto": True}),
    )
    osm = SourceResult(
        data={
            "cycling": {
                "score": 42,
                "protected_network_km": 0.8,
                "total_network_km": 1.5,
                "bicycle_parking_locations": 2,
                "network_radius_m": 1000,
            }
        },
        updated_at="2026-09-19T00:00:00+00:00",
    )

    async def fallback(*_args, **_kwargs):
        return osm

    monkeypatch.setattr(
        cycling_source,
        "_official_toronto_context",
        lambda _context: None,
    )
    monkeypatch.setattr(cycling_source, "fetch_osm_context", fallback)

    result = await fetch_cycling_context(context)

    assert result.fallback is True
    assert result.data["score"] == 42
    assert result.data["method"] == "osm_fallback"


@pytest.mark.asyncio
async def test_access_and_cycling_coalesce_one_live_overpass_request(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "cache.sqlite"))
    _INFLIGHT.clear()
    _UNHEALTHY_UNTIL.clear()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "elements": [
            _way(1, {"highway": "cycleway"}),
            {
                "type": "node",
                "id": 2,
                "lat": 0.001,
                "lon": 0.001,
                "tags": {"shop": "supermarket"},
            },
        ]
    }

    class Client:
        post_count = 0

        async def post(self, *_args, **_kwargs):
            self.post_count += 1
            await asyncio.sleep(0.01)
            return response

        async def aclose(self):
            return None

    client = Client()
    monkeypatch.setattr(
        "backend.sources.osm.httpx.AsyncClient",
        lambda **_kwargs: client,
    )
    context = _context()

    access, cycling = await asyncio.gather(
        fetch_access_context(context),
        fetch_cycling_context(context),
    )

    assert client.post_count == 1
    assert access.data["nearby_categories"]["groceries"] == 1
    assert cycling.data["score"] > 0
    assert cycling.fallback is True
