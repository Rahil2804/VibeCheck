from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.config import load_environment
from backend.models import AnalyzeRequest, Coordinates, GeographyContext, Place
from backend.snapshot import snapshot_health
from backend.sources.access import OVERPASS_URLS, fetch_access_context
from backend.sources.common import SourceContext
from backend.storage import get_database_path, initialize_database
from backend.synthesizer import get_openai_model, synthesize_profile


def collect_health() -> dict[str, Any]:
    mapbox_configured = bool(os.getenv("MAPBOX_TOKEN", "").strip())
    openai_key_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
    openai_model = get_openai_model()
    openai_configured = openai_key_configured and openai_model is not None
    sqlite_check = _sqlite_health(get_database_path())
    snapshot_check = snapshot_health()
    required_ready = (
        mapbox_configured and sqlite_check["ready"] and snapshot_check["ready"]
    )
    return {
        "status": "ok" if required_ready else "degraded",
        "mapbox": {"configured": mapbox_configured},
        "openai": {
            "configured": openai_configured,
            "api_key_configured": openai_key_configured,
            "required": False,
            "model": openai_model,
        },
        "snapshot": snapshot_check,
        "sqlite": sqlite_check,
        "osm": {
            "configured": True,
            "endpoints": list(OVERPASS_URLS),
            "live_checked": False,
        },
    }


def _sqlite_health(path: Path) -> dict[str, Any]:
    try:
        initialize_database(path)
        connection = sqlite3.connect(path)
        try:
            connection.execute("SELECT 1").fetchone()
        finally:
            connection.close()
        return {"ready": True, "path": str(path)}
    except (OSError, sqlite3.Error) as exc:
        return {"ready": False, "path": str(path), "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the local VibeCheck setup.")
    parser.add_argument("--live-sources", action="store_true")
    parser.add_argument("--live-openai", action="store_true")
    args = parser.parse_args()
    load_environment()
    health = collect_health()
    if args.live_sources:
        health["osm"] = asyncio.run(_live_osm_check())
    if args.live_openai:
        health["openai"]["live"] = asyncio.run(_live_openai_check())
    print(json.dumps(health, indent=2))
    raise SystemExit(0 if health["status"] == "ok" else 1)


async def _live_osm_check() -> dict[str, Any]:
    started = datetime.now(UTC)
    try:
        result = await fetch_access_context(
            SourceContext(
                request=AnalyzeRequest(
                    coordinates=Coordinates(lat=43.706134, lng=-79.341499)
                ),
                place=Place(
                    label="Toronto diagnostics point",
                    coordinates=Coordinates(lat=43.706134, lng=-79.341499),
                ),
                geography=GeographyContext(is_toronto=True, is_gta=True),
            ),
            use_cache=False,
        )
    except Exception as exc:
        return {
            "configured": True,
            "endpoints": list(OVERPASS_URLS),
            "live_checked": True,
            "ready": False,
            "error": type(exc).__name__,
        }
    return {
        "configured": True,
        "endpoints": list(OVERPASS_URLS),
        "live_checked": True,
        "ready": bool(result.data),
        "stale": result.stale,
        "source_url": result.source_url,
        "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000),
    }


async def _live_openai_check() -> dict[str, Any]:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return {"ready": False, "error": "not_configured"}
    if get_openai_model() is None:
        return {"ready": False, "error": "model_not_configured"}
    started = datetime.now(UTC)
    try:
        result = await synthesize_profile(
            place_label="Diagnostics fixture",
            evidence={
                "checks": [
                    {
                        "id": "transit",
                        "label": "Transit fixture",
                        "status": "supported",
                        "summary": "Scheduled service is available in the fixture.",
                        "facts": {"nearby_route_count": 3},
                    },
                    {
                        "id": "rent",
                        "label": "Rent fixture",
                        "status": "supported",
                        "summary": "A unit-matched rent benchmark is available.",
                        "facts": {"monthly_rent": 2000, "currency": "CAD"},
                    },
                ]
            },
            caveats=[],
        )
    except Exception as exc:
        return {"ready": False, "error": type(exc).__name__}
    return {
        "ready": result is not None and result.accepted_claim_count > 0,
        "accepted_claim_count": result.accepted_claim_count if result else 0,
        "rejected_claim_count": result.rejected_claim_count if result else 0,
        "duration_ms": round((datetime.now(UTC) - started).total_seconds() * 1000),
    }


if __name__ == "__main__":
    main()
