import pytest
from pydantic import ValidationError

from backend.models import (
    AnalyzeRequest,
    CarReliance,
    Coordinates,
    SourceName,
    SourceStatus,
    SourceStatusCode,
)


def test_analyze_request_requires_query_or_coordinates():
    with pytest.raises(ValidationError):
        AnalyzeRequest()


def test_analyze_request_accepts_coordinates_and_query_context():
    request = AnalyzeRequest(
        query="East Austin",
        coordinates=Coordinates(lat=30.2636, lng=-97.7114),
    )

    assert request.query == "East Austin"
    assert request.coordinates.lat == 30.2636


def test_preference_enums_reject_protected_class_proxy_values():
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            query="Austin, TX",
            preferences={"car_reliance": "families_with_children"},
        )

    request = AnalyzeRequest(
        query="Austin, TX",
        preferences={"car_reliance": CarReliance.NO_CAR},
    )
    assert request.preferences.car_reliance == CarReliance.NO_CAR


def test_source_status_has_consistent_serializable_shape():
    status = SourceStatus(
        source=SourceName.CENSUS,
        status=SourceStatusCode.SUCCESS,
        message="ACS context returned.",
        updated_at="2026-04-30",
    )

    assert status.model_dump(mode="json") == {
        "source": "census",
        "status": "success",
        "message": "ACS context returned.",
        "updated_at": "2026-04-30",
    }
