# Stitch Dialog Parity Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the Phase 2B frontend so profile and saved-report workspaces are visible, viewport-safe, and structurally closer to the Google Stitch references.

**Architecture:** Keep the current React component boundaries and backend APIs. Add lightweight frontend UI contract tests for source-level regressions that are easy to catch without a browser automation dependency, then restructure the profile workspace and CSS overlay layers around Stitch-like modal and panel patterns.

**Tech Stack:** React 19, Vite 7, lucide-react, Node built-in `node:test`, plain CSS.

---

## File Structure

- Create `frontend/src/uiContract.test.js`: static UI contract tests for mojibake, overlay layering, and viewport-safe workspace CSS.
- Modify `frontend/src/App.jsx`: remove broken landing glyph and keep workspace triggers unchanged.
- Modify `frontend/src/components/PreferenceProfiles.jsx`: make the profile editor the primary visible workspace, move selection/default/delete controls into a compact rail, preserve existing CRUD callbacks.
- Modify `frontend/src/components/SavedProfiles.jsx`: tighten the saved reports panel copy and actions to match the Stitch right-side workspace.
- Modify `frontend/src/styles.css`: add explicit overlay z-index tokens, viewport-safe dialog sizes, internal scroll areas, Stitch-like profile editor sections, and mobile sheet behavior.
- Modify `docs/superpowers/specs/2026-05-03-phase-2b-preference-profiles-design.md`: already updated with the repair addendum.

---

### Task 1: Add UI Contract Regression Tests

**Files:**
- Create: `frontend/src/uiContract.test.js`

- [ ] **Step 1: Create the failing source contract test**

Create `frontend/src/uiContract.test.js`:

```javascript
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const ROOT = resolve(import.meta.dirname, '..');

function source(path) {
  return readFileSync(resolve(ROOT, path), 'utf8');
}

test('frontend source does not contain mojibake glyphs', () => {
  const files = [
    'src/App.jsx',
    'src/components/PreferenceProfiles.jsx',
    'src/components/SavedProfiles.jsx',
    'src/styles.css',
  ];

  for (const file of files) {
    assert.equal(source(file).includes('â'), false, `${file} contains mojibake`);
  }
});

test('workspace overlays sit above the top rail and use viewport-safe sizing', () => {
  const css = source('src/styles.css');

  assert.match(css, /--layer-top-bar:\s*20;/);
  assert.match(css, /--layer-workspace:\s*40;/);
  assert.match(css, /\.top-bar\s*{[^}]*z-index:\s*var\(--layer-top-bar\)/s);
  assert.match(css, /\.workspace-backdrop\s*{[^}]*z-index:\s*var\(--layer-workspace\)/s);
  assert.match(css, /\.profile-workspace\s*{[^}]*max-height:\s*calc\(100vh - 112px\)/s);
  assert.match(css, /\.profile-workspace-main\s*{[^}]*overflow:\s*auto/s);
});
```

- [ ] **Step 2: Run the contract test and confirm it fails**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: fails because mojibake exists and overlay layer tokens/viewport-safe CSS are missing.

- [ ] **Step 3: Commit is deferred**

Do not commit after the failing test. Commit after Task 3 when the test is green.

---

### Task 2: Restructure Lifestyle Profile Workspace

**Files:**
- Modify: `frontend/src/components/PreferenceProfiles.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Remove broken landing glyph**

In `frontend/src/App.jsx`, replace:

```jsx
<div className="landing-icon">â—Ž</div>
```

with:

```jsx
<div className="landing-icon" aria-hidden="true">◎</div>
```

- [ ] **Step 2: Replace mojibake category symbols**

In `frontend/src/components/PreferenceProfiles.jsx`, replace `CATEGORY_OPTIONS` with:

```javascript
const CATEGORY_OPTIONS = [
  ['transit', 'Transit', 'T'],
  ['walkability', 'Walkability', 'W'],
  ['parks', 'Green spaces', 'G'],
  ['groceries', 'Retail access', 'R'],
  ['restaurants', 'Dining', 'D'],
  ['quiet', 'Quiet', 'Q'],
  ['social_scene', 'Nightlife', 'N'],
  ['lower_rent_pressure', 'Rent pressure', '$'],
];
```

- [ ] **Step 3: Open the editor by default**

In `PreferenceProfiles.jsx`, change the form initialization effect to keep the editor visible whenever the workspace opens:

```javascript
  useEffect(() => {
    if (!open) return;
    if (isCreating) {
      setForm({ ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] });
      return;
    }
    if (editingProfile) {
      setForm(profileToForm(editingProfile));
      return;
    }
    if (selectedProfile) {
      setForm(profileToForm(selectedProfile));
      return;
    }
    setForm({ ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] });
  }, [editingProfile, isCreating, open, selectedProfile]);
```

Then replace:

```javascript
const formOpen = isCreating || Boolean(editingProfile);
```

with:

```javascript
const activeEditorProfile = editingProfile || selectedProfile;
const isEditingExisting = Boolean(activeEditorProfile) && !isCreating;
```

- [ ] **Step 4: Make submit update selected profiles or create new ones**

In `submitForm`, replace the existing create/update branch with:

```javascript
    const payload = formToPreferenceProfilePayload(form, { mode: isEditingExisting ? 'update' : 'create' });
    if (isEditingExisting) {
      await onUpdate(activeEditorProfile.id, payload);
    } else {
      await onCreate(payload);
    }
```

After saving, keep the reset block:

```javascript
    setIsCreating(false);
    setEditingProfile(null);
    setForm({ ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] });
```

- [ ] **Step 5: Replace the workspace body layout**

In the returned JSX, keep the outer `workspace-backdrop` and `profile-workspace`, but make the main column show the editor directly:

```jsx
        <div className="profile-workspace-main">
          <div className="workspace-title-row">
            <div>
              <p className="eyebrow">Lifestyle Profile</p>
              <h1>{isEditingExisting ? 'Edit analysis lens' : 'Create analysis lens'}</h1>
              <p>Configure reusable preferences before choosing a neighborhood.</p>
            </div>
            <button type="button" className="top-icon-button" onClick={onClose} aria-label="Close profiles">
              <X size={18} aria-hidden="true" />
            </button>
          </div>

          {error && <p className="save-error">{error}</p>}

          <form className="preference-profile-form workspace-form" onSubmit={submitForm}>
            <ProfileFormFields form={form} setForm={setForm} toggleCategory={toggleCategory} />
            <div className="profile-form-actions">
              <button type="button" onClick={onClose}>Cancel</button>
              <button type="submit" className="primary-button" disabled={isSaving}>
                {isSaving ? 'Saving...' : isEditingExisting ? 'Save Profile' : 'Create Profile'}
              </button>
            </div>
          </form>
        </div>
```

- [ ] **Step 6: Move profile selection into the rail**

Replace the `profile-workspace-nav` contents with:

```jsx
        <aside className="profile-workspace-nav">
          <div>
            <p className="eyebrow">Neighborhood Analysis</p>
            <span>Active lens</span>
            <strong>{selectedProfile ? selectedProfile.name : 'Generic'}</strong>
          </div>
          <div className="profile-rail-list">
            <button
              type="button"
              className={`profile-rail-item ${selectedProfileId ? '' : 'is-active'}`}
              onClick={() => {
                setIsCreating(false);
                setEditingProfile(null);
                onSelect(null);
              }}
            >
              <strong>Generic</strong>
              <span>General check</span>
            </button>
            {profiles.map((profile) => (
              <button
                type="button"
                key={profile.id}
                className={`profile-rail-item ${profile.id === selectedProfileId ? 'is-active' : ''}`}
                onClick={() => {
                  setIsCreating(false);
                  setEditingProfile(profile);
                  onSelect(profile.id);
                }}
              >
                <strong>{profile.name}</strong>
                <span>{profile.is_default ? 'Default' : 'Saved profile'}</span>
              </button>
            ))}
          </div>
          <div className="profile-rail-actions">
            <button
              type="button"
              onClick={() => {
                setIsCreating(true);
                setEditingProfile(null);
                onSelect(null);
              }}
            >
              <Plus size={16} aria-hidden="true" />
              New
            </button>
            {selectedProfile && !selectedProfile.is_default && (
              <button type="button" onClick={() => onSetDefault(selectedProfile.id)}>
                <Star size={16} aria-hidden="true" />
                Default
              </button>
            )}
            {selectedProfile && (
              <button type="button" className="icon-danger" onClick={() => onDelete(selectedProfile.id)}>
                <Trash2 size={16} aria-hidden="true" />
                Delete
              </button>
            )}
          </div>
          <button type="button" className="primary-button" onClick={onClose}>Return to map</button>
        </aside>
```

---

### Task 3: Repair Overlay Layering And Profile CSS

**Files:**
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add explicit z-index tokens**

In `:root`, add:

```css
  --layer-map-control: 10;
  --layer-top-bar: 20;
  --layer-panel: 30;
  --layer-workspace: 40;
```

- [ ] **Step 2: Apply layer tokens**

Update these selectors:

```css
.top-bar { z-index: var(--layer-top-bar); }
.landing-card, .map-status-chip { z-index: var(--layer-map-control); }
.analysis-panel, .map-stage > .saved-profiles { z-index: var(--layer-panel); }
.workspace-backdrop { z-index: var(--layer-workspace); }
```

- [ ] **Step 3: Make the profile workspace viewport-safe**

Update `.workspace-backdrop`, `.profile-workspace`, and `.profile-workspace-main`:

```css
.workspace-backdrop {
  position: absolute;
  inset: 0;
  z-index: var(--layer-workspace);
  display: grid;
  place-items: center;
  padding: 72px 24px 24px;
  background: rgba(248, 250, 252, 0.42);
  backdrop-filter: blur(8px);
}

.profile-workspace {
  display: grid;
  grid-template-columns: minmax(0, 700px) 290px;
  width: min(1010px, 100%);
  max-height: calc(100vh - 112px);
  border: 1px solid var(--vc-border-light);
  border-radius: 16px;
  background: var(--vc-glass-strong);
  box-shadow: var(--vc-shadow-lg);
  overflow: hidden;
}

.profile-workspace-main {
  display: grid;
  gap: 18px;
  min-height: 0;
  overflow: auto;
  padding: 28px;
}
```

- [ ] **Step 4: Add rail and section CSS**

Add:

```css
.profile-rail-list {
  display: grid;
  gap: 8px;
}

.profile-rail-item {
  display: grid;
  gap: 2px;
  min-height: 58px;
  border: 1px solid var(--vc-border);
  border-radius: 10px;
  background: #ffffff;
  color: var(--vc-text);
  cursor: pointer;
  padding: 10px 12px;
  text-align: left;
}

.profile-rail-item span {
  color: var(--vc-muted);
  font-size: 0.78rem;
}

.profile-rail-item.is-active {
  border-color: rgba(37, 99, 235, 0.7);
  background: var(--vc-blue-soft);
}

.profile-rail-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.profile-rail-actions button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
}
```

- [ ] **Step 5: Make form actions sticky and visible**

Update `.profile-form-actions`:

```css
.profile-form-actions {
  position: sticky;
  bottom: -28px;
  z-index: 1;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin: 4px -28px -28px;
  padding: 16px 28px;
  border-top: 1px solid var(--vc-border);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
}
```

- [ ] **Step 6: Run the UI contract test**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: all UI contract tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src/uiContract.test.js frontend/src/App.jsx frontend/src/components/PreferenceProfiles.jsx frontend/src/styles.css
git commit -m "Repair Stitch profile workspace visibility"
```

---

### Task 4: Tighten Saved Reports Panel

**Files:**
- Modify: `frontend/src/components/SavedProfiles.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Update saved report header and row actions**

Change the header title block to:

```jsx
        <div>
          <p className="eyebrow">Saved Reports</p>
          <h2>Neighborhood Intelligence</h2>
        </div>
```

Change each row's open button text metadata to:

```jsx
                <strong>{profile.place_label}</strong>
                <span>{profile.confidence_level} confidence · Open report</span>
```

- [ ] **Step 2: Add a bottom action bar**

Before `</section>` in `SavedProfiles.jsx`, add:

```jsx
      <div className="saved-report-footer">
        <button type="button" className="primary-button">Export Report</button>
      </div>
```

The button is presentational for this phase and should not be wired to a new feature.

- [ ] **Step 3: Make saved panel viewport-safe**

Update `.map-stage > .saved-profiles`:

```css
.map-stage > .saved-profiles {
  position: absolute;
  right: 24px;
  top: 84px;
  bottom: 24px;
  z-index: var(--layer-panel);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  width: min(380px, calc(100vw - 48px));
  overflow: hidden;
  border-color: rgba(255, 255, 255, 0.75);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.14);
  backdrop-filter: blur(10px);
}
```

Update `.saved-list`:

```css
.saved-list {
  display: grid;
  align-content: start;
  gap: 10px;
  min-height: 0;
  overflow: auto;
}
```

Add:

```css
.saved-report-footer {
  border-top: 1px solid var(--vc-border);
  padding-top: 12px;
}

.saved-report-footer .primary-button {
  width: 100%;
}
```

- [ ] **Step 4: Commit**

Run:

```powershell
git add frontend/src/components/SavedProfiles.jsx frontend/src/styles.css
git commit -m "Repair Stitch saved reports panel"
```

---

### Task 5: Final Verification

**Files:**
- Modify only if verification reveals a bug.

- [ ] **Step 1: Run frontend checks**

Run:

```powershell
node --test frontend/src/utils/preferenceProfiles.test.js
node --test frontend/src/uiContract.test.js
Set-Location frontend
npm.cmd run build
```

Expected: both Node test suites pass and the frontend build succeeds.

- [ ] **Step 2: Run backend regression checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check backend tests
```

Expected: all backend tests pass and ruff is clean.

- [ ] **Step 3: Manual UI checklist**

Open the app at the current Vite URL and verify:

- Lifestyle Profile opens above the top rail.
- Lifestyle Profile editor is visible immediately.
- Profile workspace scrolls internally on short desktop heights.
- Saved Reports opens as a right panel with visible close/refresh and footer action.
- Generic selection still works.
- Create profile, edit profile, set default, and delete profile still work.
- Analyze works with Generic and with a saved profile.
- Save report, open report, and delete report still work.

- [ ] **Step 4: Final status**

Run:

```powershell
git status --short --branch
```

Expected: no staged changes. Untracked `.tmp/` may remain only if it contains local screenshots/logs and is not staged.
