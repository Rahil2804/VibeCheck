import httpx
import pytest
import respx

from backend.models import AnalyzeRequest
from backend.sources.mapbox import resolve_place


@pytest.mark.asyncio
@respx.mock
async def test_resolve_place_searches_us_and_canada(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-mapbox-token")
    route = respx.get("https://api.mapbox.com/search/geocode/v6/forward").mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    {
                        "geometry": {"coordinates": [-79.3832, 43.6532]},
                        "properties": {
                            "full_address": "Toronto, Ontario, Canada",
                            "context": {
                                "place": {"name": "Toronto"},
                                "region_code": "ON",
                            },
                        },
                    }
                ]
            },
        )
    )

    place = await resolve_place(AnalyzeRequest(query="Toronto"))

    assert place.label == "Toronto, Ontario, Canada"
    assert route.calls[0].request.url.params["country"] == "us,ca"
