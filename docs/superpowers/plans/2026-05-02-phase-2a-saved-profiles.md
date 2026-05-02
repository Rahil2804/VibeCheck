# Phase 2A Saved Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit SQLite-backed saved profiles and visible OpenAI synthesis status to the local VibeCheck app.

**Architecture:** Backend changes come first: extend response models, make synthesis status explicit, then add a small SQLite storage layer and CRUD endpoints. Frontend changes add save/reopen/delete UI around the existing map-first analysis flow without changing the analyze contract beyond the new `synthesis` field.

**Tech Stack:** FastAPI, Pydantic, Python `sqlite3`, pytest, React + Vite, plain CSS.

---

## File Structure

- Modify `backend/models.py`: add synthesis status models and saved-profile API models.
- Modify `backend/pipeline.py`: return `synthesis` metadata from every analysis.
- Create `backend/storage.py`: SQLite schema setup and saved-profile CRUD functions.
- Modify `backend/main.py`: initialize storage and expose profile endpoints.
- Create `tests/test_storage.py`: storage behavior tests using isolated repo-local test DB files.
- Modify `tests/test_pipeline.py`: synthesis status tests for skipped, used, and fallback.
- Modify `tests/conftest.py`: set a repo-local SQLite path before API tests import `backend.main`.
- Modify `tests/test_main.py`: endpoint tests for save/list/read/delete.
- Modify `.gitignore`: ignore `data/` and `.test-data/`.
- Modify `frontend/src/hooks/useNeighborhood.js`: add saved-profile API calls.
- Modify `frontend/src/App.jsx`: manage saved profiles state and pass save controls.
- Modify `frontend/src/components/Profile.jsx`: render synthesis status and save action.
- Create `frontend/src/components/SavedProfiles.jsx`: compact saved-profile list panel.
- Modify `frontend/src/styles.css`: add compact save/list/status styles.
- Modify `README.md` and `PLAN.md`: document Phase 2A behavior and remaining Phase 2 slices.

---

### Task 1: Add Synthesis Status To Analyze Responses

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing pipeline tests**

Add these imports in `tests/test_pipeline.py`:

```python
from backend.models import SynthesisStatusCode
```

Add these tests after `test_pipeline_falls_back_when_synthesizer_fails`:

```python
@pytest.mark.asyncio
async def test_pipeline_reports_synthesis_used_when_synthesizer_returns_profile():
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
    assert response.synthesis.model is not None
    assert "OpenAI" in response.synthesis.message


@pytest.mark.asyncio
async def test_pipeline_reports_synthesis_skipped_when_synthesizer_returns_none():
    async def skipped_synthesizer(**_kwargs):
        return None

    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=skipped_synthesizer,
    )

    assert response.synthesis.status == SynthesisStatusCode.SKIPPED
    assert "deterministic" in response.synthesis.message


@pytest.mark.asyncio
async def test_pipeline_reports_synthesis_fallback_when_synthesizer_fails():
    async def failing_synthesizer(**_kwargs):
        raise RuntimeError("model failed")

    response = await analyze_neighborhood(
        AnalyzeRequest(query="East Austin"),
        source_fetchers={
            SourceName.CENSUS: _success_adapter,
            SourceName.HOUSING: _success_adapter,
            SourceName.REDDIT: _success_adapter,
            SourceName.ACCESS: _success_adapter,
        },
        source_timeout_seconds=1,
        profile_synthesizer=failing_synthesizer,
    )

    assert response.synthesis.status == SynthesisStatusCode.FALLBACK
    assert "fallback" in response.synthesis.message.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py -p no:cacheprovider
```

Expected: fail because `SynthesisStatusCode` and `response.synthesis` do not exist.

- [ ] **Step 3: Add model types**

In `backend/models.py`, add after `SourceStatusCode`:

```python
class SynthesisStatusCode(StrEnum):
    USED = "used"
    SKIPPED = "skipped"
    FALLBACK = "fallback"
```

Add after `SourceStatus`:

```python
class SynthesisStatus(BaseModel):
    status: SynthesisStatusCode
    model: str | None = None
    message: str
```

Update `AnalyzeResponse`:

```python
class AnalyzeResponse(BaseModel):
    place: Place
    profile: NeighborhoodProfile
    fit: FitScore | None = None
    confidence: Confidence
    source_statuses: list[SourceStatus]
    synthesis: SynthesisStatus
```

- [ ] **Step 4: Wire pipeline synthesis status**

In `backend/pipeline.py`, import the new types:

```python
    SynthesisStatus,
    SynthesisStatusCode,
```

Update the synthesis block in `analyze_neighborhood`:

```python
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    synthesis = SynthesisStatus(
        status=SynthesisStatusCode.SKIPPED,
        model=None,
        message="OpenAI synthesis was skipped; deterministic profile was used.",
    )
    try:
        profile = await synthesizer(
            place_label=place.label,
            source_data={source.value: data for source, data in source_data.items()},
            caveats=confidence.caveats,
        )
        if profile is not None:
            synthesis = SynthesisStatus(
                status=SynthesisStatusCode.USED,
                model=model_name,
                message="OpenAI generated the profile from normalized source data.",
            )
    except Exception:
        profile = None
        synthesis = SynthesisStatus(
            status=SynthesisStatusCode.FALLBACK,
            model=model_name,
            message="OpenAI synthesis failed; deterministic fallback profile was used.",
        )
    if profile is None:
        profile = fallback_profile
```

Update the return:

```python
    return AnalyzeResponse(
        place=place,
        profile=profile,
        fit=fit,
        confidence=confidence,
        source_statuses=statuses,
        synthesis=synthesis,
    )
```

- [ ] **Step 5: Run tests to verify task passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py -p no:cacheprovider
```

Expected: all `tests/test_pipeline.py` tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add backend/models.py backend/pipeline.py tests/test_pipeline.py
git commit -m "Add synthesis status to analyze responses"
```

---

### Task 2: Add SQLite Storage Layer

**Files:**
- Modify: `backend/models.py`
- Create: `backend/storage.py`
- Modify: `.gitignore`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Create `tests/test_storage.py`:

```python
from pathlib import Path
from uuid import uuid4

import pytest

from backend.models import (
    AnalyzeResponse,
    Confidence,
    NeighborhoodProfile,
    Place,
    SourceName,
    SourceStatus,
    SourceStatusCode,
    SynthesisStatus,
    SynthesisStatusCode,
    Trajectory,
    TrajectoryDirection,
    VibeScores,
    WhoLivesHere,
)
from backend.storage import (
    delete_saved_profile,
    get_saved_profile,
    initialize_database,
    list_saved_profiles,
    save_profile,
)


def _db_path() -> Path:
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    return directory / f"{uuid4()}.db"


def _response(label: str) -> AnalyzeResponse:
    return AnalyzeResponse(
        place=Place(label=label),
        profile=NeighborhoodProfile(
            overview=f"{label} overview.",
            vibe_scores=VibeScores(
                walkability=70,
                transit_access=60,
                affordability=50,
                quiet=55,
                social_scene=65,
            ),
            who_lives_here=WhoLivesHere(),
            honest_pros=["Readable profile."],
            honest_cons=["Thin source data."],
            trajectory=Trajectory(
                direction=TrajectoryDirection.UNCERTAIN,
                summary="Trajectory is uncertain.",
            ),
        ),
        confidence=Confidence(
            level="low",
            available_sources=["mapbox"],
            missing_sources=["census"],
            caveats=["Thin data."],
        ),
        source_statuses=[
            SourceStatus(
                source=SourceName.MAPBOX,
                status=SourceStatusCode.SUCCESS,
                message="Place resolved.",
            )
        ],
        synthesis=SynthesisStatus(
            status=SynthesisStatusCode.SKIPPED,
            model=None,
            message="OpenAI synthesis was skipped; deterministic profile was used.",
        ),
    )


def test_save_profile_returns_metadata_and_persists_response():
    db_path = _db_path()
    initialize_database(db_path)

    saved = save_profile(_response("East Austin"), db_path)

    assert saved.id
    assert saved.place_label == "East Austin"
    assert saved.confidence_level == "low"
    assert saved.response.place.label == "East Austin"


def test_list_saved_profiles_returns_newest_first_without_full_response():
    db_path = _db_path()
    initialize_database(db_path)
    first = save_profile(_response("First Place"), db_path)
    second = save_profile(_response("Second Place"), db_path)

    summaries = list_saved_profiles(db_path)

    assert [summary.id for summary in summaries] == [second.id, first.id]
    assert summaries[0].place_label == "Second Place"
    assert not hasattr(summaries[0], "response")


def test_get_saved_profile_returns_original_response():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Kensington Market"), db_path)

    found = get_saved_profile(saved.id, db_path)

    assert found is not None
    assert found.response.place.label == "Kensington Market"
    assert found.response.profile.overview == "Kensington Market overview."


def test_delete_saved_profile_removes_row():
    db_path = _db_path()
    initialize_database(db_path)
    saved = save_profile(_response("Deleted Place"), db_path)

    assert delete_saved_profile(saved.id, db_path) is True
    assert get_saved_profile(saved.id, db_path) is None
    assert delete_saved_profile(saved.id, db_path) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_storage.py -p no:cacheprovider
```

Expected: fail because `backend.storage` and saved-profile models do not exist.

- [ ] **Step 3: Add saved-profile models**

In `backend/models.py`, add after `AnalyzeResponse`:

```python
class SavedProfileSummary(BaseModel):
    id: str
    place_label: str
    coordinates: Coordinates | None = None
    confidence_level: ConfidenceLevel
    source_statuses: list[SourceStatus]
    created_at: str
    updated_at: str


class SavedProfile(SavedProfileSummary):
    response: AnalyzeResponse


class DeleteProfileResponse(BaseModel):
    deleted: bool
```

- [ ] **Step 4: Implement storage module**

Create `backend/storage.py`:

```python
import json
import os
import sqlite3
from pathlib import Path
from uuid import uuid4
from datetime import UTC, datetime

from backend.models import AnalyzeResponse, SavedProfile, SavedProfileSummary


def get_database_path() -> Path:
    return Path(os.getenv("SQLITE_PATH", "data/vibecheck.db"))


def initialize_database(db_path: str | Path | None = None) -> None:
    path = Path(db_path) if db_path is not None else get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
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
        connection.commit()


def save_profile(response: AnalyzeResponse, db_path: str | Path | None = None) -> SavedProfile:
    path = Path(db_path) if db_path is not None else get_database_path()
    initialize_database(path)
    now = _utc_now()
    profile_id = uuid4().hex
    coordinates_json = (
        response.place.coordinates.model_dump_json()
        if response.place.coordinates is not None
        else None
    )
    source_statuses_json = json.dumps(
        [status.model_dump(mode="json") for status in response.source_statuses]
    )
    response_json = response.model_dump_json()

    with sqlite3.connect(path) as connection:
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
                response_json,
                now,
                now,
            ),
        )
        connection.commit()

    saved = get_saved_profile(profile_id, path)
    if saved is None:
        raise RuntimeError("Saved profile could not be loaded after insert.")
    return saved


def list_saved_profiles(db_path: str | Path | None = None) -> list[SavedProfileSummary]:
    path = Path(db_path) if db_path is not None else get_database_path()
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """
            SELECT id, place_label, coordinates_json, confidence_level,
                   source_statuses_json, created_at, updated_at
            FROM saved_profiles
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [_summary_from_row(row) for row in rows]


def get_saved_profile(profile_id: str, db_path: str | Path | None = None) -> SavedProfile | None:
    path = Path(db_path) if db_path is not None else get_database_path()
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            """
            SELECT id, place_label, coordinates_json, confidence_level,
                   source_statuses_json, response_json, created_at, updated_at
            FROM saved_profiles
            WHERE id = ?
            """,
            (profile_id,),
        ).fetchone()
    if row is None:
        return None
    summary = _summary_from_row((row[0], row[1], row[2], row[3], row[4], row[6], row[7]))
    response = AnalyzeResponse.model_validate_json(row[5])
    return SavedProfile(**summary.model_dump(), response=response)


def delete_saved_profile(profile_id: str, db_path: str | Path | None = None) -> bool:
    path = Path(db_path) if db_path is not None else get_database_path()
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        cursor = connection.execute("DELETE FROM saved_profiles WHERE id = ?", (profile_id,))
        connection.commit()
    return cursor.rowcount > 0


def _summary_from_row(row: tuple) -> SavedProfileSummary:
    coordinates = json.loads(row[2]) if row[2] else None
    source_statuses = json.loads(row[4])
    return SavedProfileSummary(
        id=row[0],
        place_label=row[1],
        coordinates=coordinates,
        confidence_level=row[3],
        source_statuses=source_statuses,
        created_at=row[5],
        updated_at=row[6],
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
```

- [ ] **Step 5: Ignore local database files**

Add to `.gitignore` near the test/cache ignores:

```gitignore
.test-data/
data/
```

- [ ] **Step 6: Run tests to verify task passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_storage.py -p no:cacheprovider
```

Expected: all `tests/test_storage.py` tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add .gitignore backend/models.py backend/storage.py tests/test_storage.py
git commit -m "Add SQLite saved profile storage"
```

---

### Task 3: Add Saved Profile API Endpoints

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Isolate test database before API imports**

In `tests/conftest.py`, add:

```python
os.environ["SQLITE_PATH"] = ".test-data/pytest-vibecheck.db"
```

The file should now look like:

```python
import os


os.environ["MAPBOX_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["SQLITE_PATH"] = ".test-data/pytest-vibecheck.db"
```

- [ ] **Step 2: Write failing endpoint tests**

In `tests/test_main.py`, add imports:

```python
from pathlib import Path
from uuid import uuid4
```

Add a helper after imports:

```python
def _test_sqlite_path(monkeypatch) -> Path:
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    db_path = directory / f"api-{uuid4()}.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    return db_path
```

Add this test after `test_analyze_returns_partial_profile_for_valid_query`:

```python
def test_profile_endpoints_save_list_read_and_delete(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)
    analyze_response = client.post("/analyze", json={"query": "East Austin"})
    assert analyze_response.status_code == 200

    save_response = client.post("/profiles", json=analyze_response.json())
    assert save_response.status_code == 200
    saved = save_response.json()
    profile_id = saved["id"]
    assert saved["place_label"] == "East Austin"
    assert saved["response"]["place"]["label"] == "East Austin"

    list_response = client.get("/profiles")
    assert list_response.status_code == 200
    summaries = list_response.json()
    assert summaries[0]["id"] == profile_id
    assert "response" not in summaries[0]

    get_response = client.get(f"/profiles/{profile_id}")
    assert get_response.status_code == 200
    assert get_response.json()["response"]["place"]["label"] == "East Austin"

    delete_response = client.delete(f"/profiles/{profile_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    missing_response = client.get(f"/profiles/{profile_id}")
    assert missing_response.status_code == 404
```

Add this test:

```python
def test_delete_missing_profile_returns_404(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)

    response = client.delete("/profiles/missing-id")

    assert response.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_main.py -p no:cacheprovider
```

Expected: fail with 404 for missing `/profiles` routes.

- [ ] **Step 4: Implement endpoints**

In `backend/main.py`, update imports:

```python
from fastapi import FastAPI, HTTPException
```

Update model imports:

```python
from backend.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    DeleteProfileResponse,
    SavedProfile,
    SavedProfileSummary,
)
```

Add storage imports:

```python
from backend.storage import (
    delete_saved_profile,
    get_saved_profile,
    initialize_database,
    list_saved_profiles,
    save_profile,
)
```

After `load_environment()` add a best-effort local initialization. This makes local startup convenient but still lets `/analyze` work if the database cannot initialize:

```python
try:
    initialize_database()
except Exception:
    pass
```

Update CORS methods so browser deletes work:

```python
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
```

Add routes after `analyze`:

```python
@app.post("/profiles", response_model=SavedProfile)
async def create_profile(response: AnalyzeResponse) -> SavedProfile:
    return save_profile(response)


@app.get("/profiles", response_model=list[SavedProfileSummary])
async def profiles() -> list[SavedProfileSummary]:
    return list_saved_profiles()


@app.get("/profiles/{profile_id}", response_model=SavedProfile)
async def profile(profile_id: str) -> SavedProfile:
    saved = get_saved_profile(profile_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved profile not found.")
    return saved


@app.delete("/profiles/{profile_id}", response_model=DeleteProfileResponse)
async def delete_profile(profile_id: str) -> DeleteProfileResponse:
    deleted = delete_saved_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved profile not found.")
    return DeleteProfileResponse(deleted=True)
```

- [ ] **Step 5: Run tests to verify task passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_main.py -p no:cacheprovider
```

Expected: all `tests/test_main.py` tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add backend/main.py tests/conftest.py tests/test_main.py
git commit -m "Add saved profile API endpoints"
```

---

### Task 4: Add Frontend Saved Profiles Flow

**Files:**
- Modify: `frontend/src/hooks/useNeighborhood.js`
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/components/SavedProfiles.jsx`
- Modify: `frontend/src/components/Profile.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add profile API calls to the hook**

In `frontend/src/hooks/useNeighborhood.js`, add state:

```javascript
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [saveError, setSaveError] = useState('');
  const [savedProfileId, setSavedProfileId] = useState('');
```

Add these functions before `retry`:

```javascript
  async function loadSavedProfiles() {
    const response = await fetch(`${API_BASE_URL}/profiles`);
    if (!response.ok) {
      throw new Error(`Load saved profiles failed with ${response.status}`);
    }
    const body = await response.json();
    setSavedProfiles(body);
    return body;
  }

  async function saveCurrentProfile(profileData = data) {
    if (!profileData) return null;
    setSaveError('');
    const response = await fetch(`${API_BASE_URL}/profiles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData),
    });
    if (!response.ok) {
      const message = `Save failed with ${response.status}`;
      setSaveError(message);
      throw new Error(message);
    }
    const body = await response.json();
    setSavedProfileId(body.id);
    await loadSavedProfiles();
    return body;
  }

  async function openSavedProfile(profileId) {
    const response = await fetch(`${API_BASE_URL}/profiles/${profileId}`);
    if (!response.ok) {
      throw new Error(`Open saved profile failed with ${response.status}`);
    }
    const body = await response.json();
    setData(body.response);
    setError('');
    setSavedProfileId(body.id);
    return body;
  }

  async function deleteSavedProfile(profileId) {
    const response = await fetch(`${API_BASE_URL}/profiles/${profileId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Delete saved profile failed with ${response.status}`);
    }
    await loadSavedProfiles();
  }
```

Update the return:

```javascript
  return {
    analyze,
    retry,
    data,
    error,
    loading,
    savedProfiles,
    savedProfileId,
    saveError,
    loadSavedProfiles,
    saveCurrentProfile,
    openSavedProfile,
    deleteSavedProfile,
  };
```

- [ ] **Step 2: Add saved profiles component**

Create `frontend/src/components/SavedProfiles.jsx`:

```javascript
export default function SavedProfiles({ profiles, onOpen, onDelete, onRefresh }) {
  return (
    <section className="saved-profiles">
      <div className="saved-profiles-header">
        <div>
          <p className="eyebrow">Saved</p>
          <h2>Profiles</h2>
        </div>
        <button type="button" onClick={onRefresh}>Refresh</button>
      </div>
      {profiles.length === 0 ? (
        <p className="saved-empty">Saved profiles will appear here.</p>
      ) : (
        <div className="saved-list">
          {profiles.map((profile) => (
            <article className="saved-row" key={profile.id}>
              <button type="button" onClick={() => onOpen(profile.id)}>
                <strong>{profile.place_label}</strong>
                <span>{profile.confidence_level} confidence</span>
              </button>
              <button
                type="button"
                className="icon-danger"
                aria-label={`Delete ${profile.place_label}`}
                onClick={() => onDelete(profile.id)}
              >
                Delete
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 3: Wire App state**

In `frontend/src/App.jsx`, update imports:

```javascript
import { useEffect, useMemo, useState } from 'react';
import SavedProfiles from './components/SavedProfiles.jsx';
```

Update hook destructuring:

```javascript
  const {
    analyze,
    data,
    error,
    loading,
    retry,
    savedProfiles,
    savedProfileId,
    saveError,
    loadSavedProfiles,
    saveCurrentProfile,
    openSavedProfile,
    deleteSavedProfile,
  } = useNeighborhood();
```

Add after `analyzePayload`:

```javascript
  useEffect(() => {
    loadSavedProfiles().catch(() => {});
  }, []);
```

Add `SavedProfiles` inside `analysis-panel`, after `Questionnaire`:

```javascript
            <SavedProfiles
              profiles={savedProfiles}
              onRefresh={() => loadSavedProfiles().catch(() => {})}
              onOpen={(id) => openSavedProfile(id).catch(() => {})}
              onDelete={(id) => deleteSavedProfile(id).catch(() => {})}
            />
```

Update the profile render:

```javascript
            {data && (
              <Profile
                response={data}
                savedProfileId={savedProfileId}
                saveError={saveError}
                onSave={() => saveCurrentProfile(data).catch(() => null)}
              />
            )}
```

- [ ] **Step 4: Render save and synthesis status in Profile**

In `frontend/src/components/Profile.jsx`, update signature:

```javascript
export default function Profile({ response, onSave, savedProfileId, saveError }) {
```

Update destructuring:

```javascript
  const { profile, fit, confidence, source_statuses: statuses, synthesis } = response;
```

Add after the heading:

```javascript
      <div className="profile-actions">
        <button type="button" className="primary-button" onClick={onSave}>
          {savedProfileId ? 'Saved' : 'Save profile'}
        </button>
        {saveError && <span className="save-error">{saveError}</span>}
      </div>
      {synthesis && (
        <article className={`synthesis-card synthesis-${synthesis.status}`}>
          <span>AI synthesis: {synthesis.status}</span>
          <p>{synthesis.message}</p>
        </article>
      )}
```

- [ ] **Step 5: Add styles**

Add near existing panel/card styles in `frontend/src/styles.css`:

```css
.saved-profiles,
.synthesis-card {
  border: 1px solid rgba(25, 39, 32, 0.12);
  border-radius: 8px;
  background: #f8faf8;
  padding: 12px;
}

.saved-profiles {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.saved-profiles-header,
.profile-actions,
.saved-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.saved-profiles-header h2 {
  margin: 0;
  font-size: 1rem;
}

.saved-profiles button,
.profile-actions button {
  min-height: 36px;
  border-radius: 6px;
  border: 1px solid rgba(25, 39, 32, 0.18);
  padding: 0 10px;
}

.saved-list {
  display: grid;
  gap: 8px;
}

.saved-row > button:first-child {
  display: grid;
  flex: 1;
  gap: 2px;
  background: white;
  color: #17211b;
  text-align: left;
}

.saved-row span,
.saved-empty,
.synthesis-card p,
.save-error {
  color: #476057;
  font-size: 0.86rem;
}

.icon-danger,
.save-error {
  color: #8a3c32;
}

.synthesis-card {
  display: grid;
  gap: 4px;
}

.synthesis-card span {
  font-weight: 700;
  text-transform: capitalize;
}

.synthesis-used {
  border-color: rgba(36, 99, 79, 0.25);
}

.synthesis-fallback,
.synthesis-skipped {
  border-color: rgba(138, 60, 50, 0.18);
}
```

- [ ] **Step 6: Run frontend build**

Run:

```powershell
Set-Location frontend
npm.cmd run build
```

Expected: build exits successfully.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src/hooks/useNeighborhood.js frontend/src/App.jsx frontend/src/components/SavedProfiles.jsx frontend/src/components/Profile.jsx frontend/src/styles.css
git commit -m "Add saved profiles frontend flow"
```

---

### Task 5: Update Documentation And Phase Tracking

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`

- [ ] **Step 1: Update README current scope**

In `README.md`, add to Current Scope:

```markdown
- Explicit SQLite-backed saved profiles with local reopen/delete controls.
- Visible AI synthesis status showing whether OpenAI was used, skipped, or fallback was used.
```

Add backend env var:

```bash
SQLITE_PATH=data/vibecheck.db
```

Add a short storage note:

```markdown
Saved profiles are stored locally in SQLite at `data/vibecheck.db` by default. The `data/` directory is ignored by git and should not contain API keys or raw provider credentials.
```

- [ ] **Step 2: Update PLAN Phase 2 checklist**

In `PLAN.md`, update Phase 2:

```markdown
- [x] Add SQLite-backed local saved profiles with provider-compliant freshness rules.
- [ ] Add public shareable profile URLs only if a hosted demo is later desired.
- [ ] Add compare mode for two or more places.
- [ ] Add provenance metadata to major generated claims.
- [x] Add UI affordances for source freshness and "why this claim" explanations for synthesis status.
- [ ] Add regression tests for cache freshness, compare response shape, and provenance display.
```

Add `SQLITE_PATH=data/vibecheck.db` to the environment variables section.

- [ ] **Step 3: Commit docs**

Run:

```powershell
git add README.md PLAN.md
git commit -m "Document Phase 2A saved profiles"
```

---

### Task 6: Full Verification

**Files:**
- No file edits expected.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 2: Run backend lint**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check backend tests
```

Expected: `All checks passed!`

- [ ] **Step 3: Run frontend build**

Run:

```powershell
Set-Location frontend
npm.cmd run build
```

Expected: Vite build completes successfully.

- [ ] **Step 4: Manual local smoke test**

Start backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Start frontend:

```powershell
Set-Location frontend
npm.cmd run dev
```

Verify:

- Select a Mapbox autocomplete result.
- Click Analyze.
- Confirm profile shows synthesis status.
- Click Save profile.
- Confirm saved profile appears in the saved list.
- Reopen the saved profile.
- Delete it.

- [ ] **Step 5: Final status check**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree, branch ahead of `origin/main` by the Phase 2A commits until pushed.
