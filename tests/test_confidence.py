from backend.confidence import build_confidence
from backend.models import SourceName, SourceStatus, SourceStatusCode


def _status(source: SourceName, code: SourceStatusCode) -> SourceStatus:
    return SourceStatus(source=source, status=code, message=f"{source.value} {code.value}")


def test_confidence_is_high_with_four_meaningful_sources():
    confidence = build_confidence(
        [
            _status(SourceName.MAPBOX, SourceStatusCode.SUCCESS),
            _status(SourceName.CENSUS, SourceStatusCode.SUCCESS),
            _status(SourceName.HOUSING, SourceStatusCode.SUCCESS),
            _status(SourceName.REDDIT, SourceStatusCode.SUCCESS),
            _status(SourceName.ACCESS, SourceStatusCode.SUCCESS),
        ]
    )

    assert confidence.level == "high"
    assert confidence.available_sources == ["census", "housing", "reddit", "access"]
    assert confidence.missing_sources == []


def test_confidence_is_medium_with_three_meaningful_sources():
    confidence = build_confidence(
        [
            _status(SourceName.MAPBOX, SourceStatusCode.SUCCESS),
            _status(SourceName.CENSUS, SourceStatusCode.SUCCESS),
            _status(SourceName.HOUSING, SourceStatusCode.SUCCESS),
            _status(SourceName.ACCESS, SourceStatusCode.SUCCESS),
            _status(SourceName.REDDIT, SourceStatusCode.ERROR),
        ]
    )

    assert confidence.level == "medium"
    assert "reddit" in confidence.missing_sources


def test_confidence_is_low_with_one_or_two_meaningful_sources():
    confidence = build_confidence(
        [
            _status(SourceName.MAPBOX, SourceStatusCode.SUCCESS),
            _status(SourceName.CENSUS, SourceStatusCode.SUCCESS),
            _status(SourceName.HOUSING, SourceStatusCode.EMPTY),
            _status(SourceName.REDDIT, SourceStatusCode.ERROR),
            _status(SourceName.ACCESS, SourceStatusCode.SUCCESS),
        ]
    )

    assert confidence.level == "low"
    assert any("thin" in caveat.lower() for caveat in confidence.caveats)


def test_confidence_no_profile_when_only_place_resolves():
    confidence = build_confidence(
        [
            _status(SourceName.MAPBOX, SourceStatusCode.SUCCESS),
            _status(SourceName.CENSUS, SourceStatusCode.ERROR),
            _status(SourceName.HOUSING, SourceStatusCode.EMPTY),
            _status(SourceName.REDDIT, SourceStatusCode.ERROR),
            _status(SourceName.ACCESS, SourceStatusCode.ERROR),
        ]
    )

    assert confidence.level == "none"
    assert "census" in confidence.missing_sources
    assert any("not enough" in caveat.lower() for caveat in confidence.caveats)
