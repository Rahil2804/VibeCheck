import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from backend.confidence import build_confidence
from backend.models import (
    AnalyzeRequest,
    AnalyzeResponse,
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
from backend.scorer import score_fit
from backend.sources.access import fetch_access_context
from backend.sources.census import fetch_census_context
from backend.sources.housing import fetch_housing_context
from backend.sources.mapbox import resolve_place
from backend.sources.reddit import fetch_reddit_context
from backend.synthesizer import synthesize_profile

SourceFetcher = Callable[[], Awaitable[dict[str, Any] | None]]
ProfileSynthesizer = Callable[..., Awaitable[NeighborhoodProfile | None]]
logger = logging.getLogger(__name__)


DEFAULT_SOURCE_FETCHERS: dict[SourceName, SourceFetcher] = {
    SourceName.CENSUS: fetch_census_context,
    SourceName.HOUSING: fetch_housing_context,
    SourceName.REDDIT: fetch_reddit_context,
    SourceName.ACCESS: fetch_access_context,
}


async def analyze_neighborhood(
    request: AnalyzeRequest,
    source_fetchers: dict[SourceName, SourceFetcher] | None = None,
    source_timeout_seconds: float | None = None,
    profile_synthesizer: ProfileSynthesizer | None = None,
) -> AnalyzeResponse:
    timeout = source_timeout_seconds or float(os.getenv("SOURCE_TIMEOUT_SECONDS", "8"))
    place = await resolve_place(request)
    place_status = SourceStatus(
        source=SourceName.MAPBOX,
        status=SourceStatusCode.SUCCESS,
        message="Place resolved.",
    )

    fetchers = source_fetchers or DEFAULT_SOURCE_FETCHERS
    source_results = await asyncio.gather(
        *[_run_source(source, fetcher, timeout) for source, fetcher in fetchers.items()]
    )
    statuses = [place_status, *[status for status, _data in source_results]]
    source_data = {source: data for (status, data), source in zip(source_results, fetchers, strict=True)}
    confidence = build_confidence(statuses)
    fallback_profile = _build_profile(place, source_data)
    synthesizer = profile_synthesizer or synthesize_profile
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    synthesis = SynthesisStatus(
        status=SynthesisStatusCode.SKIPPED,
        model=None,
        message="OpenAI synthesis was skipped; deterministic profile was used.",
    )
    try:
        profile = await synthesizer(
            place_label=place.label,
            source_data={source.value: data for source, data in source_data.items()},
            caveats=confidence.caveats,
        )
    except Exception as exc:
        logger.exception("OpenAI synthesis failed; using deterministic fallback profile.")
        profile = None
        synthesis = SynthesisStatus(
            status=SynthesisStatusCode.FALLBACK,
            model=model_name,
            message=(
                "OpenAI synthesis failed; deterministic fallback profile was used. "
                f"Reason: {_safe_exception_message(exc)}"
            ),
        )
    else:
        if profile is not None:
            synthesis = SynthesisStatus(
                status=SynthesisStatusCode.USED,
                model=model_name,
                message="OpenAI generated the profile from normalized source data.",
            )
    if profile is None:
        profile = fallback_profile
    fit = None if request.generic_mode else score_fit(profile, request.preferences)

    return AnalyzeResponse(
        place=place,
        profile=profile,
        fit=fit,
        confidence=confidence,
        source_statuses=statuses,
        synthesis=synthesis,
    )


async def _run_source(
    source: SourceName,
    fetcher: SourceFetcher,
    timeout: float,
) -> tuple[SourceStatus, dict[str, Any]]:
    try:
        data = await asyncio.wait_for(fetcher(), timeout=timeout)
    except TimeoutError:
        return (
            SourceStatus(
                source=source,
                status=SourceStatusCode.ERROR,
                message=f"{source.value} timed out after {timeout:g}s.",
            ),
            {},
        )
    except Exception as exc:
        return (
            SourceStatus(
                source=source,
                status=SourceStatusCode.ERROR,
                message=f"{source.value} failed: {exc}",
            ),
            {},
        )

    if not data:
        return (
            SourceStatus(
                source=source,
                status=SourceStatusCode.EMPTY,
                message=f"{source.value} returned no usable MVP data.",
            ),
            {},
        )

    return (
        SourceStatus(
            source=source,
            status=SourceStatusCode.SUCCESS,
            message=f"{source.value} data returned.",
        ),
        data,
    )


def _build_profile(place: Place, source_data: dict[SourceName, dict[str, Any]]) -> NeighborhoodProfile:
    access = source_data.get(SourceName.ACCESS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    census = source_data.get(SourceName.CENSUS, {})
    reddit = source_data.get(SourceName.REDDIT, {})

    scores = VibeScores(
        walkability=_score_from(access, "walkability", 50),
        transit_access=_score_from(access, "transit_access", 50),
        affordability=_score_from(housing, "affordability", 50),
        quiet=_score_from(reddit, "quiet", 50),
        social_scene=_score_from(reddit, "social_scene", 50),
    )
    label = place.neighborhood or place.label

    return NeighborhoodProfile(
        overview=f"{label} profile is based on currently available source signals.",
        vibe_scores=scores,
        who_lives_here=WhoLivesHere(
            median_age=census.get("median_age"),
            median_household_income=census.get("median_household_income"),
            population_density=census.get("population_density"),
            population_trend=census.get("population_trend"),
        ),
        honest_pros=["Profile generated with partial source-aware data."],
        honest_cons=["Some source adapters may be unavailable until API keys or open-data coverage are configured."],
        trajectory=Trajectory(
            direction=TrajectoryDirection.UNCERTAIN,
            summary="Trajectory is uncertain until housing and local trend sources return data.",
        ),
    )


def _score_from(data: dict[str, Any], key: str, default: int) -> int:
    raw = data.get(key, default)
    if not isinstance(raw, int | float):
        return default
    return max(0, min(100, int(raw)))


def _safe_exception_message(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    if len(message) > 220:
        message = f"{message[:217]}..."
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__
