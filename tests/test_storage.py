from pathlib import Path
from uuid import uuid4

from backend.models import (
    AnalyzeResponse,
    Confidence,
    NeighborhoodProfile,
    Place,
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
    delete_saved_profile,
    get_saved_profile,
    initialize_database,
    list_saved_profiles,
    save_profile,
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
