# Phase 2D Compare Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a top-level compare workflow where users can analyze 2-4 ad hoc places through the currently selected preference profile or Generic lens.

**Architecture:** Phase 2D is frontend-first and reuses the existing backend `/analyze` endpoint. The frontend owns compare slots, runs one analyze request per selected place, and renders successful or failed place results independently. Shared analyze API code is extracted so compare mode can call the API without mutating the main single-place analysis state.

**Tech Stack:** React 19, Vite 7, Mapbox search utility, existing FastAPI `/analyze` contract, Node built-in `node:test`, plain CSS.

---

## File Structure

- Create `frontend/src/utils/compareUtils.js`: pure compare helpers for slot limits, payload construction, successful result filtering, confidence risk, and summary highlights.
- Create `frontend/src/utils/compareUtils.test.js`: Node tests for compare helper behavior.
- Create `frontend/src/utils/api.js`: shared frontend API helper for `/analyze` and response parsing.
- Create `frontend/src/utils/api.test.js`: Node tests for shared API helper success/error behavior.
- Modify `frontend/src/hooks/useNeighborhood.js`: reuse `analyzeNeighborhood()` from `api.js` for the main analysis flow.
- Create `frontend/src/components/CompareMode.jsx`: compare workspace, slot state, analyze fan-out, retry/remove/add controls.
- Create `frontend/src/components/ComparePlaceSearch.jsx`: per-slot place search wrapper around the existing `SearchBar`.
- Create `frontend/src/components/CompareSummary.jsx`: summary strip from successful compare results.
- Create `frontend/src/components/CompareResultCard.jsx`: one column-card result with fit, scores, pros/cons, confidence, and source support.
- Modify `frontend/src/components/TopBar.jsx`: add a Compare button.
- Modify `frontend/src/App.jsx`: open and close compare mode while preserving the current single-place analysis result.
- Modify `frontend/src/styles.css`: compare workspace, slot row, summary strip, cards, mobile stacking.
- Modify `frontend/src/uiContract.test.js`: source-contract checks for compare entry point and no raw JSON output.
- Modify `README.md`: document Phase 2D compare mode after implementation.
- Modify `PLAN.md`: mark compare mode complete after implementation and keep future backend `POST /compare` deferred.

---

### Task 1: Add Pure Compare Helpers

**Files:**
- Create: `frontend/src/utils/compareUtils.js`
- Create: `frontend/src/utils/compareUtils.test.js`

- [ ] **Step 1: Write failing compare utility tests**

Create `frontend/src/utils/compareUtils.test.js`:

```javascript
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  MAX_COMPARE_SLOTS,
  MIN_COMPARE_SLOTS,
  buildCompareHighlights,
  buildComparePayload,
  canAddCompareSlot,
  canAnalyzeCompare,
  createCompareSlot,
  getSuccessfulCompareResults,
} from './compareUtils.js';

const PLACE = {
  label: 'East Austin, Austin, TX',
  coordinates: { lat: 30.2636, lng: -97.7114 },
};

const PROFILE = {
  id: 'profile-1',
  name: 'Transit walker',
  generic_mode: false,
};

function response(label, { fit = 70, walkability = 60, transit = 55, confidence = 'medium', missing = [] } = {}) {
  return {
    place: { label },
    fit: fit === null ? null : { score: fit, label: 'Good fit', explanation: `${label} explanation.`, flags: [] },
    profile: {
      vibe_scores: {
        walkability,
        transit_access: transit,
        affordability: 50,
        quiet: 50,
        social_scene: 50,
      },
      honest_pros: [`${label} pro.`],
      honest_cons: [`${label} con.`],
      provenance: { items: [] },
    },
    confidence: {
      level: confidence,
      missing_sources: missing,
      caveats: [],
    },
    source_statuses: [],
  };
}

describe('compare slot helpers', () => {
  it('creates empty compare slots with stable shape', () => {
    assert.deepEqual(createCompareSlot('slot-1'), {
      id: 'slot-1',
      place: null,
      status: 'idle',
      response: null,
      error: '',
    });
  });

  it('enforces the 2 to 4 slot range', () => {
    assert.equal(MIN_COMPARE_SLOTS, 2);
    assert.equal(MAX_COMPARE_SLOTS, 4);
    assert.equal(canAddCompareSlot([1, 2, 3]), true);
    assert.equal(canAddCompareSlot([1, 2, 3, 4]), false);
  });

  it('requires at least two selected places before analysis', () => {
    const slots = [
      { ...createCompareSlot('slot-1'), place: PLACE },
      createCompareSlot('slot-2'),
    ];

    assert.equal(canAnalyzeCompare(slots), false);
    assert.equal(canAnalyzeCompare(slots.map((slot) => (slot.id === 'slot-2' ? { ...slot, place: PLACE } : slot))), true);
  });
});

describe('buildComparePayload', () => {
  it('uses the current saved profile lens', () => {
    assert.deepEqual(buildComparePayload(PLACE, PROFILE), {
      query: 'East Austin, Austin, TX',
      coordinates: { lat: 30.2636, lng: -97.7114 },
      generic_mode: false,
      preference_profile_id: 'profile-1',
    });
  });

  it('uses generic mode when no saved profile is active', () => {
    assert.deepEqual(buildComparePayload(PLACE, null), {
      query: 'East Austin, Austin, TX',
      coordinates: { lat: 30.2636, lng: -97.7114 },
      preferences: {},
      generic_mode: true,
    });
  });
});

describe('compare result helpers', () => {
  it('returns only successful compare results', () => {
    const slots = [
      { ...createCompareSlot('slot-1'), status: 'success', response: response('East Austin') },
      { ...createCompareSlot('slot-2'), status: 'error', error: 'Analyze failed' },
      { ...createCompareSlot('slot-3'), status: 'success', response: response('Kensington Market') },
    ];

    assert.deepEqual(
      getSuccessfulCompareResults(slots).map((item) => item.response.place.label),
      ['East Austin', 'Kensington Market'],
    );
  });

  it('builds useful highlights from successful results', () => {
    const slots = [
      { ...createCompareSlot('slot-1'), status: 'success', response: response('East Austin', { fit: 82, walkability: 75, transit: 60, confidence: 'medium', missing: ['reddit'] }) },
      { ...createCompareSlot('slot-2'), status: 'success', response: response('Kensington Market', { fit: 74, walkability: 92, transit: 88, confidence: 'high', missing: [] }) },
      { ...createCompareSlot('slot-3'), status: 'success', response: response('Thin Data Place', { fit: 61, walkability: 50, transit: 42, confidence: 'low', missing: ['census', 'housing'] }) },
    ];

    assert.deepEqual(buildCompareHighlights(slots), [
      { id: 'best-fit', label: 'Best fit', placeLabel: 'East Austin', value: '82%' },
      { id: 'best-walkability', label: 'Best walkability', placeLabel: 'Kensington Market', value: '92' },
      { id: 'best-transit', label: 'Best transit', placeLabel: 'Kensington Market', value: '88' },
      { id: 'lowest-confidence-risk', label: 'Lowest data risk', placeLabel: 'Kensington Market', value: 'high confidence' },
    ]);
  });

  it('omits best fit in generic mode when no fit scores exist', () => {
    const slots = [
      { ...createCompareSlot('slot-1'), status: 'success', response: response('East Austin', { fit: null, walkability: 75, transit: 60 }) },
      { ...createCompareSlot('slot-2'), status: 'success', response: response('Kensington Market', { fit: null, walkability: 92, transit: 88 }) },
    ];

    assert.deepEqual(
      buildCompareHighlights(slots).map((highlight) => highlight.id),
      ['best-walkability', 'best-transit', 'lowest-confidence-risk'],
    );
  });
});
```

- [ ] **Step 2: Run utility tests and verify failure**

Run:

```powershell
node --test frontend/src/utils/compareUtils.test.js
```

Expected: fails because `frontend/src/utils/compareUtils.js` does not exist.

- [ ] **Step 3: Implement compare utilities**

Create `frontend/src/utils/compareUtils.js`:

```javascript
import { buildAnalyzePayload } from './preferenceProfiles.js';

export const MIN_COMPARE_SLOTS = 2;
export const MAX_COMPARE_SLOTS = 4;

const CONFIDENCE_RISK = {
  high: 0,
  medium: 1,
  low: 2,
  none: 3,
};

export function createCompareSlot(id) {
  return {
    id,
    place: null,
    status: 'idle',
    response: null,
    error: '',
  };
}

export function canAddCompareSlot(slots) {
  return slots.length < MAX_COMPARE_SLOTS;
}

export function canAnalyzeCompare(slots) {
  return slots.filter((slot) => Boolean(slot.place)).length >= MIN_COMPARE_SLOTS;
}

export function buildComparePayload(place, activeProfile) {
  return buildAnalyzePayload(place, activeProfile);
}

export function getSuccessfulCompareResults(slots) {
  return slots.filter((slot) => slot.status === 'success' && slot.response);
}

export function buildCompareHighlights(slots) {
  const successful = getSuccessfulCompareResults(slots);
  if (successful.length < MIN_COMPARE_SLOTS) return [];

  const highlights = [];
  const bestFit = bestBy(successful, (slot) => slot.response.fit?.score);
  if (bestFit) {
    highlights.push({
      id: 'best-fit',
      label: 'Best fit',
      placeLabel: bestFit.response.place.label,
      value: `${bestFit.response.fit.score}%`,
    });
  }

  const bestWalkability = bestBy(successful, (slot) => slot.response.profile?.vibe_scores?.walkability);
  if (bestWalkability) {
    highlights.push({
      id: 'best-walkability',
      label: 'Best walkability',
      placeLabel: bestWalkability.response.place.label,
      value: String(bestWalkability.response.profile.vibe_scores.walkability),
    });
  }

  const bestTransit = bestBy(successful, (slot) => slot.response.profile?.vibe_scores?.transit_access);
  if (bestTransit) {
    highlights.push({
      id: 'best-transit',
      label: 'Best transit',
      placeLabel: bestTransit.response.place.label,
      value: String(bestTransit.response.profile.vibe_scores.transit_access),
    });
  }

  const lowestRisk = [...successful].sort(compareConfidenceRisk)[0];
  if (lowestRisk) {
    highlights.push({
      id: 'lowest-confidence-risk',
      label: 'Lowest data risk',
      placeLabel: lowestRisk.response.place.label,
      value: `${lowestRisk.response.confidence?.level || 'unknown'} confidence`,
    });
  }

  return highlights;
}

function bestBy(slots, getValue) {
  return slots.reduce((best, slot) => {
    const value = getValue(slot);
    if (!Number.isFinite(value)) return best;
    if (!best) return slot;
    return value > getValue(best) ? slot : best;
  }, null);
}

function compareConfidenceRisk(left, right) {
  const leftLevel = left.response.confidence?.level || 'none';
  const rightLevel = right.response.confidence?.level || 'none';
  const levelDifference = (CONFIDENCE_RISK[leftLevel] ?? 3) - (CONFIDENCE_RISK[rightLevel] ?? 3);
  if (levelDifference !== 0) return levelDifference;
  return missingSourceCount(left) - missingSourceCount(right);
}

function missingSourceCount(slot) {
  return slot.response.confidence?.missing_sources?.length || 0;
}
```

- [ ] **Step 4: Run utility tests and verify pass**

Run:

```powershell
node --test frontend/src/utils/compareUtils.test.js
```

Expected: all compare utility tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add frontend/src/utils/compareUtils.js frontend/src/utils/compareUtils.test.js
git commit -m "Add compare mode utility helpers"
```

---

### Task 2: Extract Shared Analyze API Helper

**Files:**
- Create: `frontend/src/utils/api.js`
- Create: `frontend/src/utils/api.test.js`
- Modify: `frontend/src/hooks/useNeighborhood.js`

- [ ] **Step 1: Write failing API helper tests**

Create `frontend/src/utils/api.test.js`:

```javascript
import assert from 'node:assert/strict';
import { afterEach, describe, it } from 'node:test';
import { analyzeNeighborhood } from './api.js';

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe('analyzeNeighborhood', () => {
  it('posts analyze payloads to the backend and returns JSON', async () => {
    const requests = [];
    globalThis.fetch = async (url, options) => {
      requests.push({ url, options });
      return {
        ok: true,
        async json() {
          return { place: { label: 'East Austin' } };
        },
      };
    };

    const result = await analyzeNeighborhood({ query: 'East Austin', generic_mode: true });

    assert.deepEqual(result, { place: { label: 'East Austin' } });
    assert.equal(requests[0].url, 'http://127.0.0.1:8000/analyze');
    assert.equal(requests[0].options.method, 'POST');
    assert.equal(requests[0].options.headers['Content-Type'], 'application/json');
    assert.equal(requests[0].options.body, JSON.stringify({ query: 'East Austin', generic_mode: true }));
  });

  it('uses server detail messages for failed responses', async () => {
    globalThis.fetch = async () => ({
      ok: false,
      status: 422,
      async json() {
        return { detail: 'Provide either query or coordinates.' };
      },
    });

    await assert.rejects(
      () => analyzeNeighborhood({ preferences: {} }),
      /Provide either query or coordinates\./,
    );
  });
});
```

- [ ] **Step 2: Run API helper tests and verify failure**

Run:

```powershell
node --test frontend/src/utils/api.test.js
```

Expected: fails because `frontend/src/utils/api.js` does not exist.

- [ ] **Step 3: Implement shared API helper**

Create `frontend/src/utils/api.js`:

```javascript
export const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export async function analyzeNeighborhood(payload) {
  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseResponse(response, `Analyze failed with ${response.status}`);
}

export async function parseResponse(response, fallbackMessage) {
  if (response.ok) {
    return response.json();
  }

  let message = fallbackMessage;
  try {
    const body = await response.json();
    message = body.detail || body.message || message;
  } catch {
    // Keep the status-based fallback when the server did not return JSON.
  }
  throw new Error(message);
}
```

- [ ] **Step 4: Refactor `useNeighborhood` to use the shared helper**

In `frontend/src/hooks/useNeighborhood.js`, add:

```javascript
import { API_BASE_URL, analyzeNeighborhood, parseResponse } from '../utils/api.js';
```

Remove:

```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
```

Inside `analyze(payload)`, replace the manual fetch block:

```javascript
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const body = await parseResponse(response, `Analyze failed with ${response.status}`);
```

with:

```javascript
      const body = await analyzeNeighborhood(payload);
```

At the bottom of `useNeighborhood.js`, delete the local `parseResponse` function.

- [ ] **Step 5: Run API and existing profile utility tests**

Run:

```powershell
node --test frontend/src/utils/api.test.js
node --test frontend/src/utils/preferenceProfiles.test.js
```

Expected: both test files pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add frontend/src/utils/api.js frontend/src/utils/api.test.js frontend/src/hooks/useNeighborhood.js
git commit -m "Share frontend analyze API helper"
```

---

### Task 3: Add Compare Result Components

**Files:**
- Create: `frontend/src/components/CompareSummary.jsx`
- Create: `frontend/src/components/CompareResultCard.jsx`
- Modify: `frontend/src/uiContract.test.js`

- [ ] **Step 1: Add failing source-contract test for compare result components**

Append to `frontend/src/uiContract.test.js`:

```javascript
test('compare result components show summaries without raw payload output', () => {
  const summary = source('src/components/CompareSummary.jsx');
  const resultCard = source('src/components/CompareResultCard.jsx');

  assert.match(summary, /Compare highlights/);
  assert.match(summary, /buildCompareHighlights/);
  assert.match(resultCard, /CompareResultCard/);
  assert.match(resultCard, /<Confidence confidence=\{response\.confidence\} statuses=\{response\.source_statuses\} \/>/);
  assert.match(resultCard, /<Provenance provenance=\{response\.profile\?\.provenance\} \/>/);
  assert.equal(resultCard.includes('JSON.stringify'), false);
});
```

- [ ] **Step 2: Run UI contract test and verify failure**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: fails because `CompareSummary.jsx` and `CompareResultCard.jsx` do not exist.

- [ ] **Step 3: Create `CompareSummary.jsx`**

Create `frontend/src/components/CompareSummary.jsx`:

```jsx
import { buildCompareHighlights } from '../utils/compareUtils.js';

export default function CompareSummary({ slots }) {
  const highlights = buildCompareHighlights(slots);
  if (highlights.length === 0) return null;

  return (
    <section className="compare-summary" aria-label="Compare highlights">
      <div className="section-heading">
        <p className="eyebrow">Compare highlights</p>
        <h2>Standout signals</h2>
      </div>
      <div className="compare-summary-grid">
        {highlights.map((highlight) => (
          <article className="compare-highlight" key={highlight.id}>
            <span>{highlight.label}</span>
            <strong>{highlight.placeLabel}</strong>
            <small>{highlight.value}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Create `CompareResultCard.jsx`**

Create `frontend/src/components/CompareResultCard.jsx`:

```jsx
import Confidence from './Confidence.jsx';
import Provenance from './Provenance.jsx';

const SCORE_LABELS = [
  ['walkability', 'Walkability'],
  ['transit_access', 'Transit'],
  ['affordability', 'Affordability'],
  ['quiet', 'Quiet'],
  ['social_scene', 'Social'],
];

export default function CompareResultCard({ slot, onRetry }) {
  if (slot.status === 'loading') {
    return (
      <article className="compare-result-card compare-result-loading" aria-live="polite">
        <span className="eyebrow">{slot.place?.label || 'Selected place'}</span>
        <h3>Analyzing...</h3>
        <p>Checking available signals for this place.</p>
      </article>
    );
  }

  if (slot.status === 'error') {
    return (
      <article className="compare-result-card compare-result-error" role="alert">
        <span className="eyebrow">{slot.place?.label || 'Selected place'}</span>
        <h3>Analysis failed</h3>
        <p>{slot.error}</p>
        <button type="button" onClick={() => onRetry(slot.id)}>
          Retry
        </button>
      </article>
    );
  }

  const response = slot.response;
  if (!response) return null;
  const scores = response.profile?.vibe_scores || {};

  return (
    <article className="compare-result-card">
      <div className="compare-card-header">
        <span className="eyebrow">Compared place</span>
        <h3>{response.place.label}</h3>
      </div>
      {response.fit && (
        <div className="compare-fit">
          <strong>{response.fit.score}%</strong>
          <span>{response.fit.label}</span>
          <p>{response.fit.explanation}</p>
        </div>
      )}
      <div className="compare-score-list">
        {SCORE_LABELS.map(([key, label]) => (
          <div className="compare-score-row" key={key}>
            <span>{label}</span>
            <div>
              <i style={{ width: `${Math.max(0, Math.min(100, scores[key] || 0))}%` }}></i>
            </div>
            <strong>{scores[key] ?? '-'}</strong>
          </div>
        ))}
      </div>
      <div className="compare-pros-cons">
        <div>
          <h4>Pros</h4>
          <ul>{response.profile?.honest_pros?.slice(0, 2).map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
        <div>
          <h4>Cons</h4>
          <ul>{response.profile?.honest_cons?.slice(0, 2).map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
      <Confidence confidence={response.confidence} statuses={response.source_statuses} />
      <Provenance provenance={response.profile?.provenance} />
    </article>
  );
}
```

- [ ] **Step 5: Run UI contract test**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: UI contract tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add frontend/src/components/CompareSummary.jsx frontend/src/components/CompareResultCard.jsx frontend/src/uiContract.test.js
git commit -m "Add compare result components"
```

---

### Task 4: Add Compare Workspace

**Files:**
- Create: `frontend/src/components/CompareMode.jsx`
- Create: `frontend/src/components/ComparePlaceSearch.jsx`
- Modify: `frontend/src/uiContract.test.js`

- [ ] **Step 1: Add failing source-contract test for compare workspace**

Append to `frontend/src/uiContract.test.js`:

```javascript
test('compare workspace supports ad hoc 2 to 4 place analysis', () => {
  const compareMode = source('src/components/CompareMode.jsx');
  const compareSearch = source('src/components/ComparePlaceSearch.jsx');

  assert.match(compareMode, /Compare places/);
  assert.match(compareMode, /Analyze Compare/);
  assert.match(compareMode, /MAX_COMPARE_SLOTS/);
  assert.match(compareMode, /MIN_COMPARE_SLOTS/);
  assert.match(compareMode, /analyzeNeighborhood/);
  assert.match(compareMode, /Promise\.all/);
  assert.match(compareMode, /CompareResultCard/);
  assert.match(compareMode, /CompareSummary/);
  assert.match(compareSearch, /<SearchBar onSelect=\{onSelect\} \/>/);
});
```

- [ ] **Step 2: Run UI contract test and verify failure**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: fails because compare workspace files do not exist.

- [ ] **Step 3: Create `ComparePlaceSearch.jsx`**

Create `frontend/src/components/ComparePlaceSearch.jsx`:

```jsx
import SearchBar from './SearchBar.jsx';

export default function ComparePlaceSearch({ slot, canRemove, onRemove, onSelect }) {
  return (
    <article className={`compare-place-slot ${slot.place ? 'compare-place-selected' : ''}`}>
      <div className="compare-slot-topline">
        <span>{slot.place?.label || 'Add a place'}</span>
        {canRemove && (
          <button type="button" onClick={() => onRemove(slot.id)} aria-label={`Remove ${slot.place?.label || 'empty place slot'}`}>
            Remove
          </button>
        )}
      </div>
      <SearchBar onSelect={onSelect} />
    </article>
  );
}
```

- [ ] **Step 4: Create `CompareMode.jsx`**

Create `frontend/src/components/CompareMode.jsx`:

```jsx
import { useMemo, useState } from 'react';
import { analyzeNeighborhood } from '../utils/api.js';
import {
  MAX_COMPARE_SLOTS,
  MIN_COMPARE_SLOTS,
  buildComparePayload,
  canAddCompareSlot,
  canAnalyzeCompare,
  createCompareSlot,
} from '../utils/compareUtils.js';
import ComparePlaceSearch from './ComparePlaceSearch.jsx';
import CompareResultCard from './CompareResultCard.jsx';
import CompareSummary from './CompareSummary.jsx';

const INITIAL_SLOTS = [createCompareSlot('compare-1'), createCompareSlot('compare-2')];

export default function CompareMode({ activeProfile, onClose }) {
  const [slots, setSlots] = useState(INITIAL_SLOTS);
  const [nextSlotNumber, setNextSlotNumber] = useState(3);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);
  const selectedCount = slots.filter((slot) => slot.place).length;
  const isAnalyzing = slots.some((slot) => slot.status === 'loading');
  const ready = canAnalyzeCompare(slots) && !isAnalyzing;
  const lensLabel = activeProfile?.name || 'Generic neighborhood check';
  const successfulCount = slots.filter((slot) => slot.status === 'success').length;

  const helperText = useMemo(() => {
    if (selectedCount < MIN_COMPARE_SLOTS) return 'Add at least two places to compare.';
    if (isAnalyzing) return 'Checking each selected place independently.';
    if (hasAnalyzed && successfulCount < MIN_COMPARE_SLOTS) return 'At least two successful results are needed for highlights.';
    return 'Compare these places through the active lens.';
  }, [hasAnalyzed, isAnalyzing, selectedCount, successfulCount]);

  function updateSlot(slotId, patch) {
    setSlots((current) => current.map((slot) => (slot.id === slotId ? { ...slot, ...patch } : slot)));
  }

  function handleSelectPlace(slotId, place) {
    updateSlot(slotId, {
      place,
      status: 'idle',
      response: null,
      error: '',
    });
  }

  function handleAddSlot() {
    if (!canAddCompareSlot(slots)) return;
    setSlots((current) => [...current, createCompareSlot(`compare-${nextSlotNumber}`)]);
    setNextSlotNumber((current) => current + 1);
  }

  function handleRemoveSlot(slotId) {
    setSlots((current) => current.filter((slot) => slot.id !== slotId));
  }

  async function analyzeSlot(slot) {
    if (!slot.place) return null;
    updateSlot(slot.id, { status: 'loading', response: null, error: '' });
    try {
      const response = await analyzeNeighborhood(buildComparePayload(slot.place, activeProfile));
      updateSlot(slot.id, { status: 'success', response, error: '' });
      return response;
    } catch (err) {
      updateSlot(slot.id, {
        status: 'error',
        response: null,
        error: err instanceof Error ? err.message : 'Analyze failed',
      });
      return null;
    }
  }

  async function handleAnalyzeAll() {
    if (!ready) return;
    setHasAnalyzed(true);
    const selectedSlots = slots.filter((slot) => slot.place);
    await Promise.all(selectedSlots.map((slot) => analyzeSlot(slot)));
  }

  async function handleRetry(slotId) {
    const slot = slots.find((item) => item.id === slotId);
    if (slot) await analyzeSlot(slot);
  }

  return (
    <section className="compare-workspace" aria-label="Compare places">
      <header className="compare-header">
        <div>
          <p className="eyebrow">Compare mode</p>
          <h1>Compare places</h1>
          <p>{helperText}</p>
        </div>
        <div className="compare-header-actions">
          <span>{lensLabel}</span>
          <span>{selectedCount} of {MAX_COMPARE_SLOTS} places</span>
          <button type="button" className="primary-button" disabled={!ready} onClick={handleAnalyzeAll}>
            {hasAnalyzed ? 'Refresh Compare' : 'Analyze Compare'}
          </button>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </header>

      <div className="compare-place-slots">
        {slots.map((slot) => (
          <ComparePlaceSearch
            key={slot.id}
            slot={slot}
            canRemove={slots.length > MIN_COMPARE_SLOTS}
            onRemove={handleRemoveSlot}
            onSelect={(place) => handleSelectPlace(slot.id, place)}
          />
        ))}
        {canAddCompareSlot(slots) && (
          <button type="button" className="compare-add-slot" onClick={handleAddSlot}>
            Add place
          </button>
        )}
      </div>

      <CompareSummary slots={slots} />

      <div className="compare-results-grid">
        {slots.map((slot) => (
          <CompareResultCard key={slot.id} slot={slot} onRetry={handleRetry} />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Run compare utility and UI contract tests**

Run:

```powershell
node --test frontend/src/utils/compareUtils.test.js
node --test frontend/src/uiContract.test.js
```

Expected: tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add frontend/src/components/CompareMode.jsx frontend/src/components/ComparePlaceSearch.jsx frontend/src/uiContract.test.js
git commit -m "Add compare workspace"
```

---

### Task 5: Wire Compare Mode Into App Chrome

**Files:**
- Modify: `frontend/src/components/TopBar.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/uiContract.test.js`

- [ ] **Step 1: Add failing source-contract test for top-level compare entry**

Append to `frontend/src/uiContract.test.js`:

```javascript
test('app exposes top-level compare mode without replacing profile management', () => {
  const app = source('src/App.jsx');
  const topBar = source('src/components/TopBar.jsx');

  assert.match(topBar, /onCompareClick/);
  assert.match(topBar, /aria-label="Compare places"/);
  assert.match(topBar, />Compare</);
  assert.match(app, /import CompareMode from '\.\/components\/CompareMode\.jsx';/);
  assert.match(app, /activeWorkspace === 'compare'/);
  assert.match(app, /onCompareClick=\{\(\) => setActiveWorkspace\('compare'\)\}/);
  assert.match(app, /activeProfile=\{selectedPreferenceProfile\}/);
});
```

- [ ] **Step 2: Run UI contract test and verify failure**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: fails because App and TopBar do not expose compare mode yet.

- [ ] **Step 3: Update `TopBar.jsx`**

Modify imports in `frontend/src/components/TopBar.jsx`:

```jsx
import { Archive, Scale, UserRound } from 'lucide-react';
```

Add `onCompareClick` to props:

```jsx
export default function TopBar({
  activeProfile,
  preferenceProfileError,
  onProfileClick,
  onSavedReportsClick,
  onCompareClick,
  onSelectPlace,
}) {
```

Add this button before the saved reports button:

```jsx
      <button type="button" className="compare-top-button" onClick={onCompareClick} aria-label="Compare places">
        <Scale size={16} aria-hidden="true" />
        <span>Compare</span>
      </button>
```

- [ ] **Step 4: Update `App.jsx`**

Add import:

```jsx
import CompareMode from './components/CompareMode.jsx';
```

Pass compare click to `TopBar`:

```jsx
          onCompareClick={() => setActiveWorkspace('compare')}
```

Render compare mode beside the existing workspaces:

```jsx
        {activeWorkspace === 'compare' && (
          <CompareMode
            activeProfile={selectedPreferenceProfile}
            onClose={() => setActiveWorkspace(null)}
          />
        )}
```

Place this after `SavedProfiles` and before the analysis panel so compare mode overlays the map-first workflow while preserving the single-place result state.

- [ ] **Step 5: Run UI contract test**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: UI contract tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add frontend/src/components/TopBar.jsx frontend/src/App.jsx frontend/src/uiContract.test.js
git commit -m "Wire compare mode into app chrome"
```

---

### Task 6: Style Compare Mode

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/uiContract.test.js`

- [ ] **Step 1: Add failing source-contract test for compare styling**

Append to `frontend/src/uiContract.test.js`:

```javascript
test('compare mode has viewport-safe responsive styling', () => {
  const css = source('src/styles.css');

  assert.match(css, /\.compare-workspace\s*{[^}]*position:\s*absolute/s);
  assert.match(css, /\.compare-workspace\s*{[^}]*max-height:\s*calc\(100vh - 112px\)/s);
  assert.match(css, /\.compare-results-grid\s*{[^}]*grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(260px,\s*1fr\)\)/s);
  assert.match(css, /\.compare-place-slots\s*{[^}]*grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(220px,\s*1fr\)\)/s);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.compare-workspace\s*{[^}]*inset:\s*92px 12px 16px/s);
});
```

- [ ] **Step 2: Run UI contract test and verify failure**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: fails because compare styles do not exist.

- [ ] **Step 3: Add compare CSS**

Append before the existing mobile media query in `frontend/src/styles.css`:

```css
.compare-top-button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  border: 1px solid var(--vc-border);
  border-radius: 6px;
  background: #ffffff;
  color: var(--vc-ink);
  font-weight: 800;
  padding: 0 12px;
}

.compare-workspace {
  position: absolute;
  inset: 88px 24px 24px;
  z-index: var(--layer-workspace);
  display: grid;
  grid-template-rows: auto auto auto 1fr;
  gap: 14px;
  max-height: calc(100vh - 112px);
  overflow-y: auto;
  border: 1px solid var(--vc-border);
  border-radius: 12px;
  background: rgba(248, 250, 247, 0.97);
  box-shadow: 0 24px 70px rgba(25, 39, 32, 0.22);
  padding: 16px;
}

.compare-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.compare-header h1,
.compare-card-header h3 {
  margin: 0;
}

.compare-header p {
  margin: 4px 0 0;
  color: var(--vc-muted);
}

.compare-header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.compare-header-actions span {
  border-radius: 999px;
  background: var(--vc-blue-soft);
  color: var(--vc-blue);
  font-size: 0.78rem;
  font-weight: 800;
  padding: 6px 10px;
}

.compare-place-slots {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.compare-place-slot,
.compare-add-slot,
.compare-summary,
.compare-result-card {
  border: 1px solid var(--vc-border);
  border-radius: 10px;
  background: #ffffff;
}

.compare-place-slot {
  display: grid;
  gap: 10px;
  padding: 12px;
}

.compare-place-selected {
  border-color: rgba(46, 111, 84, 0.35);
}

.compare-slot-topline {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  font-weight: 800;
}

.compare-slot-topline button,
.compare-header-actions button:not(.primary-button),
.compare-result-error button {
  min-height: 34px;
  border: 1px solid var(--vc-border);
  border-radius: 6px;
  background: #ffffff;
  padding: 0 10px;
}

.compare-add-slot {
  min-height: 106px;
  border-style: dashed;
  color: var(--vc-blue);
  font-weight: 900;
}

.compare-summary {
  display: grid;
  gap: 10px;
  padding: 12px;
}

.compare-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px;
}

.compare-highlight {
  display: grid;
  gap: 3px;
  border-radius: 8px;
  background: #f4f8f6;
  padding: 10px;
}

.compare-highlight span,
.compare-highlight small {
  color: var(--vc-muted);
  font-size: 0.76rem;
  font-weight: 800;
}

.compare-highlight strong {
  color: var(--vc-ink);
}

.compare-results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.compare-result-card {
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 14px;
}

.compare-result-loading,
.compare-result-error {
  min-height: 180px;
}

.compare-result-error {
  background: #fff7f4;
  color: #5c2e27;
}

.compare-fit {
  display: grid;
  gap: 4px;
  border-radius: 10px;
  background: var(--vc-blue-soft);
  padding: 12px;
}

.compare-fit strong {
  color: var(--vc-blue);
  font-size: 2rem;
  line-height: 1;
}

.compare-fit p {
  margin: 0;
  color: var(--vc-muted);
  line-height: 1.4;
}

.compare-score-list {
  display: grid;
  gap: 8px;
}

.compare-score-row {
  display: grid;
  grid-template-columns: 86px 1fr 34px;
  gap: 8px;
  align-items: center;
  font-size: 0.82rem;
}

.compare-score-row div {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #e6ece8;
}

.compare-score-row i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--vc-blue);
}

.compare-pros-cons {
  display: grid;
  gap: 10px;
}

.compare-pros-cons h4 {
  margin: 0 0 6px;
}

.compare-pros-cons ul {
  margin: 0;
  padding-left: 18px;
  color: var(--vc-muted);
}
```

Inside the existing `@media (max-width: 760px)` block, add:

```css
  .compare-workspace {
    inset: 92px 12px 16px;
    max-height: calc(100vh - 108px);
    padding: 12px;
  }

  .compare-header {
    display: grid;
  }

  .compare-header-actions {
    justify-content: stretch;
  }

  .compare-header-actions .primary-button,
  .compare-header-actions button {
    flex: 1 1 140px;
  }
```

- [ ] **Step 4: Run UI contract test**

Run:

```powershell
node --test frontend/src/uiContract.test.js
```

Expected: UI contract tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add frontend/src/styles.css frontend/src/uiContract.test.js
git commit -m "Style compare mode workspace"
```

---

### Task 7: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`

- [ ] **Step 1: Update README current scope**

In `README.md`, add this bullet under Current Scope:

```markdown
- Dedicated compare mode for 2-4 ad hoc places using the active preference profile or Generic lens.
```

Update the Phase 2 Status paragraph to:

```markdown
Phase 2A added explicit local saved neighborhood reports. Phase 2B added reusable local preference profiles and then corrected the UI so profiles work as an app-level analysis lens selected before address search. Phase 2C adds typed provenance and compact source-support UI so major claims can be traced to normalized source signals. Phase 2D adds a dedicated compare mode for 2-4 ad hoc places using the active preference profile or Generic lens. The next Phase 2 slices should focus on source freshness, deeper city-specific adapters, and optional share/export flows.
```

- [ ] **Step 2: Update PLAN Phase 2 checklist**

In `PLAN.md`, change:

```markdown
- [ ] Add compare mode for two or more places.
```

to:

```markdown
- [x] Add compare mode for two to four ad hoc places.
```

Change:

```markdown
- [ ] Add provenance metadata to major generated claims.
```

to:

```markdown
- [x] Add provenance metadata to major generated claims.
```

Change:

```markdown
- [ ] Add regression tests for cache freshness, compare response shape, and provenance display.
```

to:

```markdown
- [ ] Add regression tests for cache freshness and future backend compare response shape.
```

- [ ] **Step 3: Run full frontend verification**

Run:

```powershell
node --test frontend/src/utils/api.test.js
node --test frontend/src/utils/compareUtils.test.js
node --test frontend/src/utils/preferenceProfiles.test.js
node --test frontend/src/uiContract.test.js
Push-Location frontend
npm.cmd run build
Pop-Location
```

Expected: Node tests pass and Vite build succeeds. The existing large Mapbox chunk warning is acceptable.

- [ ] **Step 4: Run backend regression verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check backend tests
```

Expected: backend tests pass and ruff is clean.

- [ ] **Step 5: Manual smoke checklist**

Start or reuse local servers and verify:

- Compare button appears in the top rail.
- Compare opens without clearing the active single-place result.
- Two places can be selected and analyzed with a saved preference profile.
- Three or four places can be selected and analyzed.
- A fifth slot cannot be added.
- Generic mode compare omits best-fit summary when no fit scores exist.
- A failed place can be retried without losing successful place cards.
- Closing compare returns to the map-first workflow with the previous single-place result still visible.
- Mobile viewport stacks compare cards and keeps controls reachable.

- [ ] **Step 6: Commit docs**

Run:

```powershell
git add README.md PLAN.md
git commit -m "Document compare mode"
```

- [ ] **Step 7: Check final status**

Run:

```powershell
git status --short --branch
```

Expected: no staged changes. Untracked `.tmp/` may remain only if it contains local screenshots/logs and is not staged.
