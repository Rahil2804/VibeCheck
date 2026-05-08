import asyncio

import pytest

from backend.models import (
    AnalyzeRequest,
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


async def _success_adapter():
    return {"value": 1}


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
        status for status in response.source_statuses if status.source == SourceName.LOCAL
    )
    assert local_status.status == SourceStatusCode.EMPTY
    assert local_status.message == "No local open-data adapter is configured for this region."
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
    assert response.confidence.level == "medium"
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
    assert any("timed out" in status.message.lower() for status in response.source_statuses)


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
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=synthesizer,
    )

    assert response.profile.overview == "Synthesized overview from source data."
    assert response.fit is not None
    assert response.fit.score > 50


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
    assert "OpenAI" in response.synthesis.message


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
    assert "fallback" in response.synthesis.message.lower()
    assert "RuntimeError" in response.synthesis.message
    assert "model failed" in response.synthesis.message


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
    assert any(item.claim_id == "overview" for item in response.profile.provenance.items)
