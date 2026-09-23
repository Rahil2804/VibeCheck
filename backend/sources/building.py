from __future__ import annotations

import json
import re
from typing import Any, NamedTuple

from backend.snapshot import load_manifest, partition_is_stale, snapshot_connection
from backend.sources.common import SourceContext, SourceResult

REGISTRATION_URL = (
    "https://open.toronto.ca/dataset/apartment-building-registration/"
)
EVALUATION_URL = "https://open.toronto.ca/dataset/apartment-building-evaluation/"

STREET_SUFFIXES = {
    "AV": "AVE",
    "AVENUE": "AVE",
    "BOULEVARD": "BLVD",
    "CIRCLE": "CIR",
    "COURT": "CT",
    "CRT": "CT",
    "CRESCENT": "CRES",
    "DRIVE": "DR",
    "GARDENS": "GDNS",
    "GATE": "GT",
    "HEIGHTS": "HTS",
    "HIGHWAY": "HWY",
    "LANE": "LANE",
    "PARKWAY": "PKWY",
    "PLACE": "PL",
    "ROAD": "RD",
    "STREET": "ST",
    "TERRACE": "TER",
    "TRAIL": "TRL",
    "WAY": "WAY",
}
STREET_DIRECTIONS = {
    "EAST": "E",
    "WEST": "W",
    "NORTH": "N",
    "SOUTH": "S",
}


class ParsedAddress(NamedTuple):
    civic_start: int
    civic_end: int
    street_key: str


async def fetch_building_context(context: SourceContext) -> SourceResult:
    if not (context.geography and context.geography.is_toronto):
        return SourceResult(
            data={},
            message="RentSafeTO building evidence is currently available only inside Toronto.",
            scope="RentSafeTO registered apartment buildings",
            source_url=REGISTRATION_URL,
        )

    parsed = parse_address(context.place.label)
    if parsed is None:
        return SourceResult(
            data={},
            message="An exact civic address is required for a RentSafeTO building match.",
            scope="RentSafeTO registered apartment buildings",
            source_url=REGISTRATION_URL,
        )

    manifest = load_manifest()
    connection = snapshot_connection()
    if manifest is None or connection is None:
        return SourceResult(
            data={},
            message="The bundled RentSafeTO building snapshot is unavailable.",
            scope="RentSafeTO registered apartment buildings",
            source_url=REGISTRATION_URL,
        )
    try:
        rows = connection.execute(
            """
            SELECT * FROM toronto_buildings
            WHERE street_key = ? AND civic_start <= ? AND civic_end >= ?
            """,
            (parsed.street_key, parsed.civic_start, parsed.civic_start),
        ).fetchall()
        if len(rows) != 1:
            message = (
                "The civic address matches multiple RentSafeTO records, so no building was selected."
                if len(rows) > 1
                else "No exact RentSafeTO record matched this address; this does not prove the building is unregistered."
            )
            return SourceResult(
                data={},
                message=message,
                updated_at=_partition_retrieval(manifest, "building_registration"),
                edition=str(manifest.get("snapshot_id") or "Bundled GTA snapshot"),
                scope="RentSafeTO registered apartment buildings",
                source_url=REGISTRATION_URL,
                stale=partition_is_stale(
                    manifest, "building_registration", "building_evaluations"
                ),
            )
        row = dict(rows[0])
        stale = partition_is_stale(
            manifest, "building_registration", "building_evaluations"
        )
        building_context = {
            "rsn": str(row["rsn"]),
            "site_address": row["site_address"],
            "property_type": row["property_type"],
            "year_built": row["year_built"],
            "storeys": row["storeys"],
            "units": row["units"],
            "evaluation_date": row["evaluation_date"],
            "current_score": row["current_score"],
            "proactive_score": row["proactive_score"],
            "reactive_deduction": row["reactive_deduction"],
            "rating": building_rating(row["current_score"]),
            "areas_evaluated": row["areas_evaluated"],
            "low_rated_categories": _json_list(row["low_rated_categories_json"]),
            "scope": "RentSafeTO registered apartment buildings",
            "edition": str(manifest.get("snapshot_id") or "Bundled GTA snapshot"),
            "stale": stale,
            "registration_source_url": REGISTRATION_URL,
            "evaluation_source_url": EVALUATION_URL,
        }
        return SourceResult(
            data={"building_context": building_context},
            message="An exact official RentSafeTO address record matched.",
            updated_at=_latest_building_retrieval(manifest),
            edition=building_context["edition"],
            scope=building_context["scope"],
            source_url=EVALUATION_URL,
            stale=stale,
        )
    finally:
        connection.close()


def parse_address(value: str) -> ParsedAddress | None:
    cleaned = value.upper().replace("’", "'")
    cleaned = re.sub(
        r"^\s*(?:#|UNIT\s+|APT\s+|APARTMENT\s+|SUITE\s+)"
        r"[A-Z0-9-]+\s*[-,]\s*(?=\d+\s)",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\b(?:UNIT|APT|APARTMENT|SUITE)\s*[A-Z0-9-]+\b", " ", cleaned)
    candidates = [part.strip() for part in cleaned.split(",")]
    candidates.append(cleaned)
    for candidate in candidates:
        match = re.match(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s+(.+?)\s*$", candidate)
        if match is None:
            continue
        start = int(match.group(1))
        end = int(match.group(2) or start)
        street_key = normalize_street(match.group(3))
        if street_key:
            return ParsedAddress(min(start, end), max(start, end), street_key)
    return None


def normalize_street(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9 ]+", " ", value.upper())
    tokens = [token for token in normalized.split() if token]
    return " ".join(
        STREET_DIRECTIONS.get(token, STREET_SUFFIXES.get(token, token))
        for token in tokens
    )


def building_rating(score: float | int | None) -> str | None:
    if score is None:
        return None
    if score >= 85:
        return "green"
    if score >= 70:
        return "yellow"
    return "red"


def _json_list(value: Any) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _partition_retrieval(manifest: dict[str, Any], name: str) -> str | None:
    partitions = manifest.get("partitions", {})
    item = partitions.get(name, {}) if isinstance(partitions, dict) else {}
    return item.get("retrieved_at") if isinstance(item, dict) else None


def _latest_building_retrieval(manifest: dict[str, Any]) -> str | None:
    values = [
        _partition_retrieval(manifest, "building_registration"),
        _partition_retrieval(manifest, "building_evaluations"),
    ]
    present = [value for value in values if value]
    return max(present) if present else None
