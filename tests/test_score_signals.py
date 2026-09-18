from backend.models import SourceName
from backend.score_signals import resolve_score_support, resolve_vibe_scores


def test_resolve_vibe_scores_never_turns_local_parks_into_unrelated_scores():
    scores = resolve_vibe_scores(
        {
            SourceName.LOCAL: {
                "parks_outdoors": 88,
                "parks_count": 5,
                "community_amenities_count": 2,
            }
        }
    )

    assert scores.walkability is None
    assert scores.quiet is None
    assert scores.social_scene is None
    assert scores.parks_outdoors == 88
    assert scores.transit_access is None
    assert scores.affordability is None


def test_resolve_vibe_scores_keeps_existing_source_scores_when_local_is_empty():
    scores = resolve_vibe_scores(
        {
            SourceName.ACCESS: {"walkability": 82, "transit_access": 77},
            SourceName.HOUSING: {"affordability": 61},
            SourceName.REDDIT: {"quiet": 44, "social_scene": 73},
            SourceName.LOCAL: {},
        }
    )

    assert scores.walkability == 82
    assert scores.transit_access == 77
    assert scores.affordability == 61
    assert scores.quiet is None
    assert scores.social_scene is None
    assert scores.parks_outdoors is None


def test_resolve_score_support_lists_local_fields_only_when_they_influence_scores():
    support = resolve_score_support(
        {
            SourceName.LOCAL: {
                "parks_outdoors": 88,
                "parks_count": 5,
                "community_amenities_count": 2,
            }
        }
    )

    assert support["walkability"] == []
    assert support["quiet"] == []
    assert support["social_scene"] == []
    assert support["parks_outdoors"] == ["local.parks_outdoors"]
    assert support["transit_access"] == []
    assert support["affordability"] == []
