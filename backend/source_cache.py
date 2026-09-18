import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.storage import get_database_path, initialize_database, open_database


def get_cached_source(key: str, db_path: Path | None = None) -> dict[str, Any] | None:
    return _get_cached_source(key, db_path=db_path, max_stale=None)


def get_stale_cached_source(
    key: str,
    *,
    max_stale: timedelta,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    return _get_cached_source(key, db_path=db_path, max_stale=max_stale)


def _get_cached_source(
    key: str,
    *,
    db_path: Path | None,
    max_stale: timedelta | None,
) -> dict[str, Any] | None:
    path = db_path or get_database_path()
    initialize_database(path)
    with open_database(path) as connection:
        row = connection.execute(
            "SELECT payload_json, expires_at FROM source_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
    if row is None:
        return None
    expires_at = row["expires_at"]
    if expires_at:
        expiry = datetime.fromisoformat(expires_at)
        now = datetime.now(UTC)
        if expiry <= now and (max_stale is None or expiry < now - max_stale):
            return None
    return json.loads(row["payload_json"])


def set_cached_source(
    key: str,
    payload: dict[str, Any],
    *,
    ttl: timedelta | None,
    db_path: Path | None = None,
) -> None:
    path = db_path or get_database_path()
    initialize_database(path)
    now = datetime.now(UTC)
    expires_at = (now + ttl).isoformat() if ttl is not None else None
    with open_database(path) as connection:
        connection.execute(
            """
            INSERT INTO source_cache (cache_key, payload_json, stored_at, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                stored_at = excluded.stored_at,
                expires_at = excluded.expires_at
            """,
            (key, json.dumps(payload), now.isoformat(), expires_at),
        )
