import asyncio
import inspect
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
from backend.provenance import build_profile_provenance
from backend.scorer import score_fit
from backend.sources.access import fetch_access_context
from backend.sources.census import fetch_census_context
from backend.sources.common import SourceContext, SourceFetcher, SourceResult
from backend.sources.housing import fetch_housing_context
from backend.sources.local import fetch_local_context
from backend.sources.mapbox import resolve_place
from backend.sources.reddit import fetch_reddit_context
from backend.synthesizer import synthesize_profile

ProfileSynthesizer = Callable[..., Awaitable[NeighborhoodProfile | None]]
logger = logging.getLogger(__name__)


DEFAULT_SOURCE_FETCHERS: dict[SourceName, SourceFetcher] = {
    SourceName.CENSUS: fetch_census_context,
    SourceName.HOUSING: fetch_housing_context,
    SourceName.REDDIT: fetch_reddit_context,
    SourceName.ACCESS: fetch_access_context,
    SourceName.LOCAL: fetch_local_context,
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
    context = SourceContext(request=request, place=place)
    source_results = await asyncio.gather(
        *[
            _run_source(source, fetcher, timeout, context)
            for source, fetcher in fetchers.items()
        ]
    )
    statuses = [place_status, *[status for status, _data in source_results]]
    source_data = {source: data for (status, data), source in zip(source_results, fetchers, strict=True)}
    confidence = build_confidence(statuses)
    provenance = build_profile_provenance(source_data, statuses)
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
    profile = profile.model_copy(update={"provenance": provenance})
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
    context: SourceContext,
) -> tuple[SourceStatus, dict[str, Any]]:
    try:
        result = await asyncio.wait_for(_call_source(fetcher, context), timeout=timeout)
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

    source_result = _coerce_source_result(result)
    if not source_result.data:
        return (
            SourceStatus(
                source=source,
                status=SourceStatusCode.EMPTY,
                message=source_result.message
                or f"{source.value} returned no usable MVP data.",
                updated_at=source_result.updated_at,
            ),
            {},
        )

    return (
            SourceStatus(
                source=source,
                status=SourceStatusCode.SUCCESS,
                message=source_result.message or f"{source.value} data returned.",
                updated_at=source_result.updated_at,
            ),
        source_result.data,
    )


async def _call_source(
    fetcher: SourceFetcher,
    context: SourceContext,
) -> dict[str, Any] | SourceResult | None:
    signature = inspect.signature(fetcher)
    required_parameters = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    ]
    if required_parameters:
        return await fetcher(context)
    return await fetcher()


def _coerce_source_result(result: dict[str, Any] | SourceResult | None) -> SourceResult:
    if isinstance(result, SourceResult):
        return result
    return SourceResult(data=result or {})


def _build_profile(place: Place, source_data: dict[SourceName, dict[str, Any]]) -> NeighborhoodProfile:
    access = source_data.get(SourceName.ACCESS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    census = source_data.get(SourceName.CENSUS, {})
    reddit = source_data.get(SourceName.REDDIT, {})
    local = source_data.get(SourceName.LOCAL, {})

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
        honest_pros=_build_honest_pros(local),
        honest_cons=_build_honest_cons(local),
        trajectory=_build_trajectory(local),
    )


def _build_honest_pros(local: dict[str, Any]) -> list[str]:
    pros = ["Profile generated with partial source-aware data."]
    parks_count = _int_from(local, "parks_count")
    amenities_count = _int_from(local, "community_amenities_count")
    if parks_count or amenities_count:
        pros.append(
            f"Toronto local open data found {parks_count} nearby parks and "
            f"{amenities_count} community amenity signals."
        )
    return pros


def _build_honest_cons(local: dict[str, Any]) -> list[str]:
    cons = [
        "Some source adapters may be unavailable until API keys or open-data "
        "coverage are configured."
    ]
    development_activity = _int_from(local, "development_activity")
    if development_activity >= 50:
        cons.append(
            "Local permit signals suggest visible nearby development activity; "
            "this can mean change and construction disruption, not guaranteed "
            "affordability movement."
        )
    return cons


def _build_trajectory(local: dict[str, Any]) -> Trajectory:
    if local.get("trajectory_signal") == "rising":
        return Trajectory(
            direction=TrajectoryDirection.RISING,
            summary=(
                "Local open-data signals suggest visible development/change activity "
                "nearby, based on active permit records."
            ),
        )
    if local.get("trajectory_signal") == "stable":
        return Trajectory(
            direction=TrajectoryDirection.STABLE,
            summary=(
                "Local permit signals show some nearby activity, but not enough "
                "to mark a strong change trajectory."
            ),
        )
    return Trajectory(
        direction=TrajectoryDirection.UNCERTAIN,
        summary="Trajectory is uncertain until housing and local trend sources return data.",
    )


def _int_from(data: dict[str, Any], key: str) -> int:
    raw = data.get(key, 0)
    return raw if isinstance(raw, int) else 0


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
