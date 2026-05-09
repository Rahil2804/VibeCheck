from backend.models import SourceName, SourceStatus, SourceStatusCode
from backend.provenance import build_profile_provenance


def _status(source: SourceName, status: SourceStatusCode) -> SourceStatus:
    return SourceStatus(source=source, status=status, message=f"{source.value} {status.value}.")


def test_build_profile_provenance_marks_supported_access_and_housing_claims():
    provenance = build_profile_provenance(
        {
            SourceName.ACCESS: {
                "walkability": 82,
                "transit_access": 74,
                "daily_needs": 68,
            },
            SourceName.HOUSING: {"affordability": 44},
            SourceName.CENSUS: {
                "median_age": 34,
                "median_household_income": 82000,
                "population_density": 9500,
            },
            SourceName.REDDIT: {"quiet": 58, "social_scene": 66},
        },
        [
            _status(SourceName.ACCESS, SourceStatusCode.SUCCESS),
            _status(SourceName.HOUSING, SourceStatusCode.SUCCESS),
            _status(SourceName.CENSUS, SourceStatusCode.SUCCESS),
            _status(SourceName.REDDIT, SourceStatusCode.SUCCESS),
        ],
    )

    items = {item.claim_id: item for item in provenance.items}
    assert items["vibe.walkability"].support == "inferred"
    assert items["vibe.walkability"].sources == [SourceName.ACCESS]
    assert items["vibe.walkability"].source_fields == ["access.walkability"]
    assert items["vibe.affordability"].source_fields == ["housing.affordability"]
    assert items["context.median_household_income"].support == "direct"
    assert items["trajectory"].support == "unavailable"


def test_build_profile_provenance_marks_missing_or_failed_sources_unavailable():
    provenance = build_profile_provenance(
        {
            SourceName.ACCESS: {},
            SourceName.HOUSING: {},
            SourceName.CENSUS: {},
            SourceName.REDDIT: {},
        },
        [
            _status(SourceName.ACCESS, SourceStatusCode.EMPTY),
            _status(SourceName.HOUSING, SourceStatusCode.ERROR),
            _status(SourceName.CENSUS, SourceStatusCode.EMPTY),
            _status(SourceName.REDDIT, SourceStatusCode.EMPTY),
        ],
    )

    items = {item.claim_id: item for item in provenance.items}
    assert items["vibe.walkability"].support == "unavailable"
    assert items["vibe.walkability"].sources == [SourceName.ACCESS]
    assert "access source is empty" in items["vibe.walkability"].summary.lower()
    assert items["vibe.affordability"].support == "unavailable"
    assert "housing source errored" in items["vibe.affordability"].summary.lower()
    assert items["overview"].support == "unavailable"


def test_build_profile_provenance_marks_local_trajectory_and_amenities_supported():
    provenance = build_profile_provenance(
        {
            SourceName.LOCAL: {
                "development_activity": 72,
                "recent_permits_count": 4,
                "trajectory_signal": "rising",
                "parks_count": 2,
                "community_amenities_count": 1,
                "parks_outdoors": 28,
            }
        },
        [_status(SourceName.LOCAL, SourceStatusCode.SUCCESS)],
    )

    items = {item.claim_id: item for item in provenance.items}
    assert items["overview"].sources == [SourceName.LOCAL]
    assert items["trajectory"].sources == [SourceName.LOCAL]
    assert "local.development_activity" in items["trajectory"].source_fields
    assert items["local.amenities"].support == "inferred"
    assert items["local.amenities"].source_fields == [
        "local.parks_count",
        "local.community_amenities_count",
        "local.parks_outdoors",
    ]
