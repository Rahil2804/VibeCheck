from __future__ import annotations

from typing import Any

from backend.models import (
    EvidenceCheck,
    EvidenceCheckStatus,
    FitScore,
    GeographyContext,
    NeighborhoodProfile,
    Place,
    SourceName,
    SourceStatus,
    SourceStatusCode,
    SynthesisStatus,
    SynthesisStatusCode,
)


SOURCE_CHECKS = (
    (SourceName.ACCESS, "access", "Everyday access"),
    (SourceName.CENSUS, "census", "Census context"),
    (SourceName.HOUSING, "rent", "Unit-matched rent"),
    (SourceName.LOCAL, "local", "Toronto local context"),
    (SourceName.TRANSIT, "transit", "Scheduled transit"),
    (SourceName.CYCLING, "cycling", "Cycling access"),
    (SourceName.COLLISIONS, "collisions", "Reported collision history"),
    (SourceName.BUILDING, "building", "RentSafeTO building record"),
)
SOURCE_FIELDS = {
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
        "bicycle_parking_locations",
        "network_radius_m",
        "method",
    ),
    SourceName.COLLISIONS: ("collision_context",),
    SourceName.BUILDING: ("building_context",),
}


def build_evidence_checks(
    *,
    place: Place,
    geography: GeographyContext,
    statuses: list[SourceStatus],
    profile: NeighborhoodProfile,
    fit: FitScore | None,
    snapshot: dict[str, Any],
    generic_mode: bool,
    source_data: dict[SourceName, dict[str, Any]] | None = None,
) -> list[EvidenceCheck]:
    checks = [
        EvidenceCheck(
            id="place",
            label="Place resolution",
            status=(
                EvidenceCheckStatus.SUPPORTED
                if place.coordinates is not None
                else EvidenceCheckStatus.UNAVAILABLE
            ),
            summary=(
                f"Resolved {place.label} to coordinates."
                if place.coordinates is not None
                else "The place did not resolve to coordinates."
            ),
            source=SourceName.MAPBOX,
            source_fields=["mapbox.coordinates"]
            if place.coordinates is not None
            else [],
        ),
        _snapshot_check(snapshot),
        EvidenceCheck(
            id="geography",
            label="Geography resolution",
            status=(
                EvidenceCheckStatus.SUPPORTED
                if geography.resolution != "unresolved"
                else EvidenceCheckStatus.UNAVAILABLE
            ),
            summary=_geography_summary(geography),
            scope=geography.census_subdivision_name,
            source_fields=(
                ["snapshot.census_subdivisions.geometry"]
                if geography.resolution == "bundled official boundary"
                else []
            ),
        ),
    ]
    status_by_source = {status.source: status for status in statuses}
    for source, check_id, label in SOURCE_CHECKS:
        status = status_by_source.get(source)
        check = _source_check(
            check_id,
            label,
            source,
            status,
            (source_data or {}).get(source, {}),
        )
        if (
            source == SourceName.TRANSIT
            and profile.transit_context is not None
            and profile.transit_context.fallback
        ):
            check = check.model_copy(
                update={
                    "status": EvidenceCheckStatus.FALLBACK,
                    "label": "Transit fallback",
                    "summary": "Nearby OSM stops are available, but scheduled-service evidence is unavailable.",
                    "source_fields": ["access.transit_access"],
                }
            )
        checks.append(check)
    checks.append(
        EvidenceCheck(
            id="fit",
            label="Preference fit",
            status=(
                EvidenceCheckStatus.SUPPORTED
                if fit is not None and fit.score is not None
                else EvidenceCheckStatus.UNAVAILABLE
            ),
            summary=(
                f"{len(fit.factors)} evidence-backed preference factors were evaluated."
                if fit is not None and fit.score is not None
                else "Generic mode does not calculate personal fit."
                if generic_mode
                else "No evidence-backed preference factor was available."
            ),
            source_fields=(
                list(
                    dict.fromkeys(
                        field
                        for factor in fit.factors
                        for field in factor.source_fields
                    )
                )
                if fit is not None
                else []
            ),
        )
    )
    return checks


def synthesis_check(status: SynthesisStatus) -> EvidenceCheck:
    state = {
        SynthesisStatusCode.USED: EvidenceCheckStatus.SUPPORTED,
        SynthesisStatusCode.PARTIAL: EvidenceCheckStatus.FALLBACK,
        SynthesisStatusCode.SKIPPED: EvidenceCheckStatus.UNAVAILABLE,
        SynthesisStatusCode.FALLBACK: EvidenceCheckStatus.ERROR,
    }[status.status]
    return EvidenceCheck(
        id="ai",
        label="AI narrative grounding",
        status=state,
        summary=status.message,
    )


def supported_fact_checks(checks: list[EvidenceCheck]) -> list[EvidenceCheck]:
    return [
        check
        for check in checks
        if check.id not in {"place", "snapshot", "geography", "fit", "ai"}
        and check.status
        in {
            EvidenceCheckStatus.SUPPORTED,
            EvidenceCheckStatus.FALLBACK,
            EvidenceCheckStatus.STALE,
        }
    ]


def _snapshot_check(snapshot: dict[str, Any]) -> EvidenceCheck:
    errors = snapshot.get("errors") or []
    if errors:
        state = EvidenceCheckStatus.ERROR
        summary = "The bundled GTA snapshot is unavailable to this backend process."
    elif snapshot.get("stale"):
        state = EvidenceCheckStatus.STALE
        summary = "The bundled snapshot is readable, but one or more transit feeds are expired."
    else:
        state = EvidenceCheckStatus.SUPPORTED
        summary = (
            "The bundled GTA snapshot passed readability, schema, and checksum checks."
        )
    return EvidenceCheck(
        id="snapshot",
        label="Bundled data snapshot",
        status=state,
        summary=summary,
        edition=snapshot.get("snapshot_id"),
        updated_at=snapshot.get("created_at"),
        scope=(
            "GTA transit and rent; Toronto cycling, reported collisions, "
            "and RentSafeTO buildings"
        ),
        source_fields=["snapshot.manifest", "snapshot.integrity_check"],
    )


def _geography_summary(geography: GeographyContext) -> str:
    if geography.is_toronto:
        return "Coordinates resolve inside Toronto, including former municipality labels such as East York."
    if geography.is_gta:
        return "Coordinates or place context resolve inside the Greater Toronto Area."
    return "No supported GTA geography was resolved for this place."


def _source_check(
    check_id: str,
    label: str,
    source: SourceName,
    status: SourceStatus | None,
    data: dict[str, Any],
) -> EvidenceCheck:
    if status is None:
        state = EvidenceCheckStatus.UNAVAILABLE
        summary = f"{label} was not checked."
    elif status.status == SourceStatusCode.ERROR:
        state = EvidenceCheckStatus.ERROR
        summary = f"{label} could not be loaded."
    elif status.status == SourceStatusCode.EMPTY:
        state = EvidenceCheckStatus.UNAVAILABLE
        summary = status.message
    elif status.stale:
        state = EvidenceCheckStatus.STALE
        summary = status.message
    elif status.fallback:
        state = EvidenceCheckStatus.FALLBACK
        summary = status.message
    else:
        state = EvidenceCheckStatus.SUPPORTED
        summary = status.message
    return EvidenceCheck(
        id=check_id,
        label=label,
        status=state,
        summary=summary,
        source=source,
        scope=status.scope if status else None,
        edition=status.edition if status else None,
        updated_at=status.updated_at if status else None,
        source_fields=[
            f"{source.value}.{field}"
            for field in SOURCE_FIELDS[source]
            if data.get(field) is not None
        ],
    )
