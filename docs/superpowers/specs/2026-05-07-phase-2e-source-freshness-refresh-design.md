# Phase 2E Design - Source Freshness And Refresh Controls

## Goal

Make single-place reports feel more trustworthy by showing when they were generated, when source data was last updated when known, and giving users a clear way to refresh current or saved reports.

This phase should improve trust and lifecycle clarity without adding accounts, cloud sync, public sharing, compare refresh, or deeper data adapters.

## Scope

Phase 2E includes:

- Freshness metadata for single-place analysis and saved reports.
- A 7-day stale threshold for saved reports.
- Frontend freshness labels such as `Generated today`, `Generated 3 days ago`, and `Stale: generated 12 days ago`.
- Source-level `updated_at` display when a source status includes it.
- Refresh controls for the active single-place report.
- A backend saved-report refresh endpoint that overwrites the existing saved report row.
- Tests for stale/fresh calculations, refresh persistence, API behavior, and frontend label rendering.

Phase 2E excludes:

- Compare mode refresh.
- Public share URLs.
- PDF/image export.
- Accounts or cloud sync.
- Saved report version history.
- New external data providers.
- City open-data adapters.
- Real-time source freshness guarantees.

## Product Shape

The analysis panel should answer:

- "When was this report generated?"
- "Is this saved report stale?"
- "Can I refresh this report without creating a duplicate?"
- "Do any individual sources expose their own last-updated date?"

Freshness should appear near the existing trust layer: Confidence, Source support, and source statuses. It should not become a separate admin console.

The first version focuses on the active single-place report:

- Unsaved current analyses can be refreshed by re-running the most recent `/analyze` request.
- Saved reports can be refreshed through `POST /profiles/{id}/refresh`.
- Compare results do not get their own refresh controls in this phase.

## Freshness Rules

Use a 7-day stale threshold for saved reports.

Definitions:

- `generated_at`: the best available timestamp for when the active report was generated.
- `fresh`: generated less than 7 days ago.
- `stale`: generated 7 or more days ago.
- `unknown`: no generated timestamp is available.

For saved reports:

- Use `SavedProfile.updated_at` as the generated timestamp.
- `created_at` remains the original saved-row creation time.
- Refreshing a saved report updates `updated_at` and response JSON in the same row.

For unsaved current analyses:

- The frontend should use a local `generatedAt` timestamp captured when `/analyze` succeeds.
- If the user opens an older saved report, use the saved report's `updated_at` instead.
- If no timestamp is available, show a neutral `Generated time unknown` label.

Freshness labels should be plain-spoken:

- `Generated just now`
- `Generated today`
- `Generated 3 days ago`
- `Stale: generated 12 days ago`
- `Generated time unknown`

## Backend Design

Add a backend refresh flow for saved reports.

### Endpoint

```http
POST /profiles/{profile_id}/refresh
```

Response model:

```python
SavedProfile
```

Behavior:

1. Load the saved report by ID.
2. If missing, return 404 with `Saved profile not found.`
3. Reconstruct an `AnalyzeRequest` from the saved response.
4. Re-run `analyze_neighborhood()` through the existing public analysis path.
5. Overwrite the existing saved row's response JSON, place metadata, confidence, source statuses, and `updated_at`.
6. Return the updated saved report.

### Refresh Request Reconstruction

The saved `AnalyzeResponse` does not currently store the original request payload. Phase 2E should add enough local metadata to refresh safely.

Required approach:

- Add nullable request metadata to saved reports rather than to `AnalyzeResponse`.
- Store `analyze_request_json` in `saved_profiles`.
- New saves should persist the request payload when available.
- Existing saved reports without request metadata should refresh from saved place data:
  - Use saved `response.place.coordinates` when present.
  - Use saved `response.place.label` as `query`.
  - Use `generic_mode: true` as the safe fallback.

When the original request had `preference_profile_id`:

- If the preference profile still exists, refresh with that ID so current profile settings apply.
- If the preference profile no longer exists, fall back to the stored preference fields in the saved request if present.
- If neither exists, refresh in generic mode.

When the original request was generic:

- Refresh with `generic_mode: true`.

This keeps refresh safe and avoids accidentally using a different active profile than the one that generated the saved report.

### Storage

Add storage helpers:

- `update_saved_profile(profile_id, response, analyze_request=None) -> SavedProfile | None`
- `build_refresh_request(saved_profile) -> AnalyzeRequest`

SQLite migration should be additive:

- Add nullable `analyze_request_json` column if it does not exist.
- Existing saved reports continue to load.
- Missing request metadata falls back to saved place and generic mode.

## Frontend Design

Add a compact freshness component near Confidence and Source support, for example `Freshness.jsx`.

The component should show:

- Generated label.
- Fresh/stale/unknown state.
- Refresh button when a refresh handler is available.
- Source `updated_at` dates inside source rows when present.

Single-place profile behavior:

- Unsaved current analysis shows `Refresh analysis`.
- Saved report shows `Refresh report`.
- While refreshing, button text becomes `Refreshing...`.
- Refresh errors appear near the button and do not clear the existing report.

Saved reports list behavior is unchanged in Phase 2E. Freshness appears after a report is opened in the analysis panel.

Compare mode:

- No refresh changes in Phase 2E.
- Compare continues using its existing `Refresh Compare` action, which re-runs in-memory compare calls and does not update saved reports.

## Data Flow

### Unsaved Analysis Refresh

1. User analyzes a selected place.
2. Frontend records `generatedAt` when the response arrives.
3. User clicks `Refresh analysis`.
4. Frontend reuses the last analyze payload.
5. On success, replace the active response and update `generatedAt`.
6. On failure, keep the existing response and show an error.

### Saved Report Refresh

1. User opens a saved report.
2. Frontend receives `SavedProfile` with `updated_at`.
3. Freshness UI marks it fresh/stale based on `updated_at`.
4. User clicks `Refresh report`.
5. Frontend calls `POST /profiles/{id}/refresh`.
6. Backend reconstructs the request, re-runs analysis, updates the same row, and returns the updated saved report.
7. Frontend replaces the active response, saved profile metadata, and saved reports list.

## Error Handling

Refresh failures should be non-destructive:

- If refresh fails, keep the existing report visible.
- Show a concise error near the freshness control.
- If saved report refresh returns 404, show `Saved report was not found.`
- If a preference profile referenced by old metadata is missing, backend should fall back safely rather than fail the refresh.
- If source adapters fail during refresh, the normal partial-results behavior applies and the refreshed report may still be saved with low confidence.

## Privacy And Safety

Refresh metadata must not store API keys, raw provider payloads, prompts, hidden provider responses, or private credentials.

Storing the analyze request payload is acceptable if it only contains:

- Place query and coordinates.
- Neutral preference fields.
- `generic_mode`.
- Optional `preference_profile_id`.

Freeform preference profile notes should remain local-only and should not be sent to OpenAI as part of this phase.

All existing fair-housing guardrails remain in place.

## Testing

Backend tests should cover:

- Freshness helper marks reports stale at 7 days.
- Freshness helper handles unknown timestamps.
- Saving a report can persist analyze request metadata when provided.
- Existing saved reports without request metadata still load.
- Updating a saved report overwrites the existing row and changes `updated_at`.
- `POST /profiles/{id}/refresh` returns 404 for a missing report.
- Refreshing a generic saved report re-runs generic analysis.
- Refreshing a profile-backed report uses the saved `preference_profile_id` when it still exists.
- Refreshing a profile-backed report falls back safely if the preference profile was deleted.

Frontend tests or source-contract checks should cover:

- Freshness label formatting for today, N days, stale, and unknown.
- Profile renders freshness near Confidence/Source support.
- Saved reports show `Refresh report`.
- Unsaved current analyses show `Refresh analysis`.
- Refresh errors do not remove the visible report.
- Source rows display `updated_at` when present.

Manual verification should cover:

- Analyze a new unsaved place and refresh it.
- Save a report, reopen it, and refresh the saved report.
- Confirm the saved report keeps the same ID after refresh.
- Confirm `updated_at` changes after refresh.
- Confirm a stale saved report displays as stale.
- Confirm source-level updated dates render when present.
- Confirm failed refresh keeps the old report visible.

## Acceptance Criteria

- Single-place reports show generated/freshness status.
- Saved reports become stale after 7 days.
- Current unsaved analyses can be refreshed without saving.
- Saved reports can be refreshed in place through `POST /profiles/{id}/refresh`.
- Refreshing a saved report overwrites the same row and updates `updated_at`.
- Source statuses show `updated_at` when available.
- Existing saved reports without request metadata continue to load.
- Refresh failures do not clear the current visible report.
- Compare mode refresh is left unchanged.
