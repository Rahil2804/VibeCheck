# Phase 1B Map-First Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1B AI layer and a Mapbox-first React frontend where autocomplete selection flies the 3D map to a place and reveals the questionnaire/profile experience.

**Architecture:** Keep `POST /analyze` as the single frontend-facing backend endpoint. Add an optional OpenAI synthesizer that returns validated `NeighborhoodProfile` objects and gracefully falls back to the deterministic Phase 1A profile. Add a Vite React app in `frontend/` with a full-screen map shell, search overlay, responsive analysis panel, and source-aware profile rendering.

**Tech Stack:** FastAPI, Pydantic, OpenAI Python SDK, pytest, ruff, React, Vite, Mapbox GL JS, Mapbox Search/geocoding, plain CSS.

---

## File Structure

Backend files:

- Create `backend/synthesizer.py`: owns OpenAI Structured Output profile generation and prompt construction.
- Modify `backend/pipeline.py`: calls synthesizer after source normalization and falls back to `_build_profile`.
- Modify `backend/main.py`: add CORS middleware for local Vite frontend.
- Modify `.env.example`: add `VITE_MAPBOX_TOKEN` and `VITE_API_BASE_URL`.
- Create `tests/test_synthesizer.py`: unit tests for no-key, malformed output, and parsed output behavior.
- Modify `tests/test_pipeline.py`: tests synthesizer failure fallback and successful synthesized profile integration.
- Modify `requirements.txt` only if CORS or existing SDK usage requires an additional package. FastAPI already includes Starlette CORS support.

Frontend files:

- Create `frontend/package.json`: scripts and dependencies.
- Create `frontend/index.html`: Vite root document.
- Create `frontend/vite.config.js`: React plugin config.
- Create `frontend/src/main.jsx`: React entrypoint.
- Create `frontend/src/App.jsx`: app state and map-first layout.
- Create `frontend/src/components/SearchBar.jsx`: Mapbox autocomplete and selection behavior.
- Create `frontend/src/components/MapView.jsx`: Mapbox 3D map, fly-to, marker, radius.
- Create `frontend/src/components/Questionnaire.jsx`: neutral preference form and generic mode.
- Create `frontend/src/components/Profile.jsx`: profile shell.
- Create `frontend/src/components/ScoreCards.jsx`: score cards.
- Create `frontend/src/components/Confidence.jsx`: confidence and sources panel.
- Create `frontend/src/hooks/useNeighborhood.js`: `POST /analyze`, loading, error, retry state.
- Create `frontend/src/styles.css`: responsive map-first app styling.
- Create `frontend/src/utils/mapbox.js`: Mapbox token and search helpers.
- Modify `README.md`: add full-stack setup and run commands.

Implementation will happen directly on `main` per user request. Keep commits small and verify before each push.

---

### Task 1: Backend Synthesizer Contract

**Files:**
- Create: `backend/synthesizer.py`
- Create: `tests/test_synthesizer.py`

- [ ] **Step 1: Write failing tests for synthesizer fallback and parsing**

Create `tests/test_synthesizer.py` with:

```python
import pytest
from pydantic import ValidationError

from backend.models import NeighborhoodProfile
from backend.synthesizer import SynthesizerUnavailable, parse_profile_payload, synthesize_profile


@pytest.mark.asyncio
async def test_synthesize_profile_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = await synthesize_profile(
        place_label="East Austin",
        source_data={"access": {"walkability": 82}},
        caveats=["Reddit unavailable."],
    )

    assert result is None


def test_parse_profile_payload_accepts_schema_valid_profile():
    profile = parse_profile_payload(
        {
            "overview": "Walkable, mixed-signal area with some uncertainty.",
            "vibe_scores": {
                "walkability": 82,
                "transit_access": 68,
                "affordability": 42,
                "quiet": 55,
                "social_scene": 78,
            },
            "who_lives_here": {
                "median_age": 31,
                "median_household_income": 58000,
                "population_density": 5200,
                "population_trend": "growing",
            },
            "honest_pros": ["Errands appear accessible."],
            "honest_cons": ["Affordability signals are mixed."],
            "trajectory": {
                "direction": "uncertain",
                "summary": "Trajectory is uncertain from current MVP sources.",
            },
        }
    )

    assert isinstance(profile, NeighborhoodProfile)
    assert profile.vibe_scores.walkability == 82


def test_parse_profile_payload_rejects_malformed_profile():
    with pytest.raises(ValidationError):
        parse_profile_payload({"overview": "Missing required fields."})


@pytest.mark.asyncio
async def test_synthesize_profile_converts_client_error_to_unavailable(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class FailingClient:
        class responses:
            @staticmethod
            async def parse(**_kwargs):
                raise RuntimeError("model unavailable")

    with pytest.raises(SynthesizerUnavailable):
        await synthesize_profile(
            place_label="East Austin",
            source_data={"access": {"walkability": 82}},
            caveats=[],
            client=FailingClient(),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_synthesizer.py -p no:cacheprovider
```

Expected: fail because `backend.synthesizer` does not exist.

- [ ] **Step 3: Implement minimal synthesizer**

Create `backend/synthesizer.py`:

```python
import os
from typing import Any

from openai import AsyncOpenAI

from backend.models import NeighborhoodProfile


class SynthesizerUnavailable(RuntimeError):
    """Raised when OpenAI synthesis was requested but could not produce a profile."""


SYSTEM_PROMPT = """You create honest neighborhood profiles from supplied source data only.
Use only the supplied normalized data.
Mark uncertainty clearly.
Do not make unsupported safety or crime claims.
Do not recommend based on protected classes or protected-class proxies.
Return a schema-valid NeighborhoodProfile."""


def parse_profile_payload(payload: dict[str, Any]) -> NeighborhoodProfile:
    return NeighborhoodProfile.model_validate(payload)


async def synthesize_profile(
    place_label: str,
    source_data: dict[str, Any],
    caveats: list[str],
    client: AsyncOpenAI | Any | None = None,
) -> NeighborhoodProfile | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None

    openai_client = client or AsyncOpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        response = await openai_client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Place: {place_label}\n"
                        f"Source data: {source_data}\n"
                        f"Caveats: {caveats}"
                    ),
                },
            ],
            text_format=NeighborhoodProfile,
        )
    except Exception as exc:
        raise SynthesizerUnavailable(str(exc)) from exc

    parsed = getattr(response, "output_parsed", None)
    if isinstance(parsed, NeighborhoodProfile):
        return parsed
    if isinstance(parsed, dict):
        return parse_profile_payload(parsed)
    raise SynthesizerUnavailable("OpenAI response did not include a parsed NeighborhoodProfile.")
```

- [ ] **Step 4: Run synthesizer tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_synthesizer.py -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 5: Commit backend synthesizer contract**

Run:

```powershell
git add backend/synthesizer.py tests/test_synthesizer.py
git commit -m "Add backend profile synthesizer"
```

---

### Task 2: Pipeline Synthesis Integration And CORS

**Files:**
- Modify: `backend/pipeline.py`
- Modify: `backend/main.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write failing pipeline tests for synthesis fallback and success**

Append to `tests/test_pipeline.py`:

```python
from backend.models import NeighborhoodProfile, Trajectory, TrajectoryDirection, VibeScores, WhoLivesHere


def _synthetic_profile() -> NeighborhoodProfile:
    return NeighborhoodProfile(
        overview="Synthesized overview from source data.",
        vibe_scores=VibeScores(
            walkability=80,
            transit_access=75,
            affordability=45,
            quiet=55,
            social_scene=70,
        ),
        who_lives_here=WhoLivesHere(),
        honest_pros=["Synthesized pro."],
        honest_cons=["Synthesized caveat."],
        trajectory=Trajectory(
            direction=TrajectoryDirection.UNCERTAIN,
            summary="Synthesized trajectory.",
        ),
    )


@pytest.mark.asyncio
async def test_pipeline_uses_synthesized_profile_when_available():
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

    assert response.profile.overview == "Synthesized overview from source data."
    assert response.fit is not None
    assert response.fit.score > 50


@pytest.mark.asyncio
async def test_pipeline_falls_back_when_synthesizer_fails():
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

    assert "currently available source signals" in response.profile.overview
```

- [ ] **Step 2: Add CORS test**

Append to `tests/test_main.py`:

```python
def test_cors_allows_local_vite_origin():
    client = TestClient(app)

    response = client.options(
        "/analyze",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_main.py -p no:cacheprovider
```

Expected: fail because `analyze_neighborhood` does not accept `profile_synthesizer` and CORS is not configured.

- [ ] **Step 4: Modify `backend/pipeline.py`**

Add imports:

```python
from backend.synthesizer import synthesize_profile
```

Add type alias near `SourceFetcher`:

```python
ProfileSynthesizer = Callable[..., Awaitable[NeighborhoodProfile | None]]
```

Change `analyze_neighborhood` signature:

```python
async def analyze_neighborhood(
    request: AnalyzeRequest,
    source_fetchers: dict[SourceName, SourceFetcher] | None = None,
    source_timeout_seconds: float | None = None,
    profile_synthesizer: ProfileSynthesizer | None = None,
) -> AnalyzeResponse:
```

Replace profile creation with:

```python
    source_data = {source: data for (status, data), source in zip(source_results, fetchers, strict=True)}
    fallback_profile = _build_profile(place, source_data)
    synthesizer = profile_synthesizer or synthesize_profile
    try:
        profile = await synthesizer(
            place_label=place.label,
            source_data={source.value: data for source, data in source_data.items()},
            caveats=build_confidence(statuses).caveats,
        )
    except Exception:
        profile = None
    if profile is None:
        profile = fallback_profile
    confidence = build_confidence(statuses)
    fit = None if request.generic_mode else score_fit(profile, request.preferences)
```

Then return `confidence=confidence`.

- [ ] **Step 5: Modify `backend/main.py` for CORS**

Add:

```python
from fastapi.middleware.cors import CORSMiddleware
```

After app creation:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
```

- [ ] **Step 6: Run backend integration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_main.py -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit pipeline integration**

Run:

```powershell
git add backend/pipeline.py backend/main.py tests/test_pipeline.py tests/test_main.py
git commit -m "Wire optional profile synthesis into analyze pipeline"
```

---

### Task 3: Frontend Scaffold And Configuration

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.js`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/hooks/useNeighborhood.js`
- Modify: `.env.example`

- [ ] **Step 1: Create Vite package files**

Create `frontend/package.json`:

```json
{
  "name": "vibecheck-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "vite build",
    "preview": "vite preview --host 127.0.0.1"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^7.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "mapbox-gl": "^3.8.0",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {}
}
```

Create `frontend/index.html`:

```html
<div id="root"></div>
<script type="module" src="/src/main.jsx"></script>
```

Create `frontend/vite.config.js`:

```javascript
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
```

- [ ] **Step 2: Create frontend entry and temporary app shell**

Create `frontend/src/main.jsx`:

```jsx
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

Create `frontend/src/App.jsx`:

```jsx
export default function App() {
  return (
    <main className="app-shell">
      <section className="map-stage">
        <div className="setup-panel">
          <p className="eyebrow">VibeCheck</p>
          <h1>Find the neighborhood fit behind an address.</h1>
          <p>Select a Mapbox result to reveal the profile workflow.</p>
        </div>
      </section>
    </main>
  );
}
```

Create `frontend/src/styles.css` with:

```css
:root {
  color: #17211b;
  background: #e9eef0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

button,
input,
select {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
  overflow: hidden;
}

.map-stage {
  min-height: 100vh;
  position: relative;
  background: #d8e4df;
}

.setup-panel {
  position: absolute;
  left: 24px;
  top: 24px;
  width: min(420px, calc(100vw - 48px));
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(25, 39, 32, 0.14);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 18px 50px rgba(23, 33, 27, 0.16);
}

.eyebrow {
  margin: 0 0 8px;
  color: #3d6757;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}
```

- [ ] **Step 3: Add frontend env vars**

Append to `.env.example`:

```bash
VITE_MAPBOX_TOKEN=
VITE_API_BASE_URL=http://127.0.0.1:8000
```

- [ ] **Step 4: Install frontend dependencies**

Run:

```powershell
Set-Location frontend
npm install
```

Expected: `node_modules/` and `package-lock.json` created. `node_modules/` should remain ignored by the existing `.gitignore` if present; if not, add `node_modules/` to `.gitignore`.

- [ ] **Step 5: Build scaffold**

Run:

```powershell
npm run build
```

Expected: Vite build succeeds and creates `frontend/dist/`.

- [ ] **Step 6: Commit scaffold**

Run from repo root:

```powershell
git add .env.example frontend/package.json frontend/package-lock.json frontend/index.html frontend/vite.config.js frontend/src
git commit -m "Scaffold map-first React frontend"
```

---

### Task 4: Analyze Hook And Questionnaire

**Files:**
- Create: `frontend/src/hooks/useNeighborhood.js`
- Create: `frontend/src/components/Questionnaire.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Implement analyze hook**

Create `frontend/src/hooks/useNeighborhood.js`:

```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export function useNeighborhood() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [lastRequest, setLastRequest] = useState(null);

  async function analyze(payload) {
    setLoading(true);
    setError('');
    setLastRequest(payload);
    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`Analyze failed with ${response.status}`);
      }
      const body = await response.json();
      setData(body);
      return body;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analyze failed');
      return null;
    } finally {
      setLoading(false);
    }
  }

  function retry() {
    if (!lastRequest) return Promise.resolve(null);
    return analyze(lastRequest);
  }

  return { analyze, retry, data, error, loading };
}
```

Then add the missing import at the top:

```javascript
import { useState } from 'react';
```

- [ ] **Step 2: Implement questionnaire**

Create `frontend/src/components/Questionnaire.jsx`:

```jsx
const OPTIONS = {
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

export default function Questionnaire({ preferences, genericMode, onChange, onGenericModeChange, onAnalyze, disabled }) {
  function update(field, value) {
    onChange({ ...preferences, [field]: value });
  }

  return (
    <section className="panel-section">
      <div className="section-heading">
        <p className="eyebrow">Preferences</p>
        <h2>Lifestyle fit</h2>
      </div>
      <label className="generic-toggle">
        <input
          type="checkbox"
          checked={genericMode}
          onChange={(event) => onGenericModeChange(event.target.checked)}
        />
        Skip preferences and run a generic profile
      </label>
      {!genericMode &&
        Object.entries(OPTIONS).map(([field, options]) => (
          <label className="field" key={field}>
            <span>{field.replaceAll('_', ' ')}</span>
            <select value={preferences[field] || ''} onChange={(event) => update(field, event.target.value)}>
              <option value="">No preference</option>
              {options.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        ))}
      <button className="primary-button" type="button" disabled={disabled} onClick={onAnalyze}>
        Analyze fit
      </button>
    </section>
  );
}
```

- [ ] **Step 3: Wire temporary selected-place flow in `App.jsx`**

Replace `frontend/src/App.jsx` with:

```jsx
import { useMemo, useState } from 'react';
import Questionnaire from './components/Questionnaire.jsx';
import { useNeighborhood } from './hooks/useNeighborhood.js';

const DEMO_PLACE = {
  label: 'East Austin, Austin, TX',
  coordinates: { lat: 30.2636, lng: -97.7114 },
};

export default function App() {
  const [selectedPlace, setSelectedPlace] = useState(DEMO_PLACE);
  const [preferences, setPreferences] = useState({});
  const [genericMode, setGenericMode] = useState(false);
  const { analyze, data, error, loading, retry } = useNeighborhood();

  const analyzePayload = useMemo(
    () => ({
      query: selectedPlace.label,
      coordinates: selectedPlace.coordinates,
      preferences,
      generic_mode: genericMode,
    }),
    [genericMode, preferences, selectedPlace],
  );

  return (
    <main className="app-shell">
      <section className="map-stage">
        <div className="setup-panel">
          <p className="eyebrow">VibeCheck</p>
          <h1>{selectedPlace.label}</h1>
          <p>Mapbox search lands here in the next task. This temporary place keeps the analyze flow testable.</p>
          <button type="button" onClick={() => setSelectedPlace(DEMO_PLACE)}>Use demo place</button>
        </div>
        <aside className="analysis-panel">
          <Questionnaire
            preferences={preferences}
            genericMode={genericMode}
            onChange={setPreferences}
            onGenericModeChange={setGenericMode}
            onAnalyze={() => analyze(analyzePayload)}
            disabled={loading}
          />
          {loading && <p className="status-line">Checking source availability...</p>}
          {error && (
            <div className="panel-error">
              <p>{error}</p>
              <button type="button" onClick={retry}>Retry</button>
            </div>
          )}
          {data && <pre className="debug-response">{JSON.stringify(data.profile, null, 2)}</pre>}
        </aside>
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Add panel/form CSS**

Append to `frontend/src/styles.css`:

```css
.analysis-panel {
  position: absolute;
  right: 24px;
  top: 24px;
  bottom: 24px;
  width: min(430px, calc(100vw - 48px));
  overflow: auto;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(25, 39, 32, 0.14);
  border-radius: 8px;
  padding: 18px;
  box-shadow: 0 18px 50px rgba(23, 33, 27, 0.16);
}

.panel-section {
  display: grid;
  gap: 14px;
}

.section-heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.field {
  display: grid;
  gap: 6px;
  font-size: 0.9rem;
  text-transform: capitalize;
}

.field select,
.primary-button,
.setup-panel button,
.panel-error button {
  min-height: 40px;
  border-radius: 6px;
  border: 1px solid rgba(25, 39, 32, 0.18);
  padding: 0 12px;
}

.primary-button {
  background: #214d3f;
  color: white;
  font-weight: 700;
}

.generic-toggle {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 0.92rem;
}

.status-line,
.panel-error,
.debug-response {
  margin-top: 16px;
}

.debug-response {
  white-space: pre-wrap;
  font-size: 0.78rem;
}

@media (max-width: 760px) {
  .setup-panel {
    left: 12px;
    right: 12px;
    top: 12px;
    width: auto;
  }

  .analysis-panel {
    left: 0;
    right: 0;
    top: auto;
    bottom: 0;
    width: auto;
    max-height: 62vh;
    border-radius: 8px 8px 0 0;
  }
}
```

- [ ] **Step 5: Build frontend**

Run:

```powershell
Set-Location frontend
npm run build
```

Expected: build passes.

- [ ] **Step 6: Commit hook/questionnaire**

Run from repo root:

```powershell
git add frontend/src/App.jsx frontend/src/components/Questionnaire.jsx frontend/src/hooks/useNeighborhood.js frontend/src/styles.css
git commit -m "Add analyze flow and lifestyle questionnaire"
```

---

### Task 5: Mapbox Search And 3D Map

**Files:**
- Create: `frontend/src/utils/mapbox.js`
- Create: `frontend/src/components/SearchBar.jsx`
- Create: `frontend/src/components/MapView.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Create Mapbox helpers**

Create `frontend/src/utils/mapbox.js`:

```javascript
export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || '';

export async function searchPlaces(query) {
  if (!MAPBOX_TOKEN || query.trim().length < 3) return [];
  const params = new URLSearchParams({
    q: query,
    country: 'us',
    limit: '5',
    access_token: MAPBOX_TOKEN,
  });
  const response = await fetch(`https://api.mapbox.com/search/geocode/v6/forward?${params}`);
  if (!response.ok) throw new Error('Mapbox search failed');
  const body = await response.json();
  return (body.features || []).map((feature) => ({
    id: feature.properties?.mapbox_id || feature.id,
    label: feature.properties?.full_address || feature.properties?.name || 'Selected place',
    coordinates: {
      lng: feature.geometry.coordinates[0],
      lat: feature.geometry.coordinates[1],
    },
  }));
}
```

- [ ] **Step 2: Create `SearchBar.jsx`**

Create `frontend/src/components/SearchBar.jsx`:

```jsx
import { Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { MAPBOX_TOKEN, searchPlaces } from '../utils/mapbox.js';

export default function SearchBar({ onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;
    const timeout = setTimeout(async () => {
      if (!query.trim()) {
        setResults([]);
        return;
      }
      try {
        setError('');
        const nextResults = await searchPlaces(query);
        if (!ignore) setResults(nextResults);
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : 'Search failed');
      }
    }, 250);
    return () => {
      ignore = true;
      clearTimeout(timeout);
    };
  }, [query]);

  return (
    <div className="search-card">
      <label className="search-input-wrap">
        <Search size={18} aria-hidden="true" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={MAPBOX_TOKEN ? 'Search a US address or place' : 'Add VITE_MAPBOX_TOKEN to enable search'}
          disabled={!MAPBOX_TOKEN}
        />
      </label>
      {error && <p className="search-error">{error}</p>}
      {results.length > 0 && (
        <div className="search-results">
          {results.map((result) => (
            <button
              key={result.id}
              type="button"
              onClick={() => {
                setQuery(result.label);
                setResults([]);
                onSelect(result);
              }}
            >
              {result.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `MapView.jsx`**

Create `frontend/src/components/MapView.jsx`:

```jsx
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { useEffect, useRef } from 'react';
import { MAPBOX_TOKEN } from '../utils/mapbox.js';

const DEFAULT_CENTER = [-98.5795, 39.8283];
const RADIUS_MILES = 0.5;

export default function MapView({ selectedPlace }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);

  useEffect(() => {
    if (!MAPBOX_TOKEN || !containerRef.current || mapRef.current) return;
    mapboxgl.accessToken = MAPBOX_TOKEN;
    mapRef.current = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/standard',
      center: DEFAULT_CENTER,
      zoom: 3.2,
      pitch: 62,
      bearing: -18,
      projection: 'globe',
    });
    mapRef.current.addControl(new mapboxgl.NavigationControl({ visualizePitch: true }), 'bottom-right');
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedPlace?.coordinates) return;
    const center = [selectedPlace.coordinates.lng, selectedPlace.coordinates.lat];
    map.flyTo({ center, zoom: 14.2, pitch: 68, bearing: -24, duration: 1500, essential: true });
    markerRef.current?.remove();
    markerRef.current = new mapboxgl.Marker({ color: '#214d3f' }).setLngLat(center).addTo(map);

    function drawRadius() {
      const radius = circlePolygon(center, RADIUS_MILES, 96);
      const source = map.getSource('selected-radius');
      if (source) {
        source.setData(radius);
      } else {
        map.addSource('selected-radius', { type: 'geojson', data: radius });
        map.addLayer({
          id: 'selected-radius-fill',
          type: 'fill',
          source: 'selected-radius',
          paint: { 'fill-color': '#2f6b55', 'fill-opacity': 0.16 },
        });
        map.addLayer({
          id: 'selected-radius-line',
          type: 'line',
          source: 'selected-radius',
          paint: { 'line-color': '#214d3f', 'line-width': 2 },
        });
      }
    }

    if (map.isStyleLoaded()) drawRadius();
    else map.once('load', drawRadius);
  }, [selectedPlace]);

  if (!MAPBOX_TOKEN) {
    return <div className="map-token-state">Add VITE_MAPBOX_TOKEN to render the 3D map.</div>;
  }

  return <div className="map-view" ref={containerRef} />;
}

function circlePolygon(center, radiusMiles, points) {
  const [lng, lat] = center;
  const radiusKm = radiusMiles * 1.60934;
  const coordinates = [];
  for (let i = 0; i <= points; i += 1) {
    const angle = (i / points) * 2 * Math.PI;
    const dx = radiusKm * Math.cos(angle);
    const dy = radiusKm * Math.sin(angle);
    coordinates.push([lng + dx / (111.32 * Math.cos((lat * Math.PI) / 180)), lat + dy / 110.574]);
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [coordinates] }, properties: {} };
}
```

- [ ] **Step 4: Wire map/search in `App.jsx`**

Update imports:

```jsx
import MapView from './components/MapView.jsx';
import SearchBar from './components/SearchBar.jsx';
```

Change initial selected state:

```javascript
const [selectedPlace, setSelectedPlace] = useState(null);
```

Inside `.map-stage`, render:

```jsx
<MapView selectedPlace={selectedPlace} />
<div className="top-overlay">
  <p className="eyebrow">VibeCheck</p>
  <SearchBar onSelect={setSelectedPlace} />
  {!selectedPlace && <p className="hint-line">Select an autocomplete result to fly to the neighborhood.</p>}
</div>
{selectedPlace && (
  <aside className="analysis-panel">
    ...
  </aside>
)}
```

Ensure `analyzePayload` handles `selectedPlace`:

```javascript
const analyzePayload = useMemo(
  () =>
    selectedPlace
      ? {
          query: selectedPlace.label,
          coordinates: selectedPlace.coordinates,
          preferences,
          generic_mode: genericMode,
        }
      : null,
  [genericMode, preferences, selectedPlace],
);
```

Update analyze click:

```jsx
onAnalyze={() => analyzePayload && analyze(analyzePayload)}
```

- [ ] **Step 5: Add map/search CSS**

Append to `frontend/src/styles.css`:

```css
.map-view,
.map-token-state {
  position: absolute;
  inset: 0;
}

.map-token-state {
  display: grid;
  place-items: center;
  padding: 24px;
  background: #d8e4df;
  color: #17211b;
  font-weight: 700;
}

.top-overlay {
  position: absolute;
  left: 24px;
  top: 24px;
  width: min(460px, calc(100vw - 48px));
  z-index: 2;
}

.search-card {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(25, 39, 32, 0.14);
  border-radius: 8px;
  box-shadow: 0 18px 50px rgba(23, 33, 27, 0.16);
  padding: 10px;
}

.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-input-wrap input {
  border: 0;
  outline: 0;
  min-height: 36px;
  width: 100%;
  background: transparent;
}

.search-results {
  display: grid;
  gap: 4px;
  margin-top: 8px;
}

.search-results button {
  border: 0;
  border-radius: 6px;
  background: #f3f6f4;
  color: #17211b;
  cursor: pointer;
  padding: 10px;
  text-align: left;
}

.search-error,
.hint-line {
  color: #6c342c;
  font-size: 0.88rem;
}
```

- [ ] **Step 6: Build frontend**

Run:

```powershell
Set-Location frontend
npm run build
```

Expected: build passes.

- [ ] **Step 7: Commit map/search**

Run from repo root:

```powershell
git add frontend/src
git commit -m "Add Mapbox search and 3D map shell"
```

---

### Task 6: Profile Rendering Components

**Files:**
- Create: `frontend/src/components/Profile.jsx`
- Create: `frontend/src/components/ScoreCards.jsx`
- Create: `frontend/src/components/Confidence.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Create score cards**

Create `frontend/src/components/ScoreCards.jsx`:

```jsx
const LABELS = {
  walkability: 'Walkability',
  transit_access: 'Transit',
  affordability: 'Affordability',
  quiet: 'Quiet',
  social_scene: 'Social scene',
};

export default function ScoreCards({ scores }) {
  if (!scores) return null;
  return (
    <div className="score-grid">
      {Object.entries(LABELS).map(([key, label]) => (
        <article className="score-card" key={key}>
          <span>{label}</span>
          <strong>{scores[key]}</strong>
        </article>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create confidence panel**

Create `frontend/src/components/Confidence.jsx`:

```jsx
export default function Confidence({ confidence, statuses }) {
  if (!confidence) return null;
  return (
    <section className="panel-section">
      <div className="section-heading">
        <p className="eyebrow">Confidence</p>
        <h2>{confidence.level}</h2>
      </div>
      {confidence.caveats?.length > 0 && (
        <ul className="caveat-list">
          {confidence.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      )}
      <div className="source-list">
        {statuses?.map((status) => (
          <div className={`source-row source-${status.status}`} key={status.source}>
            <span>{status.source}</span>
            <strong>{status.status}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Create profile component**

Create `frontend/src/components/Profile.jsx`:

```jsx
import Confidence from './Confidence.jsx';
import ScoreCards from './ScoreCards.jsx';

export default function Profile({ response }) {
  if (!response) return null;
  const { profile, fit, confidence, source_statuses: statuses } = response;
  return (
    <section className="profile-stack">
      <div className="section-heading">
        <p className="eyebrow">Neighborhood profile</p>
        <h2>{response.place.label}</h2>
      </div>
      <p className="overview">{profile.overview}</p>
      <ScoreCards scores={profile.vibe_scores} />
      {fit && (
        <article className="fit-card">
          <span>{fit.label}</span>
          <strong>{fit.score}</strong>
          <p>{fit.explanation}</p>
          {fit.flags?.map((flag) => <small key={flag}>{flag}</small>)}
        </article>
      )}
      <div className="pros-cons-grid">
        <div>
          <h3>Pros</h3>
          <ul>{profile.honest_pros.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
        <div>
          <h3>Cons</h3>
          <ul>{profile.honest_cons.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
      <article className="trajectory-card">
        <span>{profile.trajectory.direction}</span>
        <p>{profile.trajectory.summary}</p>
      </article>
      <Confidence confidence={confidence} statuses={statuses} />
    </section>
  );
}
```

- [ ] **Step 4: Replace debug output in `App.jsx`**

Import:

```jsx
import Profile from './components/Profile.jsx';
```

Replace:

```jsx
{data && <pre className="debug-response">{JSON.stringify(data.profile, null, 2)}</pre>}
```

with:

```jsx
{data && <Profile response={data} />}
```

- [ ] **Step 5: Add profile CSS**

Append to `frontend/src/styles.css`:

```css
.profile-stack {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}

.overview {
  margin: 0;
  line-height: 1.45;
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.score-card,
.fit-card,
.trajectory-card,
.pros-cons-grid > div {
  border: 1px solid rgba(25, 39, 32, 0.12);
  border-radius: 8px;
  background: #f8faf8;
  padding: 12px;
}

.score-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.score-card strong,
.fit-card strong {
  font-size: 1.6rem;
}

.fit-card {
  display: grid;
  gap: 6px;
}

.fit-card p,
.trajectory-card p {
  margin: 0;
}

.fit-card small {
  color: #6c342c;
}

.pros-cons-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.pros-cons-grid h3 {
  margin: 0 0 8px;
  font-size: 0.95rem;
}

.pros-cons-grid ul,
.caveat-list {
  margin: 0;
  padding-left: 18px;
}

.source-list {
  display: grid;
  gap: 6px;
}

.source-row {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid rgba(25, 39, 32, 0.1);
  padding: 6px 0;
  text-transform: capitalize;
}

.source-success strong {
  color: #24634f;
}

.source-error strong,
.source-empty strong {
  color: #8a3c32;
}
```

- [ ] **Step 6: Build frontend**

Run:

```powershell
Set-Location frontend
npm run build
```

Expected: build passes.

- [ ] **Step 7: Commit profile rendering**

Run from repo root:

```powershell
git add frontend/src
git commit -m "Render neighborhood profile panels"
```

---

### Task 7: Full Verification, Docs, And Push

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README full-stack commands**

Add to `README.md`:

````markdown
## Run Full Stack Locally

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Frontend:

```powershell
Set-Location frontend
npm install
npm run dev
```

Frontend environment:

```bash
VITE_MAPBOX_TOKEN=
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The frontend renders a setup state when `VITE_MAPBOX_TOKEN` is missing. OpenAI is optional; if `OPENAI_API_KEY` is absent or synthesis fails, the backend returns the deterministic profile.
````

- [ ] **Step 2: Run backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 3: Run backend lint**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check backend tests
```

Expected: `All checks passed!`

- [ ] **Step 4: Run frontend build**

Run:

```powershell
Set-Location frontend
npm run build
```

Expected: Vite build succeeds.

- [ ] **Step 5: Manually smoke test local app**

Run backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Run frontend in another terminal:

```powershell
Set-Location frontend
npm run dev
```

Verify:

- Initial screen is a map-first UI.
- Missing `VITE_MAPBOX_TOKEN` shows setup state.
- With token configured, search enables Mapbox autocomplete.
- Selecting a result flies the map to the place.
- Marker and 0.5 mile radius appear.
- Questionnaire appears after selection.
- Analyze returns profile, fit, confidence, and source statuses.
- API failure shows retryable panel error while map remains usable.

- [ ] **Step 6: Commit docs**

Run:

```powershell
git add README.md
git commit -m "Document Phase 1B full-stack setup"
```

- [ ] **Step 7: Push main**

Run:

```powershell
git push origin main
```

Expected: Phase 1B commits pushed to `origin/main`.
