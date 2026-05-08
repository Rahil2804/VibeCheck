from backend.models import Coordinates
from backend.sources.ontario.toronto import (
    normalize_toronto_open_data,
    summarize_amenity_records,
    summarize_permit_records,
)


CENTER = Coordinates(lat=43.654, lng=-79.401)


def test_summarize_permit_records_counts_nearby_and_major_projects():
    records = [
        {
            "LATITUDE": "43.6542",
            "LONGITUDE": "-79.4008",
            "PERMIT_TYPE": "New Building",
            "STATUS": "Permit Issued",
        },
        {
            "latitude": 43.655,
            "longitude": -79.402,
            "permit_type": "Interior Alterations",
            "status": "Inspection",
        },
        {
            "LATITUDE": "43.7000",
            "LONGITUDE": "-79.5000",
            "PERMIT_TYPE": "New Building",
            "STATUS": "Permit Issued",
        },
    ]

    summary = summarize_permit_records(records, CENTER, radius_km=1.5)

    assert summary["recent_permits_count"] == 2
    assert summary["major_project_count"] == 1
    assert summary["development_activity"] == 32
    assert summary["trajectory_signal"] == "stable"


def test_summarize_permit_records_marks_rising_for_high_activity():
    records = [
        {
            "LATITUDE": "43.6542",
            "LONGITUDE": "-79.4008",
            "PERMIT_TYPE": "New Building",
            "STATUS": "Permit Issued",
        },
        {
            "LATITUDE": "43.6543",
            "LONGITUDE": "-79.4007",
            "PERMIT_TYPE": "Demolition",
            "STATUS": "Permit Issued",
        },
        {
            "LATITUDE": "43.6544",
            "LONGITUDE": "-79.4006",
            "PERMIT_TYPE": "Addition",
            "STATUS": "Permit Issued",
        },
        {
            "LATITUDE": "43.6545",
            "LONGITUDE": "-79.4005",
            "PERMIT_TYPE": "Interior Alterations",
            "STATUS": "Inspection",
        },
    ]

    summary = summarize_permit_records(records, CENTER, radius_km=1.5)

    assert summary["major_project_count"] == 3
    assert summary["development_activity"] == 72
    assert summary["trajectory_signal"] == "rising"


def test_summarize_amenity_records_counts_parks_and_recreation_centres():
    records = [
        {
            "geometry": {"coordinates": [-79.401, 43.654]},
            "properties": {
                "AssetName": "Bellevue Square Park",
                "Type": "Park",
                "Amenity": "Playground",
            },
        },
        {
            "geometry": {"coordinates": [-79.402, 43.655]},
            "properties": {
                "AssetName": "Scadding Court Community Centre",
                "Type": "Community Recreation Centre",
                "Amenity": "Pool",
            },
        },
        {
            "geometry": {"coordinates": [-79.5, 43.7]},
            "properties": {
                "AssetName": "Far Park",
                "Type": "Park",
                "Amenity": "Trail",
            },
        },
    ]

    summary = summarize_amenity_records(records, CENTER, radius_km=1.5)

    assert summary["parks_count"] == 1
    assert summary["community_amenities_count"] == 1
    assert summary["parks_outdoors"] == 16


def test_normalize_toronto_open_data_combines_permits_and_amenities():
    permits = [
        {
            "LATITUDE": "43.6542",
            "LONGITUDE": "-79.4008",
            "PERMIT_TYPE": "New Building",
            "STATUS": "Permit Issued",
        }
    ]
    amenities = [
        {
            "geometry": {"coordinates": [-79.401, 43.654]},
            "properties": {
                "AssetName": "Bellevue Square Park",
                "Type": "Park",
                "Amenity": "Playground",
            },
        }
    ]

    normalized = normalize_toronto_open_data(
        permits,
        amenities,
        CENTER,
        updated_at="2026-05-08T00:00:00+00:00",
    )

    assert normalized["coverage_area"] == "Toronto"
    assert normalized["recent_permits_count"] == 1
    assert normalized["parks_count"] == 1
    assert normalized["updated_at"] == "2026-05-08T00:00:00+00:00"
    assert "Toronto open data" in normalized["summary"]
