import pytest
from pydantic import ValidationError

from backend.models import (
    AnalyzeRequest,
    CarReliance,
    Coordinates,
    CyclingContext,
    PreferenceProfileCreate,
    PreferenceProfileUpdate,
    ProfileProvenance,
    ProvenanceItem,
    ProvenanceSupport,
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
        "edition": None,
        "scope": None,
        "source_url": None,
        "stale": None,
        "fallback": False,
    }


def test_old_cycling_context_defaults_to_official_evidence_shape():
    context = CyclingContext(
        protected_network_km=1.2,
        total_network_km=2.4,
        bike_share_stations=3,
        scope="City of Toronto",
        edition="Legacy snapshot",
    )

    assert context.method == "toronto_official"
    assert context.fallback is False
    assert context.network_radius_m == 1000
    assert context.bicycle_parking_locations is None


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
    update = PreferenceProfileUpdate(
        name="Budget-first", must_haves=["lower_rent_pressure"]
    )

    assert update.name == "Budget-first"
    assert update.must_haves == ["lower_rent_pressure"]
    assert update.preferences.car_reliance is None


def test_preference_profile_requires_disjoint_positive_requirements():
    with pytest.raises(ValidationError):
        PreferenceProfileCreate(
            name="Overlapping",
            must_haves=["transit"],
            deal_breakers=["transit"],
        )


def test_analyze_request_accepts_preference_profile_id():
    request = AnalyzeRequest(query="East Austin", preference_profile_id="profile-123")

    assert request.preference_profile_id == "profile-123"


def test_profile_provenance_serializes_supported_claims():
    provenance = ProfileProvenance(
        items=[
            ProvenanceItem(
                claim_id="vibe.walkability",
                label="Walkability score",
                summary="Based on normalized access.walkability signal.",
                support=ProvenanceSupport.INFERRED,
                sources=[SourceName.ACCESS],
                source_fields=["access.walkability"],
            )
        ]
    )

    assert provenance.model_dump(mode="json") == {
        "items": [
            {
                "claim_id": "vibe.walkability",
                "label": "Walkability score",
                "summary": "Based on normalized access.walkability signal.",
                "support": "inferred",
                "sources": ["access"],
                "source_fields": ["access.walkability"],
            }
        ]
    }
