# Phase 2F Ontario Local Source Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Ontario/GTA local open-data source layer with Toronto development and parks/amenity signals as the first working implementation.

**Architecture:** Extend the backend source pipeline with a context-aware `local` source that receives the resolved `Place`, routes Toronto places to a Toronto Open Data adapter, and returns normalized local fields. Keep raw municipal rows out of API responses; use normalized fields for deterministic profile text, provenance, confidence/source status, and optional OpenAI synthesis.

**Tech Stack:** FastAPI, Pydantic, SQLite, httpx, pytest, React + Vite source-contract tests, Toronto Open Data CKAN/download resources.

---

## Source References

- Toronto Open Data Portal: https://open.toronto.ca/
- Toronto Open Data Licence: https://open.toronto.ca/open-data-licence/
- Building Permits - Active Permits catalogue details: https://data.urbandatacentre.ca/en/catalogue/city-toronto-building-permits-active-permits
- Parks and Recreation Facilities catalogue details: https://data.urbandatacentre.ca/catalogue/city-toronto-parks-and-recreation-facilities

The implementation should use live endpoints only in the thin adapter layer. Unit tests must use fixtures and mocked clients.

---

## File Structure

- Create `backend/sources/common.py`: shared `SourceContext`, `SourceResult`, and source result helpers.
- Modify `backend/models.py`: add `SourceName.LOCAL = "local"`.
- Modify `backend/pipeline.py`: pass resolved place/request context to context-aware fetchers, include local source, handle source-owned messages and updated dates, use local data in deterministic profile.
- Create `backend/sources/local.py`: local source entrypoint and Ontario/Toronto routing.
- Create `backend/sources/ontario/__init__.py`: Ontario source package marker.
- Create `backend/sources/ontario/toronto.py`: Toronto CKAN package constants, download client, pure parser/normalizer helpers.
- Modify `backend/provenance.py`: include local source in overview, trajectory support, and local amenities provenance.
- Modify `tests/test_pipeline.py`: source context, local pipeline, deterministic trajectory tests.
- Create `tests/test_local_source.py`: Ontario routing and unsupported-region tests.
- Create `tests/test_toronto_open_data.py`: Toronto parser/normalizer and mocked adapter tests.
- Modify `tests/test_provenance.py`: local provenance coverage.
- Modify `tests/test_main.py`: API-level local source status test using a coordinate-backed Toronto request.
- Modify `frontend/src/uiContract.test.js`: source contract that frontend does not need a special panel for local source.
- Modify `README.md` and `PLAN.md`: document Phase 2F after implementation.

---

## Task 1: Add Context-Aware Source Results To Pipeline

**Files:**
- Create: `backend/sources/common.py`
- Modify: `backend/models.py`
- Modify: `backend/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing pipeline tests for context-aware source fetchers and source-owned messages**

Append to `tests/test_pipeline.py`:

```python
from backend.sources.common import SourceContext, SourceResult
```

Add these tests near the existing pipeline tests:

```python
@pytest.mark.asyncio
async def test_pipeline_passes_resolved_place_to_context_aware_source():
    seen_context: SourceContext | None = None

    async def local_adapter(context: SourceContext):
        nonlocal seen_context
        seen_context = context
        return {"coverage_area": context.place.label}

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Toronto, ON"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
            SourceName.LOCAL: local_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    assert seen_context is not None
    assert seen_context.place.label == "Toronto, ON"
    assert seen_context.request.query == "Toronto, ON"
    assert any(status.source == SourceName.LOCAL for status in response.source_statuses)


@pytest.mark.asyncio
async def test_pipeline_uses_source_result_message_and_updated_at():
    async def local_adapter(_context: SourceContext):
        return SourceResult(
            data={},
            message="No local open-data adapter is configured for this region.",
            updated_at="2026-05-08T00:00:00+00:00",
        )

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Buffalo, NY"),
        source_fetchers={SourceName.LOCAL: local_adapter},
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    local_status = next(status for status in response.source_statuses if status.source == SourceName.LOCAL)
    assert local_status.status == SourceStatusCode.EMPTY
    assert local_status.message == "No local open-data adapter is configured for this region."
    assert local_status.updated_at == "2026-05-08T00:00:00+00:00"
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py::test_pipeline_passes_resolved_place_to_context_aware_source tests/test_pipeline.py::test_pipeline_uses_source_result_message_and_updated_at -q -p no:cacheprovider
```

Expected: fails because `SourceName.LOCAL`, `backend.sources.common`, and context-aware fetchers do not exist.

- [ ] **Step 3: Add shared source context/result models**

Create `backend/sources/common.py`:

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from backend.models import AnalyzeRequest, Place


@dataclass(frozen=True)
class SourceContext:
    request: AnalyzeRequest
    place: Place


@dataclass(frozen=True)
class SourceResult:
    data: dict[str, Any]
    message: str | None = None
    updated_at: str | None = None


SourceFetcher = Callable[..., Awaitable[dict[str, Any] | SourceResult | None]]
```

- [ ] **Step 4: Add the local source enum**

In `backend/models.py`, update `SourceName`:

```python
class SourceName(StrEnum):
    MAPBOX = "mapbox"
    CENSUS = "census"
    HOUSING = "housing"
    REDDIT = "reddit"
    ACCESS = "access"
    LOCAL = "local"
```

- [ ] **Step 5: Update pipeline source fetcher typing and context dispatch**

In `backend/pipeline.py`, remove the local `SourceFetcher` alias and import:

```python
import inspect
```

and:

```python
from backend.sources.common import SourceContext, SourceFetcher, SourceResult
```

Change source gathering in `analyze_neighborhood` from:

```python
    source_results = await asyncio.gather(
        *[_run_source(source, fetcher, timeout) for source, fetcher in fetchers.items()]
    )
```

to:

```python
    context = SourceContext(request=request, place=place)
    source_results = await asyncio.gather(
        *[_run_source(source, fetcher, timeout, context) for source, fetcher in fetchers.items()]
    )
```

Change `_run_source` signature and body:

```python
async def _run_source(
    source: SourceName,
    fetcher: SourceFetcher,
    timeout: float,
    context: SourceContext,
) -> tuple[SourceStatus, dict[str, Any]]:
    try:
        result = await asyncio.wait_for(_call_source(fetcher, context), timeout=timeout)
    except TimeoutError:
        return (
            SourceStatus(
                source=source,
                status=SourceStatusCode.ERROR,
                message=f"{source.value} timed out after {timeout:g}s.",
            ),
            {},
        )
    except Exception as exc:
        return (
            SourceStatus(
                source=source,
                status=SourceStatusCode.ERROR,
                message=f"{source.value} failed: {exc}",
            ),
            {},
        )

    source_result = _coerce_source_result(result)
    if not source_result.data:
        return (
            SourceStatus(
                source=source,
                status=SourceStatusCode.EMPTY,
                message=source_result.message or f"{source.value} returned no usable MVP data.",
                updated_at=source_result.updated_at,
            ),
            {},
        )

    return (
        SourceStatus(
            source=source,
            status=SourceStatusCode.SUCCESS,
            message=source_result.message or f"{source.value} data returned.",
            updated_at=source_result.updated_at,
        ),
        source_result.data,
    )
```

Add helpers below `_run_source`:

```python
async def _call_source(fetcher: SourceFetcher, context: SourceContext) -> dict[str, Any] | SourceResult | None:
    signature = inspect.signature(fetcher)
    required_parameters = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    ]
    if required_parameters:
        return await fetcher(context)
    return await fetcher()


def _coerce_source_result(result: dict[str, Any] | SourceResult | None) -> SourceResult:
    if isinstance(result, SourceResult):
        return result
    return SourceResult(data=result or {})
```

- [ ] **Step 6: Run the focused tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py::test_pipeline_passes_resolved_place_to_context_aware_source tests/test_pipeline.py::test_pipeline_uses_source_result_message_and_updated_at -q -p no:cacheprovider
```

Expected: both tests pass.

- [ ] **Step 7: Run full pipeline tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py -q -p no:cacheprovider
```

Expected: all pipeline tests pass, including existing no-argument source fetchers.

- [ ] **Step 8: Commit**

Run:

```powershell
git add backend/models.py backend/pipeline.py backend/sources/common.py tests/test_pipeline.py
git commit -m "Add context-aware source results"
```

---

## Task 2: Add Local Source Routing And Unsupported Region Behavior

**Files:**
- Create: `backend/sources/local.py`
- Modify: `backend/pipeline.py`
- Create: `tests/test_local_source.py`

- [ ] **Step 1: Write failing tests for local routing**

Create `tests/test_local_source.py`:

```python
import pytest

from backend.models import Coordinates, Place
from backend.sources.common import SourceContext
from backend.sources.local import fetch_local_context, is_ontario_place, is_toronto_place
from backend.models import AnalyzeRequest


def _context(place: Place) -> SourceContext:
    return SourceContext(request=AnalyzeRequest(query=place.label), place=place)


def test_detects_toronto_and_ontario_places():
    toronto = Place(
        label="Kensington Market, Toronto, ON",
        city="Toronto",
        state="ON",
        coordinates=Coordinates(lat=43.654, lng=-79.401),
    )

    assert is_ontario_place(toronto) is True
    assert is_toronto_place(toronto) is True


def test_detects_ontario_from_label_when_mapbox_context_is_thin():
    place = Place(
        label="Pickering, Ontario, Canada",
        coordinates=Coordinates(lat=43.8384, lng=-79.0868),
    )

    assert is_ontario_place(place) is True
    assert is_toronto_place(place) is False


@pytest.mark.asyncio
async def test_local_source_returns_empty_for_unsupported_ontario_municipality():
    place = Place(
        label="Pickering, Ontario, Canada",
        city="Pickering",
        state="Ontario",
        coordinates=Coordinates(lat=43.8384, lng=-79.0868),
    )

    result = await fetch_local_context(_context(place))

    assert result.data == {}
    assert result.message == "No local Ontario adapter is available yet for Pickering."


@pytest.mark.asyncio
async def test_local_source_returns_empty_for_non_ontario_region():
    place = Place(
        label="East Austin, Austin, TX",
        city="Austin",
        state="TX",
        coordinates=Coordinates(lat=30.2636, lng=-97.7114),
    )

    result = await fetch_local_context(_context(place))

    assert result.data == {}
    assert result.message == "No local open-data adapter is configured for this region."


@pytest.mark.asyncio
async def test_local_source_returns_empty_without_coordinates():
    place = Place(label="Toronto, ON", city="Toronto", state="ON")

    result = await fetch_local_context(_context(place))

    assert result.data == {}
    assert result.message == "Local open-data lookup needs resolved coordinates."
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_source.py -q -p no:cacheprovider
```

Expected: fails because `backend.sources.local` does not exist.

- [ ] **Step 3: Implement local source routing**

Create `backend/sources/local.py`:

```python
from backend.models import Place
from backend.sources.common import SourceContext, SourceResult


async def fetch_local_context(context: SourceContext) -> SourceResult:
    place = context.place
    if place.coordinates is None:
        return SourceResult(
            data={},
            message="Local open-data lookup needs resolved coordinates.",
        )

    if is_toronto_place(place):
        from backend.sources.ontario.toronto import fetch_toronto_context

        return await fetch_toronto_context(context)

    if is_ontario_place(place):
        municipality = place.city or _first_label_part(place.label)
        return SourceResult(
            data={},
            message=f"No local Ontario adapter is available yet for {municipality}.",
        )

    return SourceResult(
        data={},
        message="No local open-data adapter is configured for this region.",
    )


def is_ontario_place(place: Place) -> bool:
    values = _place_tokens(place)
    return any(value in {"on", "ontario"} for value in values)


def is_toronto_place(place: Place) -> bool:
    values = _place_tokens(place)
    return "toronto" in values


def _place_tokens(place: Place) -> set[str]:
    raw_values = [place.label, place.city or "", place.state or ""]
    tokens: set[str] = set()
    for value in raw_values:
        lowered = value.lower().replace(",", " ")
        tokens.update(part.strip() for part in lowered.split() if part.strip())
    return tokens


def _first_label_part(label: str) -> str:
    return label.split(",", maxsplit=1)[0].strip() or "this municipality"
```

- [ ] **Step 4: Add temporary Toronto adapter stub**

Create `backend/sources/ontario/__init__.py`:

```python
"""Ontario municipal open-data adapters."""
```

Create `backend/sources/ontario/toronto.py`:

```python
from backend.sources.common import SourceContext, SourceResult


async def fetch_toronto_context(_context: SourceContext) -> SourceResult:
    return SourceResult(
        data={},
        message="Toronto local open-data adapter is configured but returned no usable data.",
    )
```

This stub is replaced in Task 4 after parser tests exist.

- [ ] **Step 5: Wire local source into default pipeline fetchers**

In `backend/pipeline.py`, import:

```python
from backend.sources.local import fetch_local_context
```

Update `DEFAULT_SOURCE_FETCHERS`:

```python
DEFAULT_SOURCE_FETCHERS: dict[SourceName, SourceFetcher] = {
    SourceName.CENSUS: fetch_census_context,
    SourceName.HOUSING: fetch_housing_context,
    SourceName.REDDIT: fetch_reddit_context,
    SourceName.ACCESS: fetch_access_context,
    SourceName.LOCAL: fetch_local_context,
}
```

- [ ] **Step 6: Run local source and pipeline tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_source.py tests/test_pipeline.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/pipeline.py backend/sources/local.py backend/sources/ontario/__init__.py backend/sources/ontario/toronto.py tests/test_local_source.py
git commit -m "Add Ontario local source routing"
```

---

## Task 3: Add Toronto Open Data Parser And Normalizer

**Files:**
- Modify: `backend/sources/ontario/toronto.py`
- Create: `tests/test_toronto_open_data.py`

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_toronto_open_data.py`:

```python
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
            "properties": {"AssetName": "Bellevue Square Park", "Type": "Park", "Amenity": "Playground"},
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
            "properties": {"AssetName": "Far Park", "Type": "Park", "Amenity": "Trail"},
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
            "properties": {"AssetName": "Bellevue Square Park", "Type": "Park", "Amenity": "Playground"},
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
```

- [ ] **Step 2: Run parser tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_toronto_open_data.py -q -p no:cacheprovider
```

Expected: fails because the Toronto parser functions do not exist.

- [ ] **Step 3: Implement parser helpers and constants**

Replace `backend/sources/ontario/toronto.py` with:

```python
from __future__ import annotations

from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx

from backend.models import Coordinates
from backend.sources.common import SourceContext, SourceResult

TORONTO_PERMITS_PACKAGE_URL = (
    "https://open.toronto.ca/api/3/action/package_show"
    "?id=building-permits-active-permits"
)
TORONTO_PARKS_PACKAGE_URL = (
    "https://open.toronto.ca/api/3/action/package_show"
    "?id=parks-and-recreation-facilities"
)
TORONTO_RADIUS_KM = 1.5
MAJOR_PERMIT_KEYWORDS = ("new building", "demolition", "addition")


async def fetch_toronto_context(context: SourceContext) -> SourceResult:
    if context.place.coordinates is None:
        return SourceResult(data={}, message="Toronto local lookup needs resolved coordinates.")

    async with httpx.AsyncClient(timeout=8) as client:
        permits_payload = await _download_package_resource(
            client,
            TORONTO_PERMITS_PACKAGE_URL,
            preferred_formats=("JSON",),
        )
        parks_payload = await _download_package_resource(
            client,
            TORONTO_PARKS_PACKAGE_URL,
            preferred_formats=("GeoJSON", "JSON"),
            preferred_name="4326.geojson",
        )

    permit_records = permits_payload if isinstance(permits_payload, list) else permits_payload.get("records", [])
    amenity_records = parks_payload.get("features", []) if isinstance(parks_payload, dict) else []
    updated_at = datetime.now(UTC).isoformat()
    data = normalize_toronto_open_data(
        permit_records,
        amenity_records,
        context.place.coordinates,
        updated_at=updated_at,
    )
    if not _has_meaningful_local_data(data):
        return SourceResult(
            data={},
            message="Toronto open data returned no nearby development or parks signals.",
            updated_at=updated_at,
        )
    return SourceResult(
        data=data,
        message="Toronto open data returned development and parks signals.",
        updated_at=updated_at,
    )


def normalize_toronto_open_data(
    permit_records: list[dict[str, Any]],
    amenity_records: list[dict[str, Any]],
    center: Coordinates,
    *,
    updated_at: str,
) -> dict[str, Any]:
    permits = summarize_permit_records(permit_records, center, radius_km=TORONTO_RADIUS_KM)
    amenities = summarize_amenity_records(amenity_records, center, radius_km=TORONTO_RADIUS_KM)
    return {
        "coverage_area": "Toronto",
        **permits,
        **amenities,
        "summary": "Toronto open data returned nearby development and parks/amenity signals.",
        "updated_at": updated_at,
    }


def summarize_permit_records(
    records: list[dict[str, Any]],
    center: Coordinates,
    *,
    radius_km: float,
) -> dict[str, Any]:
    nearby = [record for record in records if _is_nearby(record, center, radius_km)]
    major = [record for record in nearby if _is_major_permit(record)]
    development_activity = _clamp_score(len(nearby) * 12 + len(major) * 8)
    trajectory_signal = "uncertain"
    if development_activity >= 50 or len(major) >= 3:
        trajectory_signal = "rising"
    elif nearby:
        trajectory_signal = "stable"
    return {
        "development_activity": development_activity,
        "recent_permits_count": len(nearby),
        "major_project_count": len(major),
        "trajectory_signal": trajectory_signal,
    }


def summarize_amenity_records(
    records: list[dict[str, Any]],
    center: Coordinates,
    *,
    radius_km: float,
) -> dict[str, Any]:
    nearby = [record for record in records if _is_nearby(record, center, radius_km)]
    parks = [_asset_name(record) for record in nearby if _record_text(record).find("park") >= 0]
    community = [
        _asset_name(record)
        for record in nearby
        if "community recreation centre" in _record_text(record)
    ]
    parks_count = len({name for name in parks if name})
    community_count = len({name for name in community if name})
    return {
        "parks_count": parks_count,
        "community_amenities_count": community_count,
        "parks_outdoors": _clamp_score(parks_count * 12 + community_count * 4),
    }


def _is_nearby(record: dict[str, Any], center: Coordinates, radius_km: float) -> bool:
    coordinates = _record_coordinates(record)
    if coordinates is None:
        return False
    return _distance_km(center, coordinates) <= radius_km


def _record_coordinates(record: dict[str, Any]) -> Coordinates | None:
    geometry = record.get("geometry")
    if isinstance(geometry, dict):
        raw = geometry.get("coordinates")
        if isinstance(raw, list) and len(raw) >= 2:
            lng = _to_float(raw[0])
            lat = _to_float(raw[1])
            if lat is not None and lng is not None:
                return Coordinates(lat=lat, lng=lng)

    lat = _first_float(record, ("LATITUDE", "latitude", "Lat", "lat", "Y"))
    lng = _first_float(record, ("LONGITUDE", "longitude", "Lon", "lng", "X"))
    if lat is None or lng is None:
        return None
    return Coordinates(lat=lat, lng=lng)


def _first_float(record: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _to_float(record.get(key))
        if value is not None:
            return value
    return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_major_permit(record: dict[str, Any]) -> bool:
    text = _record_text(record)
    return any(keyword in text for keyword in MAJOR_PERMIT_KEYWORDS)


def _record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in record.values():
        if isinstance(value, dict):
            parts.extend(str(item) for item in value.values())
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def _asset_name(record: dict[str, Any]) -> str:
    properties = record.get("properties")
    if isinstance(properties, dict):
        return str(properties.get("AssetName") or properties.get("asset_name") or "")
    return str(record.get("AssetName") or record.get("asset_name") or "")


def _distance_km(start: Coordinates, end: Coordinates) -> float:
    earth_radius_km = 6371.0
    lat1 = radians(start.lat)
    lat2 = radians(end.lat)
    delta_lat = radians(end.lat - start.lat)
    delta_lng = radians(end.lng - start.lng)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lng / 2) ** 2
    return 2 * earth_radius_km * asin(sqrt(value))


def _clamp_score(value: int | float) -> int:
    return max(0, min(100, int(value)))


def _has_meaningful_local_data(data: dict[str, Any]) -> bool:
    return any(
        int(data.get(key, 0) or 0) > 0
        for key in (
            "recent_permits_count",
            "major_project_count",
            "parks_count",
            "community_amenities_count",
        )
    )


async def _download_package_resource(
    client: httpx.AsyncClient,
    package_url: str,
    *,
    preferred_formats: tuple[str, ...],
    preferred_name: str | None = None,
) -> Any:
    package_response = await client.get(package_url)
    package_response.raise_for_status()
    package_payload = package_response.json()
    resources = package_payload.get("result", {}).get("resources", [])
    resource = _select_resource(
        resources,
        preferred_formats=preferred_formats,
        preferred_name=preferred_name,
    )
    resource_response = await client.get(resource["url"])
    resource_response.raise_for_status()
    return resource_response.json()


def _select_resource(
    resources: list[dict[str, Any]],
    *,
    preferred_formats: tuple[str, ...],
    preferred_name: str | None,
) -> dict[str, Any]:
    normalized_formats = {item.lower() for item in preferred_formats}
    for resource in resources:
        name = str(resource.get("name") or "").lower()
        resource_format = str(resource.get("format") or "").lower()
        if preferred_name and preferred_name.lower() not in name:
            continue
        if resource_format in normalized_formats and resource.get("url"):
            return resource
    for resource in resources:
        resource_format = str(resource.get("format") or "").lower()
        if resource_format in normalized_formats and resource.get("url"):
            return resource
    raise ValueError(f"No Toronto resource found for formats: {', '.join(preferred_formats)}")
```

- [ ] **Step 4: Run parser tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_toronto_open_data.py -q -p no:cacheprovider
```

Expected: parser tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add backend/sources/ontario/toronto.py tests/test_toronto_open_data.py
git commit -m "Add Toronto open data normalizers"
```

---

## Task 4: Add Mocked Toronto Adapter Integration Tests

**Files:**
- Modify: `tests/test_toronto_open_data.py`
- Modify: `backend/sources/ontario/toronto.py`

- [ ] **Step 1: Write failing tests for mocked HTTP adapter behavior**

Append to `tests/test_toronto_open_data.py`:

```python
import httpx
import pytest

from backend.models import AnalyzeRequest, Place
from backend.sources.common import SourceContext
from backend.sources.ontario import toronto
from backend.sources.ontario.toronto import fetch_toronto_context
```

Append tests:

```python
class FakeAsyncClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url):
        self.urls.append(url)
        return self.responses.pop(0)


def _response(payload):
    return httpx.Response(200, json=payload, request=httpx.Request("GET", "https://example.test"))


def _toronto_context() -> SourceContext:
    place = Place(
        label="Kensington Market, Toronto, ON",
        city="Toronto",
        state="ON",
        coordinates=CENTER,
    )
    return SourceContext(request=AnalyzeRequest(query=place.label), place=place)


@pytest.mark.asyncio
async def test_fetch_toronto_context_downloads_and_normalizes(monkeypatch):
    client = FakeAsyncClient(
        [
            _response(
                {
                    "result": {
                        "resources": [
                            {
                                "name": "building-permits-active-permits.json",
                                "format": "JSON",
                                "url": "https://example.test/permits.json",
                            }
                        ]
                    }
                }
            ),
            _response(
                [
                    {
                        "LATITUDE": "43.6542",
                        "LONGITUDE": "-79.4008",
                        "PERMIT_TYPE": "New Building",
                    }
                ]
            ),
            _response(
                {
                    "result": {
                        "resources": [
                            {
                                "name": "Parks and Recreation Facilities - 4326.geojson",
                                "format": "GeoJSON",
                                "url": "https://example.test/parks.geojson",
                            }
                        ]
                    }
                }
            ),
            _response(
                {
                    "features": [
                        {
                            "geometry": {"coordinates": [-79.401, 43.654]},
                            "properties": {"AssetName": "Bellevue Square Park", "Type": "Park"},
                        }
                    ]
                }
            ),
        ]
    )
    monkeypatch.setattr(toronto.httpx, "AsyncClient", lambda **_kwargs: client)

    result = await fetch_toronto_context(_toronto_context())

    assert result.data["coverage_area"] == "Toronto"
    assert result.data["recent_permits_count"] == 1
    assert result.data["parks_count"] == 1
    assert result.message == "Toronto open data returned development and parks signals."
    assert client.urls == [
        toronto.TORONTO_PERMITS_PACKAGE_URL,
        "https://example.test/permits.json",
        toronto.TORONTO_PARKS_PACKAGE_URL,
        "https://example.test/parks.geojson",
    ]


@pytest.mark.asyncio
async def test_fetch_toronto_context_returns_empty_when_no_nearby_records(monkeypatch):
    client = FakeAsyncClient(
        [
            _response(
                {
                    "result": {
                        "resources": [
                            {
                                "name": "building-permits-active-permits.json",
                                "format": "JSON",
                                "url": "https://example.test/permits.json",
                            }
                        ]
                    }
                }
            ),
            _response([]),
            _response(
                {
                    "result": {
                        "resources": [
                            {
                                "name": "Parks and Recreation Facilities - 4326.geojson",
                                "format": "GeoJSON",
                                "url": "https://example.test/parks.geojson",
                            }
                        ]
                    }
                }
            ),
            _response({"features": []}),
        ]
    )
    monkeypatch.setattr(toronto.httpx, "AsyncClient", lambda timeout: client)

    result = await fetch_toronto_context(_toronto_context())

    assert result.data == {}
    assert result.message == "Toronto open data returned no nearby development or parks signals."
```

- [ ] **Step 2: Run mocked adapter tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_toronto_open_data.py -q -p no:cacheprovider
```

Expected: tests pass.

- [ ] **Step 3: Commit**

Run:

```powershell
git add backend/sources/ontario/toronto.py tests/test_toronto_open_data.py
git commit -m "Wire Toronto open data adapter"
```

---

## Task 5: Use Local Data In Deterministic Profile And Provenance

**Files:**
- Modify: `backend/pipeline.py`
- Modify: `backend/provenance.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_provenance.py`

- [ ] **Step 1: Write failing deterministic profile test**

Append to `tests/test_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_pipeline_uses_local_data_for_deterministic_trajectory_and_pros():
    async def local_adapter(_context: SourceContext):
        return {
            "coverage_area": "Toronto",
            "development_activity": 72,
            "recent_permits_count": 4,
            "major_project_count": 3,
            "parks_count": 2,
            "community_amenities_count": 1,
            "parks_outdoors": 28,
            "trajectory_signal": "rising",
            "summary": "Toronto open data returned nearby development and parks/amenity signals.",
            "updated_at": "2026-05-08T00:00:00+00:00",
        }

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Kensington Market, Toronto, ON"),
        source_fetchers={
            SourceName.LOCAL: local_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    assert response.profile.trajectory.direction == TrajectoryDirection.RISING
    assert "active permit records" in response.profile.trajectory.summary
    assert any("parks" in item.lower() for item in response.profile.honest_pros)
```

- [ ] **Step 2: Write failing provenance test**

Append to `tests/test_provenance.py`:

```python
def test_build_profile_provenance_marks_local_trajectory_and_amenities_supported():
    provenance = build_profile_provenance(
        {
            SourceName.LOCAL: {
                "development_activity": 72,
                "recent_permits_count": 4,
                "trajectory_signal": "rising",
                "parks_count": 2,
                "community_amenities_count": 1,
                "parks_outdoors": 28,
            }
        },
        [_status(SourceName.LOCAL, SourceStatusCode.SUCCESS)],
    )

    items = {item.claim_id: item for item in provenance.items}
    assert items["overview"].sources == [SourceName.LOCAL]
    assert items["trajectory"].sources == [SourceName.LOCAL]
    assert "local.development_activity" in items["trajectory"].source_fields
    assert items["local.amenities"].support == "inferred"
    assert items["local.amenities"].source_fields == [
        "local.parks_count",
        "local.community_amenities_count",
        "local.parks_outdoors",
    ]
```

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py::test_pipeline_uses_local_data_for_deterministic_trajectory_and_pros tests/test_provenance.py::test_build_profile_provenance_marks_local_trajectory_and_amenities_supported -q -p no:cacheprovider
```

Expected: fails because deterministic profile and provenance do not read local fields yet.

- [ ] **Step 4: Update deterministic profile local behavior**

In `backend/pipeline.py`, inside `_build_profile`, add:

```python
    local = source_data.get(SourceName.LOCAL, {})
```

Change the `honest_pros` and `honest_cons` arguments to:

```python
        honest_pros=_build_honest_pros(local),
        honest_cons=_build_honest_cons(local),
```

Change `trajectory=` to:

```python
        trajectory=_build_trajectory(local),
```

Add helpers below `_build_profile`:

```python
def _build_honest_pros(local: dict[str, Any]) -> list[str]:
    pros = ["Profile generated with partial source-aware data."]
    parks_count = _int_from(local, "parks_count")
    amenities_count = _int_from(local, "community_amenities_count")
    if parks_count or amenities_count:
        pros.append(
            f"Toronto local open data found {parks_count} nearby parks and "
            f"{amenities_count} community amenity signals."
        )
    return pros


def _build_honest_cons(local: dict[str, Any]) -> list[str]:
    cons = ["Some source adapters may be unavailable until API keys or open-data coverage are configured."]
    development_activity = _int_from(local, "development_activity")
    if development_activity >= 50:
        cons.append(
            "Local permit signals suggest visible nearby development activity; this can mean change and construction disruption, not guaranteed affordability movement."
        )
    return cons


def _build_trajectory(local: dict[str, Any]) -> Trajectory:
    if local.get("trajectory_signal") == "rising":
        return Trajectory(
            direction=TrajectoryDirection.RISING,
            summary=(
                "Local open-data signals suggest visible development/change activity nearby, "
                "based on active permit records."
            ),
        )
    if local.get("trajectory_signal") == "stable":
        return Trajectory(
            direction=TrajectoryDirection.STABLE,
            summary="Local permit signals show some nearby activity, but not enough to mark a strong change trajectory.",
        )
    return Trajectory(
        direction=TrajectoryDirection.UNCERTAIN,
        summary="Trajectory is uncertain until housing and local trend sources return data.",
    )


def _int_from(data: dict[str, Any], key: str) -> int:
    raw = data.get(key, 0)
    return raw if isinstance(raw, int) else 0
```

Ensure no line exceeds Ruff's configured line length by wrapping the long string if needed.

- [ ] **Step 5: Update provenance local support**

In `backend/provenance.py`, update `_overview_item` tracked sources:

```python
    tracked_sources = (
        SourceName.ACCESS,
        SourceName.HOUSING,
        SourceName.CENSUS,
        SourceName.REDDIT,
        SourceName.LOCAL,
    )
```

Add this item before `_trajectory_item(...)` in `build_profile_provenance`:

```python
        _local_amenities_item(source_data, status_by_source),
```

Replace `_trajectory_item` with:

```python
def _trajectory_item(
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    trend_fields = [
        (SourceName.LOCAL, "development_activity"),
        (SourceName.LOCAL, "recent_permits_count"),
        (SourceName.LOCAL, "trajectory_signal"),
        (SourceName.HOUSING, "rent_trend"),
        (SourceName.REDDIT, "discussion_trend"),
    ]
    present_fields = [
        f"{source.value}.{field}"
        for source, field in trend_fields
        if source_data.get(source, {}).get(field) is not None
    ]
    if present_fields:
        return ProvenanceItem(
            claim_id="trajectory",
            label="Trajectory",
            summary="Trajectory is inferred from available local and trend signals.",
            support=ProvenanceSupport.INFERRED,
            sources=_sources_for_fields(trend_fields, present_fields),
            source_fields=present_fields,
        )
    return ProvenanceItem(
        claim_id="trajectory",
        label="Trajectory",
        summary=(
            "Trajectory is unavailable because trend fields are missing; "
            f"{_status_summary(SourceName.LOCAL, status_by_source)}; "
            f"{_status_summary(SourceName.HOUSING, status_by_source)}; "
            f"{_status_summary(SourceName.REDDIT, status_by_source)}."
        ),
        support=ProvenanceSupport.UNAVAILABLE,
        sources=[SourceName.LOCAL, SourceName.HOUSING, SourceName.REDDIT],
        source_fields=[],
    )
```

Add `_local_amenities_item` before `_trajectory_item`:

```python
def _local_amenities_item(
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    fields = ["parks_count", "community_amenities_count", "parks_outdoors"]
    present_fields = [
        f"local.{field}"
        for field in fields
        if source_data.get(SourceName.LOCAL, {}).get(field) is not None
    ]
    if present_fields:
        return ProvenanceItem(
            claim_id="local.amenities",
            label="Local parks and amenities",
            summary="Local amenities are inferred from normalized municipal parks and facility signals.",
            support=ProvenanceSupport.INFERRED,
            sources=[SourceName.LOCAL],
            source_fields=present_fields,
        )
    return ProvenanceItem(
        claim_id="local.amenities",
        label="Local parks and amenities",
        summary=f"Local amenities are unavailable because {_status_summary(SourceName.LOCAL, status_by_source)}.",
        support=ProvenanceSupport.UNAVAILABLE,
        sources=[SourceName.LOCAL],
        source_fields=[],
    )
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py::test_pipeline_uses_local_data_for_deterministic_trajectory_and_pros tests/test_provenance.py -q -p no:cacheprovider
```

Expected: tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/pipeline.py backend/provenance.py tests/test_pipeline.py tests/test_provenance.py
git commit -m "Use local source in profiles and provenance"
```

---

## Task 6: Add API Contract Coverage And Frontend Source Contract

**Files:**
- Modify: `tests/test_main.py`
- Modify: `frontend/src/uiContract.test.js`

- [ ] **Step 1: Add backend API test for local source status**

Add this import to `tests/test_main.py`:

```python
from backend.sources.common import SourceResult
```

Append to `tests/test_main.py`:

```python
def test_analyze_includes_local_source_status_for_toronto_coordinates(monkeypatch):
    _test_sqlite_path(monkeypatch)

    async def fake_toronto_context(_context):
        return SourceResult(
            data={
                "coverage_area": "Toronto",
                "development_activity": 72,
                "recent_permits_count": 4,
                "major_project_count": 3,
                "parks_count": 2,
                "community_amenities_count": 1,
                "parks_outdoors": 28,
                "trajectory_signal": "rising",
                "summary": "Toronto open data returned nearby development and parks/amenity signals.",
                "updated_at": "2026-05-08T00:00:00+00:00",
            },
            message="Toronto open data returned development and parks signals.",
            updated_at="2026-05-08T00:00:00+00:00",
        )

    monkeypatch.setattr(
        "backend.sources.ontario.toronto.fetch_toronto_context",
        fake_toronto_context,
    )
    client = TestClient(app)

    response = client.post(
        "/analyze",
        json={
            "query": "Kensington Market, Toronto, ON",
            "coordinates": {"lat": 43.654, "lng": -79.401},
            "generic_mode": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    local_status = next(status for status in body["source_statuses"] if status["source"] == "local")
    assert local_status["status"] == "success"
    assert local_status["message"] == "Toronto open data returned development and parks signals."
    assert local_status["updated_at"] == "2026-05-08T00:00:00+00:00"
    assert body["profile"]["trajectory"]["direction"] == "rising"
```

- [ ] **Step 2: Add frontend source contract test**

Append to `frontend/src/uiContract.test.js`:

```javascript
test('local open data uses existing source and provenance UI', () => {
  const confidence = source('src/components/Confidence.jsx');
  const provenance = source('src/components/Provenance.jsx');
  const profile = source('src/components/Profile.jsx');

  assert.match(confidence, /statuses\?\.map/);
  assert.match(provenance, /provenance\.items/);
  assert.equal(profile.includes('LocalOpenData'), false);
});
```

- [ ] **Step 3: Run new tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_main.py::test_analyze_includes_local_source_status_for_toronto_coordinates -q -p no:cacheprovider
node --test frontend/src/uiContract.test.js
```

Expected: backend test passes without live Toronto Open Data calls; UI contract passes because local data uses existing generic source/provenance rendering.

- [ ] **Step 4: Commit**

Run:

```powershell
git add tests/test_main.py frontend/src/uiContract.test.js
git commit -m "Cover local source API and UI contracts"
```

---

## Task 7: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`

- [ ] **Step 1: Update README current scope**

In `README.md`, add this bullet under Current Scope:

```markdown
- Ontario-first local open-data source depth with Toronto development and parks/amenity signals.
```

Update the Phase 2 Status paragraph to:

```markdown
Phase 2A added explicit local saved neighborhood reports. Phase 2B added reusable local preference profiles and then corrected the UI so profiles work as an app-level analysis lens selected before address search. Phase 2C adds typed provenance and compact source-support UI so major claims can be traced to normalized source signals. Phase 2D adds a dedicated compare mode for 2-4 ad hoc places using the active preference profile or Generic lens. Phase 2E adds source freshness labels and single-place refresh controls for current and saved reports. Phase 2F adds Ontario-first local open-data depth with Toronto development and parks/amenity signals, while unsupported Ontario municipalities degrade honestly. The next slices should focus on expanding Durham/Pickering coverage, preference scoring depth, and share/export flows.
```

- [ ] **Step 2: Update PLAN Phase 2 checklist**

In `PLAN.md`, under `### Phase 2 - Comparison, Sharing, And Provenance`, add:

```markdown
- [x] Add Ontario-first local open-data source depth with Toronto development and parks/amenity signals.
```

Keep the existing public share URL and regression-test items unchanged unless new tests make the regression-test item fully complete.

- [ ] **Step 3: Run backend verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check backend tests
```

Expected: all backend tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 4: Run frontend verification**

Run:

```powershell
node --test frontend/src/utils/api.test.js
node --test frontend/src/utils/compareUtils.test.js
node --test frontend/src/utils/freshness.test.js
node --test frontend/src/utils/preferenceProfiles.test.js
node --test frontend/src/utils/searchState.test.js
node --test frontend/src/uiContract.test.js
Push-Location frontend
npm.cmd run build
Pop-Location
```

Expected: Node tests pass and Vite build succeeds. The existing large Mapbox chunk warning is acceptable.

- [ ] **Step 5: Manual smoke checklist**

Start local backend/frontend and verify:

- Analyze `Kensington Market, Toronto, ON` with coordinates or a resolved Toronto place.
- Confirm the source list includes `local`.
- Confirm local status is success, empty, or error with an honest Toronto/local message.
- If live Toronto data succeeds, confirm trajectory/pros mention local development or parks signals.
- Analyze `Pickering, Ontario, Canada` and confirm it does not reuse Toronto data.
- Analyze a non-Ontario place and confirm local source degrades cleanly.
- Save and refresh a Toronto report; confirm the saved report ID is preserved.
- Confirm compare mode still works.

- [ ] **Step 6: Commit docs**

Run:

```powershell
git add README.md PLAN.md
git commit -m "Document Ontario local source depth"
```

- [ ] **Step 7: Final status**

Run:

```powershell
git status --short --branch
```

Expected: no staged changes. Existing untracked `.tmp/` may remain and should not be staged.
