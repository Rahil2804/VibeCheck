# Phase 2B Preference Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multiple local preference profiles that can be selected once and reused for every neighborhood analysis.

**Architecture:** Extend the existing FastAPI/Pydantic/SQLite backend with a separate `preference_profiles` table and REST endpoints. Keep saved neighborhood reports separate from reusable preference profiles. The React frontend gets a compact profile switcher plus create/edit controls, and analyze requests send `preference_profile_id` when a saved preference profile is selected.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, React, Vite, plain CSS.

---

## File Structure

- Modify `backend/models.py`: add preference-profile enums/models, request/update/delete response models, and `AnalyzeRequest.preference_profile_id`.
- Modify `backend/storage.py`: keep saved report CRUD and add preference-profile table/CRUD/default helpers.
- Modify `backend/main.py`: expose preference-profile API routes, allow `PUT` in CORS, resolve selected preference profiles before analysis.
- Modify `tests/test_models.py`: verify safe-category validation and `AnalyzeRequest.preference_profile_id`.
- Modify `tests/test_storage.py`: verify SQLite profile CRUD/default ordering.
- Modify `tests/test_main.py`: verify API endpoints and `/analyze` integration.
- Modify `frontend/src/hooks/useNeighborhood.js`: add preference-profile API functions and state.
- Create `frontend/src/components/PreferenceProfiles.jsx`: compact selector and create/edit form.
- Modify `frontend/src/components/Questionnaire.jsx`: support profile-managed copy and disabled states.
- Modify `frontend/src/components/Profile.jsx`: rename saved neighborhood report action text.
- Modify `frontend/src/components/SavedProfiles.jsx`: rename saved-report copy.
- Modify `frontend/src/App.jsx`: wire selected preference profile into questionnaire and analyze payload.
- Modify `frontend/src/styles.css`: style profile switcher/form controls using existing panel/card patterns.
- Modify `README.md` and `PLAN.md`: document Phase 2B behavior and remaining Phase 2 work.

---

### Task 1: Add Preference Profile Models

**Files:**
- Modify: `backend/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing model tests**

Append these tests to `tests/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from backend.models import (
    AnalyzeRequest,
    PreferenceProfileCreate,
    PreferenceProfileUpdate,
)


def test_preference_profile_create_accepts_safe_expanded_fields():
    profile = PreferenceProfileCreate(
        name="No car lifestyle",
        car_reliance="no_car",
        energy_preference="balanced",
        top_priority="transit_access",
        budget_sensitivity="moderate",
        commute_anchor={"label": "Union Station", "lat": 43.645, "lng": -79.38},
        max_monthly_rent=2200,
        must_haves=["transit", "groceries"],
        deal_breakers=["lower_rent_pressure"],
        notes="Likes short errands and transit access.",
    )

    assert profile.name == "No car lifestyle"
    assert profile.car_reliance == "no_car"
    assert profile.commute_anchor is not None
    assert profile.commute_anchor.label == "Union Station"
    assert profile.must_haves == ["transit", "groceries"]


def test_preference_profile_rejects_unsafe_categories():
    with pytest.raises(ValidationError):
        PreferenceProfileCreate(
            name="Unsafe profile",
            must_haves=["schools"],
        )


def test_preference_profile_update_allows_partial_changes():
    update = PreferenceProfileUpdate(name="Budget-first", must_haves=["lower_rent_pressure"])

    assert update.name == "Budget-first"
    assert update.must_haves == ["lower_rent_pressure"]
    assert update.preferences.car_reliance is None


def test_analyze_request_accepts_preference_profile_id():
    request = AnalyzeRequest(query="East Austin", preference_profile_id="profile-123")

    assert request.preference_profile_id == "profile-123"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_models.py -q
```

Expected: fail because `PreferenceProfileCreate` and `PreferenceProfileUpdate` do not exist, and `AnalyzeRequest` does not accept `preference_profile_id`.

- [ ] **Step 3: Add model types**

In `backend/models.py`, add these imports:

```python
from typing import Self
```

Add these enums and models after `BudgetSensitivity`:

```python
class PreferenceCategory(StrEnum):
    TRANSIT = "transit"
    WALKABILITY = "walkability"
    PARKS = "parks"
    GROCERIES = "groceries"
    RESTAURANTS = "restaurants"
    QUIET = "quiet"
    SOCIAL_SCENE = "social_scene"
    LOWER_RENT_PRESSURE = "lower_rent_pressure"
```

Add these models after `Preferences`:

```python
class CommuteAnchor(BaseModel):
    label: str = Field(min_length=1)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def require_both_coordinates(self) -> Self:
        if (self.lat is None) != (self.lng is None):
            raise ValueError("Provide both commute anchor latitude and longitude, or neither.")
        return self


class PreferenceProfileBase(Preferences):
    generic_mode: bool = False
    commute_anchor: CommuteAnchor | None = None
    max_monthly_rent: int | None = Field(default=None, ge=0)
    must_haves: list[PreferenceCategory] = Field(default_factory=list)
    deal_breakers: list[PreferenceCategory] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=1000)

    @property
    def preferences(self) -> Preferences:
        return Preferences(
            car_reliance=self.car_reliance,
            energy_preference=self.energy_preference,
            top_priority=self.top_priority,
            budget_sensitivity=self.budget_sensitivity,
        )


class PreferenceProfileCreate(PreferenceProfileBase):
    name: str = Field(min_length=1, max_length=80)


class PreferenceProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    car_reliance: CarReliance | None = None
    energy_preference: EnergyPreference | None = None
    top_priority: TopPriority | None = None
    budget_sensitivity: BudgetSensitivity | None = None
    generic_mode: bool | None = None
    commute_anchor: CommuteAnchor | None = None
    max_monthly_rent: int | None = Field(default=None, ge=0)
    must_haves: list[PreferenceCategory] | None = None
    deal_breakers: list[PreferenceCategory] | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @property
    def preferences(self) -> Preferences:
        return Preferences(
            car_reliance=self.car_reliance,
            energy_preference=self.energy_preference,
            top_priority=self.top_priority,
            budget_sensitivity=self.budget_sensitivity,
        )


class PreferenceProfile(PreferenceProfileCreate):
    id: str
    is_default: bool = False
    created_at: str
    updated_at: str


class DeletePreferenceProfileResponse(BaseModel):
    deleted: bool
```

Update `AnalyzeRequest`:

```python
class AnalyzeRequest(BaseModel):
    query: str | None = Field(default=None, min_length=1)
    coordinates: Coordinates | None = None
    preferences: Preferences = Field(default_factory=Preferences)
    generic_mode: bool = False
    preference_profile_id: str | None = Field(default=None, min_length=1)
```

- [ ] **Step 4: Run model tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_models.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add backend/models.py tests/test_models.py
git commit -m "Add preference profile models"
```

---

### Task 2: Add SQLite Preference Profile Storage

**Files:**
- Modify: `backend/storage.py`
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Append these tests to `tests/test_storage.py`:

```python
from backend.models import PreferenceProfileCreate, PreferenceProfileUpdate
from backend.storage import (
    create_preference_profile,
    delete_preference_profile,
    get_preference_profile,
    list_preference_profiles,
    set_default_preference_profile,
    update_preference_profile,
)


def test_create_preference_profile_persists_expanded_fields():
    db_path = _db_path()
    initialize_database(db_path)

    profile = create_preference_profile(
        PreferenceProfileCreate(
            name="Rahil",
            car_reliance="no_car",
            commute_anchor={"label": "Union Station", "lat": 43.645, "lng": -79.38},
            max_monthly_rent=2200,
            must_haves=["transit", "groceries"],
            notes="Local only.",
        ),
        db_path,
    )

    found = get_preference_profile(profile.id, db_path)

    assert found is not None
    assert found.name == "Rahil"
    assert found.is_default is True
    assert found.commute_anchor is not None
    assert found.commute_anchor.label == "Union Station"
    assert found.must_haves == ["transit", "groceries"]
    assert found.notes == "Local only."


def test_list_preference_profiles_orders_default_first_then_updated():
    db_path = _db_path()
    initialize_database(db_path)
    first = create_preference_profile(PreferenceProfileCreate(name="First"), db_path)
    second = create_preference_profile(PreferenceProfileCreate(name="Second"), db_path)

    set_default_preference_profile(second.id, db_path)
    profiles = list_preference_profiles(db_path)

    assert [profile.id for profile in profiles] == [second.id, first.id]
    assert profiles[0].is_default is True
    assert profiles[1].is_default is False


def test_update_preference_profile_changes_only_supplied_fields():
    db_path = _db_path()
    initialize_database(db_path)
    profile = create_preference_profile(
        PreferenceProfileCreate(name="Original", car_reliance="no_car", must_haves=["transit"]),
        db_path,
    )

    updated = update_preference_profile(
        profile.id,
        PreferenceProfileUpdate(name="Updated", deal_breakers=["quiet"]),
        db_path,
    )

    assert updated is not None
    assert updated.name == "Updated"
    assert updated.car_reliance == "no_car"
    assert updated.must_haves == ["transit"]
    assert updated.deal_breakers == ["quiet"]


def test_delete_preference_profile_removes_only_target_profile():
    db_path = _db_path()
    initialize_database(db_path)
    first = create_preference_profile(PreferenceProfileCreate(name="First"), db_path)
    second = create_preference_profile(PreferenceProfileCreate(name="Second"), db_path)

    assert delete_preference_profile(first.id, db_path) is True
    assert get_preference_profile(first.id, db_path) is None
    assert get_preference_profile(second.id, db_path) is not None
    assert delete_preference_profile(first.id, db_path) is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py -q
```

Expected: fail because preference-profile storage functions do not exist.

- [ ] **Step 3: Add storage imports**

In `backend/storage.py`, extend the model imports:

```python
from backend.models import (
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
```

- [ ] **Step 4: Add table initialization**

Inside `initialize_database()`, after the existing `CREATE TABLE IF NOT EXISTS saved_profiles` statement, add:

```python
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
                must_haves_json TEXT NOT NULL,
                deal_breakers_json TEXT NOT NULL,
                notes TEXT,
                is_default INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
```

- [ ] **Step 5: Add create/list/get helpers**

Add these functions before `_connect()`:

```python
def create_preference_profile(
    profile: PreferenceProfileCreate,
    db_path: Path | None = None,
) -> PreferenceProfile:
    path = db_path or get_database_path()
    initialize_database(path)

    profile_id = uuid4().hex
    timestamp = _utc_timestamp()

    with _connect(path) as connection:
        existing_count = connection.execute("SELECT COUNT(*) FROM preference_profiles").fetchone()[0]
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
                must_haves_json,
                deal_breakers_json,
                notes,
                is_default,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
```

- [ ] **Step 6: Add update/default/delete helpers**

Add these functions after `get_preference_profile()`:

```python
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

    merged = PreferenceProfileCreate(
        name=update.name if update.name is not None else current.name,
        car_reliance=update.car_reliance if update.car_reliance is not None else current.car_reliance,
        energy_preference=(
            update.energy_preference
            if update.energy_preference is not None
            else current.energy_preference
        ),
        top_priority=update.top_priority if update.top_priority is not None else current.top_priority,
        budget_sensitivity=(
            update.budget_sensitivity
            if update.budget_sensitivity is not None
            else current.budget_sensitivity
        ),
        generic_mode=update.generic_mode if update.generic_mode is not None else current.generic_mode,
        commute_anchor=update.commute_anchor if update.commute_anchor is not None else current.commute_anchor,
        max_monthly_rent=(
            update.max_monthly_rent
            if update.max_monthly_rent is not None
            else current.max_monthly_rent
        ),
        must_haves=update.must_haves if update.must_haves is not None else current.must_haves,
        deal_breakers=(
            update.deal_breakers
            if update.deal_breakers is not None
            else current.deal_breakers
        ),
        notes=update.notes if update.notes is not None else current.notes,
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
```

- [ ] **Step 7: Add row/value helpers**

Add these helpers before `_connect()`:

```python
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
```

- [ ] **Step 8: Run storage tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py -q
```

Expected: pass.

- [ ] **Step 9: Commit**

Run:

```powershell
git add backend/storage.py tests/test_storage.py
git commit -m "Add preference profile storage"
```

---

### Task 3: Add Preference Profile API Routes

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write failing API endpoint test**

Append this test to `tests/test_main.py`:

```python
def test_preference_profile_endpoints_crud_and_default(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)

    first_response = client.post(
        "/preference-profiles",
        json={
            "name": "Rahil",
            "car_reliance": "no_car",
            "top_priority": "transit_access",
            "must_haves": ["transit"],
        },
    )
    assert first_response.status_code == 200
    first = first_response.json()
    assert first["name"] == "Rahil"
    assert first["is_default"] is True

    second_response = client.post(
        "/preference-profiles",
        json={"name": "Budget-first", "budget_sensitivity": "very_budget_conscious"},
    )
    assert second_response.status_code == 200
    second = second_response.json()
    assert second["is_default"] is False

    list_response = client.get("/preference-profiles")
    assert list_response.status_code == 200
    assert [profile["id"] for profile in list_response.json()] == [first["id"], second["id"]]

    update_response = client.put(
        f"/preference-profiles/{second['id']}",
        json={"name": "Budget and transit", "must_haves": ["transit", "lower_rent_pressure"]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Budget and transit"
    assert updated["must_haves"] == ["transit", "lower_rent_pressure"]

    default_response = client.post(f"/preference-profiles/{second['id']}/default")
    assert default_response.status_code == 200
    assert default_response.json()["is_default"] is True

    get_response = client.get(f"/preference-profiles/{second['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["is_default"] is True

    delete_response = client.delete(f"/preference-profiles/{first['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    missing_response = client.get(f"/preference-profiles/{first['id']}")
    assert missing_response.status_code == 404
```

Append this test near the CORS test:

```python
def test_cors_allows_preference_profile_update_from_local_vite():
    client = TestClient(app)

    response = client.options(
        "/preference-profiles/example",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_main.py -q
```

Expected: fail with 404 for `/preference-profiles` and CORS failure for `PUT`.

- [ ] **Step 3: Update imports and CORS**

In `backend/main.py`, extend imports from `backend.models`:

```python
    DeletePreferenceProfileResponse,
    PreferenceProfile,
    PreferenceProfileCreate,
    PreferenceProfileUpdate,
```

Extend imports from `backend.storage`:

```python
    create_preference_profile,
    delete_preference_profile,
    get_preference_profile,
    list_preference_profiles,
    set_default_preference_profile,
    update_preference_profile,
```

Update CORS methods:

```python
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
```

- [ ] **Step 4: Add API routes**

Add these route functions after `/analyze` and before saved neighborhood report routes:

```python
@app.post("/preference-profiles", response_model=PreferenceProfile)
async def create_preference_profile_endpoint(profile: PreferenceProfileCreate) -> PreferenceProfile:
    return create_preference_profile(profile)


@app.get("/preference-profiles", response_model=list[PreferenceProfile])
async def preference_profiles() -> list[PreferenceProfile]:
    return list_preference_profiles()


@app.get("/preference-profiles/{profile_id}", response_model=PreferenceProfile)
async def preference_profile(profile_id: str) -> PreferenceProfile:
    profile = get_preference_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Preference profile not found.")
    return profile


@app.put("/preference-profiles/{profile_id}", response_model=PreferenceProfile)
async def update_preference_profile_endpoint(
    profile_id: str,
    update: PreferenceProfileUpdate,
) -> PreferenceProfile:
    profile = update_preference_profile(profile_id, update)
    if profile is None:
        raise HTTPException(status_code=404, detail="Preference profile not found.")
    return profile


@app.delete("/preference-profiles/{profile_id}", response_model=DeletePreferenceProfileResponse)
async def delete_preference_profile_endpoint(profile_id: str) -> DeletePreferenceProfileResponse:
    deleted = delete_preference_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preference profile not found.")
    return DeletePreferenceProfileResponse(deleted=True)


@app.post("/preference-profiles/{profile_id}/default", response_model=PreferenceProfile)
async def default_preference_profile(profile_id: str) -> PreferenceProfile:
    profile = set_default_preference_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Preference profile not found.")
    return profile
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_main.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add backend/main.py tests/test_main.py
git commit -m "Add preference profile API routes"
```

---

### Task 4: Apply Selected Preference Profile During Analyze

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write failing analyze integration tests**

Append these tests to `tests/test_main.py`:

```python
def test_analyze_uses_selected_preference_profile(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)
    profile_response = client.post(
        "/preference-profiles",
        json={
            "name": "Transit profile",
            "car_reliance": "no_car",
            "top_priority": "transit_access",
            "generic_mode": False,
        },
    )
    assert profile_response.status_code == 200
    profile_id = profile_response.json()["id"]

    generic_response = client.post(
        "/analyze",
        json={"query": "East Austin", "preference_profile_id": profile_id, "generic_mode": True},
    )

    assert generic_response.status_code == 200
    body = generic_response.json()
    assert body["fit"] is not None
    assert "transit" in body["fit"]["explanation"].lower()


def test_analyze_returns_404_for_missing_preference_profile(monkeypatch):
    _test_sqlite_path(monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/analyze",
        json={"query": "East Austin", "preference_profile_id": "missing-profile"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Preference profile not found."
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_main.py::test_analyze_uses_selected_preference_profile tests/test_main.py::test_analyze_returns_404_for_missing_preference_profile -q
```

Expected: first test fails because profile preferences are not applied; second test fails because missing profile is not checked.

- [ ] **Step 3: Resolve profile in `/analyze`**

In `backend/main.py`, replace the analyze route with:

```python
@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    if request.preference_profile_id is not None:
        profile = get_preference_profile(request.preference_profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Preference profile not found.")
        request = request.model_copy(
            update={
                "preferences": profile.preferences,
                "generic_mode": profile.generic_mode,
            }
        )
    return await analyze_neighborhood(request)
```

- [ ] **Step 4: Run integration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_main.py::test_analyze_uses_selected_preference_profile tests/test_main.py::test_analyze_returns_404_for_missing_preference_profile -q
```

Expected: pass.

- [ ] **Step 5: Run backend API/model/storage regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_models.py tests/test_storage.py tests/test_main.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add backend/main.py tests/test_main.py
git commit -m "Apply preference profiles during analysis"
```

---

### Task 5: Add Frontend Preference Profile API State

**Files:**
- Modify: `frontend/src/hooks/useNeighborhood.js`

- [ ] **Step 1: Add state and API functions**

In `frontend/src/hooks/useNeighborhood.js`, add these state values near the existing saved-profile state:

```javascript
  const [preferenceProfiles, setPreferenceProfiles] = useState([]);
  const [selectedPreferenceProfileId, setSelectedPreferenceProfileId] = useState(null);
  const [preferenceProfileError, setPreferenceProfileError] = useState('');
  const [isSavingPreferenceProfile, setIsSavingPreferenceProfile] = useState(false);
```

Add these functions before `loadSavedProfiles()`:

```javascript
  async function loadPreferenceProfiles() {
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles`);
      const body = await parseResponse(response, `Load preference profiles failed with ${response.status}`);
      setPreferenceProfiles(body);
      setPreferenceProfileError('');
      const defaultProfile = body.find((profile) => profile.is_default) || body[0] || null;
      setSelectedPreferenceProfileId((current) => {
        if (current && body.some((profile) => profile.id === current)) {
          return current;
        }
        return defaultProfile?.id || null;
      });
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Load preference profiles failed';
      setPreferenceProfileError(message);
      return [];
    }
  }

  async function createPreferenceProfile(profile) {
    setIsSavingPreferenceProfile(true);
    setPreferenceProfileError('');
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
      const body = await parseResponse(response, `Create preference profile failed with ${response.status}`);
      await loadPreferenceProfiles();
      setSelectedPreferenceProfileId(body.id);
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Create preference profile failed';
      setPreferenceProfileError(message);
      throw err;
    } finally {
      setIsSavingPreferenceProfile(false);
    }
  }

  async function updatePreferenceProfile(profileId, profile) {
    setIsSavingPreferenceProfile(true);
    setPreferenceProfileError('');
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles/${profileId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
      const body = await parseResponse(response, `Update preference profile failed with ${response.status}`);
      await loadPreferenceProfiles();
      setSelectedPreferenceProfileId(body.id);
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Update preference profile failed';
      setPreferenceProfileError(message);
      throw err;
    } finally {
      setIsSavingPreferenceProfile(false);
    }
  }

  async function deletePreferenceProfile(profileId) {
    setPreferenceProfileError('');
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles/${profileId}`, {
        method: 'DELETE',
      });
      const body = await parseResponse(response, `Delete preference profile failed with ${response.status}`);
      const profiles = await loadPreferenceProfiles();
      if (selectedPreferenceProfileId === profileId) {
        const defaultProfile = profiles.find((profile) => profile.is_default) || profiles[0] || null;
        setSelectedPreferenceProfileId(defaultProfile?.id || null);
      }
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete preference profile failed';
      setPreferenceProfileError(message);
      throw err;
    }
  }

  async function setDefaultPreferenceProfile(profileId) {
    setPreferenceProfileError('');
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles/${profileId}/default`, {
        method: 'POST',
      });
      const body = await parseResponse(response, `Set default preference profile failed with ${response.status}`);
      await loadPreferenceProfiles();
      setSelectedPreferenceProfileId(body.id);
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Set default preference profile failed';
      setPreferenceProfileError(message);
      throw err;
    }
  }
```

Add all new values and functions to the returned object:

```javascript
    preferenceProfiles,
    selectedPreferenceProfileId,
    setSelectedPreferenceProfileId,
    preferenceProfileError,
    isSavingPreferenceProfile,
    loadPreferenceProfiles,
    createPreferenceProfile,
    updatePreferenceProfile,
    deletePreferenceProfile,
    setDefaultPreferenceProfile,
```

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd frontend
npm.cmd run build
```

Expected: build succeeds. A large chunk warning from Mapbox is acceptable.

- [ ] **Step 3: Commit**

Run:

```powershell
git add frontend/src/hooks/useNeighborhood.js
git commit -m "Add preference profile frontend API state"
```

---

### Task 6: Add Compact Preference Profile UI

**Files:**
- Create: `frontend/src/components/PreferenceProfiles.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Questionnaire.jsx`
- Modify: `frontend/src/components/Profile.jsx`
- Modify: `frontend/src/components/SavedProfiles.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Create `PreferenceProfiles.jsx`**

Create `frontend/src/components/PreferenceProfiles.jsx`:

```javascript
import { useEffect, useMemo, useState } from 'react';

const EMPTY_FORM = {
  name: '',
  car_reliance: '',
  energy_preference: '',
  top_priority: '',
  budget_sensitivity: '',
  generic_mode: false,
  commute_anchor_label: '',
  commute_anchor_lat: '',
  commute_anchor_lng: '',
  max_monthly_rent: '',
  must_haves: [],
  deal_breakers: [],
  notes: '',
};

const CATEGORY_OPTIONS = [
  ['transit', 'Transit'],
  ['walkability', 'Walkability'],
  ['parks', 'Parks'],
  ['groceries', 'Groceries'],
  ['restaurants', 'Restaurants'],
  ['quiet', 'Quiet'],
  ['social_scene', 'Social scene'],
  ['lower_rent_pressure', 'Lower rent pressure'],
];

export default function PreferenceProfiles({
  profiles = [],
  selectedProfileId,
  onSelect,
  onCreate,
  onUpdate,
  onDelete,
  onSetDefault,
  error,
  isSaving,
}) {
  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) || null,
    [profiles, selectedProfileId],
  );
  const [editingProfile, setEditingProfile] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  useEffect(() => {
    if (isCreating) {
      setForm(EMPTY_FORM);
    } else if (editingProfile) {
      setForm(profileToForm(editingProfile));
    }
  }, [editingProfile, isCreating]);

  const formOpen = isCreating || Boolean(editingProfile);

  async function submitForm(event) {
    event.preventDefault();
    const payload = formToPayload(form);
    if (editingProfile) {
      await onUpdate(editingProfile.id, payload);
    } else {
      await onCreate(payload);
    }
    setIsCreating(false);
    setEditingProfile(null);
    setForm(EMPTY_FORM);
  }

  function toggleCategory(field, value) {
    setForm((current) => {
      const values = current[field];
      return {
        ...current,
        [field]: values.includes(value)
          ? values.filter((item) => item !== value)
          : [...values, value],
      };
    });
  }

  return (
    <section className="preference-profiles">
      <div className="saved-profiles-header">
        <div>
          <p className="eyebrow">Preference profile</p>
          <h2>{selectedProfile ? selectedProfile.name : 'Generic'}</h2>
        </div>
        <button type="button" onClick={() => setIsCreating(true)}>
          New
        </button>
      </div>

      {profiles.length > 0 ? (
        <div className="profile-switcher-row">
          <select value={selectedProfileId || ''} onChange={(event) => onSelect(event.target.value || null)}>
            <option value="">Generic analysis</option>
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}{profile.is_default ? ' (default)' : ''}
              </option>
            ))}
          </select>
          {selectedProfile && (
            <button type="button" onClick={() => setEditingProfile(selectedProfile)}>
              Edit
            </button>
          )}
        </div>
      ) : (
        <p className="saved-empty">Create a reusable profile or keep using generic analysis.</p>
      )}

      {selectedProfile && (
        <div className="profile-chip-row">
          {!selectedProfile.is_default && (
            <button type="button" onClick={() => onSetDefault(selectedProfile.id)}>
              Make default
            </button>
          )}
          <button type="button" className="icon-danger" onClick={() => onDelete(selectedProfile.id)}>
            Delete
          </button>
        </div>
      )}

      {error && <p className="save-error">{error}</p>}

      {formOpen && (
        <form className="preference-profile-form" onSubmit={submitForm}>
          <label className="field">
            <span>Name</span>
            <input
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              required
              maxLength={80}
            />
          </label>
          <label className="generic-toggle">
            <input
              type="checkbox"
              checked={form.generic_mode}
              onChange={(event) => setForm({ ...form, generic_mode: event.target.checked })}
            />
            Run this profile as generic
          </label>
          <label className="field">
            <span>Commute anchor</span>
            <input
              value={form.commute_anchor_label}
              onChange={(event) => setForm({ ...form, commute_anchor_label: event.target.value })}
              placeholder="Work, school, or general area"
            />
          </label>
          <label className="field">
            <span>Max monthly rent</span>
            <input
              type="number"
              min="0"
              value={form.max_monthly_rent}
              onChange={(event) => setForm({ ...form, max_monthly_rent: event.target.value })}
            />
          </label>
          <CategoryChecklist
            title="Must haves"
            values={form.must_haves}
            onToggle={(value) => toggleCategory('must_haves', value)}
          />
          <CategoryChecklist
            title="Deal breakers"
            values={form.deal_breakers}
            onToggle={(value) => toggleCategory('deal_breakers', value)}
          />
          <label className="field">
            <span>Notes</span>
            <textarea
              value={form.notes}
              onChange={(event) => setForm({ ...form, notes: event.target.value })}
              maxLength={1000}
            />
          </label>
          <div className="profile-form-actions">
            <button type="submit" className="primary-button" disabled={isSaving}>
              {isSaving ? 'Saving...' : editingProfile ? 'Update profile' : 'Create profile'}
            </button>
            <button
              type="button"
              onClick={() => {
                setIsCreating(false);
                setEditingProfile(null);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function CategoryChecklist({ title, values, onToggle }) {
  return (
    <fieldset className="category-checklist">
      <legend>{title}</legend>
      {CATEGORY_OPTIONS.map(([value, label]) => (
        <label key={value}>
          <input type="checkbox" checked={values.includes(value)} onChange={() => onToggle(value)} />
          {label}
        </label>
      ))}
    </fieldset>
  );
}

function profileToForm(profile) {
  return {
    name: profile.name || '',
    car_reliance: profile.car_reliance || '',
    energy_preference: profile.energy_preference || '',
    top_priority: profile.top_priority || '',
    budget_sensitivity: profile.budget_sensitivity || '',
    generic_mode: Boolean(profile.generic_mode),
    commute_anchor_label: profile.commute_anchor?.label || '',
    commute_anchor_lat: profile.commute_anchor?.lat ?? '',
    commute_anchor_lng: profile.commute_anchor?.lng ?? '',
    max_monthly_rent: profile.max_monthly_rent ?? '',
    must_haves: profile.must_haves || [],
    deal_breakers: profile.deal_breakers || [],
    notes: profile.notes || '',
  };
}

function formToPayload(form) {
  const payload = {
    name: form.name.trim(),
    generic_mode: form.generic_mode,
    must_haves: form.must_haves,
    deal_breakers: form.deal_breakers,
  };
  if (form.commute_anchor_label.trim()) {
    payload.commute_anchor = { label: form.commute_anchor_label.trim() };
  }
  if (form.max_monthly_rent !== '') {
    payload.max_monthly_rent = Number(form.max_monthly_rent);
  }
  if (form.notes.trim()) {
    payload.notes = form.notes.trim();
  }
  return payload;
}
```

- [ ] **Step 2: Update `Questionnaire.jsx` to accept profile context**

Add props:

```javascript
  selectedPreferenceProfile,
  profileManaged,
```

Update the section heading:

```javascript
        <p className="eyebrow">Preferences</p>
        <h2>{selectedPreferenceProfile ? `${selectedPreferenceProfile.name} fit` : 'Lifestyle fit'}</h2>
```

Add this paragraph after the heading:

```javascript
      {profileManaged && (
        <p className="hint-line">This analysis will use the selected saved preference profile.</p>
      )}
```

Keep the existing selects editable. The selected profile values will populate them from `App.jsx`, but backend scoring will use `preference_profile_id` when selected.

- [ ] **Step 3: Wire `App.jsx`**

Add import:

```javascript
import PreferenceProfiles from './components/PreferenceProfiles.jsx';
```

Destructure new hook values:

```javascript
    preferenceProfiles,
    selectedPreferenceProfileId,
    setSelectedPreferenceProfileId,
    preferenceProfileError,
    isSavingPreferenceProfile,
    loadPreferenceProfiles,
    createPreferenceProfile,
    updatePreferenceProfile,
    deletePreferenceProfile,
    setDefaultPreferenceProfile,
```

Add selected-profile lookup before `analyzePayload`:

```javascript
  const selectedPreferenceProfile = useMemo(
    () => preferenceProfiles.find((profile) => profile.id === selectedPreferenceProfileId) || null,
    [preferenceProfiles, selectedPreferenceProfileId],
  );
```

Update `analyzePayload`:

```javascript
  const analyzePayload = useMemo(
    () =>
      selectedPlace
        ? {
            query: selectedPlace.label,
            coordinates: selectedPlace.coordinates,
            preferences,
            generic_mode: genericMode,
            preference_profile_id: selectedPreferenceProfileId,
          }
        : null,
    [genericMode, preferences, selectedPlace, selectedPreferenceProfileId],
  );
```

Update startup effect:

```javascript
  useEffect(() => {
    loadSavedProfiles().catch(() => null);
    loadPreferenceProfiles().catch(() => null);
  }, []);
```

Add an effect to populate questionnaire from selected profile:

```javascript
  useEffect(() => {
    if (!selectedPreferenceProfile) return;
    setPreferences({
      car_reliance: selectedPreferenceProfile.car_reliance || '',
      energy_preference: selectedPreferenceProfile.energy_preference || '',
      top_priority: selectedPreferenceProfile.top_priority || '',
      budget_sensitivity: selectedPreferenceProfile.budget_sensitivity || '',
    });
    setGenericMode(Boolean(selectedPreferenceProfile.generic_mode));
  }, [selectedPreferenceProfile]);
```

Render `PreferenceProfiles` before `Questionnaire`:

```javascript
          {selectedPlace && (
            <PreferenceProfiles
              profiles={preferenceProfiles}
              selectedProfileId={selectedPreferenceProfileId}
              onSelect={setSelectedPreferenceProfileId}
              onCreate={(profile) => createPreferenceProfile({ ...profile, ...preferences, generic_mode: genericMode })}
              onUpdate={(profileId, profile) => updatePreferenceProfile(profileId, { ...profile, ...preferences, generic_mode: genericMode })}
              onDelete={(profileId) => deletePreferenceProfile(profileId).catch(() => null)}
              onSetDefault={(profileId) => setDefaultPreferenceProfile(profileId).catch(() => null)}
              error={preferenceProfileError}
              isSaving={isSavingPreferenceProfile}
            />
          )}
```

Pass profile context into `Questionnaire`:

```javascript
              selectedPreferenceProfile={selectedPreferenceProfile}
              profileManaged={Boolean(selectedPreferenceProfileId)}
```

- [ ] **Step 4: Rename saved neighborhood report copy**

In `frontend/src/components/Profile.jsx`, change:

```javascript
  const saveButtonText = isSaving ? 'Saving...' : savedProfileId ? 'Saved' : 'Save profile';
```

to:

```javascript
  const saveButtonText = isSaving ? 'Saving...' : savedProfileId ? 'Saved report' : 'Save report';
```

In `frontend/src/components/SavedProfiles.jsx`, change:

```javascript
          <h2>Profiles</h2>
```

to:

```javascript
          <h2>Reports</h2>
```

Change:

```javascript
        <p className="saved-empty">Saved profiles will appear here.</p>
```

to:

```javascript
        <p className="saved-empty">Saved neighborhood reports will appear here.</p>
```

- [ ] **Step 5: Add CSS**

Append this to `frontend/src/styles.css`:

```css
.preference-profiles {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 8px;
  padding: 16px;
}

.profile-switcher-row,
.profile-chip-row,
.profile-form-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.profile-switcher-row select,
.preference-profile-form input,
.preference-profile-form textarea {
  width: 100%;
  border: 1px solid rgba(15, 23, 42, 0.18);
  border-radius: 6px;
  padding: 10px 12px;
  font: inherit;
}

.profile-switcher-row select {
  flex: 1 1 180px;
}

.preference-profile-form {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.preference-profile-form textarea {
  min-height: 84px;
  resize: vertical;
}

.category-checklist {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 8px;
  display: grid;
  gap: 8px;
  padding: 12px;
}

.category-checklist legend {
  font-weight: 700;
  padding: 0 4px;
}

.category-checklist label {
  display: flex;
  gap: 8px;
  align-items: center;
}
```

- [ ] **Step 6: Run frontend build**

Run:

```powershell
cd frontend
npm.cmd run build
```

Expected: build succeeds. A large chunk warning from Mapbox is acceptable.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src/App.jsx frontend/src/components/PreferenceProfiles.jsx frontend/src/components/Questionnaire.jsx frontend/src/components/Profile.jsx frontend/src/components/SavedProfiles.jsx frontend/src/styles.css
git commit -m "Add preference profile selector UI"
```

---

### Task 7: Documentation And Phase Status

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`

- [ ] **Step 1: Update README Phase 2 status**

In `README.md`, update the Phase 2 status section to say:

```markdown
Phase 2A added explicit local saved neighborhood reports. Phase 2B added reusable local preference profiles so a selected profile can be applied across neighborhood analyses. The next Phase 2 slices should focus on compare mode and richer provenance/source freshness UI. Avoid adding accounts, public hosting, or share URLs until the anonymous local workflow remains excellent.
```

- [ ] **Step 2: Update PLAN checklist**

In `PLAN.md`, under `### Phase 2 - Comparison, Sharing, And Provenance`, update the checklist to include Phase 2B:

```markdown
- [x] Add SQLite-backed local saved neighborhood reports with provider-compliant freshness rules.
- [x] Add reusable SQLite-backed preference profiles that can be applied across neighborhood analyses.
- [ ] Add public shareable profile URLs only if a hosted demo is later desired.
- [ ] Add compare mode for two or more places.
- [ ] Add provenance metadata to major generated claims.
- [x] Add UI affordances for synthesis status and local saved-profile handling.
- [ ] Add regression tests for cache freshness, compare response shape, and provenance display.
```

- [ ] **Step 3: Run docs diff check**

Run:

```powershell
git diff -- README.md PLAN.md
```

Expected: diff only mentions implemented Phase 2B behavior and remaining Phase 2 slices.

- [ ] **Step 4: Commit**

Run:

```powershell
git add README.md PLAN.md
git commit -m "Document Phase 2B preference profiles"
```

---

### Task 8: Final Verification

**Files:**
- No source changes unless verification reveals a bug.

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

Expected: all checks pass.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
cd frontend
npm.cmd run build
```

Expected: build succeeds. A large chunk warning from Mapbox is acceptable.

- [ ] **Step 4: Check git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree, branch ahead of `origin/main` by the Phase 2B commits until pushed.
