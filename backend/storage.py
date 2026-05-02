import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.models import (
    AnalyzeResponse,
    Coordinates,
    SavedProfile,
    SavedProfileSummary,
    SourceStatus,
)


def get_database_path() -> Path:
    return Path(os.getenv("SQLITE_PATH", "data/vibecheck.db"))


def initialize_database(db_path: Path | None = None) -> None:
    path = db_path or get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_profiles (
                id TEXT PRIMARY KEY,
                place_label TEXT NOT NULL,
                coordinates_json TEXT,
                confidence_level TEXT NOT NULL,
                source_statuses_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def save_profile(
    response: AnalyzeResponse,
    db_path: Path | None = None,
) -> SavedProfile:
    path = db_path or get_database_path()
    initialize_database(path)

    profile_id = uuid4().hex
    timestamp = _utc_timestamp()
    coordinates_json = (
        response.place.coordinates.model_dump_json()
        if response.place.coordinates is not None
        else None
    )
    source_statuses_json = json.dumps(
        [status.model_dump(mode="json") for status in response.source_statuses]
    )

    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO saved_profiles (
                id,
                place_label,
                coordinates_json,
                confidence_level,
                source_statuses_json,
                response_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                response.place.label,
                coordinates_json,
                response.confidence.level.value,
                source_statuses_json,
                response.model_dump_json(),
                timestamp,
                timestamp,
            ),
        )

    saved = get_saved_profile(profile_id, path)
    if saved is None:
        raise RuntimeError("Saved profile could not be loaded after insert.")
    return saved


def list_saved_profiles(db_path: Path | None = None) -> list[SavedProfileSummary]:
    path = db_path or get_database_path()
    initialize_database(path)

    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                place_label,
                coordinates_json,
                confidence_level,
                source_statuses_json,
                created_at,
                updated_at
            FROM saved_profiles
            ORDER BY created_at DESC, rowid DESC
            """
        ).fetchall()

    return [_row_to_summary(row) for row in rows]


def get_saved_profile(
    profile_id: str,
    db_path: Path | None = None,
) -> SavedProfile | None:
    path = db_path or get_database_path()
    initialize_database(path)

    with _connect(path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                place_label,
                coordinates_json,
                confidence_level,
                source_statuses_json,
                response_json,
                created_at,
                updated_at
            FROM saved_profiles
            WHERE id = ?
            """,
            (profile_id,),
        ).fetchone()

    if row is None:
        return None

    return SavedProfile(
        **_summary_data(row),
        response=AnalyzeResponse.model_validate_json(row["response_json"]),
    )


def delete_saved_profile(profile_id: str, db_path: Path | None = None) -> bool:
    path = db_path or get_database_path()
    initialize_database(path)

    with _connect(path) as connection:
        cursor = connection.execute(
            "DELETE FROM saved_profiles WHERE id = ?",
            (profile_id,),
        )

    return cursor.rowcount > 0


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_summary(row: sqlite3.Row) -> SavedProfileSummary:
    return SavedProfileSummary(**_summary_data(row))


def _summary_data(row: sqlite3.Row) -> dict[str, object]:
    coordinates_json = row["coordinates_json"]
    return {
        "id": row["id"],
        "place_label": row["place_label"],
        "coordinates": (
            Coordinates.model_validate(json.loads(coordinates_json))
            if coordinates_json is not None
            else None
        ),
        "confidence_level": row["confidence_level"],
        "source_statuses": [
            SourceStatus.model_validate(status)
            for status in json.loads(row["source_statuses_json"])
        ],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
