import pytest

from backend.sources.access import fetch_access_context


@pytest.mark.asyncio
async def test_fetch_access_context_returns_conservative_normalized_signals():
    context = await fetch_access_context()

    assert context["walkability"] == 50
    assert context["transit_access"] == 50
    assert context["daily_needs"] == 50
    assert context["food_social"] == 50
    assert context["parks_outdoors"] == 50
    assert context["nearby_categories"] == {
        "groceries": 0,
        "parks": 0,
        "restaurants": 0,
        "transit": 0,
    }
