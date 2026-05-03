from pathlib import Path
from uuid import uuid4

from backend.models import (
    AnalyzeResponse,
    Confidence,
    NeighborhoodProfile,
    Place,
    PreferenceProfileCreate,
    PreferenceProfileUpdate,
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


def test_delete_saved_profile_removes_row():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Deleted Place"), db_path)

    assert delete_saved_profile(saved.id, db_path) is True
    assert get_saved_profile(saved.id, db_path) is None
    assert delete_saved_profile(saved.id, db_path) is False


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


def test_delete_preference_profile_removes_only_target_profile():
    db_path = _db_path()
    initialize_database(db_path)
    first = create_preference_profile(PreferenceProfileCreate(name="First"), db_path)
    second = create_preference_profile(PreferenceProfileCreate(name="Second"), db_path)

    assert delete_preference_profile(first.id, db_path) is True
    assert get_preference_profile(first.id, db_path) is None
    assert get_preference_profile(second.id, db_path) is not None
    assert delete_preference_profile(first.id, db_path) is False
