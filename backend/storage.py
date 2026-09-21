import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.models import (
    AnalysisLensMode,
    AnalysisLensSnapshot,
    AnalyzeRequest,
    AnalyzeResponse,
    CommuteAnchor,
    Coordinates,
    PreferenceProfile,
    PreferenceProfileCreate,
    PreferenceProfileUpdate,
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
                analyze_request_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(connection, "saved_profiles", "analyze_request_json", "TEXT")
        _ensure_column(connection, "saved_profiles", "analysis_lens_json", "TEXT")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS preference_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                car_reliance TEXT,
                energy_preference TEXT,
                top_priority TEXT,
                budget_sensitivity TEXT,
                generic_mode INTEGER NOT NULL,
                commute_anchor_json TEXT,
                max_monthly_rent INTEGER,
                rental_unit_size TEXT,
                must_haves_json TEXT NOT NULL,
                deal_breakers_json TEXT NOT NULL,
                notes TEXT,
                is_default INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(connection, "preference_profiles", "rental_unit_size", "TEXT")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS source_cache (
                cache_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                stored_at TEXT NOT NULL,
                expires_at TEXT
            )
            """
        )
        _migrate_overlapping_preference_categories(connection)


def save_profile(
    response: AnalyzeResponse,
    db_path: Path | None = None,
    analyze_request: AnalyzeRequest | None = None,
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
                analyze_request_json,
                analysis_lens_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                response.place.label,
                coordinates_json,
                response.confidence.level.value,
                source_statuses_json,
                response.model_dump_json(),
                analyze_request.model_dump_json()
                if analyze_request is not None
                else None,
                response.analysis_lens.model_dump_json(),
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
                response_json,
                analyze_request_json,
                analysis_lens_json,
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
                analyze_request_json,
                analysis_lens_json,
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


def update_saved_profile(
    profile_id: str,
    response: AnalyzeResponse,
    db_path: Path | None = None,
    analyze_request: AnalyzeRequest | None = None,
) -> SavedProfile | None:
    path = db_path or get_database_path()
    initialize_database(path)
    current = get_saved_profile(profile_id, path)
    if current is None:
        return None

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
            UPDATE saved_profiles
            SET
                place_label = ?,
                coordinates_json = ?,
                confidence_level = ?,
                source_statuses_json = ?,
                response_json = ?,
                analyze_request_json = ?,
                analysis_lens_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                response.place.label,
                coordinates_json,
                response.confidence.level.value,
                source_statuses_json,
                response.model_dump_json(),
                analyze_request.model_dump_json()
                if analyze_request is not None
                else None,
                response.analysis_lens.model_dump_json(),
                timestamp,
                profile_id,
            ),
        )

    return get_saved_profile(profile_id, path)


def build_refresh_request(saved: SavedProfile) -> AnalyzeRequest:
    if saved.analyze_request is not None:
        return saved.analyze_request

    place = saved.response.place
    return AnalyzeRequest(
        query=place.label,
        coordinates=place.coordinates,
        generic_mode=True,
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


def create_preference_profile(
    profile: PreferenceProfileCreate,
    db_path: Path | None = None,
) -> PreferenceProfile:
    path = db_path or get_database_path()
    initialize_database(path)

    profile_id = uuid4().hex
    timestamp = _utc_timestamp()

    with _connect(path) as connection:
        existing_count = connection.execute(
            "SELECT COUNT(*) FROM preference_profiles"
        ).fetchone()[0]
        is_default = existing_count == 0
        connection.execute(
            """
            INSERT INTO preference_profiles (
                id,
                name,
                car_reliance,
                energy_preference,
                top_priority,
                budget_sensitivity,
                generic_mode,
                commute_anchor_json,
                max_monthly_rent,
                rental_unit_size,
                must_haves_json,
                deal_breakers_json,
                notes,
                is_default,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _profile_values(profile_id, profile, is_default, timestamp, timestamp),
        )

    created = get_preference_profile(profile_id, path)
    if created is None:
        raise RuntimeError("Preference profile could not be loaded after insert.")
    return created


def list_preference_profiles(db_path: Path | None = None) -> list[PreferenceProfile]:
    path = db_path or get_database_path()
    initialize_database(path)

    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM preference_profiles
            ORDER BY is_default DESC, updated_at DESC, rowid DESC
            """
        ).fetchall()

    return [_row_to_preference_profile(row) for row in rows]


def get_preference_profile(
    profile_id: str,
    db_path: Path | None = None,
) -> PreferenceProfile | None:
    path = db_path or get_database_path()
    initialize_database(path)

    with _connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM preference_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()

    return _row_to_preference_profile(row) if row is not None else None


def update_preference_profile(
    profile_id: str,
    update: PreferenceProfileUpdate,
    db_path: Path | None = None,
) -> PreferenceProfile | None:
    path = db_path or get_database_path()
    initialize_database(path)
    current = get_preference_profile(profile_id, path)
    if current is None:
        return None

    fields_set = update.model_fields_set
    merged = PreferenceProfileCreate(
        name=update.name if "name" in fields_set else current.name,
        car_reliance=update.car_reliance
        if "car_reliance" in fields_set
        else current.car_reliance,
        energy_preference=(
            update.energy_preference
            if "energy_preference" in fields_set
            else current.energy_preference
        ),
        top_priority=update.top_priority
        if "top_priority" in fields_set
        else current.top_priority,
        budget_sensitivity=(
            update.budget_sensitivity
            if "budget_sensitivity" in fields_set
            else current.budget_sensitivity
        ),
        generic_mode=update.generic_mode
        if "generic_mode" in fields_set
        else current.generic_mode,
        commute_anchor=update.commute_anchor
        if "commute_anchor" in fields_set
        else current.commute_anchor,
        max_monthly_rent=(
            update.max_monthly_rent
            if "max_monthly_rent" in fields_set
            else current.max_monthly_rent
        ),
        rental_unit_size=(
            update.rental_unit_size
            if "rental_unit_size" in fields_set
            else current.rental_unit_size
        ),
        must_haves=update.must_haves
        if "must_haves" in fields_set
        else current.must_haves,
        deal_breakers=update.deal_breakers
        if "deal_breakers" in fields_set
        else current.deal_breakers,
        notes=update.notes if "notes" in fields_set else current.notes,
    )
    timestamp = _utc_timestamp()

    with _connect(path) as connection:
        connection.execute(
            """
            UPDATE preference_profiles
            SET
                name = ?,
                car_reliance = ?,
                energy_preference = ?,
                top_priority = ?,
                budget_sensitivity = ?,
                generic_mode = ?,
                commute_anchor_json = ?,
                max_monthly_rent = ?,
                rental_unit_size = ?,
                must_haves_json = ?,
                deal_breakers_json = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                merged.name,
                _enum_value(merged.car_reliance),
                _enum_value(merged.energy_preference),
                _enum_value(merged.top_priority),
                _enum_value(merged.budget_sensitivity),
                int(merged.generic_mode),
                _commute_anchor_json(merged.commute_anchor),
                merged.max_monthly_rent,
                _enum_value(merged.rental_unit_size),
                _category_json(merged.must_haves),
                _category_json(merged.deal_breakers),
                merged.notes,
                timestamp,
                profile_id,
            ),
        )

    return get_preference_profile(profile_id, path)


def set_default_preference_profile(
    profile_id: str,
    db_path: Path | None = None,
) -> PreferenceProfile | None:
    path = db_path or get_database_path()
    initialize_database(path)
    if get_preference_profile(profile_id, path) is None:
        return None

    timestamp = _utc_timestamp()
    with _connect(path) as connection:
        connection.execute("UPDATE preference_profiles SET is_default = 0")
        connection.execute(
            """
            UPDATE preference_profiles
            SET is_default = 1, updated_at = ?
            WHERE id = ?
            """,
            (timestamp, profile_id),
        )

    return get_preference_profile(profile_id, path)


def delete_preference_profile(profile_id: str, db_path: Path | None = None) -> bool:
    path = db_path or get_database_path()
    initialize_database(path)

    with _connect(path) as connection:
        row = connection.execute(
            "SELECT is_default FROM preference_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if row is None:
            return False

        deleted_default = bool(row["is_default"])
        cursor = connection.execute(
            "DELETE FROM preference_profiles WHERE id = ?",
            (profile_id,),
        )
        if deleted_default:
            replacement = connection.execute(
                """
                SELECT id
                FROM preference_profiles
                ORDER BY updated_at DESC, rowid DESC
                LIMIT 1
                """
            ).fetchone()
            if replacement is not None:
                connection.execute(
                    "UPDATE preference_profiles SET is_default = 1 WHERE id = ?",
                    (replacement["id"],),
                )

    return cursor.rowcount > 0


def _profile_values(
    profile_id: str,
    profile: PreferenceProfileCreate,
    is_default: bool,
    created_at: str,
    updated_at: str,
) -> tuple[object, ...]:
    return (
        profile_id,
        profile.name,
        _enum_value(profile.car_reliance),
        _enum_value(profile.energy_preference),
        _enum_value(profile.top_priority),
        _enum_value(profile.budget_sensitivity),
        int(profile.generic_mode),
        _commute_anchor_json(profile.commute_anchor),
        profile.max_monthly_rent,
        _enum_value(profile.rental_unit_size),
        _category_json(profile.must_haves),
        _category_json(profile.deal_breakers),
        profile.notes,
        int(is_default),
        created_at,
        updated_at,
    )


def _row_to_preference_profile(row: sqlite3.Row) -> PreferenceProfile:
    commute_anchor_json = row["commute_anchor_json"]
    return PreferenceProfile(
        id=row["id"],
        name=row["name"],
        car_reliance=row["car_reliance"],
        energy_preference=row["energy_preference"],
        top_priority=row["top_priority"],
        budget_sensitivity=row["budget_sensitivity"],
        generic_mode=bool(row["generic_mode"]),
        commute_anchor=(
            CommuteAnchor.model_validate(json.loads(commute_anchor_json))
            if commute_anchor_json is not None
            else None
        ),
        max_monthly_rent=row["max_monthly_rent"],
        rental_unit_size=row["rental_unit_size"],
        must_haves=json.loads(row["must_haves_json"]),
        deal_breakers=json.loads(row["deal_breakers_json"]),
        notes=row["notes"],
        is_default=bool(row["is_default"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _commute_anchor_json(anchor: CommuteAnchor | None) -> str | None:
    return anchor.model_dump_json() if anchor is not None else None


def _category_json(categories: list[object]) -> str:
    return json.dumps([_enum_value(category) for category in categories])


def _enum_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value


def open_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _connect(path: Path) -> sqlite3.Connection:
    return open_database(path)


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})")
    }
    if column_name not in columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_summary(row: sqlite3.Row) -> SavedProfileSummary:
    return SavedProfileSummary(**_summary_data(row))


def _summary_data(row: sqlite3.Row) -> dict[str, object]:
    coordinates_json = row["coordinates_json"]
    response = (
        AnalyzeResponse.model_validate_json(row["response_json"])
        if "response_json" in row.keys()
        else None
    )
    has_building_check = bool(
        response
        and any(check.id == "building" for check in response.evidence_checks)
    )
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
        "analyze_request": (
            AnalyzeRequest.model_validate_json(row["analyze_request_json"])
            if "analyze_request_json" in row.keys()
            and row["analyze_request_json"] is not None
            else None
        ),
        "analysis_lens": _analysis_lens_from_row(row),
        "coverage": response.coverage if response is not None else None,
        "fit_score": response.fit.score
        if response is not None and response.fit
        else None,
        "fit_label": response.fit.label
        if response is not None and response.fit
        else None,
        "collision_count": (
            response.profile.collision_context.total_collisions
            if response is not None and response.profile.collision_context is not None
            else None
        ),
        "ksi_collision_count": (
            response.profile.collision_context.ksi_collisions
            if response is not None and response.profile.collision_context is not None
            else None
        ),
        "building_match": (
            response.profile.building_context is not None
            if has_building_check
            else None
        ),
        "building_score": (
            response.profile.building_context.current_score
            if response is not None and response.profile.building_context is not None
            else None
        ),
        "cycling_score": (
            response.profile.vibe_scores.cycling_access
            if response is not None
            else None
        ),
        "cycling_evidence_method": (
            response.profile.cycling_context.method
            if response is not None and response.profile.cycling_context is not None
            else None
        ),
    }


def _analysis_lens_from_row(row: sqlite3.Row) -> AnalysisLensSnapshot:
    if "analysis_lens_json" in row.keys() and row["analysis_lens_json"]:
        return AnalysisLensSnapshot.model_validate_json(row["analysis_lens_json"])
    return AnalysisLensSnapshot(
        mode=AnalysisLensMode.LEGACY,
        profile_name="Legacy report",
    )


def _migrate_overlapping_preference_categories(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        "SELECT id, must_haves_json, deal_breakers_json FROM preference_profiles"
    ).fetchall()
    for row in rows:
        must_haves = json.loads(row["must_haves_json"])
        deal_breakers = json.loads(row["deal_breakers_json"])
        normalized = [item for item in must_haves if item not in set(deal_breakers)]
        if normalized != must_haves:
            connection.execute(
                "UPDATE preference_profiles SET must_haves_json = ? WHERE id = ?",
                (json.dumps(normalized), row["id"]),
            )
