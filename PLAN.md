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
- [x] Toronto cycling-network and Bike Share station snapshot with official protected/total network scoring; station counts remain informational.
- [x] Toronto annual all-collision history for the latest five complete years plus daily KSI events, with participant rows deduplicated by collision ID and separate 1 km counts/date windows.
- [x] RentSafeTO registration and latest-evaluation evidence with conservative normalized civic-address/range matching, explicit no-match/ambiguous states, and no nearest/fuzzy fallback.
- [x] Partition-level retrieval/data-through dates and 30/45-day/18-month freshness rules for KSI, RentSafeTO, and annual collision history.
- [x] Atomic `--only road-buildings` refresh upgrades or copies the last valid artifact and preserves it on any download, normalization, checksum, validation, or size-budget failure.
- [x] Cycling available for every resolved address: official Toronto geometry first and a labelled OSM fallback elsewhere or on partition failure, using one common network-length formula.
- [x] Shared versioned Overpass neighbourhood query coalesces access/cycling work to one request per address, with endpoint failover, cooldowns, a 24-hour fresh cache, and a seven-day stale fallback.
- [x] OSM cycleway normalization covers dedicated paths, tracks, painted/shared lanes, side-specific tags, access exclusions, way deduplication, 1 km circle clipping, and informational bicycle-parking counts.
- [x] Cycling works as a top priority, important signal, non-negotiable, compare row, evidence card, and saved-report tier; OSM fit effects use reduced strength and never fail a non-negotiable.
- [x] Transit removed from walkability to prevent double-counting.
- [x] Daily-driving and quiet preferences explicitly stored but unscored; weak walking/transit is not rewarded as a driving proxy.
- [x] Source metadata (`edition`, `scope`, `source_url`, `stale`), typed evidence contexts, `analysis_version`, and `snapshot_id` added compatibly.
- [x] Preference-profile migration for nullable rental unit size; existing IDs and saved JSON remain readable.
- [x] Immutable saved-report lens and snapshot context preserved across reopen and refresh.
- [x] `/health` and `python -m backend.doctor` provide secret-free Mapbox, optional OpenAI, snapshot, and SQLite checks.
- [x] Opt-in doctor checks for live Overpass and OpenAI; normal health never performs remote or paid requests.
- [x] Overpass identifying user agent, official-source cache, secondary endpoint, temporary endpoint cooldown, and seven-day labelled stale fallback.
- [x] Evidence checks cover place, snapshot, geography, OSM access, Census, rent, local context, transit, cycling, collisions, exact-address building context, fit, and AI grounding with supported/fallback/stale/unavailable/error states.
- [x] Confidence derives from successful evidence quality and source diversity; zero evaluated fit factors return a nullable score and “Not enough evidence.”
- [x] Grounded structured OpenAI synthesis uses only allowlisted evidence, requires citation IDs, rejects unsupported numbers/prohibited claims, and cannot mutate deterministic metrics.
- [x] Dormant Reddit adapter and `praw` removed; `SourceName.REDDIT` retained only for legacy JSON.
- [x] Backend and frontend environment examples separated; legacy API-key variables removed from active configuration.
- [x] Repository secret scan and snapshot schema/checksum validation added to CI.
- [x] Windows CI validates snapshot readability, doctor output, SQLite setup, and local snapshot queries.
- [x] GTA-first responsive UI, CAD formatting, transit/cycling/rent/collision/building evidence cards, optional KSI map points, provenance, print, compare, saved-report summaries, and profile controls.
- [x] Collision/building evidence remains informational: it can affect confidence and grounded prose but never `VibeScores`, preference controls, or fit.
- [x] Backend snapshot/calendar/scoring/migration/collision/building/OSM-cycling fixtures and frontend component/Playwright coverage for matched, unmatched, mobile, compare, saved, print, keyboard, and accessibility states.
- [x] README documents setup, sources, editions, formulas, refresh process, licences, CAD behaviour, and limitations.

## Intentionally deferred

- [ ] Real-time transit arrivals, commute routing, and travel-time scoring.
- [ ] Live Bike Share availability.
- [ ] Additional official municipal cycling datasets outside Toronto (the labelled OSM fallback remains available meanwhile).
- [ ] Live rental listings or asking-rent estimates.
- [ ] Permit/address-point joins and development trajectory.
- [ ] Crime/policing data, safety rankings, school ratings, noise claims, flood risk, protected-class recommendations, and Reddit sentiment.
- [ ] Accounts, cloud sync, public share URLs, and production deployment.
