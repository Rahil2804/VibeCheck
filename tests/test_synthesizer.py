import pytest
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from backend.models import NeighborhoodProfile
from backend.synthesizer import (
    GroundedClaim,
    SynthesizedProfilePayload,
    SynthesizedProfileResult,
    SynthesizerUnavailable,
    parse_profile_payload,
    synthesize_profile,
)


@pytest.mark.asyncio
async def test_synthesize_profile_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = await synthesize_profile(
        place_label="East Austin",
        source_data={"access": {"walkability": 82}},
        caveats=["Reddit unavailable."],
    )

    assert result is None


@pytest.mark.asyncio
async def test_synthesize_profile_returns_none_without_explicit_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    result = await synthesize_profile(
        place_label="East Austin",
        source_data={"access": {"walkability": 82}},
        caveats=[],
    )

    assert result is None


def test_parse_profile_payload_accepts_schema_valid_profile():
    profile = parse_profile_payload(
        {
            "overview": "Walkable, mixed-signal area with some uncertainty.",
            "vibe_scores": {
                "walkability": 82,
                "transit_access": 68,
                "affordability": 42,
                "quiet": 55,
                "social_scene": 78,
            },
            "who_lives_here": {
                "median_age": 31,
                "median_household_income": 58000,
                "population_density": 5200,
                "population_trend": "growing",
            },
            "honest_pros": ["Errands appear accessible."],
            "honest_cons": ["Affordability signals are mixed."],
            "trajectory": {
                "direction": "uncertain",
                "summary": "Trajectory is uncertain from current MVP sources.",
            },
        }
    )

    assert isinstance(profile, NeighborhoodProfile)
    assert profile.vibe_scores.walkability == 82


def test_parse_profile_payload_rejects_malformed_profile():
    with pytest.raises(ValidationError):
        parse_profile_payload({"overview": "Missing required fields."})


def test_synthesized_profile_payload_schema_has_no_open_ended_objects():
    schema = to_strict_json_schema(SynthesizedProfilePayload)

    def assert_no_open_objects(node):
        if isinstance(node, dict):
            assert node.get("additionalProperties") is not True
            for value in node.values():
                assert_no_open_objects(value)
        elif isinstance(node, list):
            for value in node:
                assert_no_open_objects(value)

    assert_no_open_objects(schema)


@pytest.mark.asyncio
async def test_synthesize_profile_uses_openai_safe_payload_schema(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    captured = {}

    parsed_payload = SynthesizedProfilePayload(
        overview=GroundedClaim(
            text="Access evidence is available.", evidence_ids=["access"]
        ),
        honest_pros=[
            GroundedClaim(text="Access is supported.", evidence_ids=["access"])
        ],
        honest_cons=[GroundedClaim(text="Rent is unavailable.", evidence_ids=["rent"])],
    )

    class Response:
        output_parsed = parsed_payload

    class CapturingClient:
        class responses:
            @staticmethod
            async def parse(**kwargs):
                captured.update(kwargs)
                return Response()

    result = await synthesize_profile(
        place_label="East Austin",
        evidence={
            "checks": [
                {"id": "access", "status": "supported", "facts": {"walkability": 82}},
                {
                    "id": "rent",
                    "status": "supported",
                    "facts": {"availability": "missing"},
                },
            ]
        },
        caveats=[],
        client=CapturingClient(),
    )

    assert captured["text_format"] is SynthesizedProfilePayload
    assert captured["store"] is False
    assert captured["max_output_tokens"] == 700
    assert isinstance(result, SynthesizedProfileResult)
    assert result.profile.overview == "Access evidence is available."
    assert result.profile.narrative_citations[0].evidence_check_ids == ["access"]


@pytest.mark.asyncio
async def test_synthesize_profile_converts_client_error_to_unavailable(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    class FailingClient:
        class responses:
            @staticmethod
            async def parse(**_kwargs):
                raise RuntimeError("model unavailable")

    with pytest.raises(SynthesizerUnavailable):
        await synthesize_profile(
            place_label="East Austin",
            source_data={"access": {"walkability": 82}},
            caveats=[],
            client=FailingClient(),
        )


@pytest.mark.asyncio
async def test_synthesize_profile_rejects_unsupported_and_forbidden_claims(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    parsed_payload = SynthesizedProfilePayload(
        overview=GroundedClaim(
            text="Everyday access evidence is available.", evidence_ids=["access"]
        ),
        honest_pros=[
            GroundedClaim(text="Crime is low.", evidence_ids=["access"]),
            GroundedClaim(text="Ideal for families.", evidence_ids=["access"]),
            GroundedClaim(
                text="Collision history means future risk is high.",
                evidence_ids=["access"],
            ),
        ],
        honest_cons=[
            GroundedClaim(text="Rent is uncertain.", evidence_ids=["missing"]),
            GroundedClaim(
                text="The mapped lanes make cycling comfortable.",
                evidence_ids=["access"],
            ),
            GroundedClaim(
                text="This area is routable by bicycle.", evidence_ids=["access"]
            ),
        ],
    )

    class Response:
        output_parsed = parsed_payload

    class CapturingClient:
        class responses:
            @staticmethod
            async def parse(**_kwargs):
                return Response()

    result = await synthesize_profile(
        place_label="Toronto",
        evidence={
            "checks": [
                {"id": "access", "status": "supported", "facts": {"daily_needs": 72}}
            ]
        },
        caveats=[],
        client=CapturingClient(),
    )

    assert result is not None
    assert result.accepted_claim_count == 1
    assert result.rejected_claim_count == 6
    assert result.rejected_sections == (
        "pro",
        "pro",
        "pro",
        "con",
        "con",
        "con",
    )
    assert result.profile.honest_pros == []
    assert result.profile.honest_cons == []
