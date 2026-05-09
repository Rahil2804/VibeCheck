from typing import Any

from backend.models import (
    ProfileProvenance,
    ProvenanceItem,
    ProvenanceSupport,
    SourceName,
    SourceStatus,
    SourceStatusCode,
)


def build_profile_provenance(
    source_data: dict[SourceName, dict[str, Any]],
    statuses: list[SourceStatus],
) -> ProfileProvenance:
    status_by_source = {status.source: status for status in statuses}
    items = [
        _overview_item(source_data, status_by_source),
        _field_item(
            claim_id="vibe.walkability",
            label="Walkability score",
            source=SourceName.ACCESS,
            source_field="walkability",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="vibe.transit_access",
            label="Transit access score",
            source=SourceName.ACCESS,
            source_field="transit_access",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="vibe.affordability",
            label="Affordability score",
            source=SourceName.HOUSING,
            source_field="affordability",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="vibe.quiet",
            label="Quiet score",
            source=SourceName.REDDIT,
            source_field="quiet",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="vibe.social_scene",
            label="Social scene score",
            source=SourceName.REDDIT,
            source_field="social_scene",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="context.median_age",
            label="Median age",
            source=SourceName.CENSUS,
            source_field="median_age",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.DIRECT,
        ),
        _field_item(
            claim_id="context.median_household_income",
            label="Median household income",
            source=SourceName.CENSUS,
            source_field="median_household_income",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.DIRECT,
        ),
        _field_item(
            claim_id="context.population_density",
            label="Population density",
            source=SourceName.CENSUS,
            source_field="population_density",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.DIRECT,
        ),
        _local_amenities_item(source_data, status_by_source),
        _trajectory_item(source_data, status_by_source),
    ]
    return ProfileProvenance(items=items)


def _overview_item(
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    tracked_sources = (
        SourceName.ACCESS,
        SourceName.HOUSING,
        SourceName.CENSUS,
        SourceName.REDDIT,
        SourceName.LOCAL,
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
    summaries = [_status_summary(source, status_by_source) for source in tracked_sources]
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


def _trajectory_item(
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    trend_fields = [
        (SourceName.LOCAL, "development_activity"),
        (SourceName.LOCAL, "recent_permits_count"),
        (SourceName.LOCAL, "trajectory_signal"),
        (SourceName.HOUSING, "rent_trend"),
        (SourceName.REDDIT, "discussion_trend"),
    ]
    present_fields = [
        f"{source.value}.{field}"
        for source, field in trend_fields
        if source_data.get(source, {}).get(field) is not None
    ]
    if present_fields:
        return ProvenanceItem(
            claim_id="trajectory",
            label="Trajectory",
            summary="Trajectory is inferred from available local and trend signals.",
            support=ProvenanceSupport.INFERRED,
            sources=_sources_for_fields(trend_fields, present_fields),
            source_fields=present_fields,
        )
    return ProvenanceItem(
        claim_id="trajectory",
        label="Trajectory",
        summary=(
            "Trajectory is unavailable because trend fields are missing; "
            f"{_status_summary(SourceName.LOCAL, status_by_source)}; "
            f"{_status_summary(SourceName.HOUSING, status_by_source)}; "
            f"{_status_summary(SourceName.REDDIT, status_by_source)}."
        ),
        support=ProvenanceSupport.UNAVAILABLE,
        sources=[SourceName.LOCAL, SourceName.HOUSING, SourceName.REDDIT],
        source_fields=[],
    )


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


def _has_data(source_data: dict[SourceName, dict[str, Any]], source: SourceName) -> bool:
    return bool(source_data.get(source))


def _sources_for_fields(
    trend_fields: list[tuple[SourceName, str]],
    present_fields: list[str],
) -> list[SourceName]:
    sources = {
        source for source, field in trend_fields if f"{source.value}.{field}" in present_fields
    }
    return sorted(sources, key=lambda item: item.value)


def _status_summary(source: SourceName, status_by_source: dict[SourceName, SourceStatus]) -> str:
    status = status_by_source.get(source)
    if status is None:
        return f"{source.value} source is missing"
    if status.status == SourceStatusCode.SUCCESS:
        return f"{source.value} source lacks this field"
    if status.status == SourceStatusCode.ERROR:
        return f"{source.value} source errored"
    return f"{source.value} source is empty"
