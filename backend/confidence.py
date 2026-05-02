from backend.models import Confidence, ConfidenceLevel, SourceName, SourceStatus, SourceStatusCode


MEANINGFUL_SOURCES = [
    SourceName.CENSUS,
    SourceName.HOUSING,
    SourceName.REDDIT,
    SourceName.ACCESS,
]


def build_confidence(statuses: list[SourceStatus]) -> Confidence:
    status_by_source = {status.source: status for status in statuses}
    available = [
        source.value
        for source in MEANINGFUL_SOURCES
        if status_by_source.get(source) and status_by_source[source].status == SourceStatusCode.SUCCESS
    ]
    missing = [
        source.value
        for source in MEANINGFUL_SOURCES
        if not status_by_source.get(source) or status_by_source[source].status != SourceStatusCode.SUCCESS
    ]

    count = len(available)
    if count >= 4:
        level = ConfidenceLevel.HIGH
    elif count == 3:
        level = ConfidenceLevel.MEDIUM
    elif count >= 1:
        level = ConfidenceLevel.LOW
    else:
        level = ConfidenceLevel.NONE

    caveats: list[str] = []
    if level == ConfidenceLevel.NONE:
        caveats.append("Not enough source data was available to build a reliable neighborhood profile.")
    elif level == ConfidenceLevel.LOW:
        caveats.append("Source data is thin, so treat this profile as directional rather than definitive.")

    if missing:
        caveats.append(f"Missing or unavailable sources: {', '.join(missing)}.")
    if SourceName.ACCESS.value in available:
        caveats.append(
            "Daily Needs Access is a VibeCheck score based on nearby amenities and transparent sub-scores."
        )

    return Confidence(
        level=level,
        available_sources=available,
        missing_sources=missing,
        caveats=caveats,
    )
