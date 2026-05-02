import os
from typing import Any

from openai import AsyncOpenAI

from backend.models import NeighborhoodProfile


class SynthesizerUnavailable(RuntimeError):
    """Raised when OpenAI synthesis was requested but could not produce a profile."""


SYSTEM_PROMPT = """You create honest neighborhood profiles from supplied source data only.
Use only the supplied normalized data.
Mark uncertainty clearly.
Do not make unsupported safety or crime claims.
Do not recommend based on protected classes or protected-class proxies.
Return a schema-valid NeighborhoodProfile."""


def parse_profile_payload(payload: dict[str, Any]) -> NeighborhoodProfile:
    return NeighborhoodProfile.model_validate(payload)


async def synthesize_profile(
    place_label: str,
    source_data: dict[str, Any],
    caveats: list[str],
    client: AsyncOpenAI | Any | None = None,
) -> NeighborhoodProfile | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None

    openai_client = client or AsyncOpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        response = await openai_client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Place: {place_label}\n"
                        f"Source data: {source_data}\n"
                        f"Caveats: {caveats}"
                    ),
                },
            ],
            text_format=NeighborhoodProfile,
        )
    except Exception as exc:
        raise SynthesizerUnavailable(str(exc)) from exc

    parsed = getattr(response, "output_parsed", None)
    if isinstance(parsed, NeighborhoodProfile):
        return parsed
    if isinstance(parsed, dict):
        return parse_profile_payload(parsed)
    raise SynthesizerUnavailable("OpenAI response did not include a parsed NeighborhoodProfile.")
