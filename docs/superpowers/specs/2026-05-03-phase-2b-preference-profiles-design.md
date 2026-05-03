# Phase 2B Design - Reusable Preference Profiles

## Goal

Add multiple reusable preference profiles so VibeCheck can evaluate every searched neighborhood against the selected user's lifestyle needs. This changes the current one-off questionnaire into saved local user profiles while preserving the map-first search experience.

Phase 2B should make the app feel more personal without adding accounts, hosted storage, public sharing, or a non-SQLite database.

## Scope

Phase 2B includes:

- Multiple named preference profiles stored in local SQLite.
- A compact profile switcher in the frontend.
- Create, edit, delete, list, and default-profile controls.
- Expanded fair-housing-safe preference fields.
- Optional commute anchor storage for later commute scoring.
- Backend support for analyzing with `preference_profile_id`.
- Tests for storage, API behavior, and analyze/profile integration.

Phase 2B excludes:

- Login, cloud sync, multi-user hosted persistence, or Postgres.
- Real commute-time scoring or routing APIs.
- Public share URLs.
- Compare mode.
- Sending freeform user notes to OpenAI.

## Product Shape

Use a lightweight profile switcher rather than a full profile workspace or wizard. The first screen should still prioritize the map, search, and neighborhood result. The selected profile appears as a compact control near the search/preferences area, for example "Profile: Rahil".

Users can manage profiles from that switcher:

- Create a new profile.
- Edit the selected profile.
- Choose another profile.
- Mark one profile as default.
- Delete a profile, including the only profile.

If no preference profile exists, the app should still be usable. It should show a small create-profile path and allow generic analysis without forcing setup.

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

Add a compact profile selector near the current questionnaire/search controls.

Expected behavior:

- On app load, fetch preference profiles.
- Select the default profile automatically when one exists.
- Populate the questionnaire from the selected profile.
- When analyzing, send `preference_profile_id` instead of duplicating profile data when a saved profile is selected.
- Allow generic analysis when no profile is selected.
- Create and edit profiles in a small dialog or focused inline panel.
- Keep saved neighborhood reports visible as reports, not user preference profiles.

The UI should rename user-facing saved neighborhood copy where useful to reduce confusion. Existing "Save profile" copy can become "Save neighborhood report" or a similarly clear label during implementation if the touched components make that practical.

## Error Handling

If preference profile list loading fails, show a non-blocking message and keep map/search/analyze usable with raw preferences or generic mode.

If creating, updating, deleting, or setting a default profile fails, show a local error near the profile controls. Do not clear the current neighborhood result.

If a selected profile is deleted, clear the selection and fall back to generic/raw preferences. If another default exists, select it.

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
- Selecting a profile populates the questionnaire.
- Creating or editing a profile updates the selected profile.
- Analyze sends `preference_profile_id` when a saved profile is selected.
- The frontend build still passes.

## Acceptance Criteria

- Users can create multiple named preference profiles locally.
- Users can switch between profiles without losing the map-first search flow.
- A selected profile is applied to neighborhood analysis.
- The existing saved-neighborhood-report flow still works.
- Generic analysis remains possible.
- Phase 2B does not introduce accounts, cloud persistence, share URLs, compare mode, or commute routing.
- `PLAN.md` can mark the preference-profile slice complete after implementation, leaving compare mode and provenance as the next Phase 2 work.
