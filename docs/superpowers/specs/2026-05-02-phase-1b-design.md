# Phase 1B Design - AI Layer And Map-First Frontend

## Goal

Phase 1B turns the backend foundation into a demoable single-neighborhood app. The first screen is a live Mapbox 3D world with search overlaid. A user selects an autocomplete result, the map flies to the selected location, a marker and 0.5 mile radius appear, and the questionnaire/profile experience reveals around that selected place.

The app should feel like a real neighborhood intelligence tool immediately, while still remaining usable without optional API keys beyond Mapbox.

## User Experience

The initial viewport is the actual application, not a landing page. The 3D map fills the screen. A compact search control floats near the top, with lightweight branding and status text. The user types a US address/place and chooses one autocomplete result before any analysis starts.

After selection:

- The map animates to the selected coordinates.
- A marker and 0.5 mile context radius render around the selected point.
- Desktop shows the questionnaire/profile in a side panel.
- Mobile shows the questionnaire/profile in a bottom sheet.
- The user can skip preferences and run a generic analysis.
- Loading states show which sources are being checked without implying certainty.

The profile presents overview, vibe scores, who-lives-here context, pros/cons, trajectory, fit score, confidence, and source statuses. Low-confidence caveats remain visible near the profile claims.

## Backend Design

Add `backend/synthesizer.py` as the Phase 1B AI layer. It uses the OpenAI Python SDK with Structured Outputs and validates responses against the existing Pydantic models. The model name comes from `OPENAI_MODEL`.

The synthesizer prompt must instruct the model to:

- Use only supplied normalized source data.
- Mark uncertainty clearly.
- Avoid unsupported safety or crime claims.
- Avoid protected-class recommendations.
- Produce schema-valid profile content.

`POST /analyze` remains the public frontend endpoint. The pipeline should attempt synthesis when `OPENAI_API_KEY` is configured. If the key is missing, the OpenAI request fails, or the model output fails validation, the pipeline falls back to the deterministic Phase 1A profile. Source failures still appear in `source_statuses` instead of breaking the whole response.

## Frontend Design

Create a Vite React app under `frontend/`.

Core modules:

- `frontend/src/App.jsx`: owns selected place, preferences, loading, error, and analyze response state.
- `frontend/src/components/SearchBar.jsx`: Mapbox autocomplete; analysis starts only after result selection.
- `frontend/src/components/MapView.jsx`: Mapbox GL 3D map, selected marker, and 0.5 mile radius.
- `frontend/src/components/Questionnaire.jsx`: neutral lifestyle preferences plus generic/skip mode.
- `frontend/src/components/Profile.jsx`: profile shell for summary, fit, confidence, caveats, and source statuses.
- `frontend/src/components/ScoreCards.jsx`: walkability, transit, affordability, quiet, and social scene cards.
- `frontend/src/components/Confidence.jsx`: confidence level, available/missing sources, and caveats.
- `frontend/src/hooks/useNeighborhood.js`: encapsulates `POST /analyze`, retry, loading, and error behavior.

Use plain CSS for Phase 1B unless the Vite scaffold strongly favors another local pattern. The visual tone should be quiet, utilitarian, and map-first: no marketing hero, no decorative blobs, no landing-page copy. Cards are only for repeated profile items and compact panels.

## Configuration

Backend environment variables remain in `.env.example`. Add frontend variables as needed:

- `VITE_MAPBOX_TOKEN`
- `VITE_API_BASE_URL`

If `VITE_MAPBOX_TOKEN` is missing, the frontend should show a clear setup state instead of rendering a broken map.

## Error Handling

- Mapbox search errors stay localized to the search control.
- Missing Mapbox token renders a setup state.
- Analyze API failures show a retryable profile-panel error while keeping the map usable.
- Backend source failures return partial responses with source statuses.
- OpenAI failures fall back to deterministic profile generation.
- Low-confidence data remains visible but clearly caveated.

## Testing And Verification

Backend:

- Add synthesizer tests for malformed/invalid model output handling.
- Add pipeline tests proving missing/failing OpenAI does not break `/analyze`.
- Keep existing scoring, confidence, and source failure tests passing.

Frontend:

- Verify Vite build succeeds.
- Add lightweight hook/component tests if the setup is straightforward.
- Manually verify the map-first flow: initial map, autocomplete selection, fly-to, marker/radius, questionnaire, loading, profile success, and API error.

Before pushing Phase 1B, run backend tests, backend lint, and frontend build.

## Out Of Scope

- Compare mode.
- Shareable profile URLs.
- Accounts or saved profiles.
- City open-data adapters.
- School ratings, household-type scoring, crime/safety trend cards.
- Public hosting or production monitoring.
