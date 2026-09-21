from typing import Any

from backend.models import (
    ProfileProvenance,
    ProvenanceItem,
    ProvenanceSupport,
    SourceName,
    SourceStatus,
    SourceStatusCode,
)
from backend.score_signals import resolve_score_support


def build_profile_provenance(
    source_data: dict[SourceName, dict[str, Any]],
    statuses: list[SourceStatus],
) -> ProfileProvenance:
    status_by_source = {status.source: status for status in statuses}
    score_support = resolve_score_support(source_data)
    items = [_overview_item(source_data, status_by_source)]
    score_definitions = (
        ("walkability", "Walkability score", SourceName.ACCESS),
        ("transit_access", "Scheduled transit access score", SourceName.TRANSIT),
        ("cycling_access", "Cycling access score", SourceName.CYCLING),
        ("affordability", "Affordability score", SourceName.HOUSING),
        ("parks_outdoors", "Parks and outdoors score", SourceName.ACCESS),
        ("daily_needs", "Daily needs score", SourceName.ACCESS),
        ("dining_activity", "Dining and activity score", SourceName.ACCESS),
    )
    items.extend(
        _score_item(
            claim_id=f"vibe.{key}",
            label=label,
            score_key=key,
            fallback_sources=[source],
            score_support=score_support,
            status_by_source=status_by_source,
        )
        for key, label, source in score_definitions
    )
    field_definitions = (
        (
            "context.population_density",
            "Population density",
            SourceName.CENSUS,
            "population_density",
        ),
        (
            "context.median_renter_shelter_cost",
            "Median renter shelter cost",
            SourceName.CENSUS,
            "median_renter_shelter_cost",
        ),
        (
            "context.regional_average_two_bedroom_rent",
            "Regional average two-bedroom rent",
            SourceName.HOUSING,
            "average_two_bedroom_rent",
        ),
        (
            "context.rent_benchmark",
            "Unit-matched purpose-built rent benchmark",
            SourceName.HOUSING,
            "rent_benchmark",
        ),
        (
            "context.collision_history",
            "Reported collision history within 1 km",
            SourceName.COLLISIONS,
            "collision_context",
        ),
        (
            "context.building_record",
            "Exact-address RentSafeTO building record",
            SourceName.BUILDING,
            "building_context",
        ),
    )
    items.extend(
        _field_item(
            claim_id=claim_id,
            label=label,
            source=source,
            source_field=field,
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.DIRECT,
        )
        for claim_id, label, source, field in field_definitions
    )
    items.append(_local_amenities_item(source_data, status_by_source))
    return ProfileProvenance(items=items)


def _overview_item(
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    tracked_sources = (
        SourceName.ACCESS,
        SourceName.TRANSIT,
        SourceName.CYCLING,
        SourceName.HOUSING,
        SourceName.CENSUS,
        SourceName.LOCAL,
        SourceName.COLLISIONS,
        SourceName.BUILDING,
    )
    available = [source for source in tracked_sources if _has_data(source_data, source)]
    if available:
        names = ", ".join(source.value for source in available)
        return ProvenanceItem(
            claim_id="overview",
            label="Overview",
            summary=f"Overview is generated from available normalized {names} signals.",
            support=ProvenanceSupport.INFERRED,
            sources=available,
            source_fields=[],
        )
    summaries = [
        _status_summary(source, status_by_source) for source in tracked_sources
    ]
    return ProvenanceItem(
        claim_id="overview",
        label="Overview",
        summary=f"Overview has no strong source support yet; {'; '.join(summaries)}.",
        support=ProvenanceSupport.UNAVAILABLE,
        sources=[],
        source_fields=[],
    )


def _field_item(
    *,
    claim_id: str,
    label: str,
    source: SourceName,
    source_field: str,
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
    support: ProvenanceSupport,
) -> ProvenanceItem:
    full_field = f"{source.value}.{source_field}"
    if source_data.get(source, {}).get(source_field) is not None:
        return ProvenanceItem(
            claim_id=claim_id,
            label=label,
            summary=f"Based on normalized {full_field} signal.",
            support=support,
            sources=[source],
            source_fields=[full_field],
        )
    return ProvenanceItem(
        claim_id=claim_id,
        label=label,
        summary=f"{label} is unavailable because {_status_summary(source, status_by_source)}.",
        support=ProvenanceSupport.UNAVAILABLE,
        sources=[source],
        source_fields=[],
    )


def _score_item(
    *,
    claim_id: str,
    label: str,
    score_key: str,
    fallback_sources: list[SourceName],
    score_support: dict[str, list[str]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    fields = score_support.get(score_key, [])
    if fields:
        sources = _sources_from_source_fields(fields)
        qualifiers = [
            "stale" if status_by_source[source].stale else "fallback"
            for source in sources
            if source in status_by_source
            and (status_by_source[source].stale or status_by_source[source].fallback)
        ]
        qualifier = f" ({'/'.join(dict.fromkeys(qualifiers))} evidence)" if qualifiers else ""
        return ProvenanceItem(
            claim_id=claim_id,
            label=label,
            summary=f"Based on normalized {', '.join(fields)} signals{qualifier}.",
            support=ProvenanceSupport.INFERRED,
            sources=sources,
            source_fields=fields,
        )

    summaries = "; ".join(
        _status_summary(source, status_by_source) for source in fallback_sources
    )
    return ProvenanceItem(
        claim_id=claim_id,
        label=label,
        summary=f"{label} is unavailable because {summaries}.",
        support=ProvenanceSupport.UNAVAILABLE,
        sources=fallback_sources,
        source_fields=[],
    )


def _sources_from_source_fields(fields: list[str]) -> list[SourceName]:
    ordered_sources = [
        SourceName.ACCESS,
        SourceName.TRANSIT,
        SourceName.CYCLING,
        SourceName.HOUSING,
        SourceName.CENSUS,
        SourceName.LOCAL,
        SourceName.COLLISIONS,
        SourceName.BUILDING,
    ]
    present = {field.split(".", maxsplit=1)[0] for field in fields}
    return [source for source in ordered_sources if source.value in present]


def _local_amenities_item(
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    fields = ["parks_count", "community_amenities_count", "parks_outdoors"]
    present_fields = [
        f"local.{field}"
        for field in fields
        if source_data.get(SourceName.LOCAL, {}).get(field) is not None
    ]
    if present_fields:
        return ProvenanceItem(
            claim_id="local.amenities",
            label="Local parks and amenities",
            summary="Local amenities are inferred from normalized municipal parks and facility signals.",
            support=ProvenanceSupport.INFERRED,
            sources=[SourceName.LOCAL],
            source_fields=present_fields,
        )
    return ProvenanceItem(
        claim_id="local.amenities",
        label="Local parks and amenities",
        summary=(
            "Local amenities are unavailable because "
            f"{_status_summary(SourceName.LOCAL, status_by_source)}."
        ),
        support=ProvenanceSupport.UNAVAILABLE,
        sources=[SourceName.LOCAL],
        source_fields=[],
    )


def _has_data(
    source_data: dict[SourceName, dict[str, Any]], source: SourceName
) -> bool:
    return bool(source_data.get(source))


def _status_summary(
    source: SourceName, status_by_source: dict[SourceName, SourceStatus]
) -> str:
    status = status_by_source.get(source)
    if status is None:
        return f"{source.value} source is missing"
    if status.status == SourceStatusCode.SUCCESS:
        return f"{source.value} source lacks this field"
    if status.status == SourceStatusCode.ERROR:
        return f"{source.value} source errored"
    return f"{source.value} source is empty"
