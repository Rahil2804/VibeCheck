from datetime import UTC, datetime, timedelta


FRESHNESS_STALE_DAYS = 7


def freshness_state(timestamp: str | None, *, now: datetime | None = None) -> str:
    if not timestamp:
        return "unknown"

    generated_at = _parse_timestamp(timestamp)
    if generated_at is None:
        return "unknown"

    current_time = now or datetime.now(UTC)
    return (
        "stale"
        if current_time - generated_at >= timedelta(days=FRESHNESS_STALE_DAYS)
        else "fresh"
    )


def is_stale(timestamp: str | None, *, now: datetime | None = None) -> bool:
    return freshness_state(timestamp, now=now) == "stale"


def _parse_timestamp(timestamp: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
