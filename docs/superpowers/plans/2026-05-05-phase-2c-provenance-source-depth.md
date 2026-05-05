# Phase 2C Provenance And Source Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add typed provenance to neighborhood analysis responses, show compact source support in the frontend, and enrich the access source with conservative normalized lifestyle signals.

**Architecture:** Backend owns provenance. The OpenAI synthesizer continues to return only profile content; `analyze_neighborhood()` attaches backend-generated `ProfileProvenance` from normalized source data and source statuses. The frontend renders provenance as a small source-support section near confidence and gracefully omits it for older saved reports.

**Tech Stack:** FastAPI, Pydantic, pytest, React 19, Vite 7, Node built-in `node:test`, plain CSS.

---

## File Structure

- Modify `backend/models.py`: add `ProvenanceSupport`, `ProvenanceItem`, `ProfileProvenance`, and replace loose profile provenance with the typed model.
- Create `backend/provenance.py`: build claim-support metadata from normalized source data and source statuses.
- Modify `backend/pipeline.py`: generate provenance once per analysis and attach it to deterministic and synthesized profiles.
- Modify `backend/sources/access.py`: return conservative normalized access fields so provenance has meaningful non-sensitive support.
- Modify `backend/synthesizer.py`: keep provenance out of the OpenAI payload schema and attach typed empty provenance when parsing older payloads.
- Modify `tests/test_models.py`: cover provenance serialization.
- Create `tests/test_provenance.py`: cover source-present and source-unavailable provenance behavior.
- Modify `tests/test_pipeline.py`: cover provenance attached in fallback and synthesized paths.
- Modify `tests/test_storage.py`: cover saved reports preserving provenance.
- Create `frontend/src/components/Provenance.jsx`: render compact Source support rows.
- Modify `frontend/src/components/Profile.jsx`: render provenance near confidence.
- Modify `frontend/src/styles.css`: style provenance rows and support labels.
- Modify `frontend/src/uiContract.test.js`: source-contract checks for provenance rendering and no raw payload display.
- Modify `README.md`: document Phase 2C provenance/source support.

---

### Task 1: Add Typed Provenance Models

**Files:**
- Modify: `backend/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write the failing model serialization test**

Append to `tests/test_models.py`:

```python
from backend.models import ProfileProvenance, ProvenanceItem, ProvenanceSupport


def test_profile_provenance_serializes_supported_claims():
    provenance = ProfileProvenance(
        items=[
            ProvenanceItem(
                claim_id="vibe.walkability",
                label="Walkability score",
                summary="Based on normalized access.walkability signal.",
                support=ProvenanceSupport.INFERRED,
                sources=[SourceName.ACCESS],
                source_fields=["access.walkability"],
            )
        ]
    )

    assert provenance.model_dump(mode="json") == {
        "items": [
            {
                "claim_id": "vibe.walkability",
                "label": "Walkability score",
                "summary": "Based on normalized access.walkability signal.",
                "support": "inferred",
                "sources": ["access"],
                "source_fields": ["access.walkability"],
            }
        ]
    }
```

- [ ] **Step 2: Run the model test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_models.py::test_profile_provenance_serializes_supported_claims -q -p no:cacheprovider
```

Expected: fails because `ProfileProvenance`, `ProvenanceItem`, and `ProvenanceSupport` are not defined.

- [ ] **Step 3: Add provenance models**

In `backend/models.py`, remove the now-unused `Any` import if no longer needed after replacing the loose provenance dict.

Add after `SourceStatusCode`:

```python
class ProvenanceSupport(StrEnum):
    DIRECT = "direct"
    INFERRED = "inferred"
    UNAVAILABLE = "unavailable"
```

Add after `SourceStatus`:

```python
class ProvenanceItem(BaseModel):
    claim_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    support: ProvenanceSupport
    sources: list[SourceName] = Field(default_factory=list)
    source_fields: list[str] = Field(default_factory=list)


class ProfileProvenance(BaseModel):
    items: list[ProvenanceItem] = Field(default_factory=list)
```

Change `NeighborhoodProfile`:

```python
class NeighborhoodProfile(BaseModel):
    overview: str
    vibe_scores: VibeScores
    who_lives_here: WhoLivesHere
    honest_pros: list[str]
    honest_cons: list[str]
    trajectory: Trajectory
    provenance: ProfileProvenance = Field(default_factory=ProfileProvenance)
```

- [ ] **Step 4: Run the model test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_models.py::test_profile_provenance_serializes_supported_claims -q -p no:cacheprovider
```

Expected: passes.

- [ ] **Step 5: Commit**

Run:

```powershell
git add backend/models.py tests/test_models.py
git commit -m "Add typed profile provenance models"
```

---

### Task 2: Build Backend Provenance From Source Data

**Files:**
- Create: `backend/provenance.py`
- Create: `tests/test_provenance.py`

- [ ] **Step 1: Write failing provenance builder tests**

Create `tests/test_provenance.py`:

```python
from backend.models import SourceName, SourceStatus, SourceStatusCode
from backend.provenance import build_profile_provenance


def _status(source: SourceName, status: SourceStatusCode) -> SourceStatus:
    return SourceStatus(source=source, status=status, message=f"{source.value} {status.value}.")


def test_build_profile_provenance_marks_supported_access_and_housing_claims():
    provenance = build_profile_provenance(
        {
            SourceName.ACCESS: {
                "walkability": 82,
                "transit_access": 74,
                "daily_needs": 68,
            },
            SourceName.HOUSING: {"affordability": 44},
            SourceName.CENSUS: {
                "median_age": 34,
                "median_household_income": 82000,
                "population_density": 9500,
            },
            SourceName.REDDIT: {"quiet": 58, "social_scene": 66},
        },
        [
            _status(SourceName.ACCESS, SourceStatusCode.SUCCESS),
            _status(SourceName.HOUSING, SourceStatusCode.SUCCESS),
            _status(SourceName.CENSUS, SourceStatusCode.SUCCESS),
            _status(SourceName.REDDIT, SourceStatusCode.SUCCESS),
        ],
    )

    items = {item.claim_id: item for item in provenance.items}
    assert items["vibe.walkability"].support == "inferred"
    assert items["vibe.walkability"].sources == [SourceName.ACCESS]
    assert items["vibe.walkability"].source_fields == ["access.walkability"]
    assert items["vibe.affordability"].source_fields == ["housing.affordability"]
    assert items["context.median_household_income"].support == "direct"
    assert items["trajectory"].support == "unavailable"


def test_build_profile_provenance_marks_missing_or_failed_sources_unavailable():
    provenance = build_profile_provenance(
        {
            SourceName.ACCESS: {},
            SourceName.HOUSING: {},
            SourceName.CENSUS: {},
            SourceName.REDDIT: {},
        },
        [
            _status(SourceName.ACCESS, SourceStatusCode.EMPTY),
            _status(SourceName.HOUSING, SourceStatusCode.ERROR),
            _status(SourceName.CENSUS, SourceStatusCode.EMPTY),
            _status(SourceName.REDDIT, SourceStatusCode.EMPTY),
        ],
    )

    items = {item.claim_id: item for item in provenance.items}
    assert items["vibe.walkability"].support == "unavailable"
    assert items["vibe.walkability"].sources == [SourceName.ACCESS]
    assert "access source is empty" in items["vibe.walkability"].summary.lower()
    assert items["vibe.affordability"].support == "unavailable"
    assert "housing source errored" in items["vibe.affordability"].summary.lower()
    assert items["overview"].support == "unavailable"
```

- [ ] **Step 2: Run the provenance tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_provenance.py -q -p no:cacheprovider
```

Expected: fails because `backend.provenance` does not exist.

- [ ] **Step 3: Implement provenance builder**

Create `backend/provenance.py`:

```python
from typing import Any

from backend.models import (
    ProfileProvenance,
    ProvenanceItem,
    ProvenanceSupport,
    SourceName,
    SourceStatus,
    SourceStatusCode,
)


def build_profile_provenance(
    source_data: dict[SourceName, dict[str, Any]],
    statuses: list[SourceStatus],
) -> ProfileProvenance:
    status_by_source = {status.source: status for status in statuses}
    items = [
        _overview_item(source_data, status_by_source),
        _field_item(
            claim_id="vibe.walkability",
            label="Walkability score",
            source=SourceName.ACCESS,
            source_field="walkability",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="vibe.transit_access",
            label="Transit access score",
            source=SourceName.ACCESS,
            source_field="transit_access",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="vibe.affordability",
            label="Affordability score",
            source=SourceName.HOUSING,
            source_field="affordability",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="vibe.quiet",
            label="Quiet score",
            source=SourceName.REDDIT,
            source_field="quiet",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="vibe.social_scene",
            label="Social scene score",
            source=SourceName.REDDIT,
            source_field="social_scene",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.INFERRED,
        ),
        _field_item(
            claim_id="context.median_age",
            label="Median age",
            source=SourceName.CENSUS,
            source_field="median_age",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.DIRECT,
        ),
        _field_item(
            claim_id="context.median_household_income",
            label="Median household income",
            source=SourceName.CENSUS,
            source_field="median_household_income",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.DIRECT,
        ),
        _field_item(
            claim_id="context.population_density",
            label="Population density",
            source=SourceName.CENSUS,
            source_field="population_density",
            source_data=source_data,
            status_by_source=status_by_source,
            support=ProvenanceSupport.DIRECT,
        ),
        _trajectory_item(source_data, status_by_source),
    ]
    return ProfileProvenance(items=items)


def _overview_item(
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    available = [
        source
        for source in (SourceName.ACCESS, SourceName.HOUSING, SourceName.CENSUS, SourceName.REDDIT)
        if _has_data(source_data, source)
    ]
    if available:
        names = ", ".join(source.value for source in available)
        return ProvenanceItem(
            claim_id="overview",
            label="Overview",
            summary=f"Overview is generated from available normalized {names} signals.",
            support=ProvenanceSupport.INFERRED,
            sources=available,
            source_fields=[],
        )
    tracked_sources = (SourceName.ACCESS, SourceName.HOUSING, SourceName.CENSUS, SourceName.REDDIT)
    summaries = [_status_summary(source, status_by_source) for source in tracked_sources]
    return ProvenanceItem(
        claim_id="overview",
        label="Overview",
        summary=f"Overview has no strong source support yet; {'; '.join(summaries)}.",
        support=ProvenanceSupport.UNAVAILABLE,
        sources=[],
        source_fields=[],
    )


def _field_item(
    *,
    claim_id: str,
    label: str,
    source: SourceName,
    source_field: str,
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
    support: ProvenanceSupport,
) -> ProvenanceItem:
    full_field = f"{source.value}.{source_field}"
    if source_data.get(source, {}).get(source_field) is not None:
        return ProvenanceItem(
            claim_id=claim_id,
            label=label,
            summary=f"Based on normalized {full_field} signal.",
            support=support,
            sources=[source],
            source_fields=[full_field],
        )
    return ProvenanceItem(
        claim_id=claim_id,
        label=label,
        summary=f"{label} is unavailable because {_status_summary(source, status_by_source)}.",
        support=ProvenanceSupport.UNAVAILABLE,
        sources=[source],
        source_fields=[],
    )


def _trajectory_item(
    source_data: dict[SourceName, dict[str, Any]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    trend_fields = [
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
            summary="Trajectory is inferred from available trend signals.",
            support=ProvenanceSupport.INFERRED,
            sources=_sources_for_fields(trend_fields, present_fields),
            source_fields=present_fields,
        )
    return ProvenanceItem(
        claim_id="trajectory",
        label="Trajectory",
        summary=(
            "Trajectory is unavailable because trend fields are missing; "
            f"{_status_summary(SourceName.HOUSING, status_by_source)}; "
            f"{_status_summary(SourceName.REDDIT, status_by_source)}."
        ),
        support=ProvenanceSupport.UNAVAILABLE,
        sources=[SourceName.HOUSING, SourceName.REDDIT],
        source_fields=[],
    )


def _has_data(source_data: dict[SourceName, dict[str, Any]], source: SourceName) -> bool:
    return bool(source_data.get(source))


def _sources_for_fields(
    trend_fields: list[tuple[SourceName, str]],
    present_fields: list[str],
) -> list[SourceName]:
    sources = {
        source
        for source, field in trend_fields
        if f"{source.value}.{field}" in present_fields
    }
    return sorted(sources, key=lambda item: item.value)


def _status_summary(source: SourceName, status_by_source: dict[SourceName, SourceStatus]) -> str:
    status = status_by_source.get(source)
    if status is None:
        return f"{source.value} source is missing"
    if status.status == SourceStatusCode.SUCCESS:
        return f"{source.value} source lacks this field"
    if status.status == SourceStatusCode.ERROR:
        return f"{source.value} source errored"
    return f"{source.value} source is empty"
```

- [ ] **Step 4: Run provenance tests and lint**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_provenance.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check backend/provenance.py tests/test_provenance.py
```

Expected: tests pass and ruff is clean.

- [ ] **Step 5: Commit**

Run:

```powershell
git add backend/provenance.py tests/test_provenance.py
git commit -m "Generate profile provenance from source support"
```

---

### Task 3: Attach Provenance In The Pipeline

**Files:**
- Modify: `backend/pipeline.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_synthesizer.py`

- [ ] **Step 1: Write failing pipeline provenance tests**

Append to `tests/test_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_pipeline_attaches_provenance_to_deterministic_profile():
    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=lambda **_kwargs: _returns_none(),
    )

    assert response.profile.provenance.items
    claim_ids = {item.claim_id for item in response.profile.provenance.items}
    assert "overview" in claim_ids
    assert "vibe.walkability" in claim_ids


@pytest.mark.asyncio
async def test_pipeline_attaches_backend_provenance_to_synthesized_profile():
    async def synthesizer(**_kwargs):
        return _synthetic_profile()

    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=synthesizer,
    )

    assert response.synthesis.status == SynthesisStatusCode.USED
    assert response.profile.provenance.items
    assert any(item.claim_id == "overview" for item in response.profile.provenance.items)
```

Add this helper near the existing test helpers:

```python
async def _returns_none():
    return None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py::test_pipeline_attaches_provenance_to_deterministic_profile tests/test_pipeline.py::test_pipeline_attaches_backend_provenance_to_synthesized_profile -q -p no:cacheprovider
```

Expected: fails because pipeline does not attach provenance.

- [ ] **Step 3: Attach provenance in pipeline**

In `backend/pipeline.py`, add import:

```python
from backend.provenance import build_profile_provenance
```

After `confidence = build_confidence(statuses)`, add:

```python
    provenance = build_profile_provenance(source_data, statuses)
```

After deciding the final `profile`, before scoring, add:

```python
    profile = profile.model_copy(update={"provenance": provenance})
```

The section should read:

```python
    if profile is None:
        profile = fallback_profile
    profile = profile.model_copy(update={"provenance": provenance})
    fit = None if request.generic_mode else score_fit(profile, request.preferences)
```

- [ ] **Step 4: Update synthesizer test expectation**

In `tests/test_synthesizer.py`, update:

```python
assert profile.provenance == {}
```

to:

```python
assert profile.provenance.items == []
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_synthesizer.py -q -p no:cacheprovider
```

Expected: tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add backend/pipeline.py tests/test_pipeline.py tests/test_synthesizer.py
git commit -m "Attach provenance during analysis"
```

---

### Task 4: Preserve Provenance In Saved Reports

**Files:**
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Add saved-report provenance persistence test**

In `tests/test_storage.py`, add imports:

```python
    ProfileProvenance,
    ProvenanceItem,
    ProvenanceSupport,
```

Inside `_response()`, update the `profile=NeighborhoodProfile(` call to include this argument:

```python
            provenance=ProfileProvenance(
                items=[
                    ProvenanceItem(
                        claim_id="overview",
                        label="Overview",
                        summary="Overview is generated from available normalized access signals.",
                        support=ProvenanceSupport.INFERRED,
                        sources=[SourceName.ACCESS],
                        source_fields=["access.walkability"],
                    )
                ]
            ),
```

Append:

```python
def test_saved_profile_preserves_provenance():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Source-backed Place"), db_path)

    found = get_saved_profile(saved.id, db_path)

    assert found is not None
    provenance_items = found.response.profile.provenance.items
    assert len(provenance_items) == 1
    assert provenance_items[0].claim_id == "overview"
    assert provenance_items[0].sources == [SourceName.ACCESS]
```

- [ ] **Step 2: Run storage test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py::test_saved_profile_preserves_provenance -q -p no:cacheprovider
```

Expected: passes because saved reports store full response JSON and Pydantic restores typed provenance.

- [ ] **Step 3: Commit**

Run:

```powershell
git add tests/test_storage.py
git commit -m "Test saved reports preserve provenance"
```

---

### Task 5: Enrich Conservative Access Source Output

**Files:**
- Modify: `backend/sources/access.py`
- Create: `tests/test_access_source.py`

- [ ] **Step 1: Write failing access source test**

Create `tests/test_access_source.py`:

```python
import pytest

from backend.sources.access import fetch_access_context


@pytest.mark.asyncio
async def test_fetch_access_context_returns_conservative_normalized_signals():
    context = await fetch_access_context()

    assert context["walkability"] == 50
    assert context["transit_access"] == 50
    assert context["daily_needs"] == 50
    assert context["food_social"] == 50
    assert context["parks_outdoors"] == 50
    assert context["nearby_categories"] == {
        "groceries": 0,
        "parks": 0,
        "restaurants": 0,
        "transit": 0,
    }
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_access_source.py -q -p no:cacheprovider
```

Expected: fails because `fetch_access_context()` currently returns `{}`.

- [ ] **Step 3: Implement conservative access context**

Replace `backend/sources/access.py` with:

```python
from typing import Any


async def fetch_access_context() -> dict[str, Any]:
    return {
        "walkability": 50,
        "transit_access": 50,
        "daily_needs": 50,
        "food_social": 50,
        "parks_outdoors": 50,
        "nearby_categories": {
            "groceries": 0,
            "parks": 0,
            "restaurants": 0,
            "transit": 0,
        },
    }
```

- [ ] **Step 4: Run access and provenance tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_access_source.py tests/test_provenance.py -q -p no:cacheprovider
```

Expected: tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add backend/sources/access.py tests/test_access_source.py
git commit -m "Return conservative access source signals"
```

---

### Task 6: Render Source Support In The Frontend

**Files:**
- Create: `frontend/src/components/Provenance.jsx`
- Modify: `frontend/src/components/Profile.jsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/uiContract.test.js`

- [ ] **Step 1: Add failing UI source contract tests**

Append to `frontend/src/uiContract.test.js`:

```javascript
test('profile renders source support without raw payload output', () => {
  const profile = source('src/components/Profile.jsx');
  const provenance = source('src/components/Provenance.jsx');

  assert.match(profile, /<Provenance provenance=\{profile\.provenance\} \/>/);
  assert.match(provenance, /Source support/);
  assert.match(provenance, /Supported/);
  assert.match(provenance, /Inferred/);
  assert.match(provenance, /Unavailable/);
  assert.equal(provenance.includes('JSON.stringify'), false);
});
```

- [ ] **Step 2: Run UI contract test and verify failure**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: fails because `Provenance.jsx` does not exist and `Profile.jsx` does not render it.

- [ ] **Step 3: Create Provenance component**

Create `frontend/src/components/Provenance.jsx`:

```jsx
const SUPPORT_LABELS = {
  direct: 'Supported',
  inferred: 'Inferred',
  unavailable: 'Unavailable',
};

export default function Provenance({ provenance }) {
  const items = provenance?.items || [];
  if (items.length === 0) return null;

  return (
    <section className="panel-section provenance-section">
      <div className="section-heading">
        <p className="eyebrow">Source support</p>
        <h2>Why these claims appear</h2>
      </div>
      <div className="provenance-list">
        {items.map((item) => (
          <article className={`provenance-row provenance-${item.support}`} key={item.claim_id}>
            <div>
              <strong>{item.label}</strong>
              <span>{SUPPORT_LABELS[item.support] || item.support}</span>
            </div>
            <p>{item.summary}</p>
            {item.sources?.length > 0 && (
              <div className="source-chip-row">
                {item.sources.map((source) => (
                  <small key={source}>{source}</small>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Render provenance in Profile**

In `frontend/src/components/Profile.jsx`, add import:

```jsx
import Provenance from './Provenance.jsx';
```

Render before `Confidence`:

```jsx
      <Provenance provenance={profile.provenance} />
      <Confidence confidence={confidence} statuses={statuses} />
```

- [ ] **Step 5: Add provenance CSS**

Append to `frontend/src/styles.css` before the media query:

```css
.provenance-section {
  gap: 10px;
}

.provenance-list {
  display: grid;
  gap: 8px;
}

.provenance-row {
  display: grid;
  gap: 8px;
  border: 1px solid var(--vc-border);
  border-radius: 10px;
  background: #ffffff;
  padding: 12px;
}

.provenance-row > div:first-child {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.provenance-row strong {
  font-size: 0.88rem;
}

.provenance-row span {
  color: var(--vc-blue);
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
}

.provenance-row p {
  margin: 0;
  color: var(--vc-muted);
  font-size: 0.82rem;
  line-height: 1.4;
}

.provenance-unavailable {
  background: #f8fafc;
}

.provenance-unavailable span {
  color: var(--vc-muted);
}

.source-chip-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.source-chip-row small {
  border-radius: 999px;
  background: var(--vc-blue-soft);
  color: var(--vc-blue);
  font-size: 0.68rem;
  font-weight: 800;
  padding: 3px 8px;
  text-transform: uppercase;
}
```

- [ ] **Step 6: Run UI contract test**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: UI contract tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src/components/Provenance.jsx frontend/src/components/Profile.jsx frontend/src/styles.css frontend/src/uiContract.test.js
git commit -m "Render provenance source support"
```

---

### Task 7: Documentation And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README current scope**

In `README.md`, add this bullet under Current Scope:

```markdown
- Typed provenance metadata and Source support UI showing which normalized sources support major claims.
```

Update the Phase 2 Status paragraph to:

```markdown
Phase 2A added explicit local saved neighborhood reports. Phase 2B added reusable local preference profiles and then corrected the UI so profiles work as an app-level analysis lens selected before address search. Phase 2C adds typed provenance and compact source-support UI so major claims can be traced to normalized source signals. Generic analysis remains available when no saved profile is active. The next Phase 2 slices should focus on compare mode, source freshness, and deeper city-specific adapters.
```

- [ ] **Step 2: Run full backend verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check backend tests
```

Expected: all backend tests pass and ruff is clean.

- [ ] **Step 3: Run full frontend verification**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
node --test frontend/src/uiContract.test.js
Set-Location frontend
npm.cmd run build
```

Expected: frontend helper tests pass, UI contract tests pass, and Vite build succeeds. The existing large Mapbox chunk warning is acceptable.

- [ ] **Step 4: Manual smoke checklist**

Start or reuse local servers and verify:

- Generic analysis returns a profile with Source support.
- Saved-profile analysis returns a profile with Source support.
- Source support rows show supported/inferred/unavailable states without raw JSON.
- Confidence/source statuses still render.
- Save report, open report, and delete report still work.
- Reopened saved report preserves Source support.

- [ ] **Step 5: Commit README**

Run:

```powershell
git add README.md
git commit -m "Document provenance source support"
```

- [ ] **Step 6: Check final status**

Run:

```powershell
git status --short --branch
```

Expected: no staged changes. Untracked `.tmp/` may remain only if it contains local screenshots/logs and is not staged.
