# Phase 2D Design - Compare Mode

## Goal

Add a dedicated compare workflow so users can evaluate 2-4 candidate neighborhoods through the same lifestyle lens without needing to save reports first.

Compare mode should make VibeCheck feel more useful for real apartment-hunting decisions: the user chooses who they are or what they care about, adds a few places, and sees which place best matches the selected lens. The first version should reuse the existing `/analyze` pipeline instead of adding a new backend compare contract.

## Scope

Phase 2D includes:

- A top-level Compare entry point in the app chrome.
- A dedicated compare workspace for 2-4 ad hoc address/place slots.
- Compare analysis using the current selected preference profile or Generic mode.
- Frontend orchestration of multiple existing `/analyze` calls.
- Column-card results for each compared place.
- A compact summary strip for standout results once enough analyses succeed.
- Per-place loading, error, retry, and result states.
- Source confidence and provenance summaries in each compared place card.
- Tests for compare state, payload construction, slot limits, and source-contract rendering.

Phase 2D excludes:

- Requiring saved reports before comparison.
- A new backend `POST /compare` endpoint.
- Public share URLs.
- PDF/image export.
- Accounts or cloud sync.
- City coverage matrix work.
- New source adapters or deeper data collection.
- Different preference profiles per compared place.

## Product Shape

Compare mode is opened from a **Compare** button in the top rail. It should feel like a peer to the normal selected-location analysis workflow, not a secondary saved-report tool.

The compare workspace should answer:

- "Which of these places fits my selected profile best?"
- "Where are the tradeoffs across walkability, transit, affordability, quiet, and social energy?"
- "Which result has weaker data confidence or source support?"

The active analysis lens is inherited from the main app:

- If a saved preference profile is selected, all compared places use that profile.
- If Generic mode is selected, all compared places run as generic neighborhood checks.
- The compare workspace shows the active lens clearly.
- Profile management stays outside compare mode.

Phase 2D does not add save-from-compare controls. Users should not need to save a place before comparing it, and saving can be revisited after the compare workflow itself is stable.

## User Flow

1. User selects a saved preference profile or Generic mode from the existing profile controls.
2. User clicks **Compare** in the top rail.
3. Compare workspace opens with two empty required place slots and an optional add-slot control.
4. User searches/selects 2-4 places.
5. User clicks **Analyze Compare** once at least two slots are valid.
6. Frontend sends one `/analyze` request per selected place.
7. Results render as one column card per place.
8. User can retry failed places, remove places, add places up to four, or refresh the comparison.

Returning to the main map workflow should preserve the currently selected preference profile and the previously active single-place analysis result.

## UI Layout

Use **Column Cards** for v1.

### Compare Header

The header should include:

- Title: `Compare places`
- Active lens label, such as `Rahil profile` or `Generic neighborhood check`
- Slot count, such as `3 of 4 places`
- Primary action: `Analyze Compare` or `Refresh Compare`
- Close/back control to return to the map-first workflow

### Place Slots

Place slots should:

- Support 2 required slots.
- Allow adding up to 4 slots.
- Use the existing Mapbox search/place selection behavior where practical.
- Show selected place label and a clear remove action.
- Prevent analysis until at least two slots have selected places.
- Keep layout stable when a slot is loading or selected.

### Summary Strip

Once at least two places have successful results, show a compact summary strip above the cards.

Initial highlights:

- Best fit score, if fit exists.
- Best walkability score.
- Best transit access score.
- Lowest confidence risk, based on confidence level and missing-source count.

If Generic mode has no fit scores, omit best-fit and keep the other highlights.

The summary strip should be helpful but not overconfident. It should not claim an overall winner when data is too thin or fewer than two results succeeded.

### Result Cards

Each place card should show:

- Place label.
- Fit score and explanation when available.
- Vibe score mini-bars or compact score rows.
- Top pros and cons.
- Confidence level and caveats.
- Compact source support/provenance summary.
- Per-place source status summary.
- Retry action if that place failed.

Cards should be easy to scan side by side on desktop and stack cleanly on mobile.

## Data Flow

Phase 2D should use frontend orchestration.

For each selected place, the frontend builds an existing analyze payload:

```json
{
  "query": "Selected place label",
  "coordinates": {
    "lat": 30.2636,
    "lng": -97.7114
  },
  "preferences": {},
  "generic_mode": false,
  "preference_profile_id": "profile-id"
}
```

Payload rules:

- Use coordinates when available.
- Keep query/label as context when available.
- If a saved preference profile is active, include `preference_profile_id` and the matching preference fields already used by the normal analysis flow.
- If Generic mode is active, set `generic_mode: true` and omit `preference_profile_id`.
- Do not send different profiles for different compared places.

Requests may run concurrently. Each slot should track its own `idle`, `loading`, `success`, or `error` state so one failure does not block the whole comparison.

No backend model change is required for v1. A future phase can replace the frontend fan-out with a backend `POST /compare` endpoint if compare needs caching, persisted comparisons, batch source sharing, or server-side ranking.

## State And Components

Recommended frontend boundaries:

- `CompareMode.jsx`: owns compare workspace layout and slot/result state.
- `ComparePlaceSearch.jsx`: wraps place search for a compare slot.
- `CompareSummary.jsx`: computes and renders top highlights from successful results.
- `CompareResultCard.jsx`: renders one analyzed place result.
- `compareUtils.js`: pure helpers for slot limits, payload construction, successful result filtering, and highlight selection.

The exact file names can follow existing project conventions during implementation, but compare-specific state should stay out of `Profile.jsx`.

`App.jsx` should own whether the app is in map-analysis mode or compare mode, because the top rail controls mode selection and the active profile lens already lives near app-level state.

## Error Handling

Compare mode should degrade per place:

- If one `/analyze` call fails, that card shows an error and retry action.
- Successful results remain visible.
- Summary strip uses only successful results.
- If fewer than two places succeed, summary strip stays hidden and the UI asks for another valid result.
- If the active profile is deleted while compare mode is open, the existing profile-selection fallback rules should apply.
- If Mapbox token is missing, place search should show the same missing-token behavior as the main flow.

The UI should avoid blocking the whole compare view on a single failed source or failed place.

## Privacy And Safety

Compare mode must preserve the existing fair-housing guardrails:

- Fit scoring uses only neutral lifestyle preferences and non-protected neighborhood signals.
- Demographics remain display context only.
- Do not rank or describe places as good or bad for protected groups.
- Do not introduce safety/crime or school claims.
- Do not expose API keys, raw provider payloads, prompts, or private profile notes.

Compare language should frame results as "better match for this selected lens" rather than as universal neighborhood quality.

## Testing

Frontend tests or source-contract checks should cover:

- Top rail exposes a Compare entry point.
- Compare mode supports 2-4 slots and prevents adding a fifth.
- Analysis is disabled until at least two places are selected.
- Compare payloads reuse current saved profile or Generic mode.
- One failed analysis result does not hide successful cards.
- Summary helpers select best fit, best walkability, best transit, and lowest confidence risk from successful results.
- Generic mode omits best-fit summary when no fit scores exist.
- Result cards render confidence/source support without raw JSON.

Backend tests are not required for v1 unless implementation changes backend behavior. Existing `/analyze` tests continue to cover the analysis contract.

Manual verification should cover:

- Compare two places with a saved preference profile.
- Compare three or four places with a saved preference profile.
- Compare two places in Generic mode.
- Retry one failed place without losing successful results.
- Remove a place and add another.
- Return from compare mode to the normal map-analysis flow.
- Mobile layout stacks cards and keeps controls reachable.

## Acceptance Criteria

- Users can open compare mode from the top rail.
- Users can add 2-4 ad hoc places without saving them first.
- Compare mode analyzes each selected place through the current profile or Generic lens.
- Results render as column cards with fit, vibe scores, pros/cons, confidence, and source support.
- Summary strip highlights useful differences without overclaiming when data is thin.
- One failed place does not break the whole comparison.
- No new backend compare endpoint is required.
- Existing single-place analysis, preference profiles, saved reports, CORS behavior, and source support UI continue working.
