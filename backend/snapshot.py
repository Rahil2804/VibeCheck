from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
DEFAULT_SNAPSHOT_PATH = SNAPSHOT_DIR / "gta_snapshot.sqlite"
DEFAULT_MANIFEST_PATH = SNAPSHOT_DIR / "manifest.json"
SNAPSHOT_SCHEMA_VERSION = 3


@dataclass(frozen=True)
class SnapshotPaths:
    database: Path
    manifest: Path


def get_snapshot_paths() -> SnapshotPaths:
    configured = os.getenv("GTA_SNAPSHOT_PATH")
    database = Path(configured).expanduser() if configured else DEFAULT_SNAPSHOT_PATH
    manifest = database.with_name("manifest.json")
    return SnapshotPaths(database=database, manifest=manifest)


def load_manifest(paths: SnapshotPaths | None = None) -> dict[str, Any] | None:
    selected = paths or get_snapshot_paths()
    if not selected.manifest.exists():
        return None
    try:
        payload = json.loads(selected.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def snapshot_connection(
    paths: SnapshotPaths | None = None,
) -> sqlite3.Connection | None:
    selected = paths or get_snapshot_paths()
    if not selected.database.exists():
        return None
    connection = sqlite3.connect(
        f"{selected.database.resolve().as_uri()}?mode=ro", uri=True
    )
    connection.row_factory = sqlite3.Row
    return connection


def validate_snapshot(paths: SnapshotPaths | None = None) -> list[str]:
    selected = paths or get_snapshot_paths()
    errors: list[str] = []
    try:
        manifest = json.loads(selected.manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ["Snapshot manifest is missing."]
    except PermissionError:
        return ["Snapshot manifest is not readable by the backend process."]
    except (OSError, json.JSONDecodeError):
        return ["Snapshot manifest is invalid or unreadable."]
    if not isinstance(manifest, dict):
        return ["Snapshot manifest is invalid."]
    if manifest.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        errors.append("Snapshot schema version is unsupported.")
    if not selected.database.exists():
        errors.append("Snapshot database is missing.")
        return errors
    expected = manifest.get("artifact_sha256")
    if not isinstance(expected, str) or expected != sha256_file(selected.database):
        errors.append("Snapshot checksum does not match the manifest.")
    try:
        connection = snapshot_connection(selected)
        if connection is None:
            return [*errors, "Snapshot database is missing."]
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                errors.append(f"SQLite integrity check failed: {integrity}")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            required = {
                "feed_status",
                "transit_stop_service",
                "rent_benchmarks",
                "cycling_segments",
                "bike_share_stations",
                "toronto_neighbourhood_profiles",
                "census_subdivisions",
            }
            missing = sorted(required - tables)
            if missing:
                errors.append("Snapshot tables are missing: " + ", ".join(missing))
        finally:
            connection.close()
    except sqlite3.Error:
        errors.append("Snapshot database is not readable by the backend process.")
    return errors


def snapshot_health(paths: SnapshotPaths | None = None) -> dict[str, Any]:
    selected = paths or get_snapshot_paths()
    manifest = load_manifest(selected)
    errors = validate_snapshot(selected)
    size = selected.database.stat().st_size if selected.database.exists() else 0
    tables: dict[str, int] = {}
    feed_validity: list[dict[str, Any]] = []
    if not errors:
        connection = snapshot_connection(selected)
        if connection is not None:
            try:
                for table in (
                    "transit_stop_service",
                    "rent_benchmarks",
                    "cycling_segments",
                    "bike_share_stations",
                    "toronto_neighbourhood_profiles",
                    "census_subdivisions",
                ):
                    tables[table] = int(
                        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[
                            0
                        ]
                    )
                feed_validity = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT agency, service_date, feed_end_date FROM feed_status ORDER BY agency"
                    ).fetchall()
                ]
            finally:
                connection.close()
    return {
        "ready": not errors,
        "path": str(selected.database),
        "snapshot_id": manifest.get("snapshot_id") if manifest else None,
        "created_at": manifest.get("created_at") if manifest else None,
        "artifact_bytes": size,
        "tables": tables,
        "feed_validity": feed_validity,
        "stale": _manifest_is_stale(manifest),
        "errors": errors,
    }


def snapshot_metadata() -> tuple[str | None, dict[str, Any] | None]:
    manifest = load_manifest()
    if manifest is None:
        return None, None
    snapshot_id = manifest.get("snapshot_id")
    return (str(snapshot_id) if snapshot_id else None), manifest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _manifest_is_stale(manifest: dict[str, Any] | None) -> bool:
    if manifest is None:
        return True
    valid_until = parse_date(manifest.get("valid_until"))
    deadlines = [valid_until] if valid_until is not None else []
    feed_validity = manifest.get("feed_validity", [])
    if isinstance(feed_validity, list):
        deadlines.extend(
            parsed
            for item in feed_validity
            if isinstance(item, dict)
            and (parsed := parse_date(item.get("valid_until"))) is not None
        )
    now = datetime.now(UTC)
    for deadline in deadlines:
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if deadline < now:
            return True
    return False


def main() -> None:
    health = snapshot_health()
    print(json.dumps(health, indent=2))
    raise SystemExit(0 if health["ready"] else 1)


if __name__ == "__main__":
    main()
