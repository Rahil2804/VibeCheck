import httpx
import pytest

from backend.models import AnalyzeRequest, Place
from backend.models import Coordinates
from backend.sources.common import SourceContext
from backend.sources.ontario import toronto
from backend.sources.ontario.toronto import (
    fetch_toronto_context,
    normalize_toronto_open_data,
    summarize_amenity_records,
    summarize_permit_records,
)


CENTER = Coordinates(lat=43.654, lng=-79.401)


def test_summarize_permit_records_counts_nearby_and_major_projects():
    records = [
        {
            "LATITUDE": "43.6542",
            "LONGITUDE": "-79.4008",
            "PERMIT_TYPE": "New Building",
            "STATUS": "Permit Issued",
        },
        {
            "latitude": 43.655,
            "longitude": -79.402,
            "permit_type": "Interior Alterations",
            "status": "Inspection",
        },
        {
            "LATITUDE": "43.7000",
            "LONGITUDE": "-79.5000",
            "PERMIT_TYPE": "New Building",
            "STATUS": "Permit Issued",
        },
    ]

    summary = summarize_permit_records(records, CENTER, radius_km=1.5)

    assert summary["recent_permits_count"] == 2
    assert summary["major_project_count"] == 1
    assert summary["development_activity"] == 32
    assert summary["trajectory_signal"] == "stable"


def test_summarize_permit_records_marks_rising_for_high_activity():
    records = [
        {
            "LATITUDE": "43.6542",
            "LONGITUDE": "-79.4008",
            "PERMIT_TYPE": "New Building",
            "STATUS": "Permit Issued",
        },
        {
            "LATITUDE": "43.6543",
            "LONGITUDE": "-79.4007",
            "PERMIT_TYPE": "Demolition",
            "STATUS": "Permit Issued",
        },
        {
            "LATITUDE": "43.6544",
            "LONGITUDE": "-79.4006",
            "PERMIT_TYPE": "Addition",
            "STATUS": "Permit Issued",
        },
        {
            "LATITUDE": "43.6545",
            "LONGITUDE": "-79.4005",
            "PERMIT_TYPE": "Interior Alterations",
            "STATUS": "Inspection",
        },
    ]

    summary = summarize_permit_records(records, CENTER, radius_km=1.5)

    assert summary["major_project_count"] == 3
    assert summary["development_activity"] == 72
    assert summary["trajectory_signal"] == "rising"


def test_summarize_amenity_records_counts_parks_and_recreation_centres():
    records = [
        {
            "geometry": {"coordinates": [-79.401, 43.654]},
            "properties": {
                "AssetName": "Bellevue Square Park",
                "Type": "Park",
                "Amenity": "Playground",
            },
        },
        {
            "geometry": {"coordinates": [-79.402, 43.655]},
            "properties": {
                "AssetName": "Scadding Court Community Centre",
                "Type": "Community Recreation Centre",
                "Amenity": "Pool",
            },
        },
        {
            "geometry": {"coordinates": [-79.5, 43.7]},
            "properties": {
                "AssetName": "Far Park",
                "Type": "Park",
                "Amenity": "Trail",
            },
        },
    ]

    summary = summarize_amenity_records(records, CENTER, radius_km=1.5)

    assert summary["parks_count"] == 1
    assert summary["community_amenities_count"] == 1
    assert summary["parks_outdoors"] == 16


def test_summarize_amenity_records_handles_toronto_multipoint_geometry():
    records = [
        {
            "geometry": {"type": "MultiPoint", "coordinates": [[-79.401, 43.654]]},
            "properties": {
                "ASSET_NAME": "Bellevue Square Park",
                "TYPE": "Park",
                "AMENITIES": "Playground",
            },
        }
    ]

    summary = summarize_amenity_records(records, CENTER, radius_km=1.5)

    assert summary["parks_count"] == 1
    assert summary["parks_outdoors"] == 12


def test_normalize_toronto_open_data_combines_permits_and_amenities():
    permits = [
        {
            "LATITUDE": "43.6542",
            "LONGITUDE": "-79.4008",
            "PERMIT_TYPE": "New Building",
            "STATUS": "Permit Issued",
        }
    ]
    amenities = [
        {
            "geometry": {"coordinates": [-79.401, 43.654]},
            "properties": {
                "AssetName": "Bellevue Square Park",
                "Type": "Park",
                "Amenity": "Playground",
            },
        }
    ]

    normalized = normalize_toronto_open_data(
        permits,
        amenities,
        CENTER,
        updated_at="2026-05-08T00:00:00+00:00",
    )

    assert normalized["coverage_area"] == "Toronto"
    assert normalized["recent_permits_count"] == 1
    assert normalized["parks_count"] == 1
    assert normalized["updated_at"] == "2026-05-08T00:00:00+00:00"
    assert "Toronto open data" in normalized["summary"]


def test_toronto_package_urls_use_live_ckan_api_host():
    assert toronto.TORONTO_PERMITS_PACKAGE_URL.startswith(
        "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show"
    )
    assert toronto.TORONTO_PARKS_PACKAGE_URL.startswith(
        "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show"
    )


class FakeAsyncClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url):
        self.urls.append(url)
        return self.responses.pop(0)


def _response(payload):
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("GET", "https://example.test"),
    )


def _toronto_context() -> SourceContext:
    place = Place(
        label="Kensington Market, Toronto, ON",
        city="Toronto",
        state="ON",
        coordinates=CENTER,
    )
    return SourceContext(request=AnalyzeRequest(query=place.label), place=place)


@pytest.mark.asyncio
async def test_fetch_toronto_context_downloads_and_normalizes(monkeypatch):
    client = FakeAsyncClient(
        [
            _response(
                {
                    "result": {
                        "resources": [
                            {
                                "name": "building-permits-active-permits.json",
                                "format": "JSON",
                                "url": "https://example.test/permits.json",
                            }
                        ]
                    }
                }
            ),
            _response(
                {
                    "result": {
                        "resources": [
                            {
                                "name": "Parks and Recreation Facilities - 4326.geojson",
                                "format": "GeoJSON",
                                "url": "https://example.test/parks.geojson",
                            }
                        ]
                    }
                }
            ),
            _response(
                {
                    "features": [
                        {
                            "geometry": {"coordinates": [-79.401, 43.654]},
                            "properties": {
                                "AssetName": "Bellevue Square Park",
                                "Type": "Park",
                            },
                        }
                    ]
                }
            ),
        ]
    )
    monkeypatch.setattr(toronto.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await fetch_toronto_context(_toronto_context())

    assert result.data["coverage_area"] == "Toronto"
    assert result.data["recent_permits_count"] == 0
    assert result.data["parks_count"] == 1
    assert result.message == (
        "Toronto open data returned parks signals; local permit records need address-point matching before development scoring."
    )
    assert client.urls == [
        toronto.TORONTO_PERMITS_PACKAGE_URL,
        toronto.TORONTO_PARKS_PACKAGE_URL,
        "https://example.test/parks.geojson",
    ]


@pytest.mark.asyncio
async def test_fetch_toronto_context_returns_empty_when_no_nearby_records(monkeypatch):
    client = FakeAsyncClient(
        [
            _response(
                {
                    "result": {
                        "resources": [
                            {
                                "name": "building-permits-active-permits.json",
                                "format": "JSON",
                                "url": "https://example.test/permits.json",
                            }
                        ]
                    }
                }
            ),
            _response(
                {
                    "result": {
                        "resources": [
                            {
                                "name": "Parks and Recreation Facilities - 4326.geojson",
                                "format": "GeoJSON",
                                "url": "https://example.test/parks.geojson",
                            }
                        ]
                    }
                }
            ),
            _response({"features": []}),
        ]
    )
    monkeypatch.setattr(toronto.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await fetch_toronto_context(_toronto_context())

    assert result.data == {}
    assert result.message == "Toronto open data returned no nearby development or parks signals."
