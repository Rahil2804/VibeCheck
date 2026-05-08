# Phase 2F Design - Ontario Local Source Depth

## Goal

Add an Ontario/GTA local open-data source layer that makes neighborhood analysis feel more grounded in real municipal signals. Phase 2F should introduce a reusable regional adapter shape, implement Toronto first, and prepare the app for Durham/Pickering coverage later without pretending unsupported municipalities have deep data.

The first source families are:

- Toronto development and building permit activity.
- Toronto parks and public amenity access.

This phase should improve trajectory, pros/cons, source support, provenance, and synthesis quality. It should not add public sharing, crime/safety scoring, school scoring, or protected-class recommendations.

## Current Context

The backend currently runs source fetchers in parallel after Mapbox resolves a place. Existing source names are `mapbox`, `census`, `housing`, `reddit`, and `access`. Source fetchers return normalized dictionaries, and the pipeline feeds those dictionaries into deterministic profile fallback, provenance, confidence, and optional OpenAI synthesis.

That shape is good. Phase 2F should enrich the normalized source payload rather than expose raw municipal rows to the frontend or to saved report storage.

## External Data Direction

Toronto is the first implementation target because it has an official open-data portal and strong source coverage. The design is based on:

- City of Toronto Open Data Portal: https://open.toronto.ca/
- Open Government Licence - Toronto: https://open.toronto.ca/open-data-licence/
- Building Permits - Active Permits catalogue details: https://data.urbandatacentre.ca/en/catalogue/city-toronto-building-permits-active-permits

Toronto permits are useful as a development/change signal because they describe active building applications and permits. Parks and public amenity datasets should be selected during implementation from active Toronto Open Data resources; some older parks pages may be retired or split across resources, so the implementation plan should verify the exact current resources before coding the HTTP layer.

## Scope

Phase 2F includes:

- A new local source area, `SourceName.LOCAL = "local"`.
- Ontario/GTA place detection from the resolved `Place`.
- A reusable municipal adapter interface.
- Toronto as the first working municipal adapter.
- Normalized local source fields for development and amenities.
- Deterministic profile improvements from local data.
- Provenance entries for local trajectory and local amenities.
- Source status messages that distinguish Toronto coverage, unsupported Ontario municipalities, unsupported non-Ontario regions, empty results, and errors.
- Tests with mocked municipal responses and parser fixtures.
- No live open-data calls in unit tests.

Phase 2F excludes:

- Full Durham/Pickering adapter implementation.
- Public share URLs, image export, or PDF export.
- Crime/safety, schools, protected-class, family-status, or demographic preference claims.
- Real-time source freshness guarantees.
- Storing or displaying raw municipal payload rows.
- Making permits directly change personal fit scores.

## Architecture

Current flow:

```text
Mapbox place resolution
  -> census/housing/reddit/access
  -> confidence + provenance + deterministic profile + optional synthesis
```

Phase 2F flow:

```text
Mapbox place resolution
  -> region/local resolver
  -> census/housing/reddit/access/local
  -> confidence + provenance + deterministic profile + optional synthesis
```

The `local` source should run after the place is resolved because it needs the resolved city/province and coordinates. The pipeline should support fetchers that can receive the resolved `Place` without forcing every existing source adapter to change its public function signature. A wrapper or source context object is preferable to a broad refactor.

Recommended module shape:

```text
backend/sources/local.py
backend/sources/ontario/__init__.py
backend/sources/ontario/toronto.py
backend/sources/ontario/models.py
```

`local.py` should be the pipeline entrypoint. It decides whether a place is supported and delegates to the right regional adapter.

Toronto implementation should have two seams:

- A thin HTTP/download client for Toronto open-data resources.
- Pure parser/normalizer functions that accept fixture data and produce stable normalized fields.

The parser layer should receive the heaviest tests. The HTTP layer should stay small so endpoint changes are easier to repair.

## Normalized Local Shape

The local source should return a stable dictionary such as:

```json
{
  "coverage_area": "Toronto",
  "development_activity": 72,
  "recent_permits_count": 38,
  "major_project_count": 6,
  "parks_count": 12,
  "community_amenities_count": 5,
  "parks_outdoors": 78,
  "trajectory_signal": "rising",
  "summary": "Recent permit and parks signals are available from Toronto open data.",
  "updated_at": "2026-05-08"
}
```

Field meanings:

- `coverage_area`: municipality or regional adapter that produced the data.
- `development_activity`: 0-100 normalized estimate of nearby development/change activity.
- `recent_permits_count`: count of relevant nearby or recent permit records.
- `major_project_count`: count of higher-impact permit/development records where detectable.
- `parks_count`: count of nearby public parks or park-like assets.
- `community_amenities_count`: count of nearby public amenity/facility records.
- `parks_outdoors`: 0-100 normalized local parks/outdoors signal.
- `trajectory_signal`: `rising`, `stable`, or `uncertain`.
- `summary`: short source-owned explanation for deterministic fallback and synthesis.
- `updated_at`: best available source refresh date or checked date.

The API response should only expose normalized source data through profile text, provenance, and source statuses. It should not add raw rows to `AnalyzeResponse`.

## User-Facing Behavior

For Toronto places:

- The source status list includes `local`.
- The local source message says Toronto open data returned development and parks signals.
- Trajectory becomes less generic when development signals are present.
- Pros/cons can mention public parks, amenities, and development activity where supported.
- Provenance can cite local fields for trajectory and amenities.
- Optional synthesis receives local normalized data and can write richer claims while staying source-bound.

For Pickering, Durham, and Ontario places without an adapter:

- The app does not crash.
- No Toronto data is reused outside Toronto.
- The local source status is `empty`.
- The message explains that no local Ontario adapter is available yet for that municipality.
- Other sources still produce the best available profile.

For non-Ontario places:

- The local source returns `empty` or stays clearly unsupported.
- The message says no local open-data adapter is configured for that region.

No new major frontend panel is required in Phase 2F. Existing Confidence and Provenance UI should carry the new source support. A future coverage hint, such as "Local open-data coverage: Toronto," can be added later if the source panel does not make coverage clear enough.

## Deterministic Profile Behavior

The deterministic fallback should use local data carefully:

- `development_activity` and `trajectory_signal` can improve trajectory wording.
- `parks_count`, `community_amenities_count`, and `parks_outdoors` can improve pros/cons and parks/outdoors narrative.
- Local data should not directly change personal fit score in Phase 2F.
- Local permits should not be treated as affordability proof.
- Parks and amenities should not be treated as safety proof.

Example deterministic trajectory behavior:

- High development activity: "Local open-data signals suggest visible development/change activity nearby, based on active permit records."
- Low or missing development activity: "Local development signals are limited or unavailable, so trajectory remains uncertain."
- Unsupported municipality: "No local municipal adapter is available yet for this area."

## Provenance

Add local-aware provenance items. Existing items should continue to work.

Recommended additions:

- `trajectory`: can cite `local.development_activity`, `local.recent_permits_count`, and `local.trajectory_signal`.
- `local.amenities`: cites `local.parks_count`, `local.community_amenities_count`, and `local.parks_outdoors`.
- `overview`: includes `local` in its supported source set when local data exists.

If local data is empty or unsupported, provenance should say local support is unavailable because the source is empty or unsupported. It should not imply a negative condition about the neighborhood.

## Source Status And Freshness

The local source should set `SourceStatus.updated_at` when it has a reliable date.

Freshness rules:

- Prefer official dataset metadata refresh dates when available.
- If only fetch time is available, use it as a checked date and make the source message honest.
- If no reliable date exists, leave `updated_at` null.

Status behavior:

- Toronto data returned: `success`.
- Supported adapter but no relevant records: `empty`.
- Unsupported Ontario municipality: `empty`.
- Unsupported non-Ontario region: `empty`.
- Endpoint unavailable, timeout, parse failure, or schema surprise: `error` with a sanitized message.

The existing source freshness UI can show this `updated_at` alongside other sources.

## Safety And Interpretation Boundaries

Allowed interpretations:

- Building permits indicate local development/change activity.
- Many recent or active permits may indicate more visible local change or construction activity.
- Parks and amenities indicate public recreation and everyday amenity options.
- Missing local data means lower local-data coverage, not a negative neighborhood judgment.

Disallowed interpretations:

- Permits alone do not prove gentrification.
- Permits alone do not prove affordability direction.
- Parks or amenities do not imply safety.
- 311/service requests are out of scope for this phase.
- No crime, schools, protected-class, family-status, or demographic preference claims.

## Error Handling

Local source failures should never block analysis.

Required behaviors:

- Network timeout returns source status `error` and an empty local data dictionary.
- Parser failure returns source status `error` with a sanitized message.
- Unsupported municipality returns source status `empty`.
- Missing coordinates returns source status `empty`.
- Partial Toronto dataset failure should return whichever normalized family is available if feasible; otherwise `error`.
- The old profile remains visible when refreshing a saved report fails, consistent with Phase 2E.

## Testing Strategy

Backend tests:

- Unit test Ontario/Toronto place detection.
- Unit test Toronto permit parser with fixture records.
- Unit test Toronto parks/amenities parser with fixture records.
- Unit test normalization scores clamp to 0-100.
- Unit test unsupported Pickering/Durham behavior returns empty with a clear message.
- Unit test unsupported non-Ontario behavior returns empty.
- Pipeline test that local fetcher receives the resolved `Place`.
- Pipeline test that local success improves deterministic trajectory.
- Provenance test that local fields support trajectory and amenities claims.
- API test that a Toronto-style analysis includes local source status.
- No test should require live Toronto Open Data availability.

Frontend tests:

- Existing UI contract tests should still pass with an extra source.
- Add a contract test only if frontend copy or source rendering needs local-specific handling.

Manual checks:

- Toronto search shows local source support when backend fixtures or live dev data are available.
- Pickering search remains graceful and does not show Toronto data.
- Non-Ontario search remains graceful.
- Refreshing a saved Toronto report keeps the same saved report ID and updates source freshness.

## Documentation

After implementation:

- Update `README.md` to mention Ontario/Toronto local open-data depth.
- Update `PLAN.md` Phase 2 checklist with local source depth completion.
- Keep caveats clear that Durham/Pickering is prepared for but not fully implemented yet.

## Acceptance Criteria

- Toronto analyses can include normalized local development and parks/amenity signals.
- Unsupported Ontario municipalities degrade with honest empty source status.
- No raw municipal payload rows appear in `AnalyzeResponse`, saved report response JSON beyond existing normalized profile output, or frontend debug surfaces.
- Provenance can cite local support for trajectory and amenities.
- Deterministic fallback becomes more specific for Toronto when local data exists.
- OpenAI synthesis receives local normalized fields when configured.
- Backend tests and frontend build pass.
- Documentation reflects implemented behavior and limitations.
