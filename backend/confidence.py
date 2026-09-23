from backend.models import (
    Confidence,
    ConfidenceLevel,
    EvidenceCheck,
    EvidenceCheckStatus,
    SourceName,
    SourceStatus,
    SourceStatusCode,
)

ACTIVE_SOURCES = [
    SourceName.CENSUS,
    SourceName.HOUSING,
    SourceName.ACCESS,
    SourceName.LOCAL,
    SourceName.TRANSIT,
    SourceName.CYCLING,
    SourceName.COLLISIONS,
    SourceName.BUILDING,
]


def build_confidence(
    statuses: list[SourceStatus],
    supported_signals: list[str] | None = None,
    evidence_checks: list[EvidenceCheck] | None = None,
) -> Confidence:
    status_by_source = {status.source: status for status in statuses}
    available = [
        source.value
        for source in ACTIVE_SOURCES
        if status_by_source.get(source)
        and status_by_source[source].status == SourceStatusCode.SUCCESS
    ]
    missing = [
        source.value
        for source in ACTIVE_SOURCES
        if not status_by_source.get(source)
        or status_by_source[source].status != SourceStatusCode.SUCCESS
    ]
    if evidence_checks is not None:
        source_checks = [
            check for check in evidence_checks if check.source in ACTIVE_SOURCES
        ]
        weighted_count = sum(
            1
            if check.status == EvidenceCheckStatus.SUPPORTED
            else 0.5
            if check.status in {EvidenceCheckStatus.FALLBACK, EvidenceCheckStatus.STALE}
            else 0
            for check in source_checks
        )
        supported_sources = {
            check.source
            for check in source_checks
            if check.status
            in {
                EvidenceCheckStatus.SUPPORTED,
                EvidenceCheckStatus.FALLBACK,
                EvidenceCheckStatus.STALE,
            }
        }
        if weighted_count >= 5 and len(supported_sources) >= 3:
            level = ConfidenceLevel.HIGH
        elif weighted_count >= 3 and len(supported_sources) >= 2:
            level = ConfidenceLevel.MEDIUM
        elif weighted_count >= 1:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.NONE
    else:
        signal_count = (
            len(supported_signals) if supported_signals is not None else len(available)
        )
        if signal_count >= 5:
            level = ConfidenceLevel.HIGH
        elif signal_count >= 3:
            level = ConfidenceLevel.MEDIUM
        elif signal_count >= 1:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.NONE

    caveats: list[str] = []
    if level == ConfidenceLevel.NONE:
        caveats.append(
            "Not enough supported signals were available for a reliable profile."
        )
    elif level == ConfidenceLevel.LOW:
        caveats.append(
            "Supported evidence is thin, so treat this profile as directional."
        )
    if missing:
        caveats.append(f"Missing or unavailable active sources: {', '.join(missing)}.")
    if SourceName.ACCESS.value in available:
        caveats.append(
            "OSM access scores are transparent proximity signals, not travel-time scores."
        )
    transit_status = status_by_source.get(SourceName.TRANSIT)
    if transit_status and transit_status.status != SourceStatusCode.SUCCESS:
        caveats.append(
            "Any transit score shown is an OSM fallback, not scheduled-service evidence."
        )
    if evidence_checks is not None:
        stale_labels = [
            check.label
            for check in evidence_checks
            if check.status == EvidenceCheckStatus.STALE
        ]
        fallback_labels = [
            check.label
            for check in evidence_checks
            if check.status == EvidenceCheckStatus.FALLBACK
        ]
        if stale_labels:
            caveats.append("Stale evidence: " + ", ".join(stale_labels) + ".")
        if fallback_labels:
            caveats.append("Fallback evidence: " + ", ".join(fallback_labels) + ".")
    return Confidence(
        level=level,
        available_sources=available,
        missing_sources=missing,
        caveats=caveats,
    )
