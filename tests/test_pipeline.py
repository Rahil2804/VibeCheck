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


async def _success_adapter():
    return {"value": 1}


async def _error_adapter():
    raise RuntimeError("quota exhausted")


async def _slow_adapter():
    await asyncio.sleep(0.05)
    return {"value": 2}


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
