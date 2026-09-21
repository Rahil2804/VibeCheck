import json
import sqlite3
import zipfile
from io import BytesIO
from datetime import date

import pytest
from openpyxl import Workbook

from backend.models import (
    AnalyzeRequest,
    Coordinates,
    Place,
    RentalUnitSize,
    SourceName,
)
from backend.census_bundle import lookup_bundled_census_subdivision
from backend.geography import resolve_geography
from backend.score_signals import resolve_score_support, resolve_vibe_scores
from backend.pipeline import _build_profile
from backend.sources.common import SourceContext
from backend.sources.cycling import score_cycling_access
from backend.sources.housing import lookup_rent_benchmark
from backend.sources.transit import fetch_transit_context, score_scheduled_transit
from scripts.refresh_gta_snapshot import (
    _create_schema,
    active_service_ids,
    normalize_cmhc_workbook,
    normalize_census_subdivisions,
    parse_gtfs_time,
)
from scripts import refresh_gta_snapshot


def test_gtfs_calendar_exceptions_and_after_midnight_times():
    calendar = [
        {
            "service_id": "weekday",
            "monday": "1",
            "tuesday": "1",
            "wednesday": "1",
            "thursday": "1",
            "friday": "1",
            "saturday": "0",
            "sunday": "0",
            "start_date": "20260901",
            "end_date": "20260930",
        }
    ]
    exceptions = [
        {"service_id": "weekday", "date": "20260915", "exception_type": "2"},
        {"service_id": "special", "date": "20260915", "exception_type": "1"},
    ]

    assert active_service_ids(calendar, exceptions, date(2026, 9, 15)) == {"special"}
    assert parse_gtfs_time("25:10:30") == 90630
    assert parse_gtfs_time("25:70:00") is None


def test_transit_score_deduplicates_routes_and_directions_across_nearby_stops():
    rows = [
        _transit_row("TTC", "1", "0", 6, 250),
        _transit_row("TTC", "1", "0", 8, 300),
        _transit_row("TTC", "1", "1", 8, 300),
        _transit_row("GO", "LW", "0", 2, 1_000, route_type=2, regional=True),
    ]

    context = score_scheduled_transit(rows, covered_agencies=["GO", "TTC"])

    assert context["scheduled_departures_per_hour"] == 18
    assert context["nearby_route_count"] == 2
    assert context["rapid_or_regional_access"] is True
    assert context["score"] <= 100


def test_transit_returns_zero_only_when_snapshot_covers_the_location():
    context = score_scheduled_transit([], covered_agencies=["MiWay"])

    assert context["score"] == 0
    assert context["agencies"] == ["MiWay"]


@pytest.mark.asyncio
async def test_expired_feed_is_unavailable(monkeypatch, tmp_path):
    database = tmp_path / "gta_snapshot.sqlite"
    with sqlite3.connect(database) as connection:
        _create_schema(connection)
        connection.execute(
            "INSERT INTO feed_status VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "TTC",
                "https://example.test",
                "2020-01-01",
                "2020-01-31",
                43.5,
                44.0,
                -80,
                -79,
            ),
        )
    manifest = {
        "schema_version": 1,
        "snapshot_id": "fixture",
        "edition": "Fixture",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("GTA_SNAPSHOT_PATH", str(database))
    place = Place(
        label="Toronto",
        city="Toronto",
        coordinates=Coordinates(lat=43.65, lng=-79.4),
    )

    result = await fetch_transit_context(
        SourceContext(request=AnalyzeRequest(query="Toronto"), place=place)
    )

    assert result.data == {}
    assert result.stale is True


def test_osm_transit_is_a_labelled_fallback_not_equivalent_support():
    source_data = {
        SourceName.ACCESS: {
            "transit_access": 62,
            "nearby_categories": {"transit": 4},
        }
    }

    assert resolve_vibe_scores(source_data).transit_access == 62
    assert resolve_score_support(source_data)["transit_access"] == [
        "access.transit_access"
    ]
    profile = _build_profile(Place(label="Fallback place"), source_data)
    assert profile.transit_context is not None
    assert profile.transit_context.fallback is True
    assert profile.transit_context.nearby_stop_count == 4


def test_cycling_uses_common_network_formula_and_keeps_stations_as_context():
    context = score_cycling_access(
        [
            {"distance_m": 300, "length_m": 3_000, "protected": True},
            {"distance_m": 700, "length_m": 2_000, "protected": False},
            {"distance_m": 1_100, "length_m": 9_000, "protected": True},
        ],
        [{"distance_m": 500} for _ in range(5)] + [{"distance_m": 900}],
    )

    assert context == {
        "score": 100,
        "protected_network_km": 3.0,
        "total_network_km": 5.0,
        "bike_share_stations": 5,
    }


def test_rent_lookup_preserves_unit_and_suppression_quality(tmp_path):
    database = tmp_path / "fixture.sqlite"
    with sqlite3.connect(database) as connection:
        _create_schema(connection)
        connection.execute(
            "INSERT INTO rent_benchmarks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "3521024",
                "Caledon",
                "studio",
                None,
                None,
                None,
                None,
                1,
                "CMHC 2025 Rental Market Report",
                2025,
                "https://example.test/cmhc",
            ),
        )
        connection.row_factory = sqlite3.Row
        benchmark = lookup_rent_benchmark(connection, "3521024", RentalUnitSize.STUDIO)

    assert benchmark is not None
    assert benchmark["unit_size"] == "studio"
    assert benchmark["monthly_rent"] is None
    assert benchmark["suppressed"] is True


def test_bundled_census_boundaries_resolve_east_york_coordinates(
    monkeypatch,
    tmp_path,
):
    database = tmp_path / "gta_snapshot.sqlite"
    boundaries = {
        "features": [
            {
                "properties": {
                    "CSDUID": "3520005",
                    "CSDNAME": "Toronto",
                    "CSDTYPE": "C",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-79.37, 43.69],
                            [-79.33, 43.69],
                            [-79.33, 43.72],
                            [-79.37, 43.72],
                            [-79.37, 43.69],
                        ]
                    ],
                },
            }
        ]
    }
    csv_content = (
        "DGUID,CHARACTERISTIC_NAME,C1_COUNT_TOTAL\n"
        '2021A00053520005,Population density per square kilometre,"4,427.8"\n'
        '2021A00053520005,Median monthly shelter costs for rented dwellings ($),"1,650"\n'
        "2021A00053520005,% of tenant households spending 30% or more of its income on shelter costs,36.2\n"
        "2021A00052466023,Caractère français écarté,1\n"
    )
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("profile.csv", csv_content.encode("cp1252"))
    monkeypatch.setattr(refresh_gta_snapshot, "GTA_CSD_IDS", {"3520005"})
    with sqlite3.connect(database) as connection:
        _create_schema(connection)
        normalize_census_subdivisions(connection, boundaries, archive.getvalue())
    monkeypatch.setenv("GTA_SNAPSHOT_PATH", str(database))
    point = Coordinates(lat=43.706, lng=-79.35)

    bundled = lookup_bundled_census_subdivision(point)
    geography = resolve_geography(
        Place(label="79 Thorncliffe Park Drive", city="East York", coordinates=point)
    )

    assert bundled["census_subdivision_id"] == "3520005"
    assert bundled["population_density"] == 4427.8
    assert geography.is_toronto is True
    assert geography.census_subdivision_name == "Toronto"
    assert geography.resolution == "bundled official boundary"


def test_resolved_coordinates_prevent_toronto_text_from_overriding_geography():
    geography = resolve_geography(
        Place(
            label="Toronto, Ohio",
            city="Toronto",
            coordinates=Coordinates(lat=40.4642, lng=-80.6009),
        )
    )

    assert geography.is_toronto is False
    assert geography.is_gta is False
    assert geography.census_subdivision_id is None


def test_cmhc_normalizer_selects_2025_rent_and_vacancy_columns(monkeypatch):
    monkeypatch.setattr(
        refresh_gta_snapshot,
        "RENT_GEOGRAPHIES",
        {"3520005": ("Toronto", "City of Toronto")},
    )
    workbook = Workbook()
    rents = workbook.active
    rents.title = "Table 1.1.2"
    vacancy = workbook.create_sheet("Table 1.1.1")
    rent_row = [None] * 21
    rent_row[0] = "Former City of Toronto (Zones 1-4)"
    rents.append(rent_row)
    rent_row = [None] * 21
    rent_row[0] = "City of Toronto (Zones 1-17)"
    for index, value in {
        3: 1499,
        4: "a",
        7: 1763,
        8: "a",
        11: 2055,
        12: "a",
        15: 2361,
        16: "a",
    }.items():
        rent_row[index] = value
    rents.append(rent_row)
    vacancy_row = [None] * 26
    vacancy_row[0] = "City of Toronto (Zones 1-17)"
    for index, value in {
        3: 4.2,
        4: "a",
        8: 3.5,
        9: "a",
        13: 2.1,
        14: "a",
        18: 1.8,
        19: "b",
    }.items():
        vacancy_row[index] = value
    vacancy.append(vacancy_row)
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    _create_schema(connection)

    normalize_cmhc_workbook(connection, stream.getvalue())
    benchmark = lookup_rent_benchmark(connection, "3520005", RentalUnitSize.ONE_BEDROOM)
    connection.close()

    assert benchmark is not None
    assert benchmark["monthly_rent"] == 1763
    assert benchmark["vacancy_rate"] == 3.5
    assert benchmark["quality_code"] == "a"
    assert benchmark["suppressed"] is False


def _transit_row(
    agency: str,
    route_id: str,
    direction_id: str,
    frequency: float,
    distance: float,
    *,
    route_type: int = 3,
    regional: bool = False,
) -> dict[str, object]:
    return {
        "agency": agency,
        "route_id": route_id,
        "route_name": route_id,
        "direction_id": direction_id,
        "departures_per_hour": frequency,
        "distance_m": distance,
        "route_type": route_type,
        "is_regional": regional,
        "service_date": "2026-09-15",
    }
