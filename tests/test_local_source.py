import pytest

from backend.models import AnalyzeRequest, Coordinates, Place
from backend.sources.common import SourceContext
from backend.sources.local import (
    fetch_local_context,
    is_gta_place,
    is_ontario_place,
    is_toronto_place,
)


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
    assert result.message == "No local GTA adapter is available yet for Pickering."


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


def test_detects_gta_municipalities_without_treating_them_as_toronto():
    pickering = Place(
        label="Pickering, Ontario, Canada",
        city="Pickering",
        state="Ontario",
        coordinates=Coordinates(lat=43.8384, lng=-79.0868),
    )
    richmond_hill = Place(
        label="Richmond Hill, Ontario, Canada",
        city="Richmond Hill",
        state="Ontario",
        coordinates=Coordinates(lat=43.8828, lng=-79.4403),
    )

    assert is_gta_place(pickering) is True
    assert is_gta_place(richmond_hill) is True
    assert is_toronto_place(pickering) is False
    assert is_toronto_place(richmond_hill) is False


def test_east_york_address_is_toronto_by_coordinates():
    place = Place(
        label="79 Thorncliffe Park Drive, East York, Ontario, Canada",
        city="East York",
        state="Ontario",
        coordinates=Coordinates(lat=43.706134, lng=-79.341499),
    )

    assert is_toronto_place(place) is True
    assert is_gta_place(place) is True
