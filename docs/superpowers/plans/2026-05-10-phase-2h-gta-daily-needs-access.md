# GTA Daily Needs Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace placeholder access scores with conservative no-new-key OSM/Overpass-style POI scoring for coordinate-backed Toronto/GTA neighborhood analysis.

**Architecture:** Keep the access source isolated in `backend/sources/access.py`, with pure parser/scoring helpers that can be tested without network calls. The pipeline already supports context-aware source fetchers, so `fetch_access_context(context)` will receive resolved coordinates, query a bounded public POI endpoint, normalize category counts, and return a `SourceResult`.

**Tech Stack:** FastAPI backend, `httpx`, Pydantic models, pytest/pytest-asyncio, Ruff, existing React/Vite frontend unchanged.

---

## File Structure

- Modify `backend/sources/access.py`: replace static placeholder output with OSM/Overpass query building, payload normalization, category scoring, and `SourceResult` output.
- Create `tests/test_access_source.py`: pure unit tests for category mapping, dedupe, scoring, query construction, and context behavior.
- Modify `tests/test_pipeline.py`: add an integration-style pipeline test showing access data moves visible scores away from neutral.
- Modify `tests/test_provenance.py`: add a narrow provenance regression for access-backed scores after the access source becomes real.
- Modify `README.md` and `PLAN.md`: document Phase 2H no-new-key access scoring and OSM attribution.

---

### Task 1: Add Pure Access Parser And Scoring Tests

**Files:**
- Create: `tests/test_access_source.py`
- Modify: `backend/sources/access.py`

- [ ] **Step 1: Write failing parser and scoring tests**

Create `tests/test_access_source.py`:

```python
import pytest

from backend.sources.access import normalize_access_payload


def _element(element_id: int, tags: dict[str, str], element_type: str = "node") -> dict:
    return {
        "type": element_type,
        "id": element_id,
        "lat": 43.654,
        "lon": -79.401,
        "tags": tags,
    }


def test_normalize_access_payload_counts_supported_categories_and_scores_dense_area():
    payload = {
        "elements": [
            _element(1, {"shop": "supermarket"}),
            _element(2, {"shop": "convenience"}),
            _element(3, {"amenity": "pharmacy"}),
            _element(4, {"amenity": "library"}),
            _element(5, {"amenity": "restaurant"}),
            _element(6, {"amenity": "restaurant"}),
            _element(7, {"amenity": "cafe"}),
            _element(8, {"amenity": "bar"}),
            _element(9, {"highway": "bus_stop"}),
            _element(10, {"public_transport": "station"}),
            _element(11, {"railway": "subway_entrance"}),
            _element(12, {"leisure": "park"}, element_type="way"),
            _element(13, {"leisure": "playground"}, element_type="relation"),
            _element(14, {"amenity": "community_centre"}),
        ]
    }

    access = normalize_access_payload(payload)

    assert access["nearby_categories"] == {
        "groceries": 2,
        "pharmacies": 1,
        "restaurants": 2,
        "cafes": 1,
        "bars": 1,
        "transit": 3,
        "parks": 2,
        "libraries": 1,
        "community": 1,
    }
    assert access["daily_needs"] >= 70
    assert access["food_social"] >= 65
    assert access["transit_access"] >= 60
    assert access["parks_outdoors"] >= 60
    assert access["walkability"] >= 70
    assert "public POI signals" in access["summary"]


def test_normalize_access_payload_dedupes_same_osm_element():
    payload = {
        "elements": [
            _element(1, {"amenity": "restaurant"}),
            _element(1, {"amenity": "restaurant"}),
            _element(2, {"amenity": "restaurant"}),
        ]
    }

    access = normalize_access_payload(payload)

    assert access["nearby_categories"]["restaurants"] == 2
    assert access["food_social"] > 50


def test_normalize_access_payload_accepts_way_center_and_ignores_unknown_tags():
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 20,
                "center": {"lat": 43.65, "lon": -79.4},
                "tags": {"landuse": "recreation_ground"},
            },
            _element(21, {"shop": "clothes"}),
        ]
    }

    access = normalize_access_payload(payload)

    assert access["nearby_categories"]["parks"] == 1
    assert access["nearby_categories"]["groceries"] == 0


def test_normalize_access_payload_returns_low_scores_for_successful_empty_query():
    access = normalize_access_payload({"elements": []})

    assert access["nearby_categories"]["groceries"] == 0
    assert access["nearby_categories"]["transit"] == 0
    assert access["daily_needs"] == 30
    assert access["transit_access"] == 30
    assert access["food_social"] == 30
    assert access["parks_outdoors"] == 30
    assert access["walkability"] == 30


def test_normalize_access_payload_rejects_invalid_payload_shape():
    with pytest.raises(ValueError, match="Overpass payload missing elements list"):
        normalize_access_payload({"unexpected": []})
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_access_source.py -q -p no:cacheprovider
```

Expected: FAIL with `ImportError` because `normalize_access_payload` does not exist yet.

- [ ] **Step 3: Add category constants and pure normalizer**

Replace `backend/sources/access.py` with:

```python
from typing import Any

LOW_SCORE = 30

CATEGORY_KEYS = (
    "groceries",
    "pharmacies",
    "restaurants",
    "cafes",
    "bars",
    "transit",
    "parks",
    "libraries",
    "community",
)


def normalize_access_payload(payload: dict[str, Any]) -> dict[str, Any]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass payload missing elements list")

    categories = _empty_categories()
    seen: set[tuple[str, int]] = set()

    for element in elements:
        if not isinstance(element, dict):
            continue
        element_type = str(element.get("type", "node"))
        element_id = element.get("id")
        if not isinstance(element_id, int):
            continue
        identity = (element_type, element_id)
        if identity in seen:
            continue
        seen.add(identity)

        tags = element.get("tags")
        if not isinstance(tags, dict):
            continue
        for category in _categories_for_tags(tags):
            categories[category] += 1

    daily_needs = _score_daily_needs(categories)
    food_social = _score_food_social(categories)
    transit_access = _score_count(categories["transit"], useful=4, dense=12)
    parks_outdoors = _score_count(categories["parks"], useful=2, dense=6)
    walkability = _weighted_score(
        daily_needs=daily_needs,
        food_social=food_social,
        transit_access=transit_access,
        parks_outdoors=parks_outdoors,
        community_count=categories["community"] + categories["libraries"],
    )

    return {
        "walkability": walkability,
        "transit_access": transit_access,
        "daily_needs": daily_needs,
        "food_social": food_social,
        "parks_outdoors": parks_outdoors,
        "nearby_categories": categories,
        "summary": _summary(categories),
    }


def _empty_categories() -> dict[str, int]:
    return {key: 0 for key in CATEGORY_KEYS}


def _categories_for_tags(tags: dict[str, Any]) -> list[str]:
    categories: list[str] = []
    shop = tags.get("shop")
    amenity = tags.get("amenity")
    highway = tags.get("highway")
    public_transport = tags.get("public_transport")
    railway = tags.get("railway")
    leisure = tags.get("leisure")
    landuse = tags.get("landuse")

    if shop in {"supermarket", "convenience", "grocery"}:
        categories.append("groceries")
    if amenity == "pharmacy":
        categories.append("pharmacies")
    if amenity == "library":
        categories.append("libraries")
    if amenity == "restaurant":
        categories.append("restaurants")
    if amenity in {"cafe", "fast_food"}:
        categories.append("cafes")
    if amenity in {"bar", "pub"}:
        categories.append("bars")
    if (
        highway == "bus_stop"
        or public_transport in {"platform", "station"}
        or railway in {"station", "subway_entrance", "tram_stop"}
    ):
        categories.append("transit")
    if leisure in {"park", "garden", "playground", "recreation_ground"}:
        categories.append("parks")
    if landuse == "recreation_ground":
        categories.append("parks")
    if amenity in {"community_centre", "townhall", "clinic", "doctors"}:
        categories.append("community")

    return categories


def _score_daily_needs(categories: dict[str, int]) -> int:
    weighted_count = (
        categories["groceries"] * 2
        + categories["pharmacies"] * 2
        + categories["libraries"]
        + categories["community"]
    )
    return _score_count(weighted_count, useful=4, dense=12)


def _score_food_social(categories: dict[str, int]) -> int:
    weighted_count = categories["restaurants"] + categories["cafes"] + categories["bars"]
    return _score_count(weighted_count, useful=5, dense=20)


def _score_count(count: int, *, useful: int, dense: int) -> int:
    if count <= 0:
        return LOW_SCORE
    if count >= dense:
        return 88
    if count >= useful:
        return 70 + min(15, int((count - useful) * 15 / max(dense - useful, 1)))
    return 40 + int(count * 30 / useful)


def _weighted_score(
    *,
    daily_needs: int,
    food_social: int,
    transit_access: int,
    parks_outdoors: int,
    community_count: int,
) -> int:
    score = int(
        daily_needs * 0.35
        + food_social * 0.25
        + transit_access * 0.2
        + parks_outdoors * 0.15
        + min(5, community_count)
    )
    return _clamp(score)


def _summary(categories: dict[str, int]) -> str:
    found = [label for label, count in categories.items() if count > 0]
    if not found:
        return "Public POI query returned no nearby everyday destination signals."
    return f"Nearby public POI signals found {', '.join(found)} within the access radius."


def _clamp(score: int) -> int:
    return max(0, min(100, score))
```

- [ ] **Step 4: Run parser/scoring tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_access_source.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Commit pure access normalizer**

Run:

```powershell
git add backend\sources\access.py tests\test_access_source.py
git commit -m "Add access POI normalization"
```

Expected: commit succeeds.

---

### Task 2: Add Overpass Query Builder And Fetcher

**Files:**
- Modify: `backend/sources/access.py`
- Modify: `tests/test_access_source.py`

- [ ] **Step 1: Add failing query/context tests**

Replace the import block at the top of `tests/test_access_source.py` with:

```python
from unittest.mock import AsyncMock

import pytest

from backend.models import AnalyzeRequest, Coordinates, Place
from backend.sources.access import (
    ACCESS_RADIUS_METERS,
    build_overpass_query,
    fetch_access_context,
    normalize_access_payload,
)
from backend.sources.common import SourceContext
```

Then append to `tests/test_access_source.py`:

```python


def _context_with_coordinates() -> SourceContext:
    place = Place(
        label="Kensington Market, Toronto, ON",
        city="Toronto",
        state="ON",
        coordinates=Coordinates(lat=43.654, lng=-79.401),
    )
    return SourceContext(request=AnalyzeRequest(query=place.label), place=place)


def test_build_overpass_query_is_bounded_to_radius_and_tags():
    query = build_overpass_query(lat=43.654, lng=-79.401)

    assert f"around:{ACCESS_RADIUS_METERS},43.654,-79.401" in query
    assert "[out:json][timeout:6]" in query
    assert "supermarket|convenience|grocery" in query
    assert "pharmacy|library|restaurant|cafe|bar|pub|fast_food" in query
    assert "bus_stop" in query
    assert "recreation_ground" in query
    assert "out center tags;" in query


@pytest.mark.asyncio
async def test_fetch_access_context_returns_empty_without_coordinates():
    place = Place(label="Toronto, ON", city="Toronto", state="ON")
    context = SourceContext(request=AnalyzeRequest(query=place.label), place=place)

    result = await fetch_access_context(context)

    assert result.data == {}
    assert result.message == "Access lookup needs resolved coordinates."


@pytest.mark.asyncio
async def test_fetch_access_context_uses_http_client_and_returns_source_result():
    payload = {
        "elements": [
            _element(1, {"shop": "supermarket"}),
            _element(2, {"amenity": "pharmacy"}),
            _element(3, {"highway": "bus_stop"}),
            _element(4, {"leisure": "park"}),
        ]
    }

    response = AsyncMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.post.return_value = response

    result = await fetch_access_context(_context_with_coordinates(), client=client)

    assert result.data["nearby_categories"]["groceries"] == 1
    assert result.data["nearby_categories"]["transit"] == 1
    assert result.data["walkability"] > 30
    assert result.message == result.data["summary"]
    assert result.updated_at is not None
    client.post.assert_awaited_once()
```

- [ ] **Step 2: Run new fetcher tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_access_source.py -q -p no:cacheprovider
```

Expected: FAIL because `ACCESS_RADIUS_METERS`, `build_overpass_query`, and context-aware `fetch_access_context` do not exist.

- [ ] **Step 3: Add HTTP/query implementation**

Update `backend/sources/access.py` imports:

```python
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.sources.common import SourceContext, SourceResult
```

Add constants after imports:

```python
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
ACCESS_RADIUS_METERS = 1200
OVERPASS_TIMEOUT_SECONDS = 6
LOW_SCORE = 30
```

Add this public query builder above `normalize_access_payload`:

```python
def build_overpass_query(*, lat: float, lng: float) -> str:
    around = f"around:{ACCESS_RADIUS_METERS},{lat},{lng}"
    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT_SECONDS}];
(
  node({around})[shop~"^(supermarket|convenience|grocery)$"];
  way({around})[shop~"^(supermarket|convenience|grocery)$"];
  node({around})[amenity~"^(pharmacy|library|restaurant|cafe|bar|pub|fast_food|community_centre|townhall|clinic|doctors)$"];
  way({around})[amenity~"^(pharmacy|library|restaurant|cafe|bar|pub|fast_food|community_centre|townhall|clinic|doctors)$"];
  node({around})[highway="bus_stop"];
  node({around})[public_transport~"^(platform|station)$"];
  node({around})[railway~"^(station|subway_entrance|tram_stop)$"];
  way({around})[leisure~"^(park|garden|playground|recreation_ground)$"];
  relation({around})[leisure~"^(park|garden|playground|recreation_ground)$"];
  way({around})[landuse="recreation_ground"];
  relation({around})[landuse="recreation_ground"];
);
out center tags;
""".strip()
```

Add this async source function above `build_overpass_query`:

```python
async def fetch_access_context(
    context: SourceContext,
    client: httpx.AsyncClient | None = None,
) -> SourceResult:
    coordinates = context.place.coordinates
    if coordinates is None:
        return SourceResult(data={}, message="Access lookup needs resolved coordinates.")

    query = build_overpass_query(lat=coordinates.lat, lng=coordinates.lng)
    should_close = client is None
    http_client = client or httpx.AsyncClient(timeout=OVERPASS_TIMEOUT_SECONDS + 2)
    try:
        response = await http_client.post(OVERPASS_URL, data={"data": query})
        response.raise_for_status()
        data = normalize_access_payload(response.json())
    finally:
        if should_close:
            await http_client.aclose()

    checked_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    return SourceResult(
        data=data,
        message=data["summary"],
        updated_at=checked_at,
    )
```

Remove the old no-argument placeholder `fetch_access_context`.

- [ ] **Step 4: Run access source tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_access_source.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Commit fetcher implementation**

Run:

```powershell
git add backend\sources\access.py tests\test_access_source.py
git commit -m "Fetch public POI access signals"
```

Expected: commit succeeds.

---

### Task 3: Prove Pipeline And Provenance Use Real Access Data

**Files:**
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_provenance.py`

- [ ] **Step 1: Add pipeline test for access-backed visible scores**

Append to `tests/test_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_pipeline_uses_access_scores_for_visible_scores():
    async def access_adapter(_context: SourceContext):
        return SourceResult(
            data={
                "walkability": 76,
                "transit_access": 67,
                "daily_needs": 72,
                "food_social": 71,
                "parks_outdoors": 64,
                "nearby_categories": {
                    "groceries": 2,
                    "pharmacies": 1,
                    "restaurants": 8,
                    "cafes": 3,
                    "bars": 1,
                    "transit": 5,
                    "parks": 2,
                    "libraries": 1,
                    "community": 1,
                },
                "summary": "Nearby public POI signals found groceries and transit.",
            },
            message="Nearby public POI signals found groceries and transit.",
            updated_at="2026-05-10T00:00:00+00:00",
        )

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Kensington Market, Toronto, ON"),
        source_fetchers={SourceName.ACCESS: access_adapter},
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    scores = response.profile.vibe_scores
    assert scores.walkability == 76
    assert scores.transit_access == 67
    assert scores.parks_outdoors is None

    access_status = next(
        status for status in response.source_statuses if status.source == SourceName.ACCESS
    )
    assert access_status.status == SourceStatusCode.SUCCESS
    assert access_status.updated_at == "2026-05-10T00:00:00+00:00"
```

This test expects `parks_outdoors` to stay `None` because Phase 2G intentionally treats `profile.vibe_scores.parks_outdoors` as a local municipal signal. Access `parks_outdoors` still supports visible scores through `walkability`; a separate model-design slice can merge those concepts if desired.

- [ ] **Step 2: Run the new pipeline test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py::test_pipeline_uses_access_scores_for_visible_scores -q -p no:cacheprovider
```

Expected: PASS because `score_signals.py` already reads `access.walkability` and `access.transit_access`.

- [ ] **Step 3: Add provenance regression for access fields**

Append to `tests/test_provenance.py`:

```python
def test_build_profile_provenance_cites_real_access_score_fields():
    provenance = build_profile_provenance(
        {
            SourceName.ACCESS: {
                "walkability": 76,
                "transit_access": 67,
                "daily_needs": 72,
                "food_social": 71,
                "parks_outdoors": 64,
            }
        },
        [_status(SourceName.ACCESS, SourceStatusCode.SUCCESS)],
    )

    items = {item.claim_id: item for item in provenance.items}

    assert items["vibe.walkability"].source_fields == ["access.walkability"]
    assert items["vibe.transit_access"].source_fields == ["access.transit_access"]
    assert items["vibe.walkability"].support == "inferred"
    assert items["vibe.transit_access"].support == "inferred"
```

- [ ] **Step 4: Run provenance tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_provenance.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Run targeted pipeline/provenance tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_provenance.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6: Commit pipeline/provenance coverage**

Run:

```powershell
git add tests\test_pipeline.py tests\test_provenance.py
git commit -m "Cover access score pipeline behavior"
```

Expected: commit succeeds.

---

### Task 4: Update Documentation And Attribution

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`

- [ ] **Step 1: Update README current scope**

In `README.md`, add this bullet near the Ontario/GTA score-depth bullets:

```markdown
- No-new-key Daily Needs Access scoring from bounded public OpenStreetMap/Overpass POI queries.
```

In `README.md` under `Data And Confidence Caveats`, add:

```markdown
- Daily Needs Access uses public OpenStreetMap contributor data through bounded Overpass-style POI queries; results may be incomplete or temporarily unavailable if the public endpoint is slow or rate-limited.
```

Add a short attribution line near the caveats:

```markdown
Access POI data is derived from OpenStreetMap contributors under the Open Database License.
```

- [ ] **Step 2: Update PLAN build order and data depth**

In `PLAN.md`, under Phase 2 build order, add after the Phase 2G line:

```markdown
- [x] Add no-new-key GTA Daily Needs Access scoring from bounded public OSM/Overpass POI signals.
```

Under the `backend/sources/access.py` section, ensure the description includes:

```markdown
- Use bounded public OSM/Overpass POI queries first so the access source does not require a paid API key.
```

- [ ] **Step 3: Inspect docs diff**

Run:

```powershell
git diff -- README.md PLAN.md
```

Expected: diff documents OSM/Overpass, no-new-key access scoring, and attribution without adding UI redesign work.

- [ ] **Step 4: Commit docs**

Run:

```powershell
git add README.md PLAN.md
git commit -m "Document public access scoring"
```

Expected: commit succeeds.

---

### Task 5: Final Verification

**Files:**
- Verify only; no expected source edits.

- [ ] **Step 1: Run targeted backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_access_source.py tests/test_score_signals.py tests/test_pipeline.py tests/test_provenance.py tests/test_main.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run full backend test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 3: Run Ruff**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check backend tests
```

Expected: `All checks passed!`.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
npm.cmd run build --prefix frontend
```

Expected: build succeeds. If the sandbox blocks esbuild process spawning with `EPERM`, rerun the same command with escalation.

- [ ] **Step 5: Inspect final git status**

Run:

```powershell
git status --short --branch
```

Expected: no tracked files modified. Untracked `.tmp/` may remain.

- [ ] **Step 6: Optional manual smoke check**

Start backend and frontend using README commands and analyze:

```text
Kensington Market, Toronto, ON
```

Expected:

- The UI layout is unchanged.
- Access source status is success when the public POI endpoint responds.
- `walkability` and `transit_access` can move away from `50`.
- Source failure or timeout shows in source statuses without breaking the profile.
