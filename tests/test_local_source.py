import pytest

from backend.models import AnalyzeRequest, Coordinates, Place
from backend.sources.common import SourceContext
from backend.sources.local import fetch_local_context, is_ontario_place, is_toronto_place


def _context(place: Place) -> SourceContext:
    return SourceContext(request=AnalyzeRequest(query=place.label), place=place)


def test_detects_toronto_and_ontario_places():
    toronto = Place(
        label="Kensington Market, Toronto, ON",
        city="Toronto",
        state="ON",
        coordinates=Coordinates(lat=43.654, lng=-79.401),
    )

    assert is_ontario_place(toronto) is True
    assert is_toronto_place(toronto) is True


def test_detects_ontario_from_label_when_mapbox_context_is_thin():
    place = Place(
        label="Pickering, Ontario, Canada",
        coordinates=Coordinates(lat=43.8384, lng=-79.0868),
    )

    assert is_ontario_place(place) is True
    assert is_toronto_place(place) is False


@pytest.mark.asyncio
async def test_local_source_returns_empty_for_unsupported_ontario_municipality():
    place = Place(
        label="Pickering, Ontario, Canada",
        city="Pickering",
        state="Ontario",
        coordinates=Coordinates(lat=43.8384, lng=-79.0868),
    )

    result = await fetch_local_context(_context(place))

    assert result.data == {}
    assert result.message == "No local Ontario adapter is available yet for Pickering."


@pytest.mark.asyncio
async def test_local_source_returns_empty_for_non_ontario_region():
    place = Place(
        label="East Austin, Austin, TX",
        city="Austin",
        state="TX",
        coordinates=Coordinates(lat=30.2636, lng=-97.7114),
    )

    result = await fetch_local_context(_context(place))

    assert result.data == {}
    assert result.message == "No local open-data adapter is configured for this region."


@pytest.mark.asyncio
async def test_local_source_returns_empty_without_coordinates():
    place = Place(label="Toronto, ON", city="Toronto", state="ON")

    result = await fetch_local_context(_context(place))

    assert result.data == {}
    assert result.message == "Local open-data lookup needs resolved coordinates."
