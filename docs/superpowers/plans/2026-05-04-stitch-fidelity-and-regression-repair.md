# Stitch Fidelity And Regression Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Phase 2B UI visually match the Google Stitch VibeCheck screens while preserving and repairing search, generic analysis, saved-profile analysis, profile CRUD/default, saved report CRUD, and retry flows.

**Architecture:** Keep the current React component boundaries, but tighten state semantics and visual structure. Add regression tests for active profile selection and profile update payloads before changing behavior. Then refactor the visual layer around Stitch-like tokens, a landing overlay, a precision insights sidebar, a profile workspace, and a saved reports panel.

**Tech Stack:** React 19, Vite 7, lucide-react, plain CSS, FastAPI/Pydantic/SQLite backend, pytest, Node built-in `node:test`.

---

## File Structure

- Modify `frontend/src/utils/preferenceProfiles.js`: distinguish first-load default selection from explicit Generic selection, and support update payloads that intentionally clear optional fields.
- Modify `frontend/src/utils/preferenceProfiles.test.js`: add regression tests for sticky Generic and editable/clearable profile payloads.
- Modify `frontend/src/hooks/useNeighborhood.js`: track profile-list initialization so Generic remains selected after reloads.
- Modify `backend/storage.py`: update preference profiles using Pydantic `model_fields_set` so explicit `null` clears optional fields while omitted fields remain unchanged.
- Modify `tests/test_storage.py`: add backend regression coverage for clearing optional profile fields.
- Modify `frontend/src/App.jsx`: add Stitch-like landing overlay and hide the analysis panel until a location/result state exists.
- Modify `frontend/src/components/TopBar.jsx`: adjust labels and hierarchy to match Stitch top rail.
- Modify `frontend/src/components/Profile.jsx`: restructure the result panel into Stitch-like precision insights with fit score gauge, metrics, overview, highlights, and confidence footer.
- Modify `frontend/src/components/PreferenceProfiles.jsx`: change the workspace from generic form layout to Stitch-like lifestyle profile editor with spatial priority chips and a contextual right rail.
- Modify `frontend/src/components/SavedProfiles.jsx`: change saved reports to the Stitch-like right report panel with compact rows and thumbnails.
- Modify `frontend/src/styles.css`: replace green/off-white visual language with Stitch tokens, glass surfaces, blue actions, compact typography, and responsive Stitch layouts.
- Modify `README.md`: document that Phase 2B now uses the Stitch-matched visual direction and preserved regression-tested flows.

---

### Task 1: Add Regression Tests For Profile Selection And Update Payloads

**Files:**
- Modify: `frontend/src/utils/preferenceProfiles.test.js`
- Modify: `frontend/src/utils/preferenceProfiles.js`

- [ ] **Step 1: Add failing frontend helper tests**

Append to `frontend/src/utils/preferenceProfiles.test.js`:

```javascript
describe('sticky generic profile selection', () => {
  it('selects the default profile on first load', () => {
    assert.equal(resolveSelectedPreferenceProfileId(PROFILES, null, { preferDefault: true }), 'profile-2');
  });

  it('keeps explicit Generic selected after profiles reload', () => {
    assert.equal(resolveSelectedPreferenceProfileId(PROFILES, null, { preferDefault: false }), null);
  });
});

describe('profile update payload clearing', () => {
  it('includes explicit nulls for blank optional fields in update mode', () => {
    assert.deepEqual(
      formToPreferenceProfilePayload(
        {
          name: 'Budget walker',
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
        },
        { mode: 'update' },
      ),
      {
        name: 'Budget walker',
        car_reliance: null,
        energy_preference: null,
        top_priority: null,
        budget_sensitivity: null,
        generic_mode: false,
        commute_anchor: null,
        max_monthly_rent: null,
        must_haves: [],
        deal_breakers: [],
        notes: null,
      },
    );
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
```

Expected: fail because `resolveSelectedPreferenceProfileId` does not accept `preferDefault`, and `formToPreferenceProfilePayload` does not support update-mode clearing.

- [ ] **Step 3: Implement helper behavior**

Change `resolveSelectedPreferenceProfileId` in `frontend/src/utils/preferenceProfiles.js`:

```javascript
export function resolveSelectedPreferenceProfileId(
  profiles = [],
  currentProfileId = null,
  { preferDefault = true } = {},
) {
  if (currentProfileId && profiles.some((profile) => profile.id === currentProfileId)) {
    return currentProfileId;
  }
  if (!preferDefault) {
    return null;
  }
  const defaultProfile = profiles.find((profile) => profile.is_default) || profiles[0] || null;
  return defaultProfile?.id || null;
}
```

Change `formToPreferenceProfilePayload` signature and body:

```javascript
export function formToPreferenceProfilePayload(form, { mode = 'create' } = {}) {
  const includeClears = mode === 'update';
  const payload = {
    name: form.name.trim(),
    generic_mode: Boolean(form.generic_mode),
    must_haves: form.must_haves || [],
    deal_breakers: form.deal_breakers || [],
  };

  copyOptional(payload, 'car_reliance', form.car_reliance, includeClears);
  copyOptional(payload, 'energy_preference', form.energy_preference, includeClears);
  copyOptional(payload, 'top_priority', form.top_priority, includeClears);
  copyOptional(payload, 'budget_sensitivity', form.budget_sensitivity, includeClears);

  const commuteLabel = form.commute_anchor_label.trim();
  const commuteLat = form.commute_anchor_lat === '' ? null : Number(form.commute_anchor_lat);
  const commuteLng = form.commute_anchor_lng === '' ? null : Number(form.commute_anchor_lng);
  if (commuteLabel) {
    payload.commute_anchor = { label: commuteLabel };
    if (commuteLat !== null && commuteLng !== null) {
      payload.commute_anchor.lat = commuteLat;
      payload.commute_anchor.lng = commuteLng;
    }
  } else if (includeClears) {
    payload.commute_anchor = null;
  }

  if (form.max_monthly_rent !== '') {
    payload.max_monthly_rent = Number(form.max_monthly_rent);
  } else if (includeClears) {
    payload.max_monthly_rent = null;
  }

  if (form.notes.trim()) {
    payload.notes = form.notes.trim();
  } else if (includeClears) {
    payload.notes = null;
  }
  return payload;
}

function copyOptional(target, key, value, includeClears) {
  if (value) {
    target[key] = value;
  } else if (includeClears) {
    target[key] = null;
  }
}
```

Delete the old `copyIfPresent()` helper.

- [ ] **Step 4: Run helper tests**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
```

Expected: all frontend helper tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add frontend/src/utils/preferenceProfiles.js frontend/src/utils/preferenceProfiles.test.js
git commit -m "Test profile selection and update payload regressions"
```

---

### Task 2: Fix Sticky Generic Selection And Backend Clearing

**Files:**
- Modify: `frontend/src/hooks/useNeighborhood.js`
- Modify: `frontend/src/components/PreferenceProfiles.jsx`
- Modify: `backend/storage.py`
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Add failing backend clearing test**

Append to `tests/test_storage.py`:

```python
def test_update_preference_profile_can_clear_optional_fields():
    db_path = _db_path()
    initialize_database(db_path)
    profile = create_preference_profile(
        PreferenceProfileCreate(
            name="Original",
            car_reliance="no_car",
            commute_anchor={"label": "Office"},
            max_monthly_rent=2400,
            notes="Local note.",
        ),
        db_path,
    )

    updated = update_preference_profile(
        profile.id,
        PreferenceProfileUpdate(
            car_reliance=None,
            commute_anchor=None,
            max_monthly_rent=None,
            notes=None,
        ),
        db_path,
    )

    assert updated is not None
    assert updated.car_reliance is None
    assert updated.commute_anchor is None
    assert updated.max_monthly_rent is None
    assert updated.notes is None
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py::test_update_preference_profile_can_clear_optional_fields -q
```

Expected: fail because `None` values are currently treated as "unchanged".

- [ ] **Step 3: Fix backend update merge**

In `backend/storage.py`, replace the `merged = PreferenceProfileCreate(...)` block inside `update_preference_profile()` with:

```python
    fields_set = update.model_fields_set
    merged = PreferenceProfileCreate(
        name=update.name if "name" in fields_set else current.name,
        car_reliance=update.car_reliance if "car_reliance" in fields_set else current.car_reliance,
        energy_preference=(
            update.energy_preference
            if "energy_preference" in fields_set
            else current.energy_preference
        ),
        top_priority=update.top_priority if "top_priority" in fields_set else current.top_priority,
        budget_sensitivity=(
            update.budget_sensitivity
            if "budget_sensitivity" in fields_set
            else current.budget_sensitivity
        ),
        generic_mode=update.generic_mode if "generic_mode" in fields_set else current.generic_mode,
        commute_anchor=update.commute_anchor if "commute_anchor" in fields_set else current.commute_anchor,
        max_monthly_rent=(
            update.max_monthly_rent
            if "max_monthly_rent" in fields_set
            else current.max_monthly_rent
        ),
        must_haves=update.must_haves if "must_haves" in fields_set else current.must_haves,
        deal_breakers=update.deal_breakers if "deal_breakers" in fields_set else current.deal_breakers,
        notes=update.notes if "notes" in fields_set else current.notes,
    )
```

- [ ] **Step 4: Track first profile load in frontend hook**

In `frontend/src/hooks/useNeighborhood.js`, add a ref:

```javascript
  const preferenceProfilesInitializedRef = useRef(false);
```

Replace the selection line in `loadPreferenceProfiles()`:

```javascript
      const preferDefault = !preferenceProfilesInitializedRef.current;
      setSelectedPreferenceProfileId((current) =>
        resolveSelectedPreferenceProfileId(body, current, { preferDefault }),
      );
      preferenceProfilesInitializedRef.current = true;
```

- [ ] **Step 5: Use update-mode payloads in profile workspace**

In `frontend/src/components/PreferenceProfiles.jsx`, change submit payload creation:

```javascript
    const payload = formToPreferenceProfilePayload(form, { mode: editingProfile ? 'update' : 'create' });
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py::test_update_preference_profile_can_clear_optional_fields -q
```

Expected: all focused tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/storage.py tests/test_storage.py frontend/src/hooks/useNeighborhood.js frontend/src/components/PreferenceProfiles.jsx
git commit -m "Fix profile selection and clearing regressions"
```

---

### Task 3: Convert Shell And Landing State To Stitch Visuals

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/TopBar.jsx`
- Modify: `frontend/src/components/SearchBar.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add landing actions to `App.jsx`**

After `TopBar`, render a landing card only when there is no selected place, no data, no loading, and no error:

```javascript
        {!selectedPlace && !data && !loading && !error && (
          <section className="landing-card">
            <div className="landing-icon">◎</div>
            <h1>Begin Your Analysis</h1>
            <p>Select a profile and search a place to start your analysis.</p>
            <div className="landing-actions">
              <button type="button" className="primary-button" onClick={() => setActiveWorkspace('profiles')}>
                Select Profile
              </button>
              <button type="button" onClick={() => setActiveWorkspace('savedReports')}>
                Saved Reports
              </button>
            </div>
          </section>
        )}
        <div className="map-status-chip">
          <span></span>
          Market saturation
          <strong>{selectedPlace?.label || 'San Francisco, CA'}</strong>
        </div>
```

Render the analysis panel only when a selected place, data, loading, or error exists:

```javascript
        {(selectedPlace || data || loading || error) && (
          <aside className="analysis-panel">
            ...
          </aside>
        )}
```

- [ ] **Step 2: Update `TopBar.jsx` labels**

Change the active profile button to show a small label plus value:

```javascript
      <button type="button" className="active-profile-button" onClick={onProfileClick}>
        <UserRound size={15} aria-hidden="true" />
        <span>
          <small>Active Profile</small>
          {activeProfile?.name || 'Generic'}
        </span>
      </button>
```

- [ ] **Step 3: Update SearchBar placeholder**

In `frontend/src/components/SearchBar.jsx`, change the enabled placeholder:

```javascript
placeholder={MAPBOX_TOKEN ? 'Search for a neighborhood or address...' : 'Add VITE_MAPBOX_TOKEN to enable search'}
```

- [ ] **Step 4: Replace root shell CSS with Stitch tokens**

At the top of `frontend/src/styles.css`, replace the `:root` block with:

```css
:root {
  --vc-bg: #f8fafc;
  --vc-surface: #ffffff;
  --vc-glass: rgba(255, 255, 255, 0.84);
  --vc-glass-strong: rgba(255, 255, 255, 0.94);
  --vc-text: #0f172a;
  --vc-muted: #64748b;
  --vc-border: rgba(15, 23, 42, 0.12);
  --vc-border-light: rgba(255, 255, 255, 0.75);
  --vc-blue: #2563eb;
  --vc-blue-soft: #eff6ff;
  --vc-danger: #ba1a1a;
  --vc-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
  --vc-shadow-lg: 0 18px 50px rgba(15, 23, 42, 0.14);
  color: var(--vc-text);
  background: var(--vc-bg);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
```

- [ ] **Step 5: Replace old green surface colors**

In `frontend/src/styles.css`, replace green text/background/border values in app shell selectors with the new CSS variables. Minimum required replacements:

```css
.map-stage { background: #dce5e8; }
.eyebrow { color: var(--vc-muted); font-size: 0.68rem; letter-spacing: 0.06em; }
.primary-button { background: var(--vc-blue); color: #ffffff; }
.icon-danger { color: var(--vc-danger) !important; }
```

Update `.top-bar`, `.search-card`, `.analysis-panel`, `.landing-card`, and `.map-status-chip` using the Stitch glass variables from Step 4.

- [ ] **Step 6: Run frontend build**

Run:

```powershell
Set-Location frontend
npm.cmd run build
```

Expected: build succeeds.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src/App.jsx frontend/src/components/TopBar.jsx frontend/src/components/SearchBar.jsx frontend/src/styles.css
git commit -m "Match Stitch shell and landing visuals"
```

---

### Task 4: Convert Analysis, Profile, And Saved Reports To Stitch Panels

**Files:**
- Modify: `frontend/src/components/Profile.jsx`
- Modify: `frontend/src/components/SavedProfiles.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Restructure `Profile.jsx`**

Update `Profile.jsx` so the rendered order is:

```javascript
<section className="profile-stack precision-panel">
  <div className="profile-actions">
    <div className="section-heading">
      <h2>{response.place.label}</h2>
      <p className="analysis-lens-line">...</p>
    </div>
    <button ...>{saveButtonText}</button>
  </div>
  {saveError && ...}
  {fit && <FitGauge fit={fit} />}
  <article className="vibe-overview">...</article>
  <ScoreCards scores={profile.vibe_scores} />
  <div className="insight-list">pros/cons summary</div>
  {synthesis && ...}
  <WhoLivesHere context={profile.who_lives_here} />
  <Confidence confidence={confidence} statuses={statuses} />
</section>
```

Add `FitGauge`:

```javascript
function FitGauge({ fit }) {
  const score = Math.max(0, Math.min(100, fit.score));
  return (
    <article className="fit-gauge-card">
      <div className="fit-gauge" style={{ '--score': `${score * 3.6}deg` }}>
        <strong>{score}%</strong>
        <span>Fit Score</span>
      </div>
      <p>{fit.explanation}</p>
      {fit.flags?.map((flag) => <small key={flag}>{flag}</small>)}
    </article>
  );
}
```

- [ ] **Step 2: Restructure `SavedProfiles.jsx` rows**

Each saved row should include a thumbnail placeholder:

```javascript
<div className="saved-thumb" aria-hidden="true"></div>
<button type="button" onClick={() => onOpen(profile.id)}>
  <strong>{profile.place_label}</strong>
  <span>{profile.confidence_level} confidence</span>
</button>
```

Keep delete as a separate button.

- [ ] **Step 3: Add Stitch panel CSS**

In `frontend/src/styles.css`, add/update styles for:

```css
.analysis-panel { top: 84px; right: 18px; bottom: 18px; width: min(410px, calc(100vw - 36px)); border-radius: 16px; background: var(--vc-glass-strong); border-color: var(--vc-border-light); box-shadow: var(--vc-shadow-lg); backdrop-filter: blur(10px); }
.precision-panel { margin-top: 0; gap: 14px; }
.fit-gauge-card { display: grid; place-items: center; gap: 12px; border: 0; border-radius: 14px; background: #f8fafc; padding: 18px; text-align: center; }
.fit-gauge { width: 116px; height: 116px; border-radius: 999px; display: grid; place-items: center; background: conic-gradient(var(--vc-blue) var(--score), #dbeafe 0); position: relative; }
.fit-gauge::after { content: ""; position: absolute; inset: 10px; border-radius: inherit; background: #ffffff; }
.fit-gauge strong, .fit-gauge span { position: relative; z-index: 1; }
.fit-gauge strong { font-size: 1.6rem; color: var(--vc-text); }
.fit-gauge span { color: var(--vc-blue); font-size: 0.72rem; font-weight: 800; text-transform: uppercase; }
.score-card { border: 0; border-radius: 10px; background: #f8fafc; }
.saved-thumb { width: 56px; height: 44px; flex: 0 0 auto; border-radius: 8px; background: linear-gradient(135deg, #0f172a, #2563eb 50%, #94a3b8); }
```

- [ ] **Step 4: Run frontend build**

Run:

```powershell
Set-Location frontend
npm.cmd run build
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

Run:

```powershell
git add frontend/src/components/Profile.jsx frontend/src/components/SavedProfiles.jsx frontend/src/styles.css
git commit -m "Match Stitch analysis and reports panels"
```

---

### Task 5: Convert Lifestyle Profile Workspace To Stitch Layout

**Files:**
- Modify: `frontend/src/components/PreferenceProfiles.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Rework workspace sections**

In `PreferenceProfiles.jsx`, group the form fields into sections:

- Profile name and commute anchor row.
- Max monthly rent slider/input row.
- Spatial priorities as icon-like chips.
- Must-haves and deal-breakers as two compact note boxes.
- Footer actions.

Use existing data fields and handlers. Do not remove create/edit/delete/default functionality.

- [ ] **Step 2: Preserve update-mode payload**

Ensure submit still uses:

```javascript
const payload = formToPreferenceProfilePayload(form, { mode: editingProfile ? 'update' : 'create' });
```

- [ ] **Step 3: Add workspace visual CSS**

Update `frontend/src/styles.css`:

```css
.profile-workspace { grid-template-columns: minmax(0, 680px) 290px; border-radius: 16px; background: var(--vc-glass-strong); }
.profile-workspace-main { padding: 28px; }
.profile-workspace-nav { background: rgba(248, 250, 252, 0.78); }
.category-checklist { grid-template-columns: repeat(2, minmax(0, 1fr)); border: 0; background: transparent; padding: 0; }
.category-checklist label { min-height: 40px; border: 1px solid var(--vc-border); border-radius: 10px; background: #ffffff; padding: 0 12px; }
.category-checklist input { accent-color: var(--vc-blue); }
.workspace-form input, .workspace-form select, .workspace-form textarea { border-color: var(--vc-border); border-radius: 8px; background: #ffffff; }
```

- [ ] **Step 4: Run helper tests and build**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
Set-Location frontend
npm.cmd run build
```

Expected: helper tests pass and build succeeds.

- [ ] **Step 5: Commit**

Run:

```powershell
git add frontend/src/components/PreferenceProfiles.jsx frontend/src/styles.css
git commit -m "Match Stitch lifestyle profile workspace"
```

---

### Task 6: Final Regression Verification

**Files:**
- Modify only if verification reveals a bug.

- [ ] **Step 1: Run full automated verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check backend tests
node --test frontend/src/utils/preferenceProfiles.test.js
Set-Location frontend
npm.cmd run build
```

Expected: all pass. The Mapbox chunk warning is acceptable.

- [ ] **Step 2: Manual regression checklist**

Start or reuse local backend/frontend servers and verify:

- Top rail visually matches Stitch more closely than the prior green UI.
- Landing state has no large right panel and shows the start card.
- Search results are clickable from the top rail.
- Generic can be selected and stays selected after profile reloads.
- Creating a profile selects it.
- Editing a profile can clear optional fields.
- Deleting the active profile falls back to Generic or another default as expected.
- Setting default works.
- Generic analysis sends no `preference_profile_id`.
- Saved-profile analysis sends `preference_profile_id`.
- Save report works.
- Saved reports panel opens, opens a report, and deletes a report.
- Retry still uses the last analyze payload.

- [ ] **Step 3: Commit any verification fixes**

If fixes were needed:

```powershell
git add <changed-files>
git commit -m "Fix Stitch UI regression verification issues"
```

If no fixes were needed, do not commit.

- [ ] **Step 4: Check final status**

Run:

```powershell
git status --short --branch
```

Expected: no staged changes. Untracked `.tmp/` may remain only if it contains local screenshots/logs and is not staged.
