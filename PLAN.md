# VibeCheck GTA Portfolio MVP

This checklist records implemented, verified behaviour rather than planned claims.

## Complete

- [x] GTA coverage tiers and nullable metrics; unsupported evidence is never emitted as 50.
- [x] Bundled GTA SQLite snapshot below 50 MB with schema version, snapshot ID, checksums, source URLs, retrieval dates, licences, and GTFS validity metadata.
- [x] Atomic `python -m scripts.refresh_gta_snapshot` builder that retains the last valid artifact on failure.
- [x] Snapshot staging inherits normal Windows directory ACLs; doctor validates user readability, checksums, SQLite integrity, required tables, row counts, and agency feed dates.
- [x] Official Statistics Canada boundaries and neutral 2021 Census fields bundled for 25 GTA census subdivisions, plus all 158 Toronto neighbourhood profiles.
- [x] Canonical coordinate geography resolves former municipality labels such as East York to Toronto and uses the resulting CSD ID for CMHC joins.
- [x] Static regular-weekday GTFS normalization for TTC, GO, UP Express, MiWay, Brampton Transit, YRT, and Durham Region Transit.
- [x] Calendar exceptions, service times after midnight, stop/route/direction deduplication, feed expiry, agency coverage, and labelled OSM fallback handling.
- [x] Scheduled-transit scoring from proximity, peak frequency, route diversity, and rapid/regional access.
- [x] CMHC 2025 purpose-built rent benchmarks for studio, 1-bedroom, 2-bedroom, and 3-bedroom-plus units, joined by Statistics Canada census subdivision.
- [x] CMHC quality/suppression fields and exact reporting-geography scope preserved in API and UI.
- [x] Rent ceilings skip missing or wrong-size benchmarks and never substitute historical neighbourhood shelter cost.
- [x] Toronto cycling-network and Bike Share station snapshot with protected/total network and station-count scoring.
- [x] Cycling available as a score, top priority, important signal, non-negotiable, compare row, and evidence card.
- [x] Transit removed from walkability to prevent double-counting.
- [x] Daily-driving and quiet preferences explicitly stored but unscored; weak walking/transit is not rewarded as a driving proxy.
- [x] Source metadata (`edition`, `scope`, `source_url`, `stale`), typed evidence contexts, `analysis_version`, and `snapshot_id` added compatibly.
- [x] Preference-profile migration for nullable rental unit size; existing IDs and saved JSON remain readable.
- [x] Immutable saved-report lens and snapshot context preserved across reopen and refresh.
- [x] `/health` and `python -m backend.doctor` provide secret-free Mapbox, optional OpenAI, snapshot, and SQLite checks.
- [x] Opt-in doctor checks for live Overpass and OpenAI; normal health never performs remote or paid requests.
- [x] Overpass identifying user agent, official-source cache, secondary endpoint, temporary endpoint cooldown, and seven-day labelled stale fallback.
- [x] Evidence checks cover place, snapshot, geography, OSM access, Census, rent, local context, transit, cycling, fit, and AI grounding with supported/fallback/stale/unavailable/error states.
- [x] Confidence derives from successful evidence quality and source diversity; zero evaluated fit factors return a nullable score and “Not enough evidence.”
- [x] Grounded structured OpenAI synthesis uses only allowlisted evidence, requires citation IDs, rejects unsupported numbers/prohibited claims, and cannot mutate deterministic metrics.
- [x] Dormant Reddit adapter and `praw` removed; `SourceName.REDDIT` retained only for legacy JSON.
- [x] Backend and frontend environment examples separated; legacy API-key variables removed from active configuration.
- [x] Repository secret scan and snapshot schema/checksum validation added to CI.
- [x] Windows CI validates snapshot readability, doctor output, SQLite setup, and local snapshot queries.
- [x] GTA-first responsive UI, CAD formatting, scheduled transit/cycling/rent evidence cards, provenance, print, compare, and profile controls.
- [x] Backend snapshot/calendar/scoring/migration fixtures and frontend component/Playwright coverage for new evidence.
- [x] README documents setup, sources, editions, formulas, refresh process, licences, CAD behaviour, and limitations.

## Intentionally deferred

- [ ] Real-time transit arrivals, commute routing, and travel-time scoring.
- [ ] Live Bike Share availability.
- [ ] Additional municipal cycling datasets outside Toronto.
- [ ] Live rental listings or asking-rent estimates.
- [ ] Permit/address-point joins and development trajectory.
- [ ] Crime/safety, school ratings, noise claims, flood risk, protected-class recommendations, and Reddit sentiment.
- [ ] Accounts, cloud sync, public share URLs, and production deployment.
