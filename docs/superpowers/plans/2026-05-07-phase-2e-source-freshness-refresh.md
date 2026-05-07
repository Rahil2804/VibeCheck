# Phase 2E Source Freshness And Refresh Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add freshness labels and single-place refresh controls for current and saved reports, with saved report refresh overwriting the existing row.

**Architecture:** Backend storage gains additive request metadata and an update path for saved reports. The API adds `POST /profiles/{id}/refresh`, reconstructs an analyze request from saved metadata or safe fallback, reruns the existing analysis pipeline, and updates the same saved row. The frontend tracks generated timestamps for active reports, shows freshness near confidence/source support, and calls either the saved-report refresh route or the existing analyze retry path.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, React 19, Vite 7, Node built-in `node:test`, plain CSS.

---

## File Structure

- Create `backend/freshness.py`: 7-day stale threshold, timestamp parsing, stale-state helper.
- Create `tests/test_freshness.py`: backend freshness helper tests.
- Modify `backend/models.py`: add nullable `analyze_request` metadata to `SavedProfileSummary` so saved reports can round-trip refresh metadata.
- Modify `backend/storage.py`: add nullable `analyze_request_json` column, save/update request metadata, build refresh requests.
- Modify `tests/test_storage.py`: cover metadata persistence, old-row compatibility, saved-row overwrite, and fallback refresh request construction.
- Modify `backend/main.py`: pass request metadata on save and add `POST /profiles/{id}/refresh`.
- Modify `tests/test_main.py`: cover refresh endpoint success and missing report 404.
- Create `frontend/src/utils/freshness.js`: frontend label/status helpers.
- Create `frontend/src/utils/freshness.test.js`: frontend freshness helper tests.
- Modify `frontend/src/utils/api.js`: add saved-report refresh API function.
- Modify `frontend/src/utils/api.test.js`: cover refresh API call and error parsing.
- Create `frontend/src/components/Freshness.jsx`: compact generated/stale label and refresh control.
- Modify `frontend/src/components/Profile.jsx`: render `Freshness` before Source support/Confidence.
- Modify `frontend/src/components/Confidence.jsx`: show source `updated_at` when present.
- Modify `frontend/src/hooks/useNeighborhood.js`: track generated timestamps and saved report metadata, refresh current saved/unsaved reports non-destructively.
- Modify `frontend/src/App.jsx`: pass freshness/refresh props into `Profile`.
- Modify `frontend/src/uiContract.test.js`: source-contract checks for Freshness, source updated dates, and refresh props.
- Modify `frontend/src/styles.css`: freshness panel and source updated date styling.
- Modify `README.md` and `PLAN.md`: document Phase 2E behavior after implementation.

---

### Task 1: Add Backend Freshness Helpers

**Files:**
- Create: `backend/freshness.py`
- Create: `tests/test_freshness.py`

- [ ] **Step 1: Write failing freshness tests**

Create `tests/test_freshness.py`:

```python
from datetime import UTC, datetime

from backend.freshness import FRESHNESS_STALE_DAYS, freshness_state, is_stale


NOW = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)


def test_is_stale_uses_seven_day_threshold():
    assert FRESHNESS_STALE_DAYS == 7
    assert is_stale("2026-05-01T12:00:00+00:00", now=NOW) is False
    assert is_stale("2026-04-30T12:00:00+00:00", now=NOW) is True


def test_is_stale_treats_unknown_timestamp_as_not_stale():
    assert is_stale(None, now=NOW) is False
    assert is_stale("", now=NOW) is False


def test_freshness_state_reports_unknown_fresh_and_stale():
    assert freshness_state(None, now=NOW) == "unknown"
    assert freshness_state("2026-05-07T11:00:00+00:00", now=NOW) == "fresh"
    assert freshness_state("2026-04-29T12:00:00+00:00", now=NOW) == "stale"
```

- [ ] **Step 2: Run freshness tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_freshness.py -q -p no:cacheprovider
```

Expected: fails because `backend.freshness` does not exist.

- [ ] **Step 3: Implement backend freshness helper**

Create `backend/freshness.py`:

```python
from datetime import UTC, datetime, timedelta

FRESHNESS_STALE_DAYS = 7


def freshness_state(timestamp: str | None, *, now: datetime | None = None) -> str:
    if not timestamp:
        return "unknown"
    generated_at = _parse_timestamp(timestamp)
    if generated_at is None:
        return "unknown"
    current_time = now or datetime.now(UTC)
    return "stale" if current_time - generated_at >= timedelta(days=FRESHNESS_STALE_DAYS) else "fresh"


def is_stale(timestamp: str | None, *, now: datetime | None = None) -> bool:
    return freshness_state(timestamp, now=now) == "stale"


def _parse_timestamp(timestamp: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
```

- [ ] **Step 4: Run freshness tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_freshness.py -q -p no:cacheprovider
```

Expected: freshness tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add backend/freshness.py tests/test_freshness.py
git commit -m "Add backend freshness helpers"
```

---

### Task 2: Persist Analyze Request Metadata And Update Saved Rows

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/storage.py`
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Add failing storage tests**

Modify imports in `tests/test_storage.py`:

```python
    AnalyzeRequest,
```

and:

```python
    build_refresh_request,
    update_saved_profile,
```

Append to `tests/test_storage.py`:

```python
def test_save_profile_persists_analyze_request_metadata():
    db_path = _db_path()
    initialize_database(db_path)
    request = AnalyzeRequest(query="East Austin", generic_mode=True)

    saved = save_profile(_response("East Austin"), db_path, analyze_request=request)
    found = get_saved_profile(saved.id, db_path)

    assert found is not None
    assert found.analyze_request is not None
    assert found.analyze_request.query == "East Austin"
    assert found.analyze_request.generic_mode is True


def test_existing_saved_profile_without_request_metadata_still_loads():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Legacy Place"), db_path)

    found = get_saved_profile(saved.id, db_path)

    assert found is not None
    assert found.analyze_request is None
    assert found.response.place.label == "Legacy Place"


def test_update_saved_profile_overwrites_existing_row_and_updates_timestamp():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Old Place"), db_path, analyze_request=AnalyzeRequest(query="Old Place"))

    updated = update_saved_profile(
        saved.id,
        _response("New Place"),
        db_path,
        analyze_request=AnalyzeRequest(query="New Place", generic_mode=True),
    )

    assert updated is not None
    assert updated.id == saved.id
    assert updated.created_at == saved.created_at
    assert updated.updated_at >= saved.updated_at
    assert updated.place_label == "New Place"
    assert updated.response.place.label == "New Place"
    assert updated.analyze_request is not None
    assert updated.analyze_request.query == "New Place"
    assert len(list_saved_profiles(db_path)) == 1


def test_build_refresh_request_uses_saved_request_when_available():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(
        _response("Profile-backed Place"),
        db_path,
        analyze_request=AnalyzeRequest(query="Profile-backed Place", preference_profile_id="profile-1"),
    )

    request = build_refresh_request(saved)

    assert request.query == "Profile-backed Place"
    assert request.preference_profile_id == "profile-1"
    assert request.generic_mode is False


def test_build_refresh_request_falls_back_to_saved_place_as_generic():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Legacy Place"), db_path)

    request = build_refresh_request(saved)

    assert request.query == "Legacy Place"
    assert request.generic_mode is True
    assert request.preference_profile_id is None
```

- [ ] **Step 2: Run storage tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py::test_save_profile_persists_analyze_request_metadata tests/test_storage.py::test_existing_saved_profile_without_request_metadata_still_loads tests/test_storage.py::test_update_saved_profile_overwrites_existing_row_and_updates_timestamp tests/test_storage.py::test_build_refresh_request_uses_saved_request_when_available tests/test_storage.py::test_build_refresh_request_falls_back_to_saved_place_as_generic -q -p no:cacheprovider
```

Expected: fails because models/storage do not support analyze request metadata or update helpers yet.

- [ ] **Step 3: Add request metadata to saved profile models**

In `backend/models.py`, update `SavedProfileSummary`:

```python
class SavedProfileSummary(BaseModel):
    id: str
    place_label: str
    coordinates: Coordinates | None = None
    confidence_level: ConfidenceLevel
    source_statuses: list[SourceStatus]
    created_at: str
    updated_at: str
    analyze_request: AnalyzeRequest | None = None
```

- [ ] **Step 4: Add additive SQLite migration and persistence**

In `backend/storage.py`, update the `saved_profiles` table creation to include:

```sql
                analyze_request_json TEXT,
```

after `response_json TEXT NOT NULL,`.

After the `CREATE TABLE IF NOT EXISTS saved_profiles` call, add:

```python
        _ensure_column(connection, "saved_profiles", "analyze_request_json", "TEXT")
```

Change `save_profile` signature:

```python
def save_profile(
    response: AnalyzeResponse,
    db_path: Path | None = None,
    analyze_request: AnalyzeRequest | None = None,
) -> SavedProfile:
```

Add `AnalyzeRequest` to imports from `backend.models`.

Inside the insert column list, add `analyze_request_json` after `response_json`.

Inside values placeholders, change:

```sql
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```

to:

```sql
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
```

Inside inserted values, add:

```python
                analyze_request.model_dump_json() if analyze_request is not None else None,
```

between `response.model_dump_json(),` and `timestamp,`.

Update `list_saved_profiles` and `get_saved_profile` SELECT lists to include `analyze_request_json`.

Update `_summary_data(row)` to include:

```python
        "analyze_request": (
            AnalyzeRequest.model_validate_json(row["analyze_request_json"])
            if "analyze_request_json" in row.keys() and row["analyze_request_json"] is not None
            else None
        ),
```

- [ ] **Step 5: Add storage update and refresh request helpers**

Append to `backend/storage.py` after `get_saved_profile`:

```python
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
                updated_at = ?
            WHERE id = ?
            """,
            (
                response.place.label,
                coordinates_json,
                response.confidence.level.value,
                source_statuses_json,
                response.model_dump_json(),
                analyze_request.model_dump_json() if analyze_request is not None else None,
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
```

Append near `_connect`:

```python
def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
```

- [ ] **Step 6: Run storage tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py -q -p no:cacheprovider
```

Expected: storage tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/models.py backend/storage.py tests/test_storage.py
git commit -m "Persist saved report refresh metadata"
```

---

### Task 3: Add Saved Report Refresh Endpoint

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Add failing API refresh tests**

Append to `tests/test_main.py`:

```python
def test_refresh_saved_profile_updates_existing_report(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)
    analyze_response = client.post("/analyze", json={"query": "East Austin", "generic_mode": True})
    assert analyze_response.status_code == 200
    save_response = client.post(
        "/profiles",
        json={
            "response": analyze_response.json(),
            "analyze_request": {"query": "East Austin", "generic_mode": True},
        },
    )
    assert save_response.status_code == 200
    saved = save_response.json()

    refresh_response = client.post(f"/profiles/{saved['id']}/refresh")

    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["id"] == saved["id"]
    assert refreshed["created_at"] == saved["created_at"]
    assert refreshed["updated_at"] >= saved["updated_at"]
    assert refreshed["response"]["place"]["label"] == "East Austin"
    assert refreshed["analyze_request"]["generic_mode"] is True


def test_refresh_missing_saved_profile_returns_404(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)

    response = client.post("/profiles/missing-id/refresh")

    assert response.status_code == 404
    assert response.json()["detail"] == "Saved profile not found."
```

Also update `test_profile_endpoints_save_list_read_and_delete` save call:

```python
    save_response = client.post(
        "/profiles",
        json={
            "response": analyze_response.json(),
            "analyze_request": {"query": "East Austin"},
        },
    )
```

- [ ] **Step 2: Run API refresh tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_main.py::test_refresh_saved_profile_updates_existing_report tests/test_main.py::test_refresh_missing_saved_profile_returns_404 -q -p no:cacheprovider
```

Expected: fails because `/profiles/{id}/refresh` and the wrapped save body are not implemented.

- [ ] **Step 3: Add saved profile create payload model**

In `backend/models.py`, after `AnalyzeResponse`, add:

```python
class SaveProfileRequest(BaseModel):
    response: AnalyzeResponse
    analyze_request: AnalyzeRequest | None = None
```

- [ ] **Step 4: Update profile save endpoint and add refresh endpoint**

In `backend/main.py`, import:

```python
    SaveProfileRequest,
```

and from storage:

```python
    build_refresh_request,
    update_saved_profile,
```

Change create profile endpoint:

```python
@app.post("/profiles", response_model=SavedProfile)
async def create_profile(request: SaveProfileRequest) -> SavedProfile:
    return save_profile(request.response, analyze_request=request.analyze_request)
```

Add refresh endpoint before `@app.get("/profiles/{profile_id}")`:

```python
@app.post("/profiles/{profile_id}/refresh", response_model=SavedProfile)
async def refresh_profile(profile_id: str) -> SavedProfile:
    saved = get_saved_profile(profile_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved profile not found.")

    request = build_refresh_request(saved)
    if request.preference_profile_id is not None and get_preference_profile(request.preference_profile_id) is None:
        request = request.model_copy(update={"preference_profile_id": None})
        if not any(
            (
                request.preferences.car_reliance,
                request.preferences.energy_preference,
                request.preferences.top_priority,
                request.preferences.budget_sensitivity,
            )
        ):
            request = request.model_copy(update={"generic_mode": True})

    response = await analyze(request)
    updated = update_saved_profile(profile_id, response, analyze_request=request)
    if updated is None:
        raise HTTPException(status_code=404, detail="Saved profile not found.")
    return updated
```

- [ ] **Step 5: Keep backward compatibility for raw AnalyzeResponse saves**

Because the existing frontend currently posts a raw `AnalyzeResponse` to `/profiles`, adjust `create_profile` to accept both wrapped and legacy shapes:

```python
@app.post("/profiles", response_model=SavedProfile)
async def create_profile(payload: SaveProfileRequest | AnalyzeResponse) -> SavedProfile:
    if isinstance(payload, AnalyzeResponse):
        return save_profile(payload)
    return save_profile(payload.response, analyze_request=payload.analyze_request)
```

- [ ] **Step 6: Run main API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_main.py -q -p no:cacheprovider
```

Expected: main API tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/main.py backend/models.py tests/test_main.py
git commit -m "Add saved report refresh endpoint"
```

---

### Task 4: Add Frontend Freshness Utilities And API Client

**Files:**
- Create: `frontend/src/utils/freshness.js`
- Create: `frontend/src/utils/freshness.test.js`
- Modify: `frontend/src/utils/api.js`
- Modify: `frontend/src/utils/api.test.js`

- [ ] **Step 1: Write failing frontend freshness tests**

Create `frontend/src/utils/freshness.test.js`:

```javascript
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { freshnessState, formatGeneratedLabel } from './freshness.js';

const NOW = new Date('2026-05-07T12:00:00.000Z');

describe('freshnessState', () => {
  it('returns unknown without a timestamp', () => {
    assert.equal(freshnessState(null, { now: NOW }), 'unknown');
  });

  it('marks timestamps stale at seven days', () => {
    assert.equal(freshnessState('2026-05-01T12:00:00.000Z', { now: NOW }), 'fresh');
    assert.equal(freshnessState('2026-04-30T12:00:00.000Z', { now: NOW }), 'stale');
  });
});

describe('formatGeneratedLabel', () => {
  it('formats unknown and same-day labels', () => {
    assert.equal(formatGeneratedLabel(null, { now: NOW }), 'Generated time unknown');
    assert.equal(formatGeneratedLabel('2026-05-07T11:59:00.000Z', { now: NOW }), 'Generated just now');
    assert.equal(formatGeneratedLabel('2026-05-07T08:00:00.000Z', { now: NOW }), 'Generated today');
  });

  it('formats fresh and stale day counts', () => {
    assert.equal(formatGeneratedLabel('2026-05-04T12:00:00.000Z', { now: NOW }), 'Generated 3 days ago');
    assert.equal(formatGeneratedLabel('2026-04-25T12:00:00.000Z', { now: NOW }), 'Stale: generated 12 days ago');
  });
});
```

- [ ] **Step 2: Add failing API refresh client test**

Append to `frontend/src/utils/api.test.js`:

```javascript
import { refreshSavedProfile } from './api.js';

// Add inside describe or as a new describe block:
describe('refreshSavedProfile', () => {
  it('posts to the saved profile refresh endpoint', async () => {
    const requests = [];
    globalThis.fetch = async (url, options) => {
      requests.push({ url, options });
      return {
        ok: true,
        async json() {
          return { id: 'saved-1', response: { place: { label: 'East Austin' } } };
        },
      };
    };

    const result = await refreshSavedProfile('saved-1');

    assert.equal(result.id, 'saved-1');
    assert.equal(requests[0].url, 'http://127.0.0.1:8000/profiles/saved-1/refresh');
    assert.equal(requests[0].options.method, 'POST');
  });
});
```

If the import block already imports `analyzeNeighborhood`, change it to:

```javascript
import { analyzeNeighborhood, refreshSavedProfile } from './api.js';
```

- [ ] **Step 3: Run frontend utility tests and verify failure**

Run:

```powershell
node --test frontend/src/utils/freshness.test.js
node --test frontend/src/utils/api.test.js
```

Expected: fails because `freshness.js` and `refreshSavedProfile` do not exist.

- [ ] **Step 4: Implement frontend freshness helper**

Create `frontend/src/utils/freshness.js`:

```javascript
export const STALE_AFTER_DAYS = 7;

export function freshnessState(timestamp, { now = new Date() } = {}) {
  const generated = parseTimestamp(timestamp);
  if (!generated) return 'unknown';
  return daysBetween(generated, now) >= STALE_AFTER_DAYS ? 'stale' : 'fresh';
}

export function formatGeneratedLabel(timestamp, { now = new Date() } = {}) {
  const generated = parseTimestamp(timestamp);
  if (!generated) return 'Generated time unknown';
  const days = daysBetween(generated, now);
  if (days >= STALE_AFTER_DAYS) return `Stale: generated ${days} days ago`;
  if (days === 0) {
    const minutes = Math.floor((now.getTime() - generated.getTime()) / 60000);
    return minutes < 5 ? 'Generated just now' : 'Generated today';
  }
  return `Generated ${days} ${days === 1 ? 'day' : 'days'} ago`;
}

function parseTimestamp(timestamp) {
  if (!timestamp) return null;
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? null : date;
}

function daysBetween(start, end) {
  return Math.max(0, Math.floor((end.getTime() - start.getTime()) / 86400000));
}
```

- [ ] **Step 5: Add refresh API client**

In `frontend/src/utils/api.js`, add:

```javascript
export async function refreshSavedProfile(profileId) {
  const response = await fetch(`${API_BASE_URL}/profiles/${profileId}/refresh`, {
    method: 'POST',
  });
  return parseResponse(response, `Refresh saved profile failed with ${response.status}`);
}
```

- [ ] **Step 6: Run frontend utility tests**

Run:

```powershell
node --test frontend/src/utils/freshness.test.js
node --test frontend/src/utils/api.test.js
```

Expected: frontend utility tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src/utils/freshness.js frontend/src/utils/freshness.test.js frontend/src/utils/api.js frontend/src/utils/api.test.js
git commit -m "Add frontend freshness utilities"
```

---

### Task 5: Render Freshness And Source Updated Dates

**Files:**
- Create: `frontend/src/components/Freshness.jsx`
- Modify: `frontend/src/components/Profile.jsx`
- Modify: `frontend/src/components/Confidence.jsx`
- Modify: `frontend/src/uiContract.test.js`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add failing UI contract test**

Append to `frontend/src/uiContract.test.js`:

```javascript
test('profile renders freshness and source updated dates', () => {
  const profile = source('src/components/Profile.jsx');
  const freshness = source('src/components/Freshness.jsx');
  const confidence = source('src/components/Confidence.jsx');

  assert.match(profile, /<Freshness/);
  assert.match(freshness, /Refresh report/);
  assert.match(freshness, /Refresh analysis/);
  assert.match(freshness, /formatGeneratedLabel/);
  assert.match(confidence, /updated_at/);
  assert.match(confidence, /formatSourceDate/);
});
```

- [ ] **Step 2: Run UI contract test and verify failure**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: fails because `Freshness.jsx` does not exist and Profile/Confidence do not render freshness.

- [ ] **Step 3: Create Freshness component**

Create `frontend/src/components/Freshness.jsx`:

```jsx
import { formatGeneratedLabel, freshnessState } from '../utils/freshness.js';

export default function Freshness({
  generatedAt,
  savedProfileId,
  isRefreshing,
  refreshError,
  onRefresh,
}) {
  const state = freshnessState(generatedAt);
  const label = formatGeneratedLabel(generatedAt);
  const buttonText = savedProfileId ? 'Refresh report' : 'Refresh analysis';

  return (
    <section className={`panel-section freshness-card freshness-${state}`}>
      <div className="section-heading">
        <p className="eyebrow">Freshness</p>
        <h2>{label}</h2>
      </div>
      {onRefresh && (
        <button type="button" className="primary-button" onClick={onRefresh} disabled={isRefreshing}>
          {isRefreshing ? 'Refreshing...' : buttonText}
        </button>
      )}
      {refreshError && <p className="save-error">{refreshError}</p>}
    </section>
  );
}
```

- [ ] **Step 4: Render Freshness in Profile**

In `frontend/src/components/Profile.jsx`, import:

```jsx
import Freshness from './Freshness.jsx';
```

Change signature:

```jsx
export default function Profile({
  response,
  activePreferenceProfile,
  onSave,
  savedProfileId,
  saveError,
  isSaving,
  generatedAt,
  isRefreshing,
  refreshError,
  onRefresh,
}) {
```

Render before `Provenance`:

```jsx
      <Freshness
        generatedAt={generatedAt}
        savedProfileId={savedProfileId}
        isRefreshing={isRefreshing}
        refreshError={refreshError}
        onRefresh={onRefresh}
      />
```

- [ ] **Step 5: Show source updated dates in Confidence**

In `frontend/src/components/Confidence.jsx`, change each source row to:

```jsx
          <div className={`source-row source-${status.status}`} key={status.source}>
            <span>
              {status.source}
              {status.updated_at && <small>Updated {formatSourceDate(status.updated_at)}</small>}
            </span>
            <strong>{status.status}</strong>
          </div>
```

Append:

```jsx
function formatSourceDate(value) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value));
}
```

- [ ] **Step 6: Add freshness CSS**

Append before the mobile media query in `frontend/src/styles.css`:

```css
.freshness-card {
  gap: 10px;
  border: 1px solid var(--vc-border);
  border-radius: 10px;
  background: #ffffff;
  padding: 12px;
}

.freshness-card h2 {
  font-size: 0.98rem;
}

.freshness-stale {
  background: #fff8f5;
  border-color: rgba(138, 60, 50, 0.2);
}

.source-row span {
  display: grid;
  gap: 2px;
}

.source-row small {
  color: var(--vc-muted);
  font-size: 0.72rem;
  text-transform: none;
}
```

- [ ] **Step 7: Run UI contract test**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: UI contract tests pass.

- [ ] **Step 8: Commit**

Run:

```powershell
git add frontend/src/components/Freshness.jsx frontend/src/components/Profile.jsx frontend/src/components/Confidence.jsx frontend/src/uiContract.test.js frontend/src/styles.css
git commit -m "Render report freshness"
```

---

### Task 6: Wire Refresh State Through Frontend Hook And App

**Files:**
- Modify: `frontend/src/hooks/useNeighborhood.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/uiContract.test.js`

- [ ] **Step 1: Add failing source-contract test for refresh wiring**

Append to `frontend/src/uiContract.test.js`:

```javascript
test('app wires saved and unsaved refresh into profile', () => {
  const hook = source('src/hooks/useNeighborhood.js');
  const app = source('src/App.jsx');

  assert.match(hook, /refreshCurrentProfile/);
  assert.match(hook, /refreshSavedProfile/);
  assert.match(hook, /generatedAt/);
  assert.match(hook, /refreshError/);
  assert.match(app, /generatedAt=\{generatedAt\}/);
  assert.match(app, /refreshError=\{refreshError\}/);
  assert.match(app, /onRefresh=\{refreshCurrentProfile\}/);
});
```

- [ ] **Step 2: Run UI contract test and verify failure**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: fails because refresh state is not wired.

- [ ] **Step 3: Update `useNeighborhood` imports and state**

In `frontend/src/hooks/useNeighborhood.js`, change import:

```javascript
import { API_BASE_URL, analyzeNeighborhood, parseResponse, refreshSavedProfile } from '../utils/api.js';
```

Add state after `saveError`:

```javascript
  const [refreshError, setRefreshError] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [generatedAt, setGeneratedAt] = useState(null);
```

- [ ] **Step 4: Update data setters to track timestamps**

Change `setCurrentData`:

```javascript
  function setCurrentData(nextData, nextGeneratedAt = nextData ? new Date().toISOString() : null) {
    currentProfileRef.current = nextData;
    setData(nextData);
    setGeneratedAt(nextGeneratedAt);
  }
```

Inside `analyze(payload)`, after `const body = await analyzeNeighborhood(payload);`, add:

```javascript
      const timestamp = new Date().toISOString();
```

and change:

```javascript
      setCurrentData(body);
```

to:

```javascript
      setCurrentData(body, timestamp);
```

Inside `openSavedProfile`, change:

```javascript
    setCurrentData(body.response);
```

to:

```javascript
    setCurrentData(body.response, body.updated_at);
```

Inside `clearCurrentProfile`, add:

```javascript
    setRefreshError('');
```

- [ ] **Step 5: Wrap saves with request metadata**

Inside `saveCurrentProfile`, replace the request body:

```javascript
        body: JSON.stringify(profileData),
```

with:

```javascript
        body: JSON.stringify({
          response: profileData,
          analyze_request: lastRequest,
        }),
```

This lets new saved reports refresh with the same lens.

- [ ] **Step 6: Add refreshCurrentProfile**

Inside `useNeighborhood`, before `retry()`, add:

```javascript
  async function refreshCurrentProfile() {
    if (!data) return null;
    setRefreshError('');
    setIsRefreshing(true);
    try {
      if (savedProfileId) {
        const refreshed = await refreshSavedProfile(savedProfileId);
        await loadSavedProfiles();
        setCurrentData(refreshed.response, refreshed.updated_at);
        setSavedProfileId(refreshed.id);
        return refreshed.response;
      }
      if (!lastRequest) {
        throw new Error('No analysis request is available to refresh.');
      }
      const refreshed = await analyzeNeighborhood(lastRequest);
      setCurrentData(refreshed, new Date().toISOString());
      return refreshed;
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : 'Refresh failed');
      return null;
    } finally {
      setIsRefreshing(false);
    }
  }
```

Add to returned object:

```javascript
    refreshCurrentProfile,
    refreshError,
    isRefreshing,
    generatedAt,
```

- [ ] **Step 7: Wire App to Profile**

In `frontend/src/App.jsx`, destructure from `useNeighborhood()`:

```javascript
    refreshCurrentProfile,
    refreshError,
    isRefreshing,
    generatedAt,
```

Pass to `Profile`:

```jsx
              generatedAt={generatedAt}
              isRefreshing={isRefreshing}
              refreshError={refreshError}
              onRefresh={refreshCurrentProfile}
```

- [ ] **Step 8: Run UI contract and frontend utility tests**

Run:

```powershell
node --test frontend/src/uiContract.test.js
node --test frontend/src/utils/api.test.js
node --test frontend/src/utils/freshness.test.js
```

Expected: tests pass.

- [ ] **Step 9: Commit**

Run:

```powershell
git add frontend/src/hooks/useNeighborhood.js frontend/src/App.jsx frontend/src/uiContract.test.js
git commit -m "Wire report refresh state"
```

---

### Task 7: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`

- [ ] **Step 1: Update README current scope**

In `README.md`, add this bullet under Current Scope:

```markdown
- Source freshness labels and single-place refresh controls for current and saved reports.
```

Update the Phase 2 Status paragraph to:

```markdown
Phase 2A added explicit local saved neighborhood reports. Phase 2B added reusable local preference profiles and then corrected the UI so profiles work as an app-level analysis lens selected before address search. Phase 2C adds typed provenance and compact source-support UI so major claims can be traced to normalized source signals. Phase 2D adds a dedicated compare mode for 2-4 ad hoc places using the active preference profile or Generic lens. Phase 2E adds source freshness labels and single-place refresh controls for current and saved reports. The next Phase 2 slices should focus on deeper city-specific adapters and share/export flows.
```

- [ ] **Step 2: Update PLAN Phase 2 checklist**

In `PLAN.md`, change:

```markdown
- [ ] Add result regeneration controls so users can refresh stale data intentionally.
```

to:

```markdown
- [x] Add result regeneration controls so users can refresh stale data intentionally.
```

If this bullet appears only in the roadmap narrative and not the checklist, add this completed checklist item under `### Phase 2 - Comparison, Sharing, And Provenance`:

```markdown
- [x] Add source freshness labels and single-place report refresh controls.
```

- [ ] **Step 3: Run full backend verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check backend tests
```

Expected: all backend tests pass and ruff is clean.

- [ ] **Step 4: Run full frontend verification**

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

Start or reuse local servers and verify:

- Analyze a new unsaved place and see a freshness label.
- Click `Refresh analysis` and confirm the report updates without needing to save.
- Save a report, reopen it, and see `Refresh report`.
- Click `Refresh report` and confirm the saved report keeps the same ID.
- Confirm the refreshed saved report's `updated_at` changes.
- Confirm stale labels appear for a saved report older than 7 days.
- Confirm source rows show `Updated ...` when `updated_at` exists.
- Force a refresh failure and confirm the old report remains visible.
- Confirm compare mode still opens and its existing `Refresh Compare` behavior is unchanged.

- [ ] **Step 6: Commit docs**

Run:

```powershell
git add README.md PLAN.md
git commit -m "Document source freshness refresh"
```

- [ ] **Step 7: Check final status**

Run:

```powershell
git status --short --branch
```

Expected: no staged changes. Untracked `.tmp/` may remain only if it contains local screenshots/logs and is not staged.
