import pytest
from pydantic import ValidationError

from backend.models import (
    AnalyzeRequest,
    CarReliance,
    Coordinates,
    PreferenceProfileCreate,
    PreferenceProfileUpdate,
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


def test_preference_profile_create_accepts_safe_expanded_fields():
    profile = PreferenceProfileCreate(
        name="No car lifestyle",
        car_reliance="no_car",
        energy_preference="balanced",
        top_priority="transit_access",
        budget_sensitivity="moderate",
        commute_anchor={"label": "Union Station", "lat": 43.645, "lng": -79.38},
        max_monthly_rent=2200,
        must_haves=["transit", "groceries"],
        deal_breakers=["lower_rent_pressure"],
        notes="Likes short errands and transit access.",
    )

    assert profile.name == "No car lifestyle"
    assert profile.car_reliance == "no_car"
    assert profile.commute_anchor is not None
    assert profile.commute_anchor.label == "Union Station"
    assert profile.must_haves == ["transit", "groceries"]


def test_preference_profile_rejects_unsafe_categories():
    with pytest.raises(ValidationError):
        PreferenceProfileCreate(
            name="Unsafe profile",
            must_haves=["schools"],
        )


def test_preference_profile_update_allows_partial_changes():
    update = PreferenceProfileUpdate(name="Budget-first", must_haves=["lower_rent_pressure"])

    assert update.name == "Budget-first"
    assert update.must_haves == ["lower_rent_pressure"]
    assert update.preferences.car_reliance is None


def test_analyze_request_accepts_preference_profile_id():
    request = AnalyzeRequest(query="East Austin", preference_profile_id="profile-123")

    assert request.preference_profile_id == "profile-123"
