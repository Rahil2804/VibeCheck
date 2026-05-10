# Phase 2H Design - GTA Daily Needs Access

## Goal

Replace the placeholder access source with a real no-new-key public/open-data access layer for Toronto/GTA neighborhoods. Phase 2H should make `walkability`, `transit_access`, `daily_needs`, `food_social`, `parks_outdoors`, and `nearby_categories` reflect nearby everyday destinations instead of static `50` and `0` fallback values.

This phase is backend-focused. The current UI should continue to render the same score cards and source/provenance panels.

## Product Direction

VibeCheck should continue to feel like a complete neighborhood analysis app while the data depth improves one source at a time. Paid APIs are out of scope for this phase. If public/open sources are slow, incomplete, or temporarily unavailable, the backend should degrade honestly instead of returning fake access scores.

The first implementation target is Toronto/GTA because that is the current product focus and the most useful personal testing region.

## Source Strategy

Use public/open data first:

- OpenStreetMap POI data through Overpass-style queries for broad GTA coverage.
- Existing Toronto municipal open data as a supplemental source where it is already normalized by the local adapter.

Do not add:

- Google Places.
- Paid POI providers.
- New API keys.
- Hosted geospatial infrastructure.

Public Overpass endpoints are shared infrastructure, so this phase must query conservatively:

- Small radius queries only.
- Short source timeouts.
- Bounded tag set.
- No full-city or province-wide downloads.
- No live external calls in unit tests.
- Clear error/empty source status if the public endpoint rejects or times out.

## Current Context

`backend/sources/access.py` currently returns placeholder data:

```json
{
  "walkability": 50,
  "transit_access": 50,
  "daily_needs": 50,
  "food_social": 50,
  "parks_outdoors": 50,
  "nearby_categories": {
    "groceries": 0,
    "parks": 0,
    "restaurants": 0,
    "transit": 0
  }
}
```

Phase 2G added `backend/score_signals.py`, so richer access data can flow into visible backend scores and provenance without a frontend redesign.

## Scope

Phase 2H includes:

- Convert `fetch_access_context` into a context-aware source that receives resolved coordinates.
- Query public OSM/Overpass-style POI data around the selected point.
- Normalize POIs into stable access categories.
- Produce conservative 0-100 scores for existing access fields.
- Update source statuses and provenance through existing mechanisms.
- Add parser/category/scoring tests with mocked payloads.
- Update docs to describe no-new-key GTA access scoring.

Phase 2H excludes:

- Frontend redesign.
- New score cards.
- New API keys.
- Paid POI providers.
- Full accessibility routing, travel time, sidewalks, or slope analysis.
- Exact walk-time isochrones.
- Safety, school, crime, or protected-class claims.
- Full municipal adapters outside Toronto.

## Normalized Access Shape

The access source should return:

```json
{
  "walkability": 72,
  "transit_access": 64,
  "daily_needs": 78,
  "food_social": 70,
  "parks_outdoors": 66,
  "nearby_categories": {
    "groceries": 3,
    "pharmacies": 2,
    "restaurants": 18,
    "cafes": 7,
    "transit": 9,
    "parks": 4,
    "libraries": 1,
    "community": 2
  },
  "summary": "Nearby public POI signals found groceries, pharmacies, restaurants, transit, and parks within the access radius.",
  "updated_at": "2026-05-10"
}
```

Field meanings:

- `walkability`: conservative everyday-destination access estimate from daily needs, food/social, parks, and services.
- `transit_access`: public transit stop/station count signal.
- `daily_needs`: grocery, pharmacy, library, and public-service access.
- `food_social`: restaurants, cafes, bars/pubs where tagged.
- `parks_outdoors`: parks, recreation grounds, playgrounds, and outdoor public amenities.
- `nearby_categories`: count of deduplicated nearby POIs by category.
- `summary`: short source-owned explanation for source status and synthesis.
- `updated_at`: checked date, because OSM query responses do not provide a simple authoritative dataset refresh date for the selected result set.

## Category Mapping

The implementation should start with a narrow, explainable tag mapping.

Daily needs:

- `shop=supermarket`
- `shop=convenience`
- `shop=grocery`
- `amenity=pharmacy`
- `amenity=library`

Food/social:

- `amenity=restaurant`
- `amenity=cafe`
- `amenity=bar`
- `amenity=pub`
- `amenity=fast_food`

Transit:

- `highway=bus_stop`
- `public_transport=platform`
- `public_transport=station`
- `railway=station`
- `railway=subway_entrance`
- `railway=tram_stop`

Parks/outdoors:

- `leisure=park`
- `leisure=garden`
- `leisure=playground`
- `leisure=recreation_ground`
- `landuse=recreation_ground`

Community/services:

- `amenity=community_centre`
- `amenity=townhall`
- `amenity=clinic`
- `amenity=doctors`

The parser should accept Overpass `node`, `way`, and `relation` elements. For ways/relations, use the returned `center` if present. Elements without usable coordinates can still count if they are inside the query radius, but they should not be returned as raw frontend payload.

## Query Design

Use coordinates from `SourceContext.place.coordinates`.

Recommended radius:

- Start with 1,200 meters.
- Keep the radius constant in Phase 2H.
- Do not use a full-city bounding box.

Recommended query shape:

```text
[out:json][timeout:6];
(
  node(around:1200, LAT, LNG)[shop~"^(supermarket|convenience|grocery)$"];
  way(around:1200, LAT, LNG)[shop~"^(supermarket|convenience|grocery)$"];
  node(around:1200, LAT, LNG)[amenity~"^(pharmacy|library|restaurant|cafe|bar|pub|fast_food|community_centre|townhall|clinic|doctors)$"];
  way(around:1200, LAT, LNG)[amenity~"^(pharmacy|library|restaurant|cafe|bar|pub|fast_food|community_centre|townhall|clinic|doctors)$"];
  node(around:1200, LAT, LNG)[highway="bus_stop"];
  node(around:1200, LAT, LNG)[public_transport~"^(platform|station)$"];
  node(around:1200, LAT, LNG)[railway~"^(station|subway_entrance|tram_stop)$"];
  way(around:1200, LAT, LNG)[leisure~"^(park|garden|playground|recreation_ground)$"];
  relation(around:1200, LAT, LNG)[leisure~"^(park|garden|playground|recreation_ground)$"];
  way(around:1200, LAT, LNG)[landuse="recreation_ground"];
  relation(around:1200, LAT, LNG)[landuse="recreation_ground"];
);
out center tags;
```

The implementation plan may tune syntax after testing against the Overpass QL parser, but the behavior should stay equivalent: bounded radius, narrow tags, JSON output, and no raw payload exposure.

## Scoring

Scores should be conservative and count-based.

Suggested initial normalizers:

- `daily_needs`: grocery count, pharmacy count, library/service count.
- `food_social`: restaurants/cafes/bars count.
- `transit_access`: transit stop/station count.
- `parks_outdoors`: parks/outdoor amenity count.
- `walkability`: weighted blend of `daily_needs`, `food_social`, `transit_access`, `parks_outdoors`, and community/services.

Example ranges:

- Successful query with no matching POIs: return valid low scores and zero category counts, not neutral fallback values.
- Sparse suburban signal: 45-60.
- Useful everyday access: 60-75.
- Dense mixed-use signal: 75-90.
- Avoid 95+ unless there is a very strong multi-category signal.

The source should distinguish:

- Successful query with low counts: valid low/medium scores.
- Failed query: error status, no scores.
- Missing coordinates: empty status, no scores.

## Data Flow

```text
Mapbox resolved place
  -> SourceContext(place coordinates)
  -> access source builds bounded public POI query
  -> HTTP client fetches JSON
  -> parser normalizes OSM elements into category counts
  -> scorer returns access fields
  -> score_signals uses access fields for visible scores
  -> provenance cites access fields
```

The access source should return a `SourceResult` so it can provide a useful message and checked date.

## Error Handling

Access source failures should never block analysis.

Expected behavior:

- Missing coordinates: `empty`, message says access lookup needs resolved coordinates.
- Overpass timeout: `error`, message sanitized by pipeline.
- Overpass rate limit/rejection: `error`, message sanitized by pipeline.
- Empty successful result: `success` with valid low scores and zero category counts, because the public query worked and found no nearby matching POIs.
- Parser surprise: `error` in tests if the parser cannot safely normalize the payload.

Do not store or expose raw OSM elements in `AnalyzeResponse` or saved reports.

## Attribution And Licensing

OSM data is open data under the Open Database License. VibeCheck should credit OpenStreetMap contributors in docs and, if OSM-derived access scoring becomes a prominent user-facing feature later, add appropriate in-app/source-panel attribution. Phase 2H can document attribution in README/PLAN because the current source panel already labels sources generically.

## Testing

Tests should cover:

- Category mapping for each supported tag group.
- Deduping repeated OSM elements.
- Node and way/relation center handling.
- Score normalization for empty, sparse, useful, and dense payloads.
- `fetch_access_context` returns empty without coordinates.
- Pipeline uses access scores to move visible scores away from neutral.
- Provenance continues to cite `access.walkability` and `access.transit_access`.
- External HTTP calls are mocked; no live Overpass calls in unit tests.

## Acceptance Criteria

- `backend/sources/access.py` no longer returns static placeholder scores for coordinate-backed places.
- Toronto/GTA test addresses can receive non-neutral access scores from public POI counts.
- No new API keys are required.
- Paid APIs remain out of scope.
- Source failures degrade through source statuses and do not break analysis.
- Backend tests, Ruff, and frontend build remain passing.

## References

- OpenStreetMap and the Overpass API: https://dev.overpass-api.de/overpass-doc/en/preface/preface.html
- Overpass QL reference: https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL
- OpenStreetMap copyright and license: https://www.openstreetmap.org/copyright
