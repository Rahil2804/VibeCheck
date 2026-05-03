# VibeCheck - Neighborhood Fit Product Plan

## Project Summary

VibeCheck is a neighborhood intelligence app for people evaluating where to live. It generates an honest neighborhood profile from real data sources and explains whether the area fits the user's stated lifestyle preferences.

**Tagline:** Not just what a neighborhood is, but whether it is right for you.

**Product goal:** Build the strongest personal-project version of the idea over time: a trustworthy, polished, explainable neighborhood decision tool with strong engineering fundamentals, careful data handling, and a demo-quality user experience without unnecessary recurring costs.

**Build philosophy:** There is no fixed deadline. Ship in quality gates instead of rushing: first a solid single-neighborhood MVP, then deeper data, comparison, sharing, and local persistence. Prefer free/open data and local-first infrastructure. Paid APIs, cloud hosting, and monitoring are optional upgrades only if they clearly improve the portfolio demo.

---

## Phase 1 Scope - Strong Single-Neighborhood MVP

### Included

- US-only address or place search using Mapbox Search/Geocoding.
- Mapbox map with a selected point and 0.5 mile context radius.
- Optional lifestyle questionnaire using neutral, non-protected preferences.
- Backend pipeline that fetches available data in parallel and returns partial results when some sources fail.
- OpenAI synthesis using Structured Outputs backed by Pydantic models.
- Rule-based personal fit score with a plain-English explanation.
- Data confidence indicator and source status panel.
- Polished single-neighborhood profile UI with loading, error, and low-confidence states.

### Deferred Until Later Phases

- Google Maps Geocoding and Google Places reviews.
- Compare mode.
- Public shareable profile URLs and hosted persistent cache.
- City open-data adapters for 311, permits, and crime/safety.
- School ratings and household-type scoring.
- Safety trend cards.

---

## Quality Bar

Every phase should meet these standards before moving on:

- The app remains useful when one or more external APIs fail.
- Generated claims are tied to available source data or clearly marked uncertain.
- Fit scoring uses only user preferences and non-protected neighborhood signals.
- The UI is fast, responsive, accessible, and clear on mobile and desktop.
- The source panel makes data freshness, missing data, and confidence understandable.
- Tests cover the risky logic: scoring, confidence, source failures, schema validation, cache freshness, and provider edge cases.
- Documentation stays current with implemented behavior.
- Resume/portfolio claims only describe features that actually exist.

---

## Product Principles

- **Trust over flash:** A lower-confidence honest answer is better than an impressive unsupported answer.
- **Explainability over mystery:** Users should understand why a score or claim appears.
- **Graceful degradation:** Thin data should become caveats and partial profiles, not broken screens.
- **Neutral decision support:** The app helps users match stated lifestyle preferences, not protected traits.
- **Provider compliance:** Caching, attribution, and display rules must follow each data provider's terms.
- **Incremental depth:** Add one high-quality source or city adapter at a time before expanding coverage.

---

## Long-Term Product Roadmap

### Phase 1 - Single-Neighborhood MVP

- Build the core analyze flow end to end.
- Support Mapbox search/map, neutral lifestyle preferences, partial data, confidence, source statuses, OpenAI Structured Outputs, and a polished profile UI.
- Keep safety/crime, compare mode, accounts, and sharing out of this phase.

### Phase 2 - Trust, Sharing, And Comparison

- Add local saved profiles first, then optional shareable profile URLs only if public demo hosting is desired.
- Add compare mode for two or more neighborhoods with side-by-side fit, cost, mobility, confidence, and caveats.
- Add a data provenance view that explains which source supported each major claim.
- Add result regeneration controls so users can refresh stale data intentionally.
- Add export/share actions for a profile summary image or PDF.

### Phase 3 - Richer Data Coverage

- Add city open-data adapters for a small set of high-value cities before expanding broadly.
- Add permits, 311 complaints, parks/open-space access, transit stop density, grocery/pharmacy access, and rental listing trends where reliable data exists.
- Add a provider abstraction so source adapters can be swapped without changing the profile schema.
- Add normalized geographic helpers for radius-based searches, Census tract lookup, and city/county/state extraction.
- Add a city coverage matrix in the app so users understand why one location has deeper data than another.

### Phase 4 - Personal Research Workspace

- Add optional user accounts after the anonymous flow is excellent.
- Let users save neighborhoods, notes, preferences, and comparisons.
- Add watchlists for rent changes or new data snapshots.
- Add a "decision board" view for apartment hunters comparing multiple candidate addresses.
- Keep account features optional so the app remains useful without login.

### Phase 5 - Production Quality And Public Launch

- Add CI, local diagnostics, structured logs, request IDs, and lightweight source health checks.
- Add API cost controls and caching policy for any service that has quotas.
- Add accessibility audits, mobile polish, keyboard navigation, and reduced-motion support.
- Add privacy policy, terms, and clear disclaimers for housing decision support.
- Prepare a public demo, architecture writeup, and resume/portfolio case study based only on implemented features.

---

## Product Flow

1. User enters a US address/place or clicks the map.
2. Frontend resolves the place with Mapbox and sends either a query or coordinates to the backend.
3. User can complete or skip the lifestyle questionnaire.
4. Backend fetches data from Mapbox, Census, free/open local data, Reddit, and optional paid/free-key sources in parallel.
5. Each source returns a success/error/empty status, so one failed source never breaks the whole profile.
6. Backend computes confidence, builds the profile with OpenAI Structured Outputs, computes personal fit, and returns one response object.
7. Frontend renders the profile, caveats, source panel, score cards, and fit explanation.

---

## Lifestyle Questionnaire

Use only preference-based inputs that avoid protected-class or protected-class-proxy recommendations.

- **Car reliance:** No car / Sometimes use a car / Drive daily
- **Energy preference:** Quiet and calm / Balanced / Lively and social
- **Top priority:** Walkability and errands / Transit access / Parks and outdoors / Restaurants and nightlife / Lower rent pressure
- **Budget sensitivity:** Very budget conscious / Moderate / Flexible
- **Generic mode:** User may skip all questions and receive a generic profile with no personal fit score, or a clearly labeled generic score.

Do not ask about family status, children, race, religion, disability, national origin, sex, or any equivalent proxy. Census demographics may be displayed as neutral context but must not drive recommendations or fit scoring.

---

## Architecture

```text
[React + Vite frontend]
  - Mapbox map/search
  - lifestyle questionnaire
  - profile rendering
        |
        | POST /analyze
        v
[FastAPI backend]
  - request validation
  - async pipeline orchestration
        |
        | asyncio.gather with per-source timeouts
        v
[Source adapters]
  - mapbox.py: place resolution and reverse geocoding fallback
  - census.py: ACS/Census data via direct HTTP calls
  - housing.py: free/open rent and affordability signals first
  - reddit.py: recent local discussion snippets/sentiment inputs
  - access.py: custom Daily Needs Access score from explainable POI signals
        |
        v
[Normalization + scoring]
  - source status model
  - confidence.py
  - scorer.py
        |
        v
[synthesizer.py]
  - OpenAI Structured Outputs
  - Pydantic response schema
        |
        v
[AnalyzeResponse JSON]
```

---

## Backend Public Interfaces

### `GET /health`

Returns:

```json
{
  "status": "ok"
}
```

### `POST /analyze`

Accepts either a query or coordinates. If both are present, coordinates win and query is kept only for display/context.

```json
{
  "query": "East Austin, Austin, TX",
  "coordinates": {
    "lat": 30.2636,
    "lng": -97.7114
  },
  "preferences": {
    "car_reliance": "no_car",
    "energy_preference": "balanced",
    "top_priority": "walkability_errands",
    "budget_sensitivity": "moderate"
  },
  "generic_mode": false
}
```

Returns:

```json
{
  "place": {
    "label": "East Austin, Austin, TX",
    "neighborhood": "East Austin",
    "city": "Austin",
    "state": "TX",
    "coordinates": {
      "lat": 30.2636,
      "lng": -97.7114
    }
  },
  "profile": {
    "overview": "Short honest summary.",
    "vibe_scores": {
      "walkability": 72,
      "transit_access": 68,
      "affordability": 42,
      "quiet": 55,
      "social_scene": 78
    },
    "who_lives_here": {
      "median_age": 31,
      "median_household_income": 58000,
      "population_density": 5200,
      "population_trend": "growing"
    },
    "honest_pros": ["Specific positive from available data."],
    "honest_cons": ["Specific negative from available data."],
    "trajectory": {
      "direction": "rising",
      "summary": "Supported by rent trends and available discussion signals."
    }
  },
  "fit": {
    "score": 76,
    "label": "Good fit",
    "explanation": "Plain-English explanation tied to the selected preferences.",
    "flags": ["Transit access is decent, but rent pressure is rising."]
  },
  "confidence": {
    "level": "medium",
    "available_sources": ["mapbox", "census", "rentcast", "reddit"],
    "missing_sources": [],
    "caveats": ["Daily Needs Access is a VibeCheck score based on nearby amenities and transparent sub-scores."]
  },
  "source_statuses": [
    {
      "source": "rentcast",
      "status": "success",
      "message": "Market data returned.",
      "updated_at": "2026-04-30"
    }
  ]
}
```

### Deferred Endpoints

- `GET /profile/{id}`
- `GET /compare`
- `GET /supported-cities`
- `GET /sources/health`
- `GET /coverage`
- `POST /profiles/{id}/refresh`

### Later API Interfaces

Add these only after Phase 1 is stable:

- `GET /profile/{id}` returns a cached/shareable profile with data freshness metadata.
- `GET /compare?ids=...` returns normalized side-by-side comparison data.
- `GET /supported-cities` returns source coverage by city and feature.
- `GET /sources/health` returns adapter availability for admin/debug use.
- `POST /profiles/{id}/refresh` regenerates a profile when cached data is stale.

---

## Backend Modules

### `backend/main.py`

- Create FastAPI app.
- Load the root `.env` at startup without overriding real process environment variables.
- Expose `GET /health` and `POST /analyze`.
- Validate request/response through Pydantic models.
- Return clear HTTP errors only for invalid requests; source failures should be represented inside `source_statuses`.

### `backend/config.py`

- Centralize local environment loading with `python-dotenv`.
- Keep local `.env` convenient for development while allowing deployed process environment variables to take precedence.

### `backend/models.py`

- Define all request, response, source status, confidence, profile, and fit score models.
- Use enums for preference values, confidence levels, source names, source statuses, and trajectory direction.
- Keep the OpenAI Structured Output schema derived from these Pydantic models to avoid schema/type drift.
- Include optional provenance fields so profile claims can later cite source adapters without changing the public response shape.

### `backend/pipeline.py`

- Orchestrate place resolution and source fetching.
- Run independent source calls with `asyncio.gather`.
- Apply per-source timeouts.
- Convert exceptions into `SourceStatus(status="error")`.
- Continue with partial data when non-critical sources fail.

### `backend/sources/mapbox.py`

- Resolve query or coordinates.
- Return label, city, state, neighborhood when available, and coordinates.
- Use Mapbox consistently for search/geocoding because the frontend map is Mapbox.

### `backend/sources/census.py`

- Use direct Census API requests with `httpx`.
- Fetch MVP demographic context only: median age, median household income, population density, and population trend when available.
- Display demographics as context only. Do not feed demographic composition into fit scoring.

### `backend/sources/housing.py`

- Use free/open affordability signals first: Census ACS rent and income fields, HUD Fair Market Rents where useful, and local open-data housing indicators when available.
- Return normalized rent pressure and affordability context, not exact real-time listing estimates.
- Keep RentCast as an optional provider behind the same interface when an API key is configured.
- Return empty/unavailable status if an optional paid/free-key provider quota is exhausted or no key is present.

### `backend/sources/reddit.py`

- Fetch recent local discussion snippets using Reddit API/PRAW.
- Filter deleted content, stale posts, and low-signal matches.
- Treat Reddit as anecdotal sentiment, not factual ground truth.

### `backend/sources/access.py`

- Build VibeCheck's own Daily Needs Access score instead of depending on Walk Score.
- Use Mapbox/OSM/Geoapify-style place categories if available within free tiers: grocery, pharmacy, parks, cafes, restaurants, transit stops, libraries, and gyms.
- Prefer transparent sub-scores over a single black-box score: errands, transit, food/social, parks/outdoors, and useful services.
- Explain the score in the UI so users can see which nearby amenities contributed.
- Do not call it "Walk Score" or imply it is equivalent to the official Walk Score product.

### `backend/confidence.py`

- High: 4 or more meaningful sources.
- Medium: 3 meaningful sources.
- Low: 1-2 meaningful sources.
- No profile: 0 meaningful sources beyond place resolution.
- Return caveats for missing optional sources and thin data.

### `backend/scorer.py`

- Start from 50 and clamp to 0-100.
- Use only lifestyle preferences and non-protected data signals.
- Example scoring:
  - No car + transit or walkability strong: +10 to +15.
  - No car + weak transit/walkability: -15 to -20.
  - Quiet preference + quiet score high: +10 to +15.
  - Quiet preference + social/noise signals high: -10 to -20.
  - Lively preference + social scene high: +10 to +15.
  - Walkability priority + walkability high: +15.
  - Transit priority + transit access high: +15.
  - Parks priority + park/outdoor signals available: +10.
  - Budget conscious + rising rent pressure: -15.
  - Budget conscious + stable/falling rent pressure: +10.
- Fit explanation should cite the specific signals used.

### `backend/synthesizer.py`

- Use the OpenAI Python SDK with Structured Outputs, not plain JSON mode.
- Model name comes from `OPENAI_MODEL`.
- Prompt must instruct the model to:
  - use only supplied data,
  - mark uncertainty clearly,
  - avoid unsupported safety/crime claims,
  - avoid protected-class recommendations,
  - produce the exact Pydantic schema.

### `backend/provenance.py` - Later Phase

- Track which input source supports each profile claim.
- Let the UI show "Why am I seeing this?" for important statements.
- Store source name, freshness, confidence, and the normalized data field used.

### `backend/cache.py` - Later Phase

- Cache complete profiles only after Phase 1 source behavior is stable.
- Respect provider-specific caching limits for any third-party source.
- Store freshness timestamps and source status snapshots.
- Support share links without exposing raw API payloads.

### `backend/observability.py` - Later Phase

- Add structured request logs, source latency metrics, source error counts, and request IDs.
- Keep logs free of API keys and sensitive raw user input.
- Add debug summaries that make demo failures easy to diagnose.

---

## Frontend Modules

### `frontend/src/App.jsx`

- Own app state for selected place, preferences, loading/error state, and analyze response.
- Render the search/map first, not a marketing landing page.

### `frontend/src/components/SearchBar.jsx`

- Use Mapbox Search/Geocoding.
- Let users select an address/place.
- Support re-searching after a profile is shown.

### `frontend/src/components/MapView.jsx`

- Render Mapbox GL map.
- Show selected marker and 0.5 mile radius.
- Map click updates selected coordinates and can trigger analysis.

### `frontend/src/components/Questionnaire.jsx`

- Render the neutral lifestyle preferences.
- Include a skip/generic option.

### `frontend/src/components/Profile.jsx`

- Render overview, vibe cards, who-lives-here context, pros/cons, trajectory, fit score, confidence, and source panel.
- Keep low-confidence caveats visible and plain-spoken.

### `frontend/src/components/ScoreCards.jsx`

- Render walkability, transit access, affordability, quiet, and social scene.
- Do not render safety trend in MVP.

### `frontend/src/components/Confidence.jsx`

- Render High/Medium/Low confidence and source availability.
- Show caveats when data is thin.

### `frontend/src/hooks/useNeighborhood.js`

- Encapsulate the `POST /analyze` request.
- Expose loading, error, data, and retry behavior.

### Later Frontend Additions

- `CompareView.jsx`: side-by-side comparison with aligned score cards, caveats, and source freshness.
- `ShareProfile.jsx`: share/export controls with copyable URLs and visual summary generation.
- `CoveragePanel.jsx`: explains which data sources work in the selected city.
- `ProvenanceDrawer.jsx`: shows source support behind major claims.
- `SavedResearch.jsx`: optional account-based workspace for saved neighborhoods and notes.
- `AdminSourceHealth.jsx`: local/admin-only source health diagnostics during development.

---

## Tech Stack

| Layer | Tool | MVP Reason |
|---|---|---|
| Backend | FastAPI | Async-friendly Python API with clean docs |
| Validation | Pydantic | Shared request/response/schema validation |
| HTTP client | httpx | Async external API calls |
| Place search/map | Mapbox | One vendor for search/geocoding and map display |
| AI synthesis | OpenAI Structured Outputs | Schema adherence through Pydantic models |
| Demographics | Census API via httpx | Free authoritative context without stale package dependency |
| Housing/affordability | Census ACS, HUD FMR, local open data | Free-first affordability context |
| Optional rent estimates | RentCast API | Add only if exact rental estimates are worth the quota/cost |
| Local sentiment | Reddit API/PRAW | Useful anecdotal signal with caveats |
| Walkability-style access | OSM/Mapbox/Geoapify-style POI signals | Explainable VibeCheck Daily Needs Access score |
| Frontend | React + Vite | Fast interactive demo build |
| Styling | CSS or Tailwind | Choose one during frontend setup and keep it consistent |
| Testing | pytest, pytest-asyncio, React/Vitest optional | Mocked source tests and manual UI checks |
| Default runtime | Local FastAPI + local Vite dev server | No hosting cost for personal use |
| Optional portfolio demo | Local recording, GitHub README, or static frontend preview | Avoid paid hosting unless needed |
| Later local cache | SQLite | Free saved profiles and source freshness |
| Later auth | None by default | Accounts are unnecessary for a one-user personal project |
| Diagnostics | Local structured logs | No Sentry or paid monitoring needed |

---

## Environment Variables

```bash
MAPBOX_TOKEN=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
SQLITE_PATH=data/vibecheck.db
RENTCAST_API_KEY=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=vibecheck/1.0
CENSUS_API_KEY=
SOURCE_TIMEOUT_SECONDS=8
APP_ENV=development
LOG_LEVEL=info
```

Notes:

- `RENTCAST_API_KEY` is optional and not required for the free-first build.
- No `GOOGLE_MAPS_API_KEY` in MVP.
- Use local SQLite for saved profiles by default; the database path is controlled by `SQLITE_PATH`.
- No Railway, Vercel, Redis, Sentry, or auth provider keys are required for personal use.

---

## Python Requirements

```text
fastapi
uvicorn[standard]
httpx
openai
praw
python-dotenv
pydantic
pytest
pytest-asyncio
respx
ruff
```

Do not include `censusdatadownloader` for the MVP. Use direct Census API requests or revisit a maintained Census library if direct calls become painful.

---

## Build Order

### Phase 1A - Backend Foundation

- [x] Set up backend package, virtual environment, requirements, and `.env.example`.
- [x] Define Pydantic request/response/source models.
- [x] Add `GET /health`.
- [x] Build `mapbox.py` for query/coordinate resolution.
- [x] Build source status model and timeout helper.
- [x] Build `confidence.py` with unit tests.
- [x] Build `scorer.py` with unit tests covering each lifestyle preference.
- [x] Build mocked `pipeline.py` that returns partial results.
- [x] Add source adapters for Census, housing/affordability, Reddit, and Daily Needs Access scoring.
- [x] Test source failure behavior with mocked APIs.

### Phase 1B - AI Layer And Frontend

- [x] Build `synthesizer.py` with OpenAI Structured Outputs and Pydantic parsing.
- [x] Load root `.env` during backend startup so `OPENAI_API_KEY`, `OPENAI_MODEL`, and backend provider keys are actually available locally.
- [x] Test invalid/malformed model output handling.
- [x] Wire `POST /analyze`.
- [x] Set up React + Vite frontend.
- [x] Build Mapbox search and map components.
- [x] Build neutral questionnaire.
- [x] Build profile, score cards, fit score, confidence, and source panel.
- [x] Connect frontend to backend and verify one happy-path profile with mocked or real dev keys.

### Phase 1C - Polish And Demo Readiness

- [x] Improve loading, empty, error, and low-confidence states.
- [x] Add responsive layout checks on desktop and mobile.
- [x] Run backend tests and frontend build.
- [x] Keep the app runnable locally with clear startup commands.
- [x] Write README with setup, architecture, env vars, and caveats. Screenshots/GIF intentionally deferred.
- [x] Prepare resume bullets based on implemented features only.

### Phase 2 - Comparison, Sharing, And Provenance

- [x] Add SQLite-backed local saved profiles with provider-compliant freshness rules.
- [ ] Add public shareable profile URLs only if a hosted demo is later desired.
- [ ] Add compare mode for two or more places.
- [ ] Add provenance metadata to major generated claims.
- [x] Add UI affordances for synthesis status and local saved-profile handling.
- [ ] Add regression tests for cache freshness, compare response shape, and provenance display.

### Phase 3 - Data Depth

- [ ] Add city open-data adapter interface.
- [ ] Implement 2-3 cities deeply before adding more.
- [ ] Add parks/open-space, grocery/pharmacy access, transit stop density, permits, and 311 signals where reliable.
- [ ] Add city coverage matrix and UI.
- [ ] Add source-specific contract tests using recorded/mock fixtures.

### Phase 4 - Saved Research Workspace

- [ ] Add optional auth only after anonymous flow is polished.
- [ ] Add saved neighborhoods, notes, preferences, and comparison boards.
- [ ] Add privacy controls for saved profiles.
- [ ] Add account deletion/export basics.

### Phase 5 - Production Hardening

- [ ] Add CI for backend tests, linting, frontend build, and type checks.
- [ ] Add optional preview deployments only if public sharing becomes important.
- [ ] Add local structured logs, request IDs, and source latency summaries.
- [ ] Add rate limiting and cost ceilings for external APIs.
- [ ] Add accessibility review and mobile browser checks.
- [ ] Add portfolio case study and, only if hosted publicly, privacy/terms pages.

---

## Test Plan

- Unit test fit scoring with no-car, daily-driver, quiet, lively, transit, walkability, parks, and budget-sensitive preferences.
- Unit test confidence scoring for high, medium, low, and no-profile cases.
- Mock all external APIs; tests should not require real API keys.
- Pytest startup should blank live API keys so a developer's local `.env` does not trigger external calls during unit tests.
- Test that source timeouts/errors produce `source_statuses` and still return partial profiles when possible.
- Test Structured Output validation rejects malformed model responses.
- Test that demographics are not read by `scorer.py`.
- Manually verify frontend loading, API error, low-confidence, and successful profile states.
- Before deployment, run backend tests and frontend build.

### Evaluation Plan

- Create a small fixture set of neighborhoods with known source combinations: dense city, suburb, rural/thin-data, source-error, and quota-exceeded.
- Save expected qualitative checks for each fixture, such as "does not mention crime without source" and "budget-sensitive user sees rent pressure caveat."
- Add a prompt regression checklist for hallucination, unsupported certainty, protected-class language, and malformed schema output.
- Track source latency and profile generation time so improvements are measurable.
- After launch, review anonymized failure categories rather than raw personal input.

---

## UX And Design Goals

- First screen should be the actual app: search, map, and preferences, not a marketing landing page.
- Use a quiet, utilitarian interface with strong information hierarchy.
- Make the map useful but not dominant; the profile and decision support are the main value.
- Show confidence and caveats near the claims they affect.
- Use concise labels, icons where natural, and dense but readable cards.
- Support mobile apartment-hunting use cases: one-handed search, readable profile, and easy sharing in later phases.
- Add loading skeletons that explain which sources are being checked without implying certainty.
- Avoid dark, blurred, stock-like visuals; use actual map/profile data as the visual center.

---

## Fair Housing And Safety Guardrails

- Do not recommend or discourage a neighborhood based on protected classes or protected-class proxies.
- Do not use family status, children, school ratings, race, ethnicity, religion, disability, sex, or national origin in fit scoring.
- Demographics are context only and should be factual, neutral, and optional in display.
- Do not make safety/crime claims without a reliable source and careful wording.
- Avoid ranking neighborhoods as "good" or "bad" for types of people; frame results as matches to user-selected lifestyle preferences.
- Include caveats when data is anecdotal, thin, stale, or unavailable.

---

## Known Risks And MVP Choices

| Risk | MVP Choice |
|---|---|
| Google geocoding with Mapbox display creates policy friction | Use Mapbox for search/geocoding and map display |
| Too many APIs at once can dilute quality | Add deeper data through phased source adapters |
| Third-party walkability scores are hard to explain and may add terms constraints | Build VibeCheck's own Daily Needs Access score |
| Reddit can skew negative | Label it anecdotal and combine with other sources |
| RentCast free API quota is small | Use Census/HUD/open data first and keep RentCast optional |
| OpenAI may produce unsupported claims | Use Structured Outputs, validation, and prompt guardrails |
| Rural/small-town data may be thin | Return low confidence with clear caveats |
| Fit scoring can drift into protected-class recommendations | Use neutral preference inputs and tests that keep demographics out of scoring |
| Paid hosting and monitoring add cost without personal-project value | Run locally by default; use GitHub docs/screenshots/demo video for portfolio proof |

---

## Personal Project Cost Strategy

- Default target cost is near-zero, excluding occasional OpenAI API usage.
- Run the backend and frontend locally during development and demos.
- Use free/open data first: Census, HUD Fair Market Rents, city open-data portals, OSM-style place data, and Reddit within normal developer limits.
- Make paid sources optional adapters, never core requirements.
- Avoid Sentry, paid monitoring, hosted Redis, hosted Postgres, Railway, and Vercel unless there is a specific reason to publish a live public demo.
- If a public demo is desired later, start with the cheapest option: static frontend hosting plus a clearly marked mocked/demo mode, then decide whether a live backend is worth the monthly cost.
- Keep a demo recording and screenshots in the README so the project remains impressive without needing a permanently running deployment.

### Free-First Source Alternatives

| Need | Free-first option | Paid/optional upgrade |
|---|---|---|
| Map/search | Mapbox free tier or OSM/Nominatim for limited local testing | Higher Mapbox usage |
| Demographics | Census API | None needed |
| Rent pressure | Census ACS rent fields, HUD FMR, local open data | RentCast |
| Walkability/access | VibeCheck Daily Needs Access score from POI/open data | None needed |
| Local discussion | Reddit API within normal limits | None for personal use |
| City signals | NYC/Chicago/Austin/etc. open-data portals | None unless a private data source is wanted |
| Saved profiles | SQLite local file | Hosted Postgres/Redis only for public sharing |
| Monitoring | Local logs | Sentry only for public production app |

---

## Resume-Ready Definition Of Done

- [ ] Live URL works for a major US city address.
- [ ] Personal preferences meaningfully change the fit score and explanation.
- [ ] Low-confidence case renders clearly for a thin-data area.
- [ ] One failed source does not break the profile.
- [ ] Backend tests cover scoring, confidence, source failures, and schema validation.
- [ ] Frontend renders loading, error, low-confidence, and success states cleanly.
- [ ] README explains setup, architecture, data sources, limitations, and fair-housing guardrails.
- [ ] Resume bullets match features actually implemented.

---

## Reviewed Source References

- Google Geocoding billing: https://developers.google.com/maps/documentation/geocoding/usage-and-billing
- Google Geocoding policies: https://developers.google.com/maps/documentation/geocoding/policies
- Mapbox pricing: https://www.mapbox.com/pricing
- OpenAI Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs
- RentCast API pricing: https://www.rentcast.io/api
- HUD Fair Housing overview: https://www.hud.gov/helping-americans/fair-housing-act-overview
