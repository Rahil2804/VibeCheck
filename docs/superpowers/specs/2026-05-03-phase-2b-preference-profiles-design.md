# Phase 2B Design - Reusable Preference Profiles

## Goal

Add multiple reusable preference profiles so VibeCheck can evaluate every searched neighborhood against the selected user's lifestyle needs. This changes the current one-off questionnaire into saved local user profiles while preserving the map-first search experience.

Phase 2B should make the app feel more personal without adding accounts, hosted storage, public sharing, or a non-SQLite database.

This revised design moves preference profiles out of the selected-location result flow. A preference profile is the user's reusable analysis lens: who they are and what they care about. The selected neighborhood result panel should focus on the place and its source-aware analysis, not on profile management.

## Scope

Phase 2B includes:

- Multiple named preference profiles stored in local SQLite.
- A compact app-level active-profile control in the top bar.
- A Stitch-inspired lifestyle profile workspace for create, edit, delete, select, and default controls.
- Create, edit, delete, list, and default-profile controls.
- Expanded fair-housing-safe preference fields.
- Optional commute anchor storage for later commute scoring.
- Backend support for analyzing with `preference_profile_id`.
- Tests for storage, API behavior, and analyze/profile integration.
- A frontend flow where generic analysis is the default when no saved profile is active.

Phase 2B excludes:

- Login, cloud sync, multi-user hosted persistence, or Postgres.
- Real commute-time scoring or routing APIs.
- Public share URLs.
- Compare mode.
- Sending freeform user notes to OpenAI.
- Making the AI synthesis appear deeper by prompt changes alone; later phases should improve analysis quality through richer data sources and provenance.

## Product Shape

Use a compact active-profile lens in the top bar and a dedicated profile workspace for management. The first screen should still prioritize the map and search, but the selected profile appears before or beside the address search as an app-level control, for example "Active profile: Rahil" or "Active profile: Generic".

The default shell should feel close to the Stitch "Map Landing" and "Neighborhood Analysis" screens:

- A top bar contains the VibeCheck brand, active profile control, address/place search, saved reports entry, and small utility controls.
- The map remains the canvas.
- The right-side analysis panel appears for location and result states, not for profile management.
- Profile management opens as a dedicated "Lifestyle Profile" workspace over or beside the map, similar to the Stitch profile management screen.

Users can manage profiles from the lifestyle profile workspace:

- Create a new profile.
- Edit the selected profile.
- Choose another profile.
- Mark one profile as default.
- Delete a profile, including the only profile.

If no preference profile exists, the app should still be usable. The active profile control should show "Generic" and allow immediate address search. It should also provide a clear path to create a lifestyle profile without forcing setup.

The result panel should show the active analysis lens as read-only context, such as "Analyzed for Rahil" or "Generic neighborhood check." It should not contain profile creation, editing, defaulting, deletion, or the full preference questionnaire.

## Data Model

Add a new SQLite table named `preference_profiles`. It is separate from the existing `saved_profiles` table, which stores saved neighborhood reports.

Each preference profile stores:

- `id`: generated string ID.
- `name`: user-visible profile name.
- `car_reliance`: existing neutral preference enum.
- `energy_preference`: existing neutral preference enum.
- `top_priority`: existing neutral preference enum.
- `budget_sensitivity`: existing neutral preference enum.
- `generic_mode`: whether this profile intentionally skips personalized scoring.
- `commute_anchor_label`: optional work, school, or other destination label.
- `commute_anchor_lat`: optional latitude for the commute anchor.
- `commute_anchor_lng`: optional longitude for the commute anchor.
- `max_monthly_rent`: optional numeric budget signal.
- `must_haves`: JSON list of neutral lifestyle categories.
- `deal_breakers`: JSON list of neutral lifestyle categories.
- `notes`: optional local-only text.
- `is_default`: one profile should be the default when profiles exist.
- `created_at` and `updated_at`: UTC ISO timestamps.

Allowed `must_haves` and `deal_breakers` should use neutral categories only:

- `transit`
- `walkability`
- `parks`
- `groceries`
- `restaurants`
- `quiet`
- `social_scene`
- `lower_rent_pressure`

Do not add protected-class or proxy fields such as family status, schools, religion, race, ethnicity, disability, sex, national origin, or age-targeted recommendations.

## Backend API

Add these endpoints:

- `POST /preference-profiles`: create a preference profile.
- `GET /preference-profiles`: list profiles, default first and then recently updated.
- `GET /preference-profiles/{profile_id}`: return one profile.
- `PUT /preference-profiles/{profile_id}`: update a profile.
- `DELETE /preference-profiles/{profile_id}`: delete a profile.
- `POST /preference-profiles/{profile_id}/default`: mark a profile as the default.

Add `preference_profile_id` to `AnalyzeRequest`. The request should continue to accept raw `preferences` and `generic_mode` for backwards compatibility.

Analyze resolution order:

1. If `preference_profile_id` is provided, load that profile and use its preferences and generic mode.
2. If no profile ID is provided, use the raw `preferences` and `generic_mode` fields already supported.
3. If the selected profile is missing, return a clear `404` instead of silently falling back to another profile.

For Phase 2B, commute anchor and expanded fields are stored and returned, but only the existing preference fields and `generic_mode` affect scoring. `max_monthly_rent`, `must_haves`, and `deal_breakers` may be displayed in the UI, but should not change scoring until a later scoring-design pass adds tests and explainable rules.

## Frontend Flow

Move preference selection to the app shell before address selection. The active profile is independent from the selected place and persists across searches.

Expected behavior:

- On app load, fetch preference profiles.
- Select the default profile automatically when one exists.
- If no saved profile is selected, show "Generic" as the active analysis lens.
- Allow search and analysis immediately in generic mode.
- Show the active profile control in the top bar before or beside the location search.
- Open a dedicated Stitch-inspired lifestyle profile workspace from the active profile control.
- Let profile selection, creation, editing, deletion, and defaulting work without a selected place.
- When analyzing with a saved profile, send `preference_profile_id` instead of duplicating profile data.
- When analyzing generically, send no `preference_profile_id` and use `generic_mode: true`.
- Keep preference fields inside the profile workspace rather than in the selected-location analysis flow.
- The analysis panel should render selected location, analyze action, loading/error states, results, confidence, sources, and saved-report actions only.
- Keep saved neighborhood reports visible as reports, not user preference profiles.

The UI should rename user-facing saved neighborhood copy where useful to reduce confusion. Existing "Save profile" copy should become "Save report" or "Save neighborhood report".

### Component Direction

- `App.jsx` owns active profile, selected place, current workspace/view mode, and analyze payload.
- The top bar replaces the current scattered search/profile placement with a single app-level control strip.
- `PreferenceProfiles.jsx` becomes the lifestyle profile workspace rather than an inline analysis-panel widget.
- `Questionnaire.jsx` should either be removed from the active address flow or reused internally by profile-edit sections.
- `Profile.jsx` remains focused on neighborhood result rendering.
- `SavedProfiles.jsx` remains focused on saved neighborhood reports.

### AI Analysis Framing

The UI should avoid implying that the AI can deeply analyze beyond the normalized source payload. The result panel should frame output as source-aware neighborhood analysis with visible confidence, caveats, and source statuses. Later phases should improve perceived and actual analysis depth by adding richer source adapters and provenance, not by simply changing prompt copy.

## Error Handling

If preference profile list loading fails, show a non-blocking message and keep map/search/analyze usable in generic mode.

If creating, updating, deleting, or setting a default profile fails, show a local error near the profile controls. Do not clear the current neighborhood result.

If a selected profile is deleted, clear the selection and fall back to the generic analysis lens. If another default exists, select it.

Deleting the only profile is allowed. The app returns to the no-profile state.

## Privacy And Safety

Preference profiles are local-only in Phase 2B. SQLite may store the preferences and notes because they are user-entered local app state, but it must not store API keys, raw provider credentials, raw OpenAI prompts, or hidden provider payloads.

Freeform notes are local-only and should not be sent to OpenAI in Phase 2B. This avoids accidental personal-sensitive input affecting generated neighborhood claims before there is a separate prompt and safety design.

Fit scoring must continue to use only neutral preference inputs and non-protected neighborhood signals.

## Testing

Backend tests should cover:

- Creating, listing, reading, updating, deleting, and defaulting preference profiles.
- Exactly one default profile when profiles exist and a default is set.
- JSON list validation for `must_haves` and `deal_breakers`.
- `AnalyzeRequest` accepting `preference_profile_id`.
- `POST /analyze` using a stored profile's preferences.
- `POST /analyze` returning `404` for a missing `preference_profile_id`.
- Existing raw-preference analyze requests still working.

Frontend verification should cover:

- Profiles load on app startup.
- The default profile is selected automatically.
- Generic mode is available before any profile exists.
- Profile management works without a selected place.
- Selecting a profile updates the app-level active profile lens.
- Creating or editing a profile updates the selected profile.
- Analyze sends `preference_profile_id` when a saved profile is active.
- Generic analysis sends no `preference_profile_id`.
- The analysis panel renders no profile management controls.
- The frontend build still passes.

## Acceptance Criteria

- Users can create multiple named preference profiles locally.
- Users can switch between profiles without losing the map-first search flow.
- Users can select or create a preference profile before entering/selecting an address.
- A selected profile is applied to neighborhood analysis.
- Generic analysis runs when no saved profile is selected.
- The selected-location analysis panel focuses on location, results, confidence, sources, and saved reports.
- Profile management is not embedded in the result panel.
- The existing saved-neighborhood-report flow still works.
- Phase 2B does not introduce accounts, cloud persistence, share URLs, compare mode, or commute routing.
- `PLAN.md` can mark the preference-profile slice complete after implementation, leaving compare mode and provenance as the next Phase 2 work.
