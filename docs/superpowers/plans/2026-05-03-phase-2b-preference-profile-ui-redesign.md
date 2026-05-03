# Phase 2B Preference Profile UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move preference profiles out of the selected-location result flow and make the active profile an app-level analysis lens selected before address search.

**Architecture:** Keep the existing FastAPI, SQLite, and preference-profile API contract. Refactor the React shell so `selectedPreferenceProfileId` is independent from `selectedPlace`, the top bar owns profile/search entry points, profile management opens as a Stitch-inspired workspace, and the analysis panel renders only location/results/report actions. Add dependency-free Node tests for pure profile selection and analyze-payload helpers.

**Tech Stack:** React 19, Vite 7, plain CSS, lucide-react, Node built-in `node:test`.

---

## File Structure

- Create `frontend/src/utils/preferenceProfiles.js`: pure helper functions for profile selection, active-profile labeling, analyze payloads, and profile form serialization.
- Create `frontend/src/utils/preferenceProfiles.test.js`: Node built-in tests for the helper behavior.
- Create `frontend/src/components/TopBar.jsx`: app-level brand, active profile control, search, saved reports action, and error display.
- Modify `frontend/src/components/PreferenceProfiles.jsx`: convert the inline profile card/form into a Stitch-inspired profile management workspace.
- Modify `frontend/src/App.jsx`: remove profile management and questionnaire from the location-result panel, wire top bar/workspace state, and analyze with the active profile lens.
- Modify `frontend/src/components/Profile.jsx`: add read-only active lens context near the neighborhood heading.
- Modify `frontend/src/components/SavedProfiles.jsx`: allow it to render as a workspace/drawer panel instead of always living in the analysis panel.
- Modify `frontend/src/styles.css`: update the shell, top bar, workspace, and analysis panel styling to match the Stitch direction.
- Modify `README.md`: document the corrected Phase 2B UI behavior.

Backend files should not change in this plan unless frontend verification uncovers a contract bug.

---

### Task 1: Add Pure Profile Helpers And Tests

**Files:**
- Create: `frontend/src/utils/preferenceProfiles.js`
- Create: `frontend/src/utils/preferenceProfiles.test.js`

- [ ] **Step 1: Write failing helper tests**

Create `frontend/src/utils/preferenceProfiles.test.js`:

```javascript
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  buildAnalyzePayload,
  formToPreferenceProfilePayload,
  getActiveProfileLabel,
  profileToForm,
  resolveSelectedPreferenceProfileId,
} from './preferenceProfiles.js';

const PLACE = {
  label: 'Mission District, San Francisco, CA',
  coordinates: { lat: 37.7599, lng: -122.4148 },
};

const PROFILES = [
  {
    id: 'profile-1',
    name: 'Budget walker',
    is_default: false,
    car_reliance: 'no_car',
    energy_preference: 'balanced',
    top_priority: 'walkability_errands',
    budget_sensitivity: 'very_budget_conscious',
    generic_mode: false,
    commute_anchor: { label: 'Union Station', lat: 43.645, lng: -79.38 },
    max_monthly_rent: 2200,
    must_haves: ['transit', 'groceries'],
    deal_breakers: ['lower_rent_pressure'],
    notes: 'Local only.',
  },
  {
    id: 'profile-2',
    name: 'Default profile',
    is_default: true,
    generic_mode: false,
    must_haves: [],
    deal_breakers: [],
  },
];

describe('resolveSelectedPreferenceProfileId', () => {
  it('keeps the current profile when it still exists', () => {
    assert.equal(resolveSelectedPreferenceProfileId(PROFILES, 'profile-1'), 'profile-1');
  });

  it('falls back to the default profile when the current profile is missing', () => {
    assert.equal(resolveSelectedPreferenceProfileId(PROFILES, 'missing-profile'), 'profile-2');
  });

  it('falls back to generic when no profiles exist', () => {
    assert.equal(resolveSelectedPreferenceProfileId([], 'profile-1'), null);
  });
});

describe('getActiveProfileLabel', () => {
  it('formats a saved active profile', () => {
    assert.equal(getActiveProfileLabel(PROFILES[0]), 'Active profile: Budget walker');
  });

  it('formats generic mode', () => {
    assert.equal(getActiveProfileLabel(null), 'Active profile: Generic');
  });
});

describe('buildAnalyzePayload', () => {
  it('sends profile id for saved profile analysis', () => {
    assert.deepEqual(buildAnalyzePayload(PLACE, PROFILES[0]), {
      query: 'Mission District, San Francisco, CA',
      coordinates: { lat: 37.7599, lng: -122.4148 },
      generic_mode: false,
      preference_profile_id: 'profile-1',
    });
  });

  it('sends generic mode without profile id when no saved profile is active', () => {
    assert.deepEqual(buildAnalyzePayload(PLACE, null), {
      query: 'Mission District, San Francisco, CA',
      coordinates: { lat: 37.7599, lng: -122.4148 },
      preferences: {},
      generic_mode: true,
    });
  });

  it('returns null when no place is selected', () => {
    assert.equal(buildAnalyzePayload(null, PROFILES[0]), null);
  });
});

describe('profile form serialization', () => {
  it('converts an API profile to string-backed form state', () => {
    assert.deepEqual(profileToForm(PROFILES[0]), {
      name: 'Budget walker',
      car_reliance: 'no_car',
      energy_preference: 'balanced',
      top_priority: 'walkability_errands',
      budget_sensitivity: 'very_budget_conscious',
      generic_mode: false,
      commute_anchor_label: 'Union Station',
      commute_anchor_lat: '43.645',
      commute_anchor_lng: '-79.38',
      max_monthly_rent: '2200',
      must_haves: ['transit', 'groceries'],
      deal_breakers: ['lower_rent_pressure'],
      notes: 'Local only.',
    });
  });

  it('converts form state to API payload and omits blank optional values', () => {
    assert.deepEqual(
      formToPreferenceProfilePayload({
        name: ' Transit person ',
        car_reliance: 'no_car',
        energy_preference: '',
        top_priority: 'transit_access',
        budget_sensitivity: '',
        generic_mode: false,
        commute_anchor_label: ' Downtown ',
        commute_anchor_lat: '',
        commute_anchor_lng: '',
        max_monthly_rent: '',
        must_haves: ['transit'],
        deal_breakers: [],
        notes: '  ',
      }),
      {
        name: 'Transit person',
        car_reliance: 'no_car',
        top_priority: 'transit_access',
        generic_mode: false,
        commute_anchor: { label: 'Downtown' },
        must_haves: ['transit'],
        deal_breakers: [],
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

Expected: fail with `Cannot find module` or missing export errors because `preferenceProfiles.js` does not exist yet.

- [ ] **Step 3: Add helper implementation**

Create `frontend/src/utils/preferenceProfiles.js`:

```javascript
export const EMPTY_PROFILE_FORM = {
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

export function resolveSelectedPreferenceProfileId(profiles = [], currentProfileId = null) {
  if (currentProfileId && profiles.some((profile) => profile.id === currentProfileId)) {
    return currentProfileId;
  }
  const defaultProfile = profiles.find((profile) => profile.is_default) || profiles[0] || null;
  return defaultProfile?.id || null;
}

export function getActiveProfileLabel(profile) {
  return `Active profile: ${profile?.name || 'Generic'}`;
}

export function buildAnalyzePayload(place, activeProfile) {
  if (!place) return null;
  const basePayload = {
    query: place.label,
    coordinates: place.coordinates,
  };
  if (activeProfile?.id) {
    return {
      ...basePayload,
      generic_mode: Boolean(activeProfile.generic_mode),
      preference_profile_id: activeProfile.id,
    };
  }
  return {
    ...basePayload,
    preferences: {},
    generic_mode: true,
  };
}

export function profileToForm(profile) {
  if (!profile) return { ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] };
  return {
    name: profile.name || '',
    car_reliance: profile.car_reliance || '',
    energy_preference: profile.energy_preference || '',
    top_priority: profile.top_priority || '',
    budget_sensitivity: profile.budget_sensitivity || '',
    generic_mode: Boolean(profile.generic_mode),
    commute_anchor_label: profile.commute_anchor?.label || '',
    commute_anchor_lat: numberToInput(profile.commute_anchor?.lat),
    commute_anchor_lng: numberToInput(profile.commute_anchor?.lng),
    max_monthly_rent: numberToInput(profile.max_monthly_rent),
    must_haves: profile.must_haves || [],
    deal_breakers: profile.deal_breakers || [],
    notes: profile.notes || '',
  };
}

export function formToPreferenceProfilePayload(form) {
  const payload = {
    name: form.name.trim(),
    generic_mode: Boolean(form.generic_mode),
    must_haves: form.must_haves || [],
    deal_breakers: form.deal_breakers || [],
  };

  copyIfPresent(payload, 'car_reliance', form.car_reliance);
  copyIfPresent(payload, 'energy_preference', form.energy_preference);
  copyIfPresent(payload, 'top_priority', form.top_priority);
  copyIfPresent(payload, 'budget_sensitivity', form.budget_sensitivity);

  const commuteLabel = form.commute_anchor_label.trim();
  const commuteLat = form.commute_anchor_lat === '' ? null : Number(form.commute_anchor_lat);
  const commuteLng = form.commute_anchor_lng === '' ? null : Number(form.commute_anchor_lng);
  if (commuteLabel) {
    payload.commute_anchor = { label: commuteLabel };
    if (commuteLat !== null && commuteLng !== null) {
      payload.commute_anchor.lat = commuteLat;
      payload.commute_anchor.lng = commuteLng;
    }
  }

  if (form.max_monthly_rent !== '') {
    payload.max_monthly_rent = Number(form.max_monthly_rent);
  }
  if (form.notes.trim()) {
    payload.notes = form.notes.trim();
  }
  return payload;
}

function copyIfPresent(target, key, value) {
  if (value) {
    target[key] = value;
  }
}

function numberToInput(value) {
  return value === null || value === undefined ? '' : String(value);
}
```

- [ ] **Step 4: Update `useNeighborhood` to use selection helper**

Modify `frontend/src/hooks/useNeighborhood.js` imports:

```javascript
import { useRef, useState } from 'react';
import { resolveSelectedPreferenceProfileId } from '../utils/preferenceProfiles.js';
```

Replace the `loadPreferenceProfiles()` selection block:

```javascript
      setPreferenceProfiles(body);
      setPreferenceProfileError('');
      setSelectedPreferenceProfileId((current) => resolveSelectedPreferenceProfileId(body, current));
```

- [ ] **Step 5: Run helper tests**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
```

Expected: all tests pass.

- [ ] **Step 6: Run frontend build**

Run:

```powershell
Set-Location frontend
npm.cmd run build
```

Expected: build succeeds. A large Mapbox chunk warning is acceptable.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src/hooks/useNeighborhood.js frontend/src/utils/preferenceProfiles.js frontend/src/utils/preferenceProfiles.test.js
git commit -m "Add preference profile UI helpers"
```

---

### Task 2: Add App-Level Top Bar

**Files:**
- Create: `frontend/src/components/TopBar.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Create `TopBar.jsx`**

Create `frontend/src/components/TopBar.jsx`:

```javascript
import { Archive, UserRound } from 'lucide-react';
import SearchBar from './SearchBar.jsx';
import { getActiveProfileLabel } from '../utils/preferenceProfiles.js';

export default function TopBar({
  activeProfile,
  preferenceProfileError,
  onProfileClick,
  onSavedReportsClick,
  onSelectPlace,
}) {
  return (
    <header className="top-bar">
      <div className="brand-lockup">VibeCheck</div>
      <button type="button" className="active-profile-button" onClick={onProfileClick}>
        <UserRound size={16} aria-hidden="true" />
        <span>{getActiveProfileLabel(activeProfile)}</span>
      </button>
      <div className="top-search">
        <SearchBar onSelect={onSelectPlace} />
      </div>
      <button type="button" className="top-icon-button" onClick={onSavedReportsClick} aria-label="Saved reports">
        <Archive size={17} aria-hidden="true" />
      </button>
      {preferenceProfileError && <p className="top-bar-error">{preferenceProfileError}</p>}
    </header>
  );
}
```

- [ ] **Step 2: Import and render TopBar in `App.jsx`**

Modify imports in `frontend/src/App.jsx`:

```javascript
import { useEffect, useMemo, useState } from 'react';
import MapView from './components/MapView.jsx';
import PreferenceProfiles from './components/PreferenceProfiles.jsx';
import Profile from './components/Profile.jsx';
import SavedProfiles from './components/SavedProfiles.jsx';
import TopBar from './components/TopBar.jsx';
import { useNeighborhood } from './hooks/useNeighborhood.js';
import { buildAnalyzePayload } from './utils/preferenceProfiles.js';
```

Remove these imports:

```javascript
import Questionnaire from './components/Questionnaire.jsx';
import SearchBar from './components/SearchBar.jsx';
```

Add workspace state near `selectedPlace`:

```javascript
  const [activeWorkspace, setActiveWorkspace] = useState(null);
```

Valid values are `null`, `'profiles'`, and `'savedReports'`.

Render `TopBar` immediately inside `<section className="map-stage">`:

```javascript
        <TopBar
          activeProfile={selectedPreferenceProfile}
          preferenceProfileError={preferenceProfileError}
          onProfileClick={() => setActiveWorkspace('profiles')}
          onSavedReportsClick={() => setActiveWorkspace('savedReports')}
          onSelectPlace={handleSelectPlace}
        />
```

- [ ] **Step 3: Remove the old top overlay from `App.jsx`**

Delete this block:

```javascript
        <div className="top-overlay">
          <p className="eyebrow">VibeCheck</p>
          <SearchBar onSelect={handleSelectPlace} />
          {!selectedPlace && <p className="hint-line">Select an autocomplete result to fly to the neighborhood.</p>}
        </div>
```

- [ ] **Step 4: Add top bar CSS**

Append this block near the existing `.top-overlay` styles in `frontend/src/styles.css`:

```css
.top-bar {
  position: absolute;
  left: 12px;
  right: 12px;
  top: 12px;
  z-index: 4;
  display: grid;
  grid-template-columns: auto auto minmax(260px, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 48px;
  padding: 7px 10px;
  border: 1px solid rgba(255, 255, 255, 0.75);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.84);
  box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(10px);
}

.brand-lockup {
  color: #0f172a;
  font-weight: 800;
}

.active-profile-button,
.top-icon-button {
  min-height: 34px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.8);
  color: #0f172a;
  cursor: pointer;
}

.active-profile-button {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 0 12px;
  white-space: nowrap;
}

.top-icon-button {
  display: grid;
  width: 34px;
  place-items: center;
}

.top-search .search-card {
  box-shadow: none;
  padding: 7px 10px;
}

.top-bar-error {
  grid-column: 1 / -1;
  margin: 0;
  color: #8a3c32;
  font-size: 0.84rem;
}
```

- [ ] **Step 5: Run frontend build**

Run:

```powershell
Set-Location frontend
npm.cmd run build
```

Expected: build succeeds. The app may still show duplicate old profile UI until later tasks remove it.

- [ ] **Step 6: Commit**

Run:

```powershell
git add frontend/src/App.jsx frontend/src/components/TopBar.jsx frontend/src/styles.css
git commit -m "Add app-level profile top bar"
```

---

### Task 3: Convert Preference Profiles To Stitch-Inspired Workspace

**Files:**
- Modify: `frontend/src/components/PreferenceProfiles.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Replace local helper definitions in `PreferenceProfiles.jsx`**

Modify imports:

```javascript
import { useEffect, useMemo, useState } from 'react';
import { Check, Plus, Star, Trash2, X } from 'lucide-react';
import {
  EMPTY_PROFILE_FORM,
  formToPreferenceProfilePayload,
  profileToForm,
} from '../utils/preferenceProfiles.js';
```

Delete the local `EMPTY_FORM`, local `profileToForm()`, and local `formToPayload()` definitions.

- [ ] **Step 2: Update the component props**

Change the component signature to:

```javascript
export default function PreferenceProfiles({
  open,
  profiles = [],
  selectedProfileId,
  onClose,
  onSelect,
  onCreate,
  onUpdate,
  onDelete,
  onSetDefault,
  error,
  isSaving,
}) {
```

Add an early return:

```javascript
  if (!open) return null;
```

- [ ] **Step 3: Update form initialization and submission**

Use this state:

```javascript
  const [editingProfile, setEditingProfile] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [form, setForm] = useState(EMPTY_PROFILE_FORM);
```

Update the effect:

```javascript
  useEffect(() => {
    if (isCreating) {
      setForm({ ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] });
    } else if (editingProfile) {
      setForm(profileToForm(editingProfile));
    }
  }, [editingProfile, isCreating]);
```

Update submit:

```javascript
  async function submitForm(event) {
    event.preventDefault();
    const payload = formToPreferenceProfilePayload(form);
    if (editingProfile) {
      await onUpdate(editingProfile.id, payload);
    } else {
      await onCreate(payload);
    }
    setIsCreating(false);
    setEditingProfile(null);
    setForm({ ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] });
  }
```

- [ ] **Step 4: Replace the rendered shell**

Replace the returned JSX with this workspace structure:

```javascript
  const formOpen = isCreating || Boolean(editingProfile);

  return (
    <section className="workspace-backdrop" aria-label="Lifestyle profile workspace">
      <div className="profile-workspace">
        <div className="profile-workspace-main">
          <div className="workspace-title-row">
            <div>
              <p className="eyebrow">Lifestyle Profile</p>
              <h1>Configure your analysis lens</h1>
              <p>Set reusable preferences before choosing a neighborhood.</p>
            </div>
            <button type="button" className="top-icon-button" onClick={onClose} aria-label="Close profiles">
              <X size={18} aria-hidden="true" />
            </button>
          </div>

          <div className="profile-selection-grid">
            <button
              type="button"
              className={`profile-choice-card ${selectedProfileId ? '' : 'is-active'}`}
              onClick={() => onSelect(null)}
            >
              <strong>Generic</strong>
              <span>Run a general neighborhood check without personal fit scoring.</span>
              {!selectedProfileId && <Check size={18} aria-hidden="true" />}
            </button>
            {profiles.map((profile) => (
              <button
                type="button"
                key={profile.id}
                className={`profile-choice-card ${profile.id === selectedProfileId ? 'is-active' : ''}`}
                onClick={() => onSelect(profile.id)}
              >
                <strong>{profile.name}</strong>
                <span>{profile.is_default ? 'Default profile' : 'Saved lifestyle profile'}</span>
                {profile.id === selectedProfileId && <Check size={18} aria-hidden="true" />}
              </button>
            ))}
          </div>

          <div className="profile-workspace-actions">
            <button type="button" className="primary-button" onClick={() => setIsCreating(true)}>
              <Plus size={16} aria-hidden="true" />
              New profile
            </button>
            {selectedProfile && (
              <>
                <button type="button" onClick={() => setEditingProfile(selectedProfile)}>
                  Edit selected
                </button>
                {!selectedProfile.is_default && (
                  <button type="button" onClick={() => onSetDefault(selectedProfile.id)}>
                    <Star size={16} aria-hidden="true" />
                    Make default
                  </button>
                )}
                <button type="button" className="icon-danger" onClick={() => onDelete(selectedProfile.id)}>
                  <Trash2 size={16} aria-hidden="true" />
                  Delete
                </button>
              </>
            )}
          </div>

          {error && <p className="save-error">{error}</p>}

          {formOpen && (
            <form className="preference-profile-form workspace-form" onSubmit={submitForm}>
              <ProfileFormFields form={form} setForm={setForm} toggleCategory={toggleCategory} />
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
        </div>

        <aside className="profile-workspace-nav">
          <p className="eyebrow">Neighborhood Analysis</p>
          <span>Preference Profile</span>
          <strong>{selectedProfile ? selectedProfile.name : 'Generic'}</strong>
          <button type="button" onClick={onClose}>Return to map</button>
        </aside>
      </div>
    </section>
  );
```

- [ ] **Step 5: Add preference select fields**

Add these constants after `CATEGORY_OPTIONS`:

```javascript
const SELECT_OPTIONS = {
  car_reliance: [
    ['no_car', 'No car'],
    ['sometimes_car', 'Sometimes use a car'],
    ['drive_daily', 'Drive daily'],
  ],
  energy_preference: [
    ['quiet', 'Quiet and calm'],
    ['balanced', 'Balanced'],
    ['lively', 'Lively and social'],
  ],
  top_priority: [
    ['walkability_errands', 'Walkability and errands'],
    ['transit_access', 'Transit access'],
    ['parks_outdoors', 'Parks and outdoors'],
    ['restaurants_nightlife', 'Restaurants and nightlife'],
    ['lower_rent_pressure', 'Lower rent pressure'],
  ],
  budget_sensitivity: [
    ['very_budget_conscious', 'Very budget conscious'],
    ['moderate', 'Moderate'],
    ['flexible', 'Flexible'],
  ],
};
```

Add `ProfileFormFields` below the component:

```javascript
function ProfileFormFields({ form, setForm, toggleCategory }) {
  return (
    <>
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
        Run this saved profile as generic
      </label>
      {Object.entries(SELECT_OPTIONS).map(([field, options]) => (
        <label className="field" key={field}>
          <span>{field.replaceAll('_', ' ')}</span>
          <select value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })}>
            <option value="">No preference</option>
            {options.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      ))}
      <label className="field">
        <span>Commute anchor</span>
        <input
          value={form.commute_anchor_label}
          onChange={(event) => setForm({ ...form, commute_anchor_label: event.target.value })}
          placeholder="Work, school, or general area"
        />
      </label>
      <div className="coordinate-grid">
        <label className="field">
          <span>Anchor latitude</span>
          <input
            type="number"
            step="any"
            value={form.commute_anchor_lat}
            onChange={(event) => setForm({ ...form, commute_anchor_lat: event.target.value })}
          />
        </label>
        <label className="field">
          <span>Anchor longitude</span>
          <input
            type="number"
            step="any"
            value={form.commute_anchor_lng}
            onChange={(event) => setForm({ ...form, commute_anchor_lng: event.target.value })}
          />
        </label>
      </div>
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
      <label className="field notes-field">
        <span>Notes</span>
        <textarea
          value={form.notes}
          onChange={(event) => setForm({ ...form, notes: event.target.value })}
          maxLength={1000}
        />
      </label>
    </>
  );
}
```

- [ ] **Step 6: Render workspace from `App.jsx`**

Render `PreferenceProfiles` as a direct child of `.map-stage`, after `TopBar` and before `.analysis-panel`:

```javascript
        <PreferenceProfiles
          open={activeWorkspace === 'profiles'}
          profiles={preferenceProfiles}
          selectedProfileId={selectedPreferenceProfileId}
          onClose={() => setActiveWorkspace(null)}
          onSelect={setSelectedPreferenceProfileId}
          onCreate={createPreferenceProfile}
          onUpdate={updatePreferenceProfile}
          onDelete={(profileId) => deletePreferenceProfile(profileId).catch(() => null)}
          onSetDefault={(profileId) => setDefaultPreferenceProfile(profileId).catch(() => null)}
          error={preferenceProfileError}
          isSaving={isSavingPreferenceProfile}
        />
```

Delete the old `{selectedPlace && <PreferenceProfiles ... />}` block from the analysis panel.

- [ ] **Step 7: Add workspace CSS**

Append this to `frontend/src/styles.css`:

```css
.workspace-backdrop {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: grid;
  place-items: start center;
  padding: 84px 24px 24px;
  background: rgba(248, 250, 252, 0.38);
  backdrop-filter: blur(4px);
}

.profile-workspace {
  display: grid;
  grid-template-columns: minmax(0, 680px) 260px;
  width: min(980px, 100%);
  border: 1px solid rgba(255, 255, 255, 0.75);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.14);
  overflow: hidden;
}

.profile-workspace-main {
  display: grid;
  gap: 18px;
  padding: 24px;
}

.workspace-title-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
}

.workspace-title-row h1 {
  margin: 0 0 6px;
  color: #0f172a;
  font-size: 1.55rem;
}

.workspace-title-row p:last-child {
  margin: 0;
  color: #45464d;
}

.profile-selection-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.profile-choice-card {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 10px;
  min-height: 82px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 8px;
  background: #ffffff;
  color: #0f172a;
  cursor: pointer;
  padding: 12px;
  text-align: left;
}

.profile-choice-card span {
  grid-column: 1 / -1;
  color: #45464d;
  font-size: 0.86rem;
}

.profile-choice-card.is-active {
  border-color: rgba(37, 99, 235, 0.65);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.profile-workspace-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.profile-workspace-actions button,
.profile-workspace-nav button {
  min-height: 36px;
  border: 1px solid rgba(15, 23, 42, 0.14);
  border-radius: 8px;
  background: #ffffff;
  color: #0f172a;
  cursor: pointer;
  padding: 0 12px;
}

.profile-workspace-actions .primary-button {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  background: #2563eb;
  color: #ffffff;
}

.workspace-form {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.workspace-form .generic-toggle,
.workspace-form .category-checklist,
.workspace-form .profile-form-actions,
.workspace-form .notes-field {
  grid-column: 1 / -1;
}

.coordinate-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.profile-workspace-nav {
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 24px;
  background: rgba(248, 250, 252, 0.96);
  border-left: 1px solid rgba(15, 23, 42, 0.08);
}

.profile-workspace-nav span {
  color: #45464d;
  font-size: 0.9rem;
}
```

- [ ] **Step 8: Run helper tests and build**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
Set-Location frontend
npm.cmd run build
```

Expected: helper tests pass and frontend build succeeds.

- [ ] **Step 9: Commit**

Run:

```powershell
git add frontend/src/App.jsx frontend/src/components/PreferenceProfiles.jsx frontend/src/styles.css
git commit -m "Move preference profiles to workspace"
```

---

### Task 4: Make Analysis Panel Location-Only

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Profile.jsx`
- Modify: `frontend/src/components/SavedProfiles.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Replace local preference state in `App.jsx`**

Delete these state declarations:

```javascript
  const [preferences, setPreferences] = useState({});
  const [genericMode, setGenericMode] = useState(false);
```

Delete this effect:

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

Replace `analyzePayload` with:

```javascript
  const analyzePayload = useMemo(
    () => buildAnalyzePayload(selectedPlace, selectedPreferenceProfile),
    [selectedPlace, selectedPreferenceProfile],
  );
```

- [ ] **Step 2: Delete Questionnaire rendering from `App.jsx`**

Delete the entire `{selectedPlace && <Questionnaire ... />}` block.

Update the selected-place card copy:

```javascript
          {selectedPlace && (
            <div className="selected-place-card">
              <p className="eyebrow">Selected place</p>
              <h1>{selectedPlace.label}</h1>
              <p>{selectedPreferenceProfile ? `Analyzing for ${selectedPreferenceProfile.name}.` : 'Running a generic neighborhood check.'}</p>
              <button className="primary-button" type="button" disabled={loading} onClick={() => analyzePayload && analyze(analyzePayload)}>
                {loading ? 'Analyzing...' : 'Analyze neighborhood'}
              </button>
            </div>
          )}
```

- [ ] **Step 3: Keep the empty state useful before location selection**

Replace the current empty state with:

```javascript
          {!loading && !error && !data && (
            <div className="empty-profile-state">
              <strong>{selectedPlace ? 'Ready to analyze.' : 'Choose a place to begin.'}</strong>
              <p>
                {selectedPlace
                  ? 'The profile will show fit, confidence, caveats, source statuses, and neighborhood context.'
                  : 'Select a saved lifestyle profile or keep Generic active, then search for an address or neighborhood.'}
              </p>
            </div>
          )}
```

- [ ] **Step 4: Pass active profile context into `Profile`**

Update the `Profile` render in `App.jsx`:

```javascript
            <Profile
              response={data}
              activePreferenceProfile={selectedPreferenceProfile}
              savedProfileId={savedProfileId}
              saveError={saveError}
              isSaving={isSaving}
              onSave={() => saveCurrentProfile(data).catch(() => null)}
            />
```

Modify `frontend/src/components/Profile.jsx` signature:

```javascript
export default function Profile({ response, activePreferenceProfile, onSave, savedProfileId, saveError, isSaving }) {
```

Add this under the heading block:

```javascript
        <p className="analysis-lens-line">
          {activePreferenceProfile ? `Analyzed for ${activePreferenceProfile.name}` : 'Generic neighborhood check'}
        </p>
```

- [ ] **Step 5: Move saved reports into workspace**

Modify `SavedProfiles.jsx` signature:

```javascript
export default function SavedProfiles({ open = true, profiles = [], onClose, onOpen, onDelete, onRefresh }) {
  if (!open) return null;
```

Add a close button in the header when `onClose` exists:

```javascript
        <div className="saved-header-actions">
          <button type="button" onClick={onRefresh}>Refresh</button>
          {onClose && <button type="button" onClick={onClose}>Close</button>}
        </div>
```

Wrap `SavedProfiles` in `App.jsx` outside the analysis panel:

```javascript
        <SavedProfiles
          open={activeWorkspace === 'savedReports'}
          profiles={savedProfiles}
          onClose={() => setActiveWorkspace(null)}
          onRefresh={() => loadSavedProfiles().catch(() => null)}
          onOpen={(profileId) => {
            handleOpenSavedProfile(profileId).catch(() => null);
            setActiveWorkspace(null);
          }}
          onDelete={(profileId) => handleDeleteSavedProfile(profileId).catch(() => null)}
        />
```

Delete the old always-visible `SavedProfiles` block from the analysis panel.

- [ ] **Step 6: Add location-only panel CSS**

Append this to `frontend/src/styles.css`:

```css
.selected-place-card {
  display: grid;
  gap: 10px;
}

.analysis-lens-line {
  margin: 4px 0 0;
  color: #45464d;
  font-size: 0.88rem;
}

.saved-header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.map-stage > .saved-profiles {
  position: absolute;
  right: 24px;
  top: 84px;
  bottom: 24px;
  z-index: 3;
  width: min(360px, calc(100vw - 48px));
  overflow: auto;
  border-color: rgba(255, 255, 255, 0.75);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.14);
  backdrop-filter: blur(10px);
}
```

- [ ] **Step 7: Run helper tests and build**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
Set-Location frontend
npm.cmd run build
```

Expected: helper tests pass and frontend build succeeds.

- [ ] **Step 8: Commit**

Run:

```powershell
git add frontend/src/App.jsx frontend/src/components/Profile.jsx frontend/src/components/SavedProfiles.jsx frontend/src/styles.css
git commit -m "Focus analysis panel on neighborhood results"
```

---

### Task 5: Responsive Polish And Documentation

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `README.md`

- [ ] **Step 1: Add mobile CSS for top bar and workspaces**

Append this inside the existing `@media (max-width: 760px)` block in `frontend/src/styles.css`:

```css
  .top-bar {
    grid-template-columns: 1fr auto auto;
  }

  .brand-lockup {
    display: none;
  }

  .active-profile-button {
    grid-column: 1 / -1;
    justify-content: center;
  }

  .top-search {
    grid-column: 1 / -1;
  }

  .workspace-backdrop {
    padding: 104px 12px 12px;
    place-items: stretch;
  }

  .profile-workspace {
    grid-template-columns: 1fr;
    max-height: calc(100vh - 116px);
    overflow: auto;
  }

  .profile-workspace-nav {
    border-left: 0;
    border-top: 1px solid rgba(15, 23, 42, 0.08);
  }

  .profile-selection-grid,
  .workspace-form,
  .coordinate-grid {
    grid-template-columns: 1fr;
  }

  .map-stage > .saved-profiles {
    left: 12px;
    right: 12px;
    top: 104px;
    bottom: 12px;
    width: auto;
  }
```

- [ ] **Step 2: Update README Phase 2 status**

In `README.md`, replace the Phase 2 status paragraph with:

```markdown
Phase 2A added explicit local saved neighborhood reports. Phase 2B added reusable local preference profiles and then corrected the UI so profiles work as an app-level analysis lens selected before address search. Generic analysis remains available when no saved profile is active. The selected-location panel now focuses on neighborhood results, confidence, sources, and saved-report actions. The next Phase 2 slices should focus on compare mode and richer provenance/source freshness UI.
```

- [ ] **Step 3: Run helper tests and frontend build**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
Set-Location frontend
npm.cmd run build
```

Expected: helper tests pass and frontend build succeeds.

- [ ] **Step 4: Review docs diff**

Run:

```powershell
git diff -- README.md frontend/src/styles.css
```

Expected: README only describes implemented Phase 2B UI behavior, and CSS changes are limited to responsive layout.

- [ ] **Step 5: Commit**

Run:

```powershell
git add README.md frontend/src/styles.css
git commit -m "Polish preference profile UI redesign"
```

---

### Task 6: Final Verification

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

- [ ] **Step 3: Run helper tests**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
```

Expected: all tests pass.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
Set-Location frontend
npm.cmd run build
```

Expected: build succeeds. A large Mapbox chunk warning is acceptable.

- [ ] **Step 5: Manual UI verification**

Run the app locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

In another terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

Open `http://127.0.0.1:5173` and verify:

- The top bar shows `Active profile: Generic` before any address is selected if no profile is active.
- The user can search/select an address while Generic is active.
- Clicking the active profile control opens the lifestyle profile workspace before any place is selected.
- Creating a profile selects it and updates the top bar.
- Editing, deleting, and setting a default profile work from the workspace.
- Selecting an address does not show profile management in the analysis panel.
- Running analysis with Generic sends no `preference_profile_id`.
- Running analysis with a saved active profile sends `preference_profile_id`.
- Saved neighborhood reports open from the saved reports workspace, not from an always-visible result-panel card.

- [ ] **Step 6: Check git status**

Run:

```powershell
git status --short --branch
```

Expected: only intentional commits are present. No `.tmp/` or `.superpowers/brainstorm/` files should be staged.
