import asyncio
import inspect
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from backend.confidence import build_confidence
from backend.coverage import build_coverage
from backend.evidence import (
    build_evidence_checks,
    synthesis_check,
)
from backend.geography import resolve_geography
from backend.models import (
    AnalysisLensMode,
    AnalysisLensSnapshot,
    AnalyzeRequest,
    AnalyzeResponse,
    NeighborhoodProfile,
    Place,
    SourceName,
    SourceStatus,
    SourceStatusCode,
    SynthesisStatus,
    SynthesisStatusCode,
    WhoLivesHere,
)
from backend.provenance import build_profile_provenance
from backend.score_signals import resolve_vibe_scores
from backend.scorer import score_fit
from backend.sources.access import fetch_access_context
from backend.sources.census import fetch_census_context
from backend.sources.common import SourceContext, SourceFetcher, SourceResult
from backend.sources.housing import fetch_housing_context
from backend.sources.local import fetch_local_context
from backend.sources.mapbox import resolve_place
from backend.sources.transit import fetch_transit_context
from backend.sources.cycling import fetch_cycling_context
from backend.snapshot import snapshot_health
from backend.synthesizer import (
    PROMPT_VERSION,
    SynthesizedProfileResult,
    synthesize_profile,
)

ProfileSynthesizer = Callable[..., Awaitable[Any]]
logger = logging.getLogger(__name__)
ANALYSIS_VERSION = "2026.09-grounded-evidence-v3"
SNAPSHOT_SOURCES = {SourceName.HOUSING, SourceName.TRANSIT, SourceName.CYCLING}


DEFAULT_SOURCE_FETCHERS: dict[SourceName, SourceFetcher] = {
    SourceName.CENSUS: fetch_census_context,
    SourceName.HOUSING: fetch_housing_context,
    SourceName.ACCESS: fetch_access_context,
    SourceName.LOCAL: fetch_local_context,
    SourceName.TRANSIT: fetch_transit_context,
    SourceName.CYCLING: fetch_cycling_context,
}


async def analyze_neighborhood(
    request: AnalyzeRequest,
    source_fetchers: dict[SourceName, SourceFetcher] | None = None,
    source_timeout_seconds: float | None = None,
    profile_synthesizer: ProfileSynthesizer | None = None,
    analysis_lens: AnalysisLensSnapshot | None = None,
) -> AnalyzeResponse:
    timeout = source_timeout_seconds or float(os.getenv("SOURCE_TIMEOUT_SECONDS", "8"))
    place = await resolve_place(request)
    geography = resolve_geography(place)
    snapshot = snapshot_health()
    place_status = SourceStatus(
        source=SourceName.MAPBOX,
        status=SourceStatusCode.SUCCESS,
        message="Place resolved.",
    )

    fetchers = source_fetchers or DEFAULT_SOURCE_FETCHERS
    active_fetchers = (
        fetchers
        if source_fetchers is not None or snapshot["ready"]
        else {
            source: fetcher
            for source, fetcher in fetchers.items()
            if source not in SNAPSHOT_SOURCES
        }
    )
    context = SourceContext(request=request, place=place, geography=geography)
    source_results = await asyncio.gather(
        *[
            _run_source(source, fetcher, timeout, context)
            for source, fetcher in active_fetchers.items()
        ]
    )
    statuses = [place_status, *[status for status, _data in source_results]]
    source_data = {
        source: data
        for (_status, data), source in zip(source_results, active_fetchers, strict=True)
    }
    if source_fetchers is None and not snapshot["ready"]:
        for source in SNAPSHOT_SOURCES:
            source_data[source] = {}
            statuses.append(
                SourceStatus(
                    source=source,
                    status=SourceStatusCode.EMPTY,
                    message="Bundled snapshot unavailable; see the snapshot evidence check.",
                )
            )
    provenance = build_profile_provenance(source_data, statuses)
    fallback_profile = _build_profile(place, source_data).model_copy(
        update={"provenance": provenance}
    )
    scores = fallback_profile.vibe_scores
    coverage = build_coverage(place, scores)
    contextual_signals: list[str] = []
    context = fallback_profile.who_lives_here
    if context.population_density is not None:
        contextual_signals.append("Population density")
    if context.median_renter_shelter_cost is not None:
        contextual_signals.append("Neighbourhood renter shelter cost")
    if context.regional_average_two_bedroom_rent is not None:
        contextual_signals.append("CMHC regional rent benchmark")
    if context.rent_benchmark is not None:
        contextual_signals.append("CMHC unit-matched rent benchmark")
    supported_signals = list(
        dict.fromkeys([*coverage.supported_signals, *contextual_signals])
    )
    coverage = coverage.model_copy(
        update={
            "supported_signals": supported_signals,
            "message": (
                f"{coverage.region.value.replace('_', ' ').title()} evidence tier. "
                f"Supported now: {', '.join(supported_signals) if supported_signals else 'no analytical signals'}. "
                f"Unavailable now: {', '.join(coverage.unavailable_signals) if coverage.unavailable_signals else 'none'}."
            ),
        }
    )
    lens = analysis_lens or AnalysisLensSnapshot(
        mode=AnalysisLensMode.GENERIC
        if request.generic_mode
        else AnalysisLensMode.CUSTOM,
        profile_name="Generic" if request.generic_mode else "Custom preferences",
        preferences=request.preferences,
    )
    fit = (
        None
        if request.generic_mode
        else score_fit(fallback_profile, request.preferences)
    )
    evidence_checks = build_evidence_checks(
        place=place,
        geography=geography,
        statuses=statuses,
        profile=fallback_profile,
        fit=fit,
        snapshot=snapshot,
        generic_mode=request.generic_mode,
        source_data=source_data,
    )
    confidence = build_confidence(
        statuses,
        coverage.supported_signals,
        evidence_checks=evidence_checks,
    )
    synthesizer = profile_synthesizer or synthesize_profile
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    ai_evidence = _build_ai_evidence(
        checks=evidence_checks,
        source_data=source_data,
        lens=lens,
        fit=fit,
        coverage=coverage.model_dump(mode="json"),
    )
    fact_checks = [
        check for check in ai_evidence["checks"] if check["id"] not in {"fit"}
    ]
    synthesis = SynthesisStatus(
        status=SynthesisStatusCode.SKIPPED,
        model=None,
        message="OpenAI synthesis was skipped; deterministic profile was used.",
        reason_code=(
            "insufficient_evidence"
            if len(fact_checks) < 2
            else "not_configured"
            if not os.getenv("OPENAI_API_KEY")
            else None
        ),
        prompt_version=PROMPT_VERSION,
        evidence_count=len(fact_checks),
    )
    profile: NeighborhoodProfile = fallback_profile
    if len(fact_checks) >= 2:
        try:
            result = await synthesizer(
                place_label=place.label,
                evidence=ai_evidence,
                caveats=confidence.caveats,
            )
        except Exception:
            logger.exception(
                "OpenAI synthesis failed; using deterministic fallback profile."
            )
            synthesis = SynthesisStatus(
                status=SynthesisStatusCode.FALLBACK,
                model=model_name,
                message="AI narrative generation failed; deterministic copy was used.",
                reason_code="provider_error",
                prompt_version=PROMPT_VERSION,
                evidence_count=len(fact_checks),
            )
        else:
            profile, synthesis = _apply_synthesis_result(
                result=result,
                fallback_profile=fallback_profile,
                model_name=model_name,
                evidence_count=len(fact_checks),
            )
    profile = profile.model_copy(
        update={
            "vibe_scores": fallback_profile.vibe_scores,
            "who_lives_here": fallback_profile.who_lives_here,
            "transit_context": fallback_profile.transit_context,
            "cycling_context": fallback_profile.cycling_context,
            "trajectory": None,
            "provenance": provenance,
        }
    )
    evidence_checks.append(synthesis_check(synthesis))
    return AnalyzeResponse(
        place=place,
        geography=geography,
        profile=profile,
        fit=fit,
        confidence=confidence,
        source_statuses=statuses,
        synthesis=synthesis,
        evidence_checks=evidence_checks,
        analysis_lens=lens,
        coverage=coverage,
        analysis_version=ANALYSIS_VERSION,
        snapshot_id=snapshot.get("snapshot_id") if snapshot["ready"] else None,
    )


def _build_ai_evidence(
    *,
    checks: list[Any],
    source_data: dict[SourceName, dict[str, Any]],
    lens: AnalysisLensSnapshot,
    fit: Any,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    allowed_fields = {
        SourceName.ACCESS: (
            "walkability",
            "daily_needs",
            "food_social",
            "parks_outdoors",
            "nearby_categories",
        ),
        SourceName.CENSUS: (
            "population_density",
            "median_renter_shelter_cost",
            "renter_cost_burden_percent",
            "census_year",
        ),
        SourceName.HOUSING: (
            "rent_benchmark",
            "affordability",
            "vacancy_rate",
            "geographic_scope",
            "edition",
        ),
        SourceName.LOCAL: (
            "neighbourhood_name",
            "population_density",
            "median_renter_shelter_cost",
            "renter_cost_burden_percent",
            "parks_count",
            "community_amenities_count",
        ),
        SourceName.TRANSIT: (
            "score",
            "scheduled_departures_per_hour",
            "nearby_route_count",
            "nearby_stop_count",
            "nearby_routes",
            "agencies",
            "nearest_stop_distance_m",
            "rapid_or_regional_access",
            "service_date",
        ),
        SourceName.CYCLING: (
            "score",
            "protected_network_km",
            "total_network_km",
            "bike_share_stations",
        ),
    }
    facts_by_check = {
        "access": _allowed_source_values(
            source_data.get(SourceName.ACCESS, {}), allowed_fields[SourceName.ACCESS]
        ),
        "census": _allowed_source_values(
            source_data.get(SourceName.CENSUS, {}), allowed_fields[SourceName.CENSUS]
        ),
        "rent": _allowed_source_values(
            source_data.get(SourceName.HOUSING, {}), allowed_fields[SourceName.HOUSING]
        ),
        "local": _allowed_source_values(
            source_data.get(SourceName.LOCAL, {}), allowed_fields[SourceName.LOCAL]
        ),
        "transit": _allowed_source_values(
            source_data.get(SourceName.TRANSIT, {}), allowed_fields[SourceName.TRANSIT]
        ),
        "cycling": _allowed_source_values(
            source_data.get(SourceName.CYCLING, {}), allowed_fields[SourceName.CYCLING]
        ),
        "fit": fit.model_dump(mode="json") if fit is not None else {},
    }
    eligible_states = {"supported", "fallback", "stale"}
    serialized_checks = []
    for check in checks:
        item = check.model_dump(mode="json")
        if item["status"] not in eligible_states:
            continue
        facts = facts_by_check.get(item["id"], {})
        if not facts:
            continue
        serialized_checks.append({**item, "facts": facts})
    return {
        "prompt_version": PROMPT_VERSION,
        "lens": lens.model_dump(mode="json"),
        "fit": fit.model_dump(mode="json") if fit is not None else None,
        "coverage": coverage,
        "checks": serialized_checks,
    }


def _allowed_source_values(
    data: dict[str, Any], fields: tuple[str, ...]
) -> dict[str, Any]:
    return {field: data[field] for field in fields if data.get(field) is not None}


def _apply_synthesis_result(
    *,
    result: Any,
    fallback_profile: NeighborhoodProfile,
    model_name: str,
    evidence_count: int,
) -> tuple[NeighborhoodProfile, SynthesisStatus]:
    if result is None:
        return fallback_profile, SynthesisStatus(
            status=SynthesisStatusCode.SKIPPED,
            model=None,
            message="AI narrative was not configured; deterministic copy was used.",
            reason_code="not_configured"
            if not os.getenv("OPENAI_API_KEY")
            else "no_output",
            prompt_version=PROMPT_VERSION,
            evidence_count=evidence_count,
        )
    if isinstance(result, SynthesizedProfileResult):
        generated = result.profile
        accepted = result.accepted_claim_count
        rejected = result.rejected_claim_count
        duration_ms = result.duration_ms
        rejected_sections = result.rejected_sections
    elif isinstance(result, NeighborhoodProfile):
        generated = result
        accepted = 1 + len(result.honest_pros) + len(result.honest_cons)
        rejected = 0
        duration_ms = None
        rejected_sections = ()
    else:
        return fallback_profile, SynthesisStatus(
            status=SynthesisStatusCode.FALLBACK,
            model=model_name,
            message="AI returned an invalid narrative; deterministic copy was used.",
            reason_code="invalid_output",
            prompt_version=PROMPT_VERSION,
            evidence_count=evidence_count,
        )
    if accepted == 0:
        return fallback_profile, SynthesisStatus(
            status=SynthesisStatusCode.FALLBACK,
            model=model_name,
            message="AI claims did not pass grounding checks; deterministic copy was used.",
            reason_code="grounding_rejected",
            prompt_version=PROMPT_VERSION,
            evidence_count=evidence_count,
            accepted_claim_count=0,
            rejected_claim_count=rejected,
            duration_ms=duration_ms,
        )
    merged = generated.model_copy(
        update={
            "overview": (
                fallback_profile.overview
                if "overview" in rejected_sections or not generated.overview
                else generated.overview
            ),
            "honest_pros": _replace_rejected_claims(
                generated.honest_pros,
                fallback_profile.honest_pros,
                rejected_sections.count("pro"),
            ),
            "honest_cons": _replace_rejected_claims(
                generated.honest_cons,
                fallback_profile.honest_cons,
                rejected_sections.count("con"),
            ),
        }
    )
    status_code = SynthesisStatusCode.PARTIAL if rejected else SynthesisStatusCode.USED
    return merged, SynthesisStatus(
        status=status_code,
        model=model_name,
        message=(
            "AI narrative was partially grounded; rejected claims were replaced."
            if rejected
            else "AI narrative was generated from validated evidence."
        ),
        reason_code="partial_grounding" if rejected else None,
        prompt_version=PROMPT_VERSION,
        evidence_count=evidence_count,
        accepted_claim_count=accepted,
        rejected_claim_count=rejected,
        duration_ms=duration_ms,
    )


def _replace_rejected_claims(
    accepted: list[str],
    deterministic: list[str],
    rejected_count: int,
) -> list[str]:
    output = list(accepted)
    for claim in deterministic:
        if rejected_count <= 0 or len(output) >= 3:
            break
        if claim not in output:
            output.append(claim)
            rejected_count -= 1
    return output or deterministic[:3]


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
                message=(
                    "Bundled snapshot is not readable by the backend process."
                    if "database" in str(exc).casefold()
                    else f"{source.value} could not be loaded ({type(exc).__name__})."
                ),
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
                edition=source_result.edition,
                scope=source_result.scope,
                source_url=source_result.source_url,
                stale=source_result.stale,
            ),
            {},
        )

    return (
        SourceStatus(
            source=source,
            status=SourceStatusCode.SUCCESS,
            message=source_result.message or f"{source.value} data returned.",
            updated_at=source_result.updated_at,
            edition=source_result.edition,
            scope=source_result.scope,
            source_url=source_result.source_url,
            stale=source_result.stale,
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


def _build_profile(
    place: Place, source_data: dict[SourceName, dict[str, Any]]
) -> NeighborhoodProfile:
    census = source_data.get(SourceName.CENSUS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    local = source_data.get(SourceName.LOCAL, {})
    transit = source_data.get(SourceName.TRANSIT, {})
    cycling = source_data.get(SourceName.CYCLING, {})

    scores = resolve_vibe_scores(source_data)
    label = place.neighborhood or place.label

    return NeighborhoodProfile(
        overview=f"{label} profile is based on currently available source signals.",
        vibe_scores=scores,
        who_lives_here=WhoLivesHere(
            median_age=census.get("median_age"),
            median_household_income=census.get("median_household_income"),
            population_density=(
                local.get("population_density") or census.get("population_density")
            ),
            population_trend=census.get("population_trend"),
            median_renter_shelter_cost=(
                local.get("median_renter_shelter_cost")
                or census.get("median_renter_shelter_cost")
                or housing.get("median_renter_shelter_cost")
            ),
            renter_cost_burden_percent=(
                local.get("renter_cost_burden_percent")
                or census.get("renter_cost_burden_percent")
            ),
            regional_average_two_bedroom_rent=housing.get("average_two_bedroom_rent"),
            rental_vacancy_rate=housing.get("vacancy_rate"),
            rent_geographic_scope=housing.get("geographic_scope"),
            rent_edition=housing.get("edition"),
            context_year=local.get("profile_year") or census.get("census_year"),
            rent_benchmark=housing.get("rent_benchmark"),
        ),
        honest_pros=_build_honest_pros(local),
        honest_cons=_build_honest_cons(local),
        trajectory=None,
        transit_context=(
            {
                "scheduled_departures_per_hour": transit.get(
                    "scheduled_departures_per_hour", 0
                ),
                "nearby_route_count": transit.get("nearby_route_count", 0),
                "nearby_stop_count": transit.get("nearby_stop_count"),
                "nearby_routes": transit.get("nearby_routes", []),
                "agencies": transit.get("agencies", []),
                "nearest_stop_distance_m": transit.get("nearest_stop_distance_m"),
                "rapid_or_regional_access": transit.get(
                    "rapid_or_regional_access", False
                ),
                "service_date": transit.get("service_date"),
                "scope": transit.get("scope", "GTA core transit agencies"),
                "edition": transit.get("edition", "Bundled GTA snapshot"),
                "fallback": False,
            }
            if transit.get("score") is not None
            else _osm_transit_fallback(source_data.get(SourceName.ACCESS, {}))
        ),
        cycling_context=(
            {
                "protected_network_km": cycling.get("protected_network_km", 0),
                "total_network_km": cycling.get("total_network_km", 0),
                "bike_share_stations": cycling.get("bike_share_stations", 0),
                "scope": cycling.get("scope", "City of Toronto"),
                "edition": cycling.get("edition", "Bundled GTA snapshot"),
            }
            if cycling.get("score") is not None
            else None
        ),
    )


def _successful_housing_status(data: dict[str, Any]) -> SourceStatus:
    return SourceStatus(
        source=SourceName.HOUSING,
        status=SourceStatusCode.SUCCESS,
        message="CMHC benchmark joined to the Statistics Canada census subdivision.",
        updated_at=str(data.get("reference_year") or "2025"),
        edition=str(data.get("edition") or "CMHC 2025 Rental Market Report"),
        scope=str(data.get("geographic_scope") or "GTA census subdivision"),
        source_url=data.get("source_url"),
        stale=False,
    )


def _osm_transit_fallback(access: dict[str, Any]) -> dict[str, Any] | None:
    categories = access.get("nearby_categories", {})
    stop_count = categories.get("transit") if isinstance(categories, dict) else None
    if access.get("transit_access") is None or not isinstance(stop_count, int):
        return None
    return {
        "scheduled_departures_per_hour": None,
        "nearby_route_count": 0,
        "nearby_stop_count": stop_count,
        "nearby_routes": [],
        "agencies": ["OpenStreetMap"],
        "nearest_stop_distance_m": None,
        "rapid_or_regional_access": False,
        "service_date": None,
        "scope": "Nearby OSM transit-stop fallback",
        "edition": "Live OpenStreetMap proximity query",
        "fallback": True,
    }


def _build_honest_pros(local: dict[str, Any]) -> list[str]:
    pros = ["Only supported, source-backed signals are shown."]
    parks_count = _int_from(local, "parks_count")
    amenities_count = _int_from(local, "community_amenities_count")
    if parks_count or amenities_count:
        pros.append(
            f"Toronto local open data found {parks_count} nearby parks and "
            f"{amenities_count} community amenity signals."
        )
    return pros


def _build_honest_cons(local: dict[str, Any]) -> list[str]:
    return [
        "Signals marked unavailable are excluded from the fit score rather than estimated."
    ]


def _int_from(data: dict[str, Any], key: str) -> int:
    raw = data.get(key, 0)
    return raw if isinstance(raw, int) else 0


def _safe_exception_message(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    if len(message) > 220:
        message = f"{message[:217]}..."
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__
