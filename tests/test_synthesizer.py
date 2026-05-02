import pytest
from pydantic import ValidationError

from backend.models import NeighborhoodProfile
from backend.synthesizer import SynthesizerUnavailable, parse_profile_payload, synthesize_profile


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
