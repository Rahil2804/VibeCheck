import pytest
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from backend.models import NeighborhoodProfile
from backend.synthesizer import (
    SynthesizedProfilePayload,
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
    captured = {}

    parsed_payload = SynthesizedProfilePayload(
        overview="Synthesized overview.",
        vibe_scores={
            "walkability": 81,
            "transit_access": 67,
            "affordability": 45,
            "quiet": 58,
            "social_scene": 73,
        },
        who_lives_here={
            "median_age": None,
            "median_household_income": None,
            "population_density": None,
            "population_trend": None,
        },
        honest_pros=["Good access signals."],
        honest_cons=["Affordability is mixed."],
        trajectory={
            "direction": "uncertain",
            "summary": "Trajectory is uncertain from current MVP sources.",
        },
    )

    class Response:
        output_parsed = parsed_payload

    class CapturingClient:
        class responses:
            @staticmethod
            async def parse(**kwargs):
                captured.update(kwargs)
                return Response()

    profile = await synthesize_profile(
        place_label="East Austin",
        source_data={"access": {"walkability": 82}},
        caveats=[],
        client=CapturingClient(),
    )

    assert captured["text_format"] is SynthesizedProfilePayload
    assert isinstance(profile, NeighborhoodProfile)
    assert profile.overview == "Synthesized overview."
    assert profile.provenance == {}


@pytest.mark.asyncio
async def test_synthesize_profile_converts_client_error_to_unavailable(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

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
