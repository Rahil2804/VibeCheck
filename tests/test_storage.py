from pathlib import Path
from uuid import uuid4

from backend.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Confidence,
    NeighborhoodProfile,
    Place,
    PreferenceProfileCreate,
    PreferenceProfileUpdate,
    ProfileProvenance,
    ProvenanceItem,
    ProvenanceSupport,
    SourceName,
    SourceStatus,
    SourceStatusCode,
    SynthesisStatus,
    SynthesisStatusCode,
    Trajectory,
    TrajectoryDirection,
    VibeScores,
    WhoLivesHere,
)
from backend.storage import (
    build_refresh_request,
    create_preference_profile,
    delete_preference_profile,
    delete_saved_profile,
    get_preference_profile,
    get_saved_profile,
    initialize_database,
    list_preference_profiles,
    list_saved_profiles,
    save_profile,
    set_default_preference_profile,
    update_preference_profile,
    update_saved_profile,
)


def _db_path() -> Path:
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    return directory / f"{uuid4()}.db"


def _response(label: str) -> AnalyzeResponse:
    return AnalyzeResponse(
        place=Place(label=label),
        profile=NeighborhoodProfile(
            overview=f"{label} overview.",
            vibe_scores=VibeScores(
                walkability=70,
                transit_access=60,
                affordability=50,
                quiet=55,
                social_scene=65,
            ),
            who_lives_here=WhoLivesHere(),
            honest_pros=["Readable profile."],
            honest_cons=["Thin source data."],
            trajectory=Trajectory(
                direction=TrajectoryDirection.UNCERTAIN,
                summary="Trajectory is uncertain.",
            ),
            provenance=ProfileProvenance(
                items=[
                    ProvenanceItem(
                        claim_id="overview",
                        label="Overview",
                        summary="Overview is generated from available normalized access signals.",
                        support=ProvenanceSupport.INFERRED,
                        sources=[SourceName.ACCESS],
                        source_fields=["access.walkability"],
                    )
                ]
            ),
        ),
        confidence=Confidence(
            level="low",
            available_sources=["mapbox"],
            missing_sources=["census"],
            caveats=["Thin data."],
        ),
        source_statuses=[
            SourceStatus(
                source=SourceName.MAPBOX,
                status=SourceStatusCode.SUCCESS,
                message="Place resolved.",
            )
        ],
        synthesis=SynthesisStatus(
            status=SynthesisStatusCode.SKIPPED,
            model=None,
            message="OpenAI synthesis was skipped; deterministic profile was used.",
        ),
    )


def test_save_profile_returns_metadata_and_persists_response():
    db_path = _db_path()
    initialize_database(db_path)

    saved = save_profile(_response("East Austin"), db_path)

    assert saved.id
    assert saved.place_label == "East Austin"
    assert saved.confidence_level == "low"
    assert saved.response.place.label == "East Austin"


def test_list_saved_profiles_returns_newest_first_without_full_response():
    db_path = _db_path()
    initialize_database(db_path)
    first = save_profile(_response("First Place"), db_path)
    second = save_profile(_response("Second Place"), db_path)

    summaries = list_saved_profiles(db_path)

    assert [summary.id for summary in summaries] == [second.id, first.id]
    assert summaries[0].place_label == "Second Place"
    assert not hasattr(summaries[0], "response")


def test_get_saved_profile_returns_original_response():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Kensington Market"), db_path)

    found = get_saved_profile(saved.id, db_path)

    assert found is not None
    assert found.response.place.label == "Kensington Market"
    assert found.response.profile.overview == "Kensington Market overview."


def test_saved_profile_preserves_provenance():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Source-backed Place"), db_path)

    found = get_saved_profile(saved.id, db_path)

    assert found is not None
    provenance_items = found.response.profile.provenance.items
    assert len(provenance_items) == 1
    assert provenance_items[0].claim_id == "overview"
    assert provenance_items[0].sources == [SourceName.ACCESS]


def test_delete_saved_profile_removes_row():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Deleted Place"), db_path)

    assert delete_saved_profile(saved.id, db_path) is True
    assert get_saved_profile(saved.id, db_path) is None
    assert delete_saved_profile(saved.id, db_path) is False


def test_save_profile_persists_analyze_request_metadata():
    db_path = _db_path()
    initialize_database(db_path)
    request = AnalyzeRequest(query="East Austin", generic_mode=True)

    saved = save_profile(_response("East Austin"), db_path, analyze_request=request)
    found = get_saved_profile(saved.id, db_path)

    assert found is not None
    assert found.analyze_request is not None
    assert found.analyze_request.query == "East Austin"
    assert found.analyze_request.generic_mode is True


def test_existing_saved_profile_without_request_metadata_still_loads():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Legacy Place"), db_path)

    found = get_saved_profile(saved.id, db_path)

    assert found is not None
    assert found.analyze_request is None
    assert found.response.place.label == "Legacy Place"


def test_update_saved_profile_overwrites_existing_row_and_updates_timestamp():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(
        _response("Old Place"),
        db_path,
        analyze_request=AnalyzeRequest(query="Old Place"),
    )

    updated = update_saved_profile(
        saved.id,
        _response("New Place"),
        db_path,
        analyze_request=AnalyzeRequest(query="New Place", generic_mode=True),
    )

    assert updated is not None
    assert updated.id == saved.id
    assert updated.created_at == saved.created_at
    assert updated.updated_at >= saved.updated_at
    assert updated.place_label == "New Place"
    assert updated.response.place.label == "New Place"
    assert updated.analyze_request is not None
    assert updated.analyze_request.query == "New Place"
    assert len(list_saved_profiles(db_path)) == 1


def test_build_refresh_request_uses_saved_request_when_available():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(
        _response("Profile-backed Place"),
        db_path,
        analyze_request=AnalyzeRequest(
            query="Profile-backed Place",
            preference_profile_id="profile-1",
        ),
    )

    request = build_refresh_request(saved)

    assert request.query == "Profile-backed Place"
    assert request.preference_profile_id == "profile-1"
    assert request.generic_mode is False


def test_build_refresh_request_falls_back_to_saved_place_as_generic():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Legacy Place"), db_path)

    request = build_refresh_request(saved)

    assert request.query == "Legacy Place"
    assert request.generic_mode is True
    assert request.preference_profile_id is None


def test_create_preference_profile_persists_expanded_fields():
    db_path = _db_path()
    initialize_database(db_path)

    profile = create_preference_profile(
        PreferenceProfileCreate(
            name="Rahil",
            car_reliance="no_car",
            commute_anchor={"label": "Union Station", "lat": 43.645, "lng": -79.38},
            max_monthly_rent=2200,
            must_haves=["transit", "groceries"],
            notes="Local only.",
        ),
        db_path,
    )

    found = get_preference_profile(profile.id, db_path)

    assert found is not None
    assert found.name == "Rahil"
    assert found.is_default is True
    assert found.commute_anchor is not None
    assert found.commute_anchor.label == "Union Station"
    assert found.must_haves == ["transit", "groceries"]
    assert found.notes == "Local only."


def test_list_preference_profiles_orders_default_first_then_updated():
    db_path = _db_path()
    initialize_database(db_path)
    first = create_preference_profile(PreferenceProfileCreate(name="First"), db_path)
    second = create_preference_profile(PreferenceProfileCreate(name="Second"), db_path)

    set_default_preference_profile(second.id, db_path)
    profiles = list_preference_profiles(db_path)

    assert [profile.id for profile in profiles] == [second.id, first.id]
    assert profiles[0].is_default is True
    assert profiles[1].is_default is False


def test_update_preference_profile_changes_only_supplied_fields():
    db_path = _db_path()
    initialize_database(db_path)
    profile = create_preference_profile(
        PreferenceProfileCreate(name="Original", car_reliance="no_car", must_haves=["transit"]),
        db_path,
    )

    updated = update_preference_profile(
        profile.id,
        PreferenceProfileUpdate(name="Updated", deal_breakers=["quiet"]),
        db_path,
    )

    assert updated is not None
    assert updated.name == "Updated"
    assert updated.car_reliance == "no_car"
    assert updated.must_haves == ["transit"]
    assert updated.deal_breakers == ["quiet"]


def test_update_preference_profile_can_clear_optional_fields():
    db_path = _db_path()
    initialize_database(db_path)
    profile = create_preference_profile(
        PreferenceProfileCreate(
            name="Original",
            car_reliance="no_car",
            commute_anchor={"label": "Office"},
            max_monthly_rent=2400,
            notes="Local note.",
        ),
        db_path,
    )

    updated = update_preference_profile(
        profile.id,
        PreferenceProfileUpdate(
            car_reliance=None,
            commute_anchor=None,
            max_monthly_rent=None,
            notes=None,
        ),
        db_path,
    )

    assert updated is not None
    assert updated.car_reliance is None
    assert updated.commute_anchor is None
    assert updated.max_monthly_rent is None
    assert updated.notes is None


def test_delete_preference_profile_removes_only_target_profile():
    db_path = _db_path()
    initialize_database(db_path)
    first = create_preference_profile(PreferenceProfileCreate(name="First"), db_path)
    second = create_preference_profile(PreferenceProfileCreate(name="Second"), db_path)

    assert delete_preference_profile(first.id, db_path) is True
    assert get_preference_profile(first.id, db_path) is None
    assert get_preference_profile(second.id, db_path) is not None
    assert delete_preference_profile(first.id, db_path) is False
