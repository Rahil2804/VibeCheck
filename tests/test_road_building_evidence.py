import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from backend.models import AnalyzeRequest, Coordinates, GeographyContext, Place
from backend.snapshot import partition_is_stale, sha256_file, snapshot_health
from backend.sources.building import (
    building_rating,
    fetch_building_context,
    parse_address,
)
from backend.sources.collisions import _nearby_rows, fetch_collision_context
from backend.sources.common import SourceContext
from scripts.refresh_gta_snapshot import (
    _create_schema,
    normalize_building_data,
    normalize_collision_data,
    refresh_road_buildings_snapshot,
)


def _csv(headers, rows):
    lines = [",".join(headers)]
    lines.extend(",".join(str(row.get(header, "")) for header in headers) for row in rows)
    return ("\n".join(lines) + "\n").encode()


def _collision_payloads():
    last_year = datetime.now(UTC).year - 1
    traffic_headers = [
        "_id",
        "OCC_DATE",
        "OCC_YEAR",
        "FATALITIES",
        "INJURY_COLLISIONS",
        "PEDESTRIAN",
        "BICYCLE",
        "LONG_WGS84",
        "LAT_WGS84",
    ]
    traffic_rows = [
        {
            "_id": year,
            "OCC_YEAR": year,
            "FATALITIES": 1 if year == last_year else 0,
            "INJURY_COLLISIONS": "YES",
            "PEDESTRIAN": "YES" if year == last_year else "NO",
            "BICYCLE": "YES" if year == last_year - 1 else "NO",
            "LONG_WGS84": -79.42,
            "LAT_WGS84": 43.68,
        }
        for year in range(last_year - 5, last_year + 1)
    ]
    ksi_headers = [
        "collision_id",
        "accdate",
        "acclass",
        "latitude",
        "longitude",
        "pedestrian",
        "cyclist",
        "motorcyclist",
        "other_micromobility",
    ]
    ksi_rows = [
        {
            "collision_id": "ksi-1",
            "accdate": f"{last_year}-02-01T12:00:00Z",
            "acclass": "Fatal",
            "latitude": 43.68,
            "longitude": -79.42,
            "pedestrian": "true",
        },
        {
            "collision_id": "ksi-1",
            "accdate": f"{last_year}-02-01T12:00:00Z",
            "acclass": "Fatal",
            "latitude": 43.68,
            "longitude": -79.42,
            "cyclist": "true",
        },
        {
            "collision_id": "ksi-2",
            "accdate": f"{last_year}-03-01T12:00:00Z",
            "acclass": "Non-Fatal Injury",
            "latitude": 44.68,
            "longitude": -79.42,
            "motorcyclist": "true",
        },
    ]
    return _csv(traffic_headers, traffic_rows), _csv(ksi_headers, ksi_rows)


def _building_payloads():
    registration = _csv(
        [
            "RSN",
            "SITE_ADDRESS",
            "PROPERTY_TYPE",
            "YEAR_BUILT",
            "NO_OF_STOREYS",
            "NO_OF_UNITS",
            "YEAR_REGISTERED",
        ],
        [
            {
                "RSN": "1001",
                "SITE_ADDRESS": "210 WYCHWOOD AVENUE",
                "PROPERTY_TYPE": "PRIVATE",
                "YEAR_BUILT": 1970,
                "NO_OF_STOREYS": 12,
                "NO_OF_UNITS": 120,
                "YEAR_REGISTERED": 2017,
            },
            {
                "RSN": "1002",
                "SITE_ADDRESS": "220-224 WYCHWOOD AVE",
                "PROPERTY_TYPE": "PRIVATE",
                "YEAR_BUILT": 1980,
                "NO_OF_STOREYS": 8,
                "NO_OF_UNITS": 80,
                "YEAR_REGISTERED": 2018,
            },
        ],
    )
    evaluations = _csv(
        [
            "RSN",
            "EVALUATION COMPLETED ON",
            "CURRENT BUILDING EVAL SCORE",
            "PROACTIVE BUILDING SCORE",
            "CURRENT REACTIVE SCORE",
            "NO OF AREAS EVALUATED",
            "BALCONY GUARDS",
        ],
        [
            {
                "RSN": "1001",
                "EVALUATION COMPLETED ON": "2024-01-01",
                "CURRENT BUILDING EVAL SCORE": 68,
                "PROACTIVE BUILDING SCORE": 70,
                "CURRENT REACTIVE SCORE": -2,
                "NO OF AREAS EVALUATED": 10,
                "BALCONY GUARDS": 1,
            },
            {
                "RSN": "1001",
                "EVALUATION COMPLETED ON": "2025-02-03",
                "CURRENT BUILDING EVAL SCORE": 86,
                "PROACTIVE BUILDING SCORE": 88,
                "CURRENT REACTIVE SCORE": -2,
                "NO OF AREAS EVALUATED": 12,
                "BALCONY GUARDS": 1,
            },
        ],
    )
    return registration, evaluations


def _write_snapshot(tmp_path):
    database = tmp_path / "gta_snapshot.sqlite"
    with sqlite3.connect(database) as connection:
        _create_schema(connection)
        collision_partitions = normalize_collision_data(connection, *_collision_payloads())
        building_partitions = normalize_building_data(connection, *_building_payloads())
    manifest = {
        "schema_version": 4,
        "snapshot_id": "road-building-fixture",
        "created_at": datetime.now(UTC).isoformat(),
        "artifact_sha256": sha256_file(database),
        "partitions": {**collision_partitions, **building_partitions},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return database


def _toronto_context(label="210 Wychwood Avenue, Toronto"):
    place = Place(
        label=label,
        city="Toronto",
        coordinates=Coordinates(lat=43.68, lng=-79.42),
    )
    return SourceContext(
        request=AnalyzeRequest(query=label),
        place=place,
        geography=GeographyContext(is_toronto=True, is_gta=True),
    )


def test_collision_normalization_keeps_five_years_and_deduplicates_ksi_participants():
    connection = sqlite3.connect(":memory:")
    _create_schema(connection)
    partitions = normalize_collision_data(connection, *_collision_payloads())

    assert connection.execute("SELECT COUNT(*) FROM toronto_collisions").fetchone()[0] == 5
    assert connection.execute("SELECT COUNT(*) FROM toronto_ksi_collisions").fetchone()[0] == 2
    event = connection.execute(
        "SELECT fatal, pedestrian_involved, cyclist_involved FROM toronto_ksi_collisions WHERE collision_id = 'ksi-1'"
    ).fetchone()
    assert event == (1, 1, 1)
    assert partitions["collisions_all"]["row_count"] == 5
    assert partitions["collisions_ksi"]["row_count"] == 2


def test_collision_radius_includes_inside_point_and_excludes_outside_point():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    _create_schema(connection)
    connection.executemany(
        "INSERT INTO toronto_collisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("inside", "2025-01-01", 43.6889, -79.42, 0, 0, 0, 0),
            ("outside", "2025-01-01", 43.6891, -79.42, 0, 0, 0, 0),
        ],
    )

    nearby = _nearby_rows(connection, "toronto_collisions", 43.68, -79.42)

    assert [row["collision_id"] for row in nearby] == ["inside"]


@pytest.mark.asyncio
async def test_collision_source_keeps_annual_and_ksi_counts_separate(monkeypatch, tmp_path):
    database = _write_snapshot(tmp_path)
    monkeypatch.setenv("GTA_SNAPSHOT_PATH", str(database))

    result = await fetch_collision_context(_toronto_context())

    collision = result.data["collision_context"]
    assert collision["total_collisions"] == 5
    assert collision["ksi_collisions"] == 1
    assert collision["ksi_fatal_collisions"] == 1
    assert collision["severe_events"][0]["pedestrian_involved"] is True
    assert collision["severe_events"][0]["cyclist_involved"] is True
    assert "not the probability" in result.message


@pytest.mark.asyncio
async def test_collision_source_caps_deduplicated_ksi_map_points(monkeypatch, tmp_path):
    database = _write_snapshot(tmp_path)
    base = datetime.now(UTC) - timedelta(days=1)
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "INSERT INTO toronto_ksi_collisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    f"cap-{index:03d}",
                    (base + timedelta(minutes=index)).isoformat(),
                    43.68,
                    -79.42,
                    0,
                    0,
                    0,
                    1,
                )
                for index in range(105)
            ],
        )
    monkeypatch.setenv("GTA_SNAPSHOT_PATH", str(database))

    result = await fetch_collision_context(_toronto_context())
    points = result.data["collision_context"]["severe_events"]

    assert result.data["collision_context"]["ksi_collisions"] == 106
    assert len(points) == 100
    assert points[0]["collision_id"] == "cap-104"


def test_address_normalization_supports_units_suffixes_and_civic_ranges():
    exact = parse_address("Unit 8, 210 Wychwood Avenue, Toronto")
    hash_unit = parse_address("#8-210 Wychwood Av, Toronto")
    ranged = parse_address("222 Wychwood Ave")
    official_range = parse_address("220-224 Wychwood Avenue")

    assert exact is not None and exact.street_key == "WYCHWOOD AVE"
    assert exact.civic_start == 210
    assert hash_unit == exact
    assert ranged is not None and official_range is not None
    assert official_range.civic_start <= ranged.civic_start <= official_range.civic_end


@pytest.mark.asyncio
async def test_building_source_requires_one_exact_or_range_match(monkeypatch, tmp_path):
    database = _write_snapshot(tmp_path)
    monkeypatch.setenv("GTA_SNAPSHOT_PATH", str(database))

    exact = await fetch_building_context(_toronto_context())
    ranged = await fetch_building_context(_toronto_context("222 Wychwood Avenue, Toronto"))
    missing = await fetch_building_context(_toronto_context("79 Thorncliffe Park Drive"))

    building = exact.data["building_context"]
    assert building["rsn"] == "1001"
    assert building["current_score"] == 86
    assert building["rating"] == "green"
    assert building["reactive_deduction"] == 2
    assert building["low_rated_categories"] == ["Balcony Guards"]
    assert ranged.data["building_context"]["rsn"] == "1002"
    assert missing.data == {}
    assert "does not prove" in missing.message


@pytest.mark.asyncio
async def test_building_source_returns_unavailable_for_ambiguous_and_outside_toronto(
    monkeypatch, tmp_path
):
    database = _write_snapshot(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO toronto_buildings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "duplicate",
                210,
                210,
                "WYCHWOOD AVE",
                "210 WYCHWOOD AVE",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "[]",
            ),
        )
    monkeypatch.setenv("GTA_SNAPSHOT_PATH", str(database))

    ambiguous = await fetch_building_context(_toronto_context())
    outside_context = _toronto_context()
    outside_context = SourceContext(
        request=outside_context.request,
        place=outside_context.place,
        geography=GeographyContext(is_toronto=False, is_gta=True),
    )
    outside = await fetch_building_context(outside_context)

    assert ambiguous.data == {}
    assert "multiple" in ambiguous.message
    assert outside.data == {}
    assert "only inside Toronto" in outside.message


def test_building_rating_thresholds_and_partition_freshness():
    assert building_rating(85) == "green"
    assert building_rating(84) == "yellow"
    assert building_rating(69) == "red"
    now = datetime.now(UTC)
    manifest = {
        "partitions": {
            "fresh": {
                "retrieved_at": now.isoformat(),
                "stale_after_days": 30,
            },
            "old": {
                "retrieved_at": (now - timedelta(days=31)).isoformat(),
                "stale_after_days": 30,
            },
        }
    }
    assert partition_is_stale(manifest, "fresh") is False
    assert partition_is_stale(manifest, "old") is True


def test_partition_refresh_preserves_snapshot_when_download_fails(monkeypatch, tmp_path):
    database = _write_snapshot(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    database_checksum = sha256_file(database)
    manifest_before = manifest_path.read_bytes()

    def fail_download(*_args, **_kwargs):
        raise RuntimeError("malformed download")

    monkeypatch.setattr("scripts.refresh_gta_snapshot._download", fail_download)

    with pytest.raises(RuntimeError, match="malformed download"):
        refresh_road_buildings_snapshot(database)

    assert sha256_file(database) == database_checksum
    assert manifest_path.read_bytes() == manifest_before


def test_bundled_road_building_snapshot_is_valid_and_below_size_budget():
    health = snapshot_health()

    assert health["ready"] is True
    assert health["artifact_bytes"] < 50 * 1024 * 1024
    assert health["tables"]["toronto_collisions"] > 0
    assert health["tables"]["toronto_ksi_collisions"] > 0
    assert health["tables"]["toronto_buildings"] > 0
