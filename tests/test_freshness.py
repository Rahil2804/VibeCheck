from datetime import UTC, datetime

from backend.freshness import FRESHNESS_STALE_DAYS, freshness_state, is_stale


NOW = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)


def test_is_stale_uses_seven_day_threshold():
    assert FRESHNESS_STALE_DAYS == 7
    assert is_stale("2026-05-01T12:00:00+00:00", now=NOW) is False
    assert is_stale("2026-04-30T12:00:00+00:00", now=NOW) is True


def test_is_stale_treats_unknown_timestamp_as_not_stale():
    assert is_stale(None, now=NOW) is False
    assert is_stale("", now=NOW) is False


def test_freshness_state_reports_unknown_fresh_and_stale():
    assert freshness_state(None, now=NOW) == "unknown"
    assert freshness_state("2026-05-07T11:00:00+00:00", now=NOW) == "fresh"
    assert freshness_state("2026-04-29T12:00:00+00:00", now=NOW) == "stale"
