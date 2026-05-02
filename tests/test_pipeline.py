import asyncio

import pytest

from backend.models import AnalyzeRequest, SourceName, SourceStatusCode
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
