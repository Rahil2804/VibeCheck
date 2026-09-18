from datetime import timedelta
from io import BytesIO

import httpx
import pytest
from openpyxl import Workbook

from backend.coverage import build_coverage
from backend.models import Coordinates, Place, VibeScores
from backend.source_cache import get_cached_source, set_cached_source
from backend.sources.census import (
    _response_json,
    normalize_census_profile,
    normalize_geography_response,
)
from backend.sources.housing import CMHC_GTA_SNAPSHOT, normalize_cmhc_snapshot
from backend.sources.ontario.toronto_profiles import (
    normalize_toronto_neighbourhood_profile,
)


def test_statistics_canada_trimmed_fixtures_keep_only_neutral_context():
    geography = normalize_geography_response(
        {
            "features": [
                {"attributes": {"DAUID": "35200123", "DGUID": "2021S051235200123"}}
            ]
        }
    )
    profile = normalize_census_profile(
        {
            "DATA": [
                {
                    "CHARACTERISTIC_NAME": "Population density per square kilometre",
                    "C1_COUNT_TOTAL": "9,205.4",
                },
                {
                    "CHARACTERISTIC_NAME": "Median monthly shelter costs for rented dwellings ($)",
                    "C1_COUNT_TOTAL": "1,750",
                },
                {
                    "CHARACTERISTIC_NAME": (
                        "% of tenant households spending 30% or more of its income on shelter costs"
                    ),
                    "C1_COUNT_TOTAL": "39.2",
                },
                {"CHARACTERISTIC_NAME": "Age", "C1_COUNT_TOTAL": "34"},
            ]
        }
    )

    assert geography == {"dauid": "35200123", "dguid": "2021S051235200123"}
    assert profile == {
        "population_density": 9205.4,
        "median_renter_shelter_cost": 1750,
        "renter_cost_burden_percent": 39.2,
    }


def test_statistics_canada_html_redirect_target_is_rejected_cleanly():
    request = httpx.Request(
        "GET", "https://www12.statcan.gc.ca/census-recensement/srvmsg/srvmsg404.html"
    )
    response = httpx.Response(
        200,
        headers={"content-type": "text/html"},
        text="<html>File not found</html>",
        request=request,
    )

    with pytest.raises(RuntimeError, match="HTML error page"):
        _response_json(response)


def test_toronto_boundary_and_workbook_join_uses_158_model_fields():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Characteristic", "Kensington-Chinatown (78)"])
    sheet.append(["Total - Age groups of the population - 25% sample data", 18000])
    sheet.append(["Median monthly shelter costs for rented dwellings ($)", 1685])
    sheet.append(
        [
            "% of tenant households spending 30% or more of its income on shelter costs",
            41.3,
        ]
    )
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    boundaries = {
        "features": [
            {
                "properties": {
                    "AREA_SHORT_CODE": "78",
                    "AREA_NAME": "Kensington-Chinatown",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-79.42, 43.64],
                            [-79.38, 43.64],
                            [-79.38, 43.68],
                            [-79.42, 43.68],
                            [-79.42, 43.64],
                        ]
                    ],
                },
            }
        ]
    }

    normalized = normalize_toronto_neighbourhood_profile(
        boundaries,
        stream.getvalue(),
        Coordinates(lat=43.654, lng=-79.401),
    )

    assert normalized["neighbourhood_id"] == "78"
    assert normalized["population_density"] > 0
    assert normalized["median_renter_shelter_cost"] == 1685
    assert normalized["renter_cost_burden_percent"] == 41.3


def test_cmhc_snapshot_is_versioned_scoped_and_cad():
    normalized = normalize_cmhc_snapshot(CMHC_GTA_SNAPSHOT)

    assert normalized["reference_year"] == 2025
    assert normalized["geographic_scope"] == "Greater Toronto Area"
    assert normalized["currency"] == "CAD"
    assert normalized["average_two_bedroom_rent"] == 2034


def test_source_cache_honours_expiry(tmp_path):
    path = tmp_path / "cache.db"
    set_cached_source("expired", {"value": 1}, ttl=timedelta(seconds=-1), db_path=path)
    set_cached_source("versioned", {"value": 2}, ttl=None, db_path=path)

    assert get_cached_source("expired", path) is None
    assert get_cached_source("versioned", path) == {"value": 2}


def test_coverage_tiers_include_supported_and_unavailable_signals():
    coverage = build_coverage(
        Place(
            label="The Annex, Toronto, ON",
            city="Toronto",
            state="ON",
            coordinates=Coordinates(lat=43.67, lng=-79.4),
        ),
        VibeScores(transit_access=80, daily_needs=72),
    )

    assert coverage.region == "toronto"
    assert coverage.level == "full"
    assert "Transit access" in coverage.supported_signals
    assert "Rent context" in coverage.unavailable_signals
