# VibeCheck

VibeCheck is a neighborhood-fit app for evaluating whether a place matches a
user's stated lifestyle preferences. The current implementation is Phase 1A:
the backend foundation for a single-neighborhood MVP.

## Current Scope

- FastAPI backend with `GET /health` and `POST /analyze`.
- Pydantic request and response models for the planned analyze contract.
- Source status handling for Mapbox, Census, housing, Reddit, and access data.
- Partial-result pipeline behavior when a source fails, times out, or returns no data.
- Rule-based confidence and lifestyle fit scoring.
- Conservative source adapters that do not require real API keys for local tests.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill in API keys only when you want live provider calls. The backend tests do
not require real keys.

## Run The Backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
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
```

## Guardrails

Fit scoring uses only neutral lifestyle preferences and non-protected
neighborhood signals. Demographic context is modeled for display only and is
covered by tests to prevent it from influencing the fit score.
