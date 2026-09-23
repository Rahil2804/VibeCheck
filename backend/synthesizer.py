from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from time import monotonic
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from backend.models import (
    NarrativeCitation,
    NeighborhoodProfile,
    VibeScores,
    WhoLivesHere,
)


class SynthesizerUnavailable(RuntimeError):
    """Raised when OpenAI synthesis was requested but could not produce a profile."""


SYSTEM_PROMPT = """You write a concise neighborhood decision brief from supplied evidence only.
Every statement must cite one or more evidence check IDs supplied in the input.
Explain the deterministic fit and preferences without changing any score or metric.
Mark stale or fallback evidence clearly. Do not infer crime, safety, protected classes,
demographics, noise, sentiment, development trajectory, schools, or unsupported facts.
Collision evidence may only be described as reported historical counts; never infer safety,
danger, causation, or future risk. RentSafeTO evidence describes the matched building's
official registration and common-area evaluation only, not units, residents, or its area.
Cycling evidence describes mapped infrastructure only; never call an area comfortable or
routable from these facts.
Return one overview, one to three pros, and one to three cons."""
PROMPT_VERSION = "grounded-neighbourhood-v1"
FORBIDDEN_CLAIM_PATTERN = re.compile(
    r"\b(crime|safe(?:ty)?|dangerous|racial|race|ethnic|demographic|religio\w*|"
    r"disab\w*|famil(?:y|ies|ial)|national origin|gender|sex(?:ual)?|income|"
    r"noise|quiet|sentiment|gentrif\w*|development trajectory|school ranking|"
    r"risk\w*|caus(?:e|es|ed|ing|ation|al)\w*|neighbou?rhood quality|"
    r"resident characteristics|comfort\w*|routab\w*)\b",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\b")


class GroundedClaim(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    evidence_ids: list[str] = Field(min_length=1, max_length=5)


class SynthesizedProfilePayload(BaseModel):
    overview: GroundedClaim
    honest_pros: list[GroundedClaim] = Field(min_length=1, max_length=3)
    honest_cons: list[GroundedClaim] = Field(min_length=1, max_length=3)


@dataclass(frozen=True)
class SynthesizedProfileResult:
    profile: NeighborhoodProfile
    accepted_claim_count: int
    rejected_claim_count: int
    duration_ms: int
    rejected_sections: tuple[str, ...] = ()


def parse_profile_payload(payload: dict[str, Any]) -> NeighborhoodProfile:
    """Retain the legacy parser for old fixtures and saved payloads."""
    return NeighborhoodProfile.model_validate(payload)


async def synthesize_profile(
    place_label: str,
    evidence: dict[str, Any] | None = None,
    caveats: list[str] | None = None,
    client: AsyncOpenAI | Any | None = None,
    source_data: dict[str, Any] | None = None,
) -> SynthesizedProfileResult | None:
    model = get_openai_model()
    if not os.getenv("OPENAI_API_KEY", "").strip() or model is None:
        return None

    evidence_payload = evidence or {
        "checks": [],
        "legacy_source_data": source_data or {},
    }
    openai_client = client or AsyncOpenAI(timeout=12, max_retries=1)
    started = monotonic()

    try:
        response = await openai_client.responses.parse(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=json.dumps(
                {
                    "place": place_label,
                    "evidence": evidence_payload,
                    "caveats": caveats or [],
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            text_format=SynthesizedProfilePayload,
            store=False,
            max_output_tokens=700,
        )
    except Exception as exc:
        raise SynthesizerUnavailable(type(exc).__name__) from exc

    parsed = getattr(response, "output_parsed", None)
    if isinstance(parsed, dict):
        parsed = SynthesizedProfilePayload.model_validate(parsed)
    if not isinstance(parsed, SynthesizedProfilePayload):
        raise SynthesizerUnavailable("invalid_structured_output")

    profile, accepted, rejected, rejected_sections = _ground_profile(
        parsed, evidence_payload
    )
    return SynthesizedProfileResult(
        profile=profile,
        accepted_claim_count=accepted,
        rejected_claim_count=rejected,
        duration_ms=round((monotonic() - started) * 1000),
        rejected_sections=rejected_sections,
    )


def get_openai_model() -> str | None:
    return os.getenv("OPENAI_MODEL", "").strip() or None


def _ground_profile(
    payload: SynthesizedProfilePayload,
    evidence: dict[str, Any],
) -> tuple[NeighborhoodProfile, int, int, tuple[str, ...]]:
    checks = {
        str(check.get("id")): check
        for check in evidence.get("checks", [])
        if isinstance(check, dict) and check.get("id")
    }
    citations: list[NarrativeCitation] = []
    accepted = 0
    rejected = 0
    rejected_sections: list[str] = []

    overview = ""
    if _claim_is_grounded(payload.overview, checks):
        overview = payload.overview.text.strip()
        citations.append(
            NarrativeCitation(
                section="overview",
                evidence_check_ids=payload.overview.evidence_ids,
            )
        )
        accepted += 1
    else:
        rejected += 1
        rejected_sections.append("overview")

    pros: list[str] = []
    for claim in payload.honest_pros:
        if _claim_is_grounded(claim, checks):
            citations.append(
                NarrativeCitation(
                    section="pro",
                    item_index=len(pros),
                    evidence_check_ids=claim.evidence_ids,
                )
            )
            pros.append(claim.text.strip())
            accepted += 1
        else:
            rejected += 1
            rejected_sections.append("pro")

    cons: list[str] = []
    for claim in payload.honest_cons:
        if _claim_is_grounded(claim, checks):
            citations.append(
                NarrativeCitation(
                    section="con",
                    item_index=len(cons),
                    evidence_check_ids=claim.evidence_ids,
                )
            )
            cons.append(claim.text.strip())
            accepted += 1
        else:
            rejected += 1
            rejected_sections.append("con")

    return (
        NeighborhoodProfile(
            overview=overview,
            vibe_scores=VibeScores(),
            who_lives_here=WhoLivesHere(),
            honest_pros=pros,
            honest_cons=cons,
            trajectory=None,
            narrative_citations=citations,
        ),
        accepted,
        rejected,
        tuple(rejected_sections),
    )


def _claim_is_grounded(claim: GroundedClaim, checks: dict[str, dict[str, Any]]) -> bool:
    if FORBIDDEN_CLAIM_PATTERN.search(claim.text):
        return False
    if not claim.evidence_ids or any(
        check_id not in checks for check_id in claim.evidence_ids
    ):
        return False
    cited = [checks[check_id] for check_id in claim.evidence_ids]
    if any(
        check.get("status") not in {"supported", "fallback", "stale"} for check in cited
    ):
        return False
    claim_numbers = {
        _normalize_number(value) for value in NUMBER_PATTERN.findall(claim.text)
    }
    evidence_numbers = {
        _normalize_number(value)
        for value in NUMBER_PATTERN.findall(json.dumps(cited, sort_keys=True))
    }
    return claim_numbers <= evidence_numbers


def _normalize_number(value: str) -> str:
    return value.replace(",", "").lstrip("0") or "0"
