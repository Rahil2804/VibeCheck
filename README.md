# VibeCheck

VibeCheck is a GTA-first neighbourhood field guide that compares a place with a person’s stated lifestyle preferences. It is a local portfolio MVP: no accounts, cloud sync, live tracking, crime scoring, or demographic recommendations.

The central product rule is simple: missing evidence stays unavailable. It is never converted into a neutral-looking score.

![Desktop landing state](docs/screenshots/gta-landing-desktop.png)
![Mobile field guide](docs/screenshots/gta-mobile-landing.png)

## Included evidence

| Signal | Coverage | Evidence |
|---|---|---|
| Scheduled transit | GTA core systems | Bundled regular-weekday GTFS for TTC, GO, UP Express, MiWay, Brampton Transit, YRT, and Durham Region Transit |
| Rent benchmark | GTA census subdivisions | CMHC 2025 purpose-built apartment rents by studio, 1-bedroom, 2-bedroom, and 3-bedroom-plus reporting geography |
| Cycling | Toronto | City cycling-network geometry and Bike Share station locations; live availability is not stored or scored |
| Everyday access | Where OSM responds | Nearby groceries, pharmacies, community amenities, dining, parks, and transit-stop fallback |
| Local context | Toronto | 2021 Toronto Neighbourhood Profiles and City parks/open data |
| Census context | GTA, with deeper Toronto detail | Bundled Statistics Canada 2021 census-subdivision boundaries/context and Toronto 158-neighbourhood profiles |

Toronto has the deepest coverage. The rest of the GTA has scheduled transit, unit-matched rent, bundled Census context, and OSM context where available. Outside the GTA remains a visibly limited Mapbox/OSM analysis; Statistics Canada's retired Census Profile endpoint is not part of the critical GTA runtime path. Every source status can carry its edition, geographic scope, official URL, update date, stale state, and exact evidence fields.

The checked-in normalized snapshot is under `backend/snapshots/`, is below 50 MB, and has a manifest containing source URLs, retrieval dates, input checksums, licences, feed validity, artifact checksum, and snapshot ID. Saved reports retain the exact `analysis_version`, `snapshot_id`, and preference lens used when they were created.

Toronto neighbourhood population density is derived reproducibly from the official 2021 profile population estimate and official neighbourhood boundary area. Municipal GTA density comes directly from the Statistics Canada 2021 Census Profile.

## Scoring

- Scheduled transit: proximity 25%, peak scheduled frequency 40%, route diversity 25%, and rapid/regional access 10%. Frequency caps at 20 departures/hour and diversity at six routes.
- Toronto cycling: protected-network length within 1 km 50%, all cycling-network length within 1 km 25%, and Bike Share stations within 800 m 25%.
- Walkability: everyday destinations, parks, dining/activity, and community amenities. Transit is deliberately excluded to prevent double-counting.
- Rent: only the selected unit size’s CMHC purpose-built benchmark can affect a rent ceiling or rent-pressure fit. A different bedroom size and Toronto’s historical 2021 shelter-cost field are never substituted.
- Fit: top priorities use up to ±15, important signals up to ±6 each, and failed positive non-negotiables up to −15. Missing evidence is skipped.

Driving and quiet preferences remain stored in a local lens but are labelled unscored until defensible evidence exists. OpenAI is optional and can improve prose only; metrics, availability, fit, coverage, and provenance are deterministic. AI runs only when at least two non-Mapbox evidence checks are usable. Each accepted sentence cites evidence-check IDs; unsupported numbers and prohibited safety, protected-class, noise, school, sentiment, and trajectory claims are rejected.

## Local setup

Requirements: Python 3.12+, Node 22+, and a public Mapbox token.

Backend configuration belongs in the root `.env`:

```dotenv
MAPBOX_TOKEN=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
SOURCE_TIMEOUT_SECONDS=8
SQLITE_PATH=data/vibecheck.db
```

`OPENAI_API_KEY` is optional. Do not put any real token in examples, fixtures, screenshots, logs, or Git. If a key has been exposed, revoke it before running this project again.

Frontend configuration belongs in `frontend/.env`:

```dotenv
VITE_MAPBOX_TOKEN=
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Allow both `http://127.0.0.1:5173/*` and `http://localhost:5173/*` in the Mapbox public-token URL restrictions. Vite reads environment variables only when it starts, so restart it after changes.

Install and run the backend from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m backend.doctor
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

`backend.doctor` performs local, secret-free checks only. Remote diagnostics are explicit:

```powershell
.\.venv\Scripts\python.exe -m backend.doctor --live-sources
.\.venv\Scripts\python.exe -m backend.doctor --live-openai
```

The OpenAI option makes a small paid request. Neither live option prints tokens or raw provider payloads.

Run the frontend in a second terminal:

```powershell
Set-Location frontend
npm.cmd install
Copy-Item .env.example .env
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The Mapbox terrain-cutoff console warning is non-fatal. If the basemap is blank, hard-refresh, check browser privacy extensions, confirm the frontend token is present, and verify its localhost URL restrictions.

## Refreshing the bundled snapshot

Run this only when updating checked-in official data:

```powershell
.\.venv\Scripts\python.exe -m scripts.refresh_gta_snapshot
.\.venv\Scripts\python.exe -m backend.snapshot
```

The refresh stages files directly beside the final artifact so Windows permissions inherit from `backend/snapshots/`. It validates required agencies/tables, SQLite integrity, source normalization, and the 50 MB limit, then atomically replaces the prior database and manifest. A failed refresh leaves the last valid snapshot intact. The current schema includes 25 official GTA census subdivisions and all 158 Toronto neighbourhood profiles.

Input sources and licence links are recorded in `backend/snapshots/manifest.json`. The relevant publishers are Statistics Canada, Metrolinx, TTC/City of Toronto, MiWay/City of Mississauga, Brampton Transit, YRT/York Region, Durham Region Transit, CMHC, and Bike Share Toronto.

## Verification

```powershell
.\.venv\Scripts\ruff.exe check backend scripts tests
.\.venv\Scripts\python.exe -m scripts.check_secrets
.\.venv\Scripts\python.exe -m backend.snapshot
.\.venv\Scripts\python.exe -m pytest -q

Set-Location frontend
npm.cmd test
npm.cmd run build
npm.cmd run check:bundle
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

CI runs Ruff, secret scanning, snapshot schema/checksum validation, pytest, Node/Vitest tests, the Vite production build, the initial-shell bundle budget, Playwright screenshots, and axe accessibility checks.

## Deliberate limitations

- Static scheduled service is included; real-time arrivals, live Bike Share availability, and commute routing are not.
- Some CMHC rows represent official grouped reporting zones or regions rather than a single municipality; the displayed scope always says so.
- Recently expired or missing GTFS feeds are marked stale and fall back to clearly labelled OSM stop evidence when available.
- Toronto’s 2021 renter shelter cost is historical household context, not a current asking-rent proxy.
- Live listings, Reddit, noise claims, permits/trajectory, flood risk, crime/safety, schools, accounts, deployment, and cloud sync are out of scope.
- OSM proximity is not a route or travel-time estimate and may be incomplete.

## Fair-housing guardrails

Fit uses only explicit lifestyle preferences and neutral place evidence. Age, income, race, religion, disability, family status, national origin, sex, and proxies never affect fit. Census demographics are not used to recommend a neighbourhood for a kind of person.
