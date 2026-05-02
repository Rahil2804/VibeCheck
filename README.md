# VibeCheck

VibeCheck is a map-first neighborhood-fit app for evaluating whether a place matches a user's stated lifestyle preferences. Phase 1 is complete as a local single-neighborhood MVP.

The app opens on a Mapbox 3D map. A user searches for a US or Canadian address/place, selects an autocomplete result, the map flies to that point, and the profile panel renders fit scoring, confidence, caveats, and source statuses.

## Current Scope

- React + Vite frontend with Mapbox GL 3D map, autocomplete search, marker, and 0.5 mile radius.
- FastAPI backend with `GET /health` and `POST /analyze`.
- Pydantic request/response models for the analyze contract.
- Optional OpenAI Structured Outputs synthesis with deterministic fallback.
- Source status handling for Mapbox, Census, housing, Reddit, and access data.
- Partial results when sources fail, time out, or return no MVP data.
- Rule-based confidence and lifestyle fit scoring.
- Neutral questionnaire that avoids protected-class and protected-class-proxy inputs.
- Loading, empty, API-error, low-confidence, missing-token, and success states.

## Architecture

```text
frontend/ React + Vite
  - Mapbox search and 3D map
  - neutral lifestyle questionnaire
  - profile, confidence, and source status panels
        |
        | POST /analyze
        v
backend/ FastAPI
  - request validation
  - source orchestration with per-source statuses
  - confidence and fit scoring
  - optional OpenAI profile synthesis
```

## Local Setup

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Frontend:

```powershell
Set-Location frontend
npm install
Copy-Item ..\.env.example .env
```

Set these in `frontend/.env`:

```bash
VITE_MAPBOX_TOKEN=
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Set backend keys in root `.env` when needed:

```bash
MAPBOX_TOKEN=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

OpenAI is optional. If `OPENAI_API_KEY` is absent or synthesis fails, the backend returns the deterministic profile.

## Run Locally

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Frontend:

```powershell
Set-Location frontend
npm.cmd run dev
```

Open:

```text
http://127.0.0.1:5173
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Analyze example:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/analyze `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"East Austin","preferences":{"car_reliance":"no_car"}}'
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check backend tests
Set-Location frontend
npm.cmd run build
```

## Data And Confidence Caveats

- Phase 1 source adapters are intentionally conservative and may return empty data without configured provider keys or deeper open-data coverage.
- Mapbox search supports US and Canada in the frontend and backend resolver.
- Reddit is treated as anecdotal signal only.
- The app does not make safety/crime claims in the MVP.
- Confidence and source statuses are part of the response so missing data stays visible.

## Fair Housing Guardrails

- Fit scoring uses only neutral lifestyle preferences and non-protected neighborhood signals.
- The questionnaire does not ask about family status, children, race, religion, disability, national origin, sex, or equivalent proxies.
- Demographic context is modeled for display only and is covered by tests to prevent it from influencing fit scoring.
- Results are framed as matches to selected lifestyle preferences, not judgments about whether a neighborhood is good or bad for protected groups.

## Resume Bullets

- Built a map-first neighborhood intelligence MVP with React, Vite, Mapbox GL, and FastAPI.
- Implemented source-aware partial-result orchestration with confidence scoring and graceful degradation.
- Added neutral lifestyle fit scoring with tests guarding against demographic/protected-class inputs.
- Integrated optional OpenAI Structured Outputs synthesis with Pydantic validation and deterministic fallback.
- Delivered local full-stack setup, API tests, linting, frontend build verification, and clear data caveats.

## Phase 2 Starting Point

Phase 2 should begin with saved local profiles, compare mode, and richer provenance/source freshness UI. Avoid adding accounts, public hosting, or share URLs until the anonymous local workflow remains excellent.
