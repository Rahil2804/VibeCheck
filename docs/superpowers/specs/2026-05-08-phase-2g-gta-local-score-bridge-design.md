# Phase 2G Design - GTA Local Score Bridge

## Goal

Make the current VibeCheck UI feel more data-backed for Toronto/GTA places without redesigning the frontend. Phase 2G should keep the app experience complete and unchanged, while the backend quietly prioritizes Ontario/GTA local data and uses Toronto municipal parks/amenity signals to move supported score fields away from neutral `50` values.

This is a backend-focused slice. The current UI should continue to work as-is.

## Product Direction

VibeCheck should feel like a complete neighborhood analysis app, not a coverage demo. The app should not add prominent "best coverage" or "limited coverage" marketing copy in the main UI. Over time, more cities, provinces, and countries can be added behind the same analysis experience.

For now, implementation should prioritize:

- Toronto as the first deep local-data adapter.
- GTA/Ontario region detection as the routing layer for future municipal adapters.
- Honest source statuses and provenance when local data is unsupported or unavailable.
- No reuse of Toronto data outside Toronto.

## Current Context

Phase 2F added:

- `SourceName.LOCAL`.
- Ontario local source routing.
- A Toronto Open Data adapter.
- Toronto parks and community amenity normalization.
- Local source statuses and provenance.
- Deterministic pros/trajectory support from local data.

After the Toronto adapter repair, parks/amenity data can be returned for places such as Kensington Market. However, the visible score cards still often show neutral `50` values because:

- `backend/sources/access.py` currently returns placeholder access scores.
- `NeighborhoodProfile.vibe_scores` only exposes the existing UI fields: `walkability`, `transit_access`, `affordability`, `quiet`, and `social_scene`.
- Toronto local `parks_outdoors` is used in pros/provenance, but not yet bridged into visible scoring.

## Scope

Phase 2G includes:

- Backend-only changes, with no frontend code changes expected.
- A local score bridge that uses normalized Toronto local parks/amenity fields to influence existing `VibeScores`.
- Preference fit improvements for users who prioritize parks/outdoors, using backend data already available in the profile.
- Provenance updates so any score affected by local data cites local source fields.
- Region handling that treats Ontario/GTA as the near-term local-data priority without changing the main app UI.
- Tests for Toronto local data changing backed scores and unsupported areas staying neutral.

Phase 2G excludes:

- Frontend redesign.
- New visible score cards.
- Prominent UI copy about "best coverage."
- Permit/development scoring from Toronto active permits until the `GEO_ID` or address-point join is implemented.
- Full Pickering, Durham, York, Peel, Halton, or Hamilton municipal adapters.
- Crime, school, protected-class, demographic, or safety scoring.
- Claims that parks imply safety, affordability, or demographic fit.

## Backend Design

Add a small backend scoring bridge between normalized source data and `VibeScores`.

Recommended shape:

```text
source_data
  -> score signal resolver
  -> deterministic profile builder
  -> fit scorer
  -> provenance
```

The bridge should be a focused helper rather than a broad rewrite. It should answer:

- Which source fields support each visible score?
- Is the score genuinely supported or just a neutral fallback?
- Which fields should provenance cite?

Suggested module/function names:

```text
backend/score_signals.py
resolve_vibe_scores(source_data: dict[SourceName, dict]) -> VibeScores
resolve_score_support(source_data: dict[SourceName, dict]) -> dict[str, list[str]]
```

The existing `_build_profile` logic in `backend/pipeline.py` can call this helper instead of directly reading every score inline.

## Local Score Mapping

Toronto local parks/amenity data should influence only score meanings it can reasonably support.

Allowed mappings:

- `local.parks_outdoors` can modestly influence `walkability` because nearby parks and public facilities are everyday local destinations.
- `local.parks_count` and `local.community_amenities_count` can support the walkability/access explanation, but should not be treated as a complete walkability model.
- `local.parks_outdoors` can modestly influence `quiet` when there are several nearby parks/outdoor spaces, because it indicates access to calmer public space, not overall noise.
- `local.community_amenities_count` can modestly influence `social_scene` when public community facilities are nearby, but should not stand in for restaurants/nightlife.

Disallowed mappings:

- Local parks/amenities must not affect `affordability`.
- Local parks/amenities must not affect `transit_access`.
- Local parks/amenities must not imply safety.
- Toronto permit metadata must not affect scores until permit records can be spatially matched honestly.

Initial scoring should be conservative. A strong Toronto parks/amenity signal can move relevant scores above `50`, but should not produce extreme scores by itself. For example, local parks data can lift walkability-style access into the `60-75` range when strong, while transit and affordability remain neutral unless real source data supports them.

## Fit Scoring

Preference fit should become more meaningful for parks/outdoors users without requiring frontend changes.

If a user selects `parks_outdoors` as `top_priority`, the fit scorer should reward profiles where the backend has a supported local parks/outdoors signal.

Use a backend-compatible model extension:

- Add `parks_outdoors: int | None = None` to `VibeScores`.
- Keep the current frontend unchanged; `ScoreCards.jsx` renders only its existing label list, so the extra field is ignored visually unless a later UI slice chooses to show it.
- Use `profile.vibe_scores.parks_outdoors` in `score_fit` for parks/outdoors priority, must-have, and deal-breaker logic where applicable.

The user-facing fit explanation should make clear that the boost comes from parks/outdoors or public amenities, not generic walkability.

## Region Handling

The backend should treat Ontario/GTA as the current local-data focus.

Behavior:

- Toronto places use the Toronto adapter.
- Recognized GTA/Ontario municipalities without adapters return an honest empty local status.
- Non-Ontario places continue to analyze with generic sources and no local municipal data.
- The API does not reject outside-region searches.
- The app does not show a major UI warning or coverage banner.

Potential recognized GTA municipalities for routing/future adapters:

- Toronto
- Pickering, Ajax, Whitby, Oshawa, Clarington, Uxbridge, Scugog, Brock
- Markham, Vaughan, Richmond Hill, Newmarket, Aurora
- Mississauga, Brampton, Caledon
- Oakville, Burlington, Milton, Halton Hills

Phase 2G does not need adapters for those municipalities. It only needs routing to avoid accidental Toronto reuse and to leave clean extension points.

## Provenance

Any visible score that local data changes should cite local source fields.

Examples:

- `vibe.walkability`: cites `access.walkability` when access data exists, and can also cite `local.parks_outdoors`, `local.parks_count`, and `local.community_amenities_count` when the local bridge influenced the score.
- `vibe.quiet`: can cite `local.parks_outdoors` when local parks/outdoors materially contributed.
- `vibe.social_scene`: can cite `local.community_amenities_count` when public community amenities contributed.
- `local.amenities`: remains as the dedicated local amenities provenance item.

If a score remains a fallback `50`, provenance should continue to label support as unavailable or inferred from thin data. It should not pretend neutral scores are measured.

## Error Handling

Local source failures should never block analysis.

Expected behavior:

- Toronto local success: scores may incorporate local parks/amenity signals.
- Toronto local empty: scores fall back to existing neutral behavior.
- Toronto local error: analysis still returns, source status reports a sanitized local error, and scores do not use partial/untrusted local data.
- Unsupported GTA/Ontario municipality: local source status is empty, no Toronto data is used, and scores remain based on other available sources.
- Non-Ontario place: local source is unsupported/empty, and generic analysis still works.

## Testing

Backend tests should cover:

- Toronto local parks/amenity data can raise supported existing score fields above neutral.
- Transit and affordability remain neutral when only local parks/amenities are available.
- Parks/outdoors top-priority preferences can affect fit explanation/score when local parks data exists.
- Provenance cites local fields for any score changed by the local bridge.
- Unsupported Ontario/GTA municipalities do not reuse Toronto data.
- Non-Ontario places keep working.
- Local source errors do not change scores or block responses.

Existing frontend tests should continue to pass without redesign work.

## Acceptance Criteria

- A Toronto result with meaningful local parks/amenity data no longer shows all visible score cards as `50` solely because access/housing/census/reddit are thin.
- Score changes are conservative and source-backed.
- Unsupported regions still analyze without crashes.
- The current UI remains visually unchanged.
- No API keys, raw municipal payload rows, or provider credentials are stored or exposed.
- README and `PLAN.md` reflect that near-term data depth is Ontario/GTA-first internally while the app remains a general neighborhood analysis experience.
