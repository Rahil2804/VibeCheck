# Phase 1C Design - Polish And Demo Readiness

## Goal

Finish Phase 1 as a polished local MVP without adding Phase 2 features. The app should be understandable, resilient to missing or thin data, and ready for a future Phase 2 handoff.

## Scope

Phase 1C includes:

- Better frontend loading, empty, API-error, missing-token, and low-confidence states.
- Responsive cleanup for desktop side panel and mobile bottom sheet.
- Profile completeness improvements for implemented data fields, including who-lives-here context.
- README updates that describe current architecture, setup, env vars, caveats, and implemented behavior.
- `PLAN.md` updates that mark Phase 1 status and leave Phase 2 as the next clean starting point.
- Resume bullets based only on implemented features.

Phase 1C excludes screenshots/GIFs, compare mode, saving, sharing, accounts, provenance drawers, and deeper city/open-data adapters.

## User Experience

The map remains the first screen. Search is visible immediately. Once a place is selected, the analysis panel explains the next action, shows a source-aware loading state during analysis, displays retryable errors if the backend fails, and renders low-confidence caveats near the profile.

On mobile, the search control stays reachable and the profile panel behaves like a readable bottom sheet. Text should not overlap controls or disappear behind panels.

## Verification

Before pushing, run:

- `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider`
- `.\.venv\Scripts\python.exe -m ruff check backend tests`
- `npm.cmd run build` from `frontend/`

Manual verification should include missing token, selected place before analysis, loading, API error, low-confidence, and success states.
