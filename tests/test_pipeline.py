import asyncio

import pytest

from backend.models import (
    AnalyzeRequest,
    NarrativeCitation,
    NeighborhoodProfile,
    Preferences,
    SourceName,
    SourceStatusCode,
    SynthesisStatusCode,
    TopPriority,
    Trajectory,
    TrajectoryDirection,
    VibeScores,
    WhoLivesHere,
)
from backend.pipeline import analyze_neighborhood
from backend.sources.common import SourceContext, SourceResult
from backend.synthesizer import SynthesizedProfileResult


async def _success_adapter():
    return {
        "value": 1,
        "population_density": 1000,
        "affordability": 55,
        "walkability": 70,
        "score": 65,
    }


async def _access_adapter():
    return {
        "walkability": 80,
        "transit_access": 75,
        "daily_needs": 72,
        "food_social": 68,
        "parks_outdoors": 60,
    }


async def _error_adapter():
    raise RuntimeError("quota exhausted")


async def _slow_adapter():
    await asyncio.sleep(0.05)
    return {"value": 2}


async def _returns_none(**_kwargs):
    return None


@pytest.mark.asyncio
async def test_pipeline_passes_resolved_place_to_context_aware_source():
    seen_context: SourceContext | None = None

    async def local_adapter(context: SourceContext):
        nonlocal seen_context
        seen_context = context
        return {"coverage_area": context.place.label}

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Toronto, ON"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
            SourceName.LOCAL: local_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    assert seen_context is not None
    assert seen_context.place.label == "Toronto, ON"
    assert seen_context.request.query == "Toronto, ON"
    assert any(status.source == SourceName.LOCAL for status in response.source_statuses)


@pytest.mark.asyncio
async def test_pipeline_uses_source_result_message_and_updated_at():
    async def local_adapter(_context: SourceContext):
        return SourceResult(
            data={},
            message="No local open-data adapter is configured for this region.",
            updated_at="2026-05-08T00:00:00+00:00",
        )

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Buffalo, NY"),
        source_fetchers={SourceName.LOCAL: local_adapter},
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    local_status = next(
        status
        for status in response.source_statuses
        if status.source == SourceName.LOCAL
    )
    assert local_status.status == SourceStatusCode.EMPTY
    assert (
        local_status.message
        == "No local open-data adapter is configured for this region."
    )
    assert local_status.updated_at == "2026-05-08T00:00:00+00:00"


@pytest.mark.asyncio
async def test_pipeline_keeps_partial_results_when_source_fails():
    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _error_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
    )

    statuses = {status.source: status.status for status in response.source_statuses}
    assert statuses[SourceName.CENSUS] == SourceStatusCode.SUCCESS
    assert statuses[SourceName.HOUSING] == SourceStatusCode.ERROR
    assert response.confidence.level == "low"
    assert response.place.label == "East Austin"


@pytest.mark.asyncio
async def test_pipeline_converts_source_timeout_to_status():
    response = await analyze_neighborhood(
        AnalyzeRequest(query="Thin data place"),
        source_fetchers={
            SourceName.CENSUS: _slow_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=0.001,
    )

    statuses = {status.source: status.status for status in response.source_statuses}
    assert statuses[SourceName.CENSUS] == SourceStatusCode.ERROR
    assert any(
        "timed out" in status.message.lower() for status in response.source_statuses
    )


def _synthetic_profile() -> NeighborhoodProfile:
    return NeighborhoodProfile(
        overview="Synthesized overview from source data.",
        vibe_scores=VibeScores(
            walkability=80,
            transit_access=75,
            affordability=45,
            quiet=55,
            social_scene=70,
        ),
        who_lives_here=WhoLivesHere(),
        honest_pros=["Synthesized pro."],
        honest_cons=["Synthesized caveat."],
        trajectory=Trajectory(
            direction=TrajectoryDirection.UNCERTAIN,
            summary="Synthesized trajectory.",
        ),
    )


@pytest.mark.asyncio
async def test_pipeline_uses_synthesized_profile_when_available():
    async def synthesizer(**_kwargs):
        return _synthetic_profile()

    response = await analyze_neighborhood(
        AnalyzeRequest(
            query="East Austin",
            preferences=Preferences(top_priority=TopPriority.TRANSIT_ACCESS),
        ),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _access_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=synthesizer,
    )

    assert response.profile.overview == "Synthesized overview from source data."
    assert response.fit is not None
    assert response.fit.score > 50


@pytest.mark.asyncio
async def test_road_and_building_evidence_affects_context_not_fit_metrics():
    captured_evidence = None

    async def collision_adapter():
        return {
            "collision_context": {
                "radius_m": 1000,
                "baseline_period_start": "2020-01-01",
                "baseline_period_end": "2024-12-31",
                "total_collisions": 20,
                "injury_collisions": 4,
                "fatal_collisions": 0,
                "pedestrian_involved_collisions": 2,
                "cyclist_involved_collisions": 1,
                "ksi_period_start": "2020-01-01",
                "ksi_period_end": "2026-09-01",
                "ksi_collisions": 3,
                "ksi_fatal_collisions": 0,
                "ksi_pedestrian_involved_collisions": 1,
                "ksi_cyclist_involved_collisions": 1,
                "severe_events": [],
                "edition": "fixture",
            }
        }

    async def building_adapter():
        return {
            "building_context": {
                "rsn": "1234",
                "site_address": "210 WYCHWOOD AVE",
                "current_score": 86,
                "rating": "green",
                "edition": "fixture",
            }
        }

    async def capture_synthesizer(**kwargs):
        nonlocal captured_evidence
        captured_evidence = kwargs["evidence"]
        return None

    response = await analyze_neighborhood(
        AnalyzeRequest(
            query="210 Wychwood Avenue, Toronto",
            preferences=Preferences(top_priority=TopPriority.WALKABILITY_ERRANDS),
        ),
        source_fetchers={
            SourceName.ACCESS: _access_adapter,
            SourceName.COLLISIONS: collision_adapter,
            SourceName.BUILDING: building_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=capture_synthesizer,
    )

    assert response.profile.vibe_scores.walkability == 80
    assert response.fit is not None and response.fit.score == 65
    assert response.profile.collision_context is not None
    assert response.profile.building_context is not None
    assert response.confidence.level == "medium"
    assert {
        check.id for check in response.evidence_checks if check.status == "supported"
    } >= {"access", "collisions", "building"}
    assert captured_evidence is not None
    assert {check["id"] for check in captured_evidence["checks"]} >= {
        "access",
        "collisions",
        "building",
    }


@pytest.mark.asyncio
async def test_pipeline_falls_back_when_synthesizer_fails():
    async def failing_synthesizer(**_kwargs):
        raise RuntimeError("model failed")

    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=failing_synthesizer,
    )

    assert "currently available source signals" in response.profile.overview


@pytest.mark.asyncio
async def test_pipeline_reports_synthesis_used_when_synthesizer_returns_profile():
    async def synthesizer(**_kwargs):
        return _synthetic_profile()

    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=synthesizer,
    )

    assert response.synthesis.status == SynthesisStatusCode.USED
    assert response.synthesis.model is not None
    assert "AI narrative" in response.synthesis.message


@pytest.mark.asyncio
async def test_pipeline_replaces_rejected_ai_claims_with_deterministic_copy():
    async def partially_grounded(**_kwargs):
        return SynthesizedProfileResult(
            profile=NeighborhoodProfile(
                overview="Access evidence is available.",
                vibe_scores=VibeScores(),
                who_lives_here=WhoLivesHere(),
                honest_pros=[],
                honest_cons=["Some evidence is unavailable."],
                narrative_citations=[
                    NarrativeCitation(
                        section="overview", evidence_check_ids=["access"]
                    ),
                    NarrativeCitation(
                        section="con", item_index=0, evidence_check_ids=["census"]
                    ),
                ],
            ),
            accepted_claim_count=2,
            rejected_claim_count=1,
            duration_ms=5,
            rejected_sections=("pro",),
        )

    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.ACCESS: _access_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=partially_grounded,
    )

    assert response.synthesis.status == SynthesisStatusCode.PARTIAL
    assert response.synthesis.rejected_claim_count == 1
    assert response.profile.honest_pros
    assert response.profile.honest_cons == ["Some evidence is unavailable."]


@pytest.mark.asyncio
async def test_pipeline_reports_synthesis_skipped_when_synthesizer_returns_none():
    async def skipped_synthesizer(**_kwargs):
        return None

    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=skipped_synthesizer,
    )

    assert response.synthesis.status == SynthesisStatusCode.SKIPPED
    assert "deterministic" in response.synthesis.message


@pytest.mark.asyncio
async def test_pipeline_reports_synthesis_fallback_when_synthesizer_fails():
    async def failing_synthesizer(**_kwargs):
        raise RuntimeError("model failed")

    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=failing_synthesizer,
    )

    assert response.synthesis.status == SynthesisStatusCode.FALLBACK
    assert "deterministic" in response.synthesis.message.lower()
    assert "RuntimeError" not in response.synthesis.message
    assert "model failed" not in response.synthesis.message


@pytest.mark.asyncio
async def test_pipeline_attaches_provenance_to_deterministic_profile():
    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    assert response.profile.provenance.items
    claim_ids = {item.claim_id for item in response.profile.provenance.items}
    assert "overview" in claim_ids
    assert "vibe.walkability" in claim_ids


@pytest.mark.asyncio
async def test_pipeline_attaches_backend_provenance_to_synthesized_profile():
    async def synthesizer(**_kwargs):
        return _synthetic_profile()

    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=synthesizer,
    )

    assert response.synthesis.status == SynthesisStatusCode.USED
    assert response.profile.provenance.items
    assert any(
        item.claim_id == "overview" for item in response.profile.provenance.items
    )


@pytest.mark.asyncio
async def test_pipeline_uses_local_data_for_deterministic_trajectory_and_pros():
    async def local_adapter(_context: SourceContext):
        return {
            "coverage_area": "Toronto",
            "development_activity": 72,
            "recent_permits_count": 4,
            "major_project_count": 3,
            "parks_count": 2,
            "community_amenities_count": 1,
            "parks_outdoors": 28,
            "trajectory_signal": "rising",
            "summary": "Toronto open data returned nearby development and parks/amenity signals.",
            "updated_at": "2026-05-08T00:00:00+00:00",
        }

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Kensington Market, Toronto, ON"),
        source_fetchers={
            SourceName.LOCAL: local_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    assert response.profile.trajectory is None
    assert any("parks" in item.lower() for item in response.profile.honest_pros)


@pytest.mark.asyncio
async def test_pipeline_bridges_local_parks_into_visible_scores():
    async def local_adapter(_context: SourceContext):
        return {
            "coverage_area": "Toronto",
            "parks_count": 5,
            "community_amenities_count": 2,
            "parks_outdoors": 88,
            "trajectory_signal": "uncertain",
            "summary": "Toronto open data returned nearby parks/amenity signals.",
            "updated_at": "2026-05-08T00:00:00+00:00",
        }

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Kensington Market, Toronto, ON"),
        source_fetchers={SourceName.LOCAL: local_adapter},
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    scores = response.profile.vibe_scores
    assert scores.walkability is None
    assert scores.quiet is None
    assert scores.social_scene is None
    assert scores.parks_outdoors == 88
    assert scores.transit_access is None
    assert scores.affordability is None


@pytest.mark.asyncio
async def test_pipeline_uses_access_scores_for_visible_scores():
    async def access_adapter(_context: SourceContext):
        return SourceResult(
            data={
                "walkability": 76,
                "transit_access": 67,
                "daily_needs": 72,
                "food_social": 71,
                "parks_outdoors": 64,
                "nearby_categories": {
                    "groceries": 2,
                    "pharmacies": 1,
                    "restaurants": 8,
                    "cafes": 3,
                    "bars": 1,
                    "transit": 5,
                    "parks": 2,
                    "libraries": 1,
                    "community": 1,
                },
                "summary": "Nearby public POI signals found groceries and transit.",
            },
            message="Nearby public POI signals found groceries and transit.",
            updated_at="2026-05-10T00:00:00+00:00",
        )

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Kensington Market, Toronto, ON"),
        source_fetchers={SourceName.ACCESS: access_adapter},
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    scores = response.profile.vibe_scores
    assert scores.walkability == 76
    assert scores.transit_access == 67
    assert scores.parks_outdoors == 64
    assert scores.daily_needs == 72
    assert scores.dining_activity == 71

    access_status = next(
        status
        for status in response.source_statuses
        if status.source == SourceName.ACCESS
    )
    assert access_status.status == SourceStatusCode.SUCCESS
    assert access_status.updated_at == "2026-05-10T00:00:00+00:00"


@pytest.mark.asyncio
async def test_pipeline_skips_ai_and_numeric_fit_when_evidence_is_empty():
    calls = 0

    async def empty_adapter(_context: SourceContext):
        return SourceResult(data={}, message="No evidence returned.")

    async def synthesizer(**_kwargs):
        nonlocal calls
        calls += 1
        return _synthetic_profile()

    response = await analyze_neighborhood(
        AnalyzeRequest(
            query="Thin evidence place",
            preferences=Preferences(top_priority=TopPriority.TRANSIT_ACCESS),
        ),
        source_fetchers={
            SourceName.CENSUS: empty_adapter,
            SourceName.HOUSING: empty_adapter,
            SourceName.ACCESS: empty_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=synthesizer,
    )

    assert calls == 0
    assert response.fit is not None
    assert response.fit.score is None
    assert response.confidence.level == "none"
    assert response.synthesis.status == SynthesisStatusCode.SKIPPED
    assert response.synthesis.reason_code == "insufficient_evidence"
    assert any(check.id == "ai" for check in response.evidence_checks)


@pytest.mark.asyncio
async def test_pipeline_requires_two_allowlisted_non_mapbox_facts_before_ai():
    calls = 0

    async def irrelevant_adapter():
        return {"provider_internal_value": 1}

    async def synthesizer(**_kwargs):
        nonlocal calls
        calls += 1
        return _synthetic_profile()

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Thin evidence place"),
        source_fetchers={
            SourceName.CENSUS: irrelevant_adapter,
            SourceName.ACCESS: irrelevant_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=synthesizer,
    )

    assert calls == 0
    assert response.synthesis.reason_code == "insufficient_evidence"
    assert response.synthesis.evidence_count == 0


@pytest.mark.asyncio
async def test_unreadable_snapshot_produces_one_actionable_setup_check(monkeypatch):
    monkeypatch.setattr(
        "backend.pipeline.snapshot_health",
        lambda: {
            "ready": False,
            "stale": True,
            "errors": ["Snapshot database is not readable by the backend process."],
        },
    )
    monkeypatch.setattr(
        "backend.pipeline.DEFAULT_SOURCE_FETCHERS",
        {
            SourceName.HOUSING: _success_adapter,
            SourceName.TRANSIT: _success_adapter,
            SourceName.CYCLING: _success_adapter,
        },
    )

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Toronto"),
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    snapshot_checks = [
        check for check in response.evidence_checks if check.id == "snapshot"
    ]
    assert len(snapshot_checks) == 1
    assert snapshot_checks[0].status == "error"
    snapshot_statuses = [
        status
        for status in response.source_statuses
        if status.source in {SourceName.HOUSING, SourceName.TRANSIT, SourceName.CYCLING}
    ]
    assert len(snapshot_statuses) == 3
    statuses = {status.source: status.status for status in snapshot_statuses}
    assert statuses[SourceName.HOUSING] == SourceStatusCode.EMPTY
    assert statuses[SourceName.TRANSIT] == SourceStatusCode.EMPTY
    assert statuses[SourceName.CYCLING] == SourceStatusCode.SUCCESS
    assert not any(
        "unable to open database" in status.message for status in snapshot_statuses
    )


@pytest.mark.asyncio
async def test_pipeline_preserves_valid_zero_osm_cycling_as_fallback_evidence():
    async def cycling_adapter(_context: SourceContext):
        return SourceResult(
            data={
                "score": 0,
                "protected_network_km": 0,
                "total_network_km": 0,
                "bike_share_stations": None,
                "bicycle_parking_locations": 0,
                "network_radius_m": 1000,
                "scope": "OpenStreetMap mapped cycling infrastructure",
                "edition": "OpenStreetMap live proximity query",
                "method": "osm_fallback",
                "fallback": True,
            },
            message=(
                "OpenStreetMap returned no mapped qualifying cycling "
                "infrastructure within 1 km."
            ),
            scope="OpenStreetMap mapped cycling infrastructure",
            edition="OpenStreetMap live proximity query",
            fallback=True,
        )

    response = await analyze_neighborhood(
        AnalyzeRequest(
            query="Ottawa, Ontario",
            coordinates={"lat": 45.4215, "lng": -75.6972},
            preferences=Preferences(top_priority=TopPriority.CYCLING_ACCESS),
        ),
        source_fetchers={SourceName.CYCLING: cycling_adapter},
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    cycling_status = next(
        status
        for status in response.source_statuses
        if status.source == SourceName.CYCLING
    )
    cycling_check = next(
        check for check in response.evidence_checks if check.id == "cycling"
    )
    assert cycling_status.fallback is True
    assert cycling_check.status == "fallback"
    assert response.profile.vibe_scores.cycling_access == 0
    assert response.profile.cycling_context is not None
    assert response.profile.cycling_context.method == "osm_fallback"
    assert "Cycling access" in response.coverage.supported_signals
    assert response.fit is not None
    assert response.fit.factors[0].impact == -8
