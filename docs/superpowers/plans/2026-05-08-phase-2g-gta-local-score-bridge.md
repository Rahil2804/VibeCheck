# GTA Local Score Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Toronto/GTA local parks and amenity data affect backend scores and fit explanations while keeping the current frontend UI unchanged.

**Architecture:** Add a focused score-signal resolver that converts normalized source payloads into `VibeScores` plus score provenance support. The pipeline will call that resolver, `score_fit` will use the new optional parks/outdoors signal, and provenance will cite local fields when they affect visible scores.

**Tech Stack:** FastAPI backend, Pydantic models, pytest/pytest-asyncio tests, Ruff, existing React/Vite frontend left unchanged.

---

## File Structure

- Create `backend/score_signals.py`: owns deterministic source-to-score mapping and support-field resolution.
- Create `tests/test_score_signals.py`: unit tests for the new score bridge.
- Modify `backend/models.py`: add optional `parks_outdoors` to `VibeScores`.
- Modify `backend/pipeline.py`: call `resolve_vibe_scores()` when building deterministic profiles.
- Modify `backend/scorer.py`: use `parks_outdoors` for parks/outdoors priority instead of the current quiet-score proxy.
- Modify `backend/provenance.py`: cite local source fields for any visible score influenced by local data.
- Modify `backend/sources/local.py`: add GTA municipality recognition and keep Toronto-only adapter routing.
- Modify `tests/test_pipeline.py`, `tests/test_scorer.py`, `tests/test_provenance.py`, and `tests/test_local_source.py`: lock the behavior.
- Modify `README.md` and `PLAN.md`: document Phase 2G and the Ontario/GTA-first backend depth without adding user-facing coverage-banner language.

---

### Task 1: Add Score Signal Resolver

**Files:**
- Create: `backend/score_signals.py`
- Create: `tests/test_score_signals.py`
- Modify: `backend/models.py`

- [ ] **Step 1: Write failing tests for the score resolver**

Create `tests/test_score_signals.py`:

```python
from backend.models import SourceName
from backend.score_signals import resolve_score_support, resolve_vibe_scores


def test_resolve_vibe_scores_uses_local_parks_without_touching_transit_or_affordability():
    scores = resolve_vibe_scores(
        {
            SourceName.LOCAL: {
                "parks_outdoors": 88,
                "parks_count": 5,
                "community_amenities_count": 2,
            }
        }
    )

    assert scores.walkability == 69
    assert scores.quiet == 59
    assert scores.social_scene == 58
    assert scores.parks_outdoors == 88
    assert scores.transit_access == 50
    assert scores.affordability == 50


def test_resolve_vibe_scores_keeps_existing_source_scores_when_local_is_empty():
    scores = resolve_vibe_scores(
        {
            SourceName.ACCESS: {"walkability": 82, "transit_access": 77},
            SourceName.HOUSING: {"affordability": 61},
            SourceName.REDDIT: {"quiet": 44, "social_scene": 73},
            SourceName.LOCAL: {},
        }
    )

    assert scores.walkability == 82
    assert scores.transit_access == 77
    assert scores.affordability == 61
    assert scores.quiet == 44
    assert scores.social_scene == 73
    assert scores.parks_outdoors is None


def test_resolve_score_support_lists_local_fields_only_when_they_influence_scores():
    support = resolve_score_support(
        {
            SourceName.LOCAL: {
                "parks_outdoors": 88,
                "parks_count": 5,
                "community_amenities_count": 2,
            }
        }
    )

    assert support["walkability"] == [
        "local.parks_outdoors",
        "local.parks_count",
        "local.community_amenities_count",
    ]
    assert support["quiet"] == ["local.parks_outdoors", "local.parks_count"]
    assert support["social_scene"] == ["local.community_amenities_count"]
    assert support["parks_outdoors"] == ["local.parks_outdoors"]
    assert support["transit_access"] == []
    assert support["affordability"] == []
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_score_signals.py -q -p no:cacheprovider
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.score_signals'`.

- [ ] **Step 3: Extend `VibeScores`**

In `backend/models.py`, update `VibeScores`:

```python
class VibeScores(BaseModel):
    walkability: int = Field(ge=0, le=100)
    transit_access: int = Field(ge=0, le=100)
    affordability: int = Field(ge=0, le=100)
    quiet: int = Field(ge=0, le=100)
    social_scene: int = Field(ge=0, le=100)
    parks_outdoors: int | None = Field(default=None, ge=0, le=100)
```

- [ ] **Step 4: Create the resolver implementation**

Create `backend/score_signals.py`:

```python
from typing import Any

from backend.models import SourceName, VibeScores

ScoreSupport = dict[str, list[str]]


def resolve_vibe_scores(source_data: dict[SourceName, dict[str, Any]]) -> VibeScores:
    access = source_data.get(SourceName.ACCESS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    reddit = source_data.get(SourceName.REDDIT, {})
    local = source_data.get(SourceName.LOCAL, {})

    local_parks = _optional_score(local, "parks_outdoors")
    parks_count = _int_from(local, "parks_count")
    amenities_count = _int_from(local, "community_amenities_count")

    walkability = _score_from(access, "walkability", 50)
    local_walkability = _local_walkability_score(local_parks, parks_count, amenities_count)
    if local_walkability is not None:
        walkability = max(walkability, local_walkability)

    quiet = _score_from(reddit, "quiet", 50)
    local_quiet = _local_quiet_score(local_parks, parks_count)
    if local_quiet is not None:
        quiet = max(quiet, local_quiet)

    social_scene = _score_from(reddit, "social_scene", 50)
    local_social = _local_social_score(amenities_count)
    if local_social is not None:
        social_scene = max(social_scene, local_social)

    return VibeScores(
        walkability=walkability,
        transit_access=_score_from(access, "transit_access", 50),
        affordability=_score_from(housing, "affordability", 50),
        quiet=quiet,
        social_scene=social_scene,
        parks_outdoors=local_parks,
    )


def resolve_score_support(source_data: dict[SourceName, dict[str, Any]]) -> ScoreSupport:
    access = source_data.get(SourceName.ACCESS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    reddit = source_data.get(SourceName.REDDIT, {})
    local = source_data.get(SourceName.LOCAL, {})
    scores = resolve_vibe_scores(source_data)

    base_walkability = _score_from(access, "walkability", 50)
    base_quiet = _score_from(reddit, "quiet", 50)
    base_social_scene = _score_from(reddit, "social_scene", 50)

    support: ScoreSupport = {
        "walkability": _field_if_present(access, SourceName.ACCESS, "walkability"),
        "transit_access": _field_if_present(access, SourceName.ACCESS, "transit_access"),
        "affordability": _field_if_present(housing, SourceName.HOUSING, "affordability"),
        "quiet": _field_if_present(reddit, SourceName.REDDIT, "quiet"),
        "social_scene": _field_if_present(reddit, SourceName.REDDIT, "social_scene"),
        "parks_outdoors": _field_if_present(local, SourceName.LOCAL, "parks_outdoors"),
    }

    if scores.walkability > base_walkability and _optional_score(local, "parks_outdoors") is not None:
        support["walkability"].extend(
            [
                "local.parks_outdoors",
                "local.parks_count",
                "local.community_amenities_count",
            ]
        )
    if scores.quiet > base_quiet and _optional_score(local, "parks_outdoors") is not None:
        support["quiet"].extend(["local.parks_outdoors", "local.parks_count"])
    if scores.social_scene > base_social_scene and _int_from(local, "community_amenities_count") > 0:
        support["social_scene"].append("local.community_amenities_count")

    return {key: _dedupe(fields) for key, fields in support.items()}


def _local_walkability_score(
    local_parks: int | None,
    parks_count: int,
    amenities_count: int,
) -> int | None:
    if local_parks is None:
        return None
    lift = max(local_parks - 50, 0) * 0.35
    destination_lift = min(6, parks_count + amenities_count)
    return _clamp(int(50 + lift + destination_lift))


def _local_quiet_score(local_parks: int | None, parks_count: int) -> int | None:
    if local_parks is None:
        return None
    lift = max(local_parks - 50, 0) * 0.2
    park_lift = min(4, parks_count // 2)
    return _clamp(int(50 + lift + park_lift))


def _local_social_score(amenities_count: int) -> int | None:
    if amenities_count <= 0:
        return None
    return _clamp(50 + min(16, amenities_count * 4))


def _field_if_present(data: dict[str, Any], source: SourceName, field: str) -> list[str]:
    return [f"{source.value}.{field}"] if data.get(field) is not None else []


def _optional_score(data: dict[str, Any], key: str) -> int | None:
    raw = data.get(key)
    if not isinstance(raw, int | float):
        return None
    return _clamp(int(raw))


def _score_from(data: dict[str, Any], key: str, default: int) -> int:
    raw = data.get(key, default)
    if not isinstance(raw, int | float):
        return default
    return _clamp(int(raw))


def _int_from(data: dict[str, Any], key: str) -> int:
    raw = data.get(key, 0)
    return raw if isinstance(raw, int) else 0


def _clamp(score: int) -> int:
    return max(0, min(100, score))


def _dedupe(fields: list[str]) -> list[str]:
    deduped: list[str] = []
    for field in fields:
        if field not in deduped:
            deduped.append(field)
    return deduped
```

- [ ] **Step 5: Run the resolver tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_score_signals.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6: Commit the resolver**

Run:

```powershell
git add backend\models.py backend\score_signals.py tests\test_score_signals.py
git commit -m "Add local score signal resolver"
```

Expected: commit succeeds.

---

### Task 2: Bridge Resolver Into Pipeline

**Files:**
- Modify: `backend/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing pipeline test for local-backed visible scores**

Append to `tests/test_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_pipeline_bridges_local_parks_into_visible_scores():
    async def local_adapter(_context: SourceContext):
        return {
            "coverage_area": "Toronto",
            "parks_count": 5,
            "community_amenities_count": 2,
            "parks_outdoors": 88,
            "trajectory_signal": "uncertain",
            "summary": "Toronto open data returned nearby parks/amenity signals.",
            "updated_at": "2026-05-08T00:00:00+00:00",
        }

    response = await analyze_neighborhood(
        AnalyzeRequest(query="Kensington Market, Toronto, ON"),
        source_fetchers={SourceName.LOCAL: local_adapter},
        source_timeout_seconds=1,
        profile_synthesizer=_returns_none,
    )

    scores = response.profile.vibe_scores
    assert scores.walkability == 69
    assert scores.quiet == 59
    assert scores.social_scene == 58
    assert scores.parks_outdoors == 88
    assert scores.transit_access == 50
    assert scores.affordability == 50
```

- [ ] **Step 2: Run the pipeline test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py::test_pipeline_bridges_local_parks_into_visible_scores -q -p no:cacheprovider
```

Expected: FAIL because `_build_profile` still builds `VibeScores` directly from access/housing/reddit.

- [ ] **Step 3: Update `backend/pipeline.py` to use the resolver**

Add the import near the other backend imports:

```python
from backend.score_signals import resolve_vibe_scores
```

Remove `VibeScores` from the `backend.models` import list if it becomes unused.

Inside `_build_profile`, replace the current direct `VibeScores(...)` block:

```python
    access = source_data.get(SourceName.ACCESS, {})
    housing = source_data.get(SourceName.HOUSING, {})
    census = source_data.get(SourceName.CENSUS, {})
    reddit = source_data.get(SourceName.REDDIT, {})
    local = source_data.get(SourceName.LOCAL, {})

    scores = VibeScores(
        walkability=_score_from(access, "walkability", 50),
        transit_access=_score_from(access, "transit_access", 50),
        affordability=_score_from(housing, "affordability", 50),
        quiet=_score_from(reddit, "quiet", 50),
        social_scene=_score_from(reddit, "social_scene", 50),
    )
```

with:

```python
    census = source_data.get(SourceName.CENSUS, {})
    local = source_data.get(SourceName.LOCAL, {})

    scores = resolve_vibe_scores(source_data)
```

Remove `_score_from` at the bottom of `backend/pipeline.py` if Ruff reports it as unused.

- [ ] **Step 4: Run pipeline tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Commit the pipeline bridge**

Run:

```powershell
git add backend\pipeline.py tests\test_pipeline.py
git commit -m "Use local score resolver in pipeline"
```

Expected: commit succeeds.

---

### Task 3: Use Parks/Outdoors Signal In Fit Scoring

**Files:**
- Modify: `backend/scorer.py`
- Modify: `tests/test_scorer.py`

- [ ] **Step 1: Write failing scorer tests**

In `tests/test_scorer.py`, update the `_profile` helper score defaults:

```python
    scores = {
        "walkability": 50,
        "transit_access": 50,
        "affordability": 50,
        "quiet": 50,
        "social_scene": 50,
        "parks_outdoors": None,
    }
```

Append these tests:

```python
def test_parks_priority_rewards_supported_parks_outdoors_signal():
    fit = score_fit(
        _profile(quiet=45, parks_outdoors=82),
        Preferences(top_priority=TopPriority.PARKS_OUTDOORS),
    )

    assert fit.score >= 62
    assert "parks" in fit.explanation.lower()


def test_parks_priority_no_longer_uses_quiet_as_proxy_when_parks_signal_is_missing():
    fit = score_fit(
        _profile(quiet=82, parks_outdoors=None),
        Preferences(top_priority=TopPriority.PARKS_OUTDOORS),
    )

    assert fit.score == 50
    assert "neutral" in fit.explanation.lower()
```

- [ ] **Step 2: Run the scorer tests and verify the new proxy test fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_scorer.py -q -p no:cacheprovider
```

Expected: FAIL because the current parks/outdoors branch rewards `quiet >= 60`.

- [ ] **Step 3: Update parks/outdoors scoring**

In `backend/scorer.py`, replace this branch:

```python
    elif preferences.top_priority == TopPriority.PARKS_OUTDOORS:
        if scores.quiet >= 60:
            score += 10
            reasons.append("outdoor and calmer-access signals are favorable")
```

with:

```python
    elif preferences.top_priority == TopPriority.PARKS_OUTDOORS:
        if scores.parks_outdoors is not None and scores.parks_outdoors >= 75:
            score += 12
            reasons.append("parks and outdoor access are supported by local amenity signals")
        elif scores.parks_outdoors is not None and scores.parks_outdoors >= 60:
            score += 8
            reasons.append("parks and outdoor access look favorable")
        elif scores.parks_outdoors is not None and scores.parks_outdoors < 45:
            score -= 8
            flags.append("Parks and outdoor access look weak for your stated priority.")
```

- [ ] **Step 4: Run scorer tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_scorer.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Commit fit scoring update**

Run:

```powershell
git add backend\scorer.py tests\test_scorer.py
git commit -m "Use parks signal in fit scoring"
```

Expected: commit succeeds.

---

### Task 4: Cite Local Fields In Provenance

**Files:**
- Modify: `backend/provenance.py`
- Modify: `tests/test_provenance.py`

- [ ] **Step 1: Write failing provenance test**

Append to `tests/test_provenance.py`:

```python
def test_build_profile_provenance_cites_local_fields_for_scores_changed_by_local_bridge():
    provenance = build_profile_provenance(
        {
            SourceName.LOCAL: {
                "parks_outdoors": 88,
                "parks_count": 5,
                "community_amenities_count": 2,
            }
        },
        [_status(SourceName.LOCAL, SourceStatusCode.SUCCESS)],
    )

    items = {item.claim_id: item for item in provenance.items}

    assert items["vibe.walkability"].support == "inferred"
    assert items["vibe.walkability"].sources == [SourceName.LOCAL]
    assert items["vibe.walkability"].source_fields == [
        "local.parks_outdoors",
        "local.parks_count",
        "local.community_amenities_count",
    ]

    assert items["vibe.quiet"].source_fields == [
        "local.parks_outdoors",
        "local.parks_count",
    ]
    assert items["vibe.social_scene"].source_fields == ["local.community_amenities_count"]
    assert items["vibe.transit_access"].support == "unavailable"
    assert items["vibe.affordability"].support == "unavailable"
```

- [ ] **Step 2: Run the provenance test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_provenance.py::test_build_profile_provenance_cites_local_fields_for_scores_changed_by_local_bridge -q -p no:cacheprovider
```

Expected: FAIL because score provenance currently only looks at the original single source for each visible score.

- [ ] **Step 3: Import score support resolver**

In `backend/provenance.py`, add:

```python
from backend.score_signals import resolve_score_support
```

- [ ] **Step 4: Compute score support once in `build_profile_provenance`**

At the start of `build_profile_provenance`, after `status_by_source`:

```python
    score_support = resolve_score_support(source_data)
```

- [ ] **Step 5: Replace the five score `_field_item` calls with `_score_item` calls**

Replace the existing `vibe.walkability`, `vibe.transit_access`, `vibe.affordability`, `vibe.quiet`, and `vibe.social_scene` items with:

```python
        _score_item(
            claim_id="vibe.walkability",
            label="Walkability score",
            score_key="walkability",
            fallback_sources=[SourceName.ACCESS],
            score_support=score_support,
            status_by_source=status_by_source,
        ),
        _score_item(
            claim_id="vibe.transit_access",
            label="Transit access score",
            score_key="transit_access",
            fallback_sources=[SourceName.ACCESS],
            score_support=score_support,
            status_by_source=status_by_source,
        ),
        _score_item(
            claim_id="vibe.affordability",
            label="Affordability score",
            score_key="affordability",
            fallback_sources=[SourceName.HOUSING],
            score_support=score_support,
            status_by_source=status_by_source,
        ),
        _score_item(
            claim_id="vibe.quiet",
            label="Quiet score",
            score_key="quiet",
            fallback_sources=[SourceName.REDDIT],
            score_support=score_support,
            status_by_source=status_by_source,
        ),
        _score_item(
            claim_id="vibe.social_scene",
            label="Social scene score",
            score_key="social_scene",
            fallback_sources=[SourceName.REDDIT],
            score_support=score_support,
            status_by_source=status_by_source,
        ),
```

- [ ] **Step 6: Add helper functions for score provenance**

Add these helpers below `_field_item`:

```python
def _score_item(
    *,
    claim_id: str,
    label: str,
    score_key: str,
    fallback_sources: list[SourceName],
    score_support: dict[str, list[str]],
    status_by_source: dict[SourceName, SourceStatus],
) -> ProvenanceItem:
    fields = score_support.get(score_key, [])
    if fields:
        return ProvenanceItem(
            claim_id=claim_id,
            label=label,
            summary=f"Based on normalized {', '.join(fields)} signals.",
            support=ProvenanceSupport.INFERRED,
            sources=_sources_from_source_fields(fields),
            source_fields=fields,
        )

    summaries = "; ".join(_status_summary(source, status_by_source) for source in fallback_sources)
    return ProvenanceItem(
        claim_id=claim_id,
        label=label,
        summary=f"{label} is unavailable because {summaries}.",
        support=ProvenanceSupport.UNAVAILABLE,
        sources=fallback_sources,
        source_fields=[],
    )


def _sources_from_source_fields(fields: list[str]) -> list[SourceName]:
    ordered_sources = [
        SourceName.ACCESS,
        SourceName.HOUSING,
        SourceName.CENSUS,
        SourceName.REDDIT,
        SourceName.LOCAL,
    ]
    present = {field.split(".", maxsplit=1)[0] for field in fields}
    return [source for source in ordered_sources if source.value in present]
```

- [ ] **Step 7: Run provenance tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_provenance.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 8: Commit provenance update**

Run:

```powershell
git add backend\provenance.py tests\test_provenance.py
git commit -m "Cite local score support in provenance"
```

Expected: commit succeeds.

---

### Task 5: Add GTA Local Routing Recognition

**Files:**
- Modify: `backend/sources/local.py`
- Modify: `tests/test_local_source.py`

- [ ] **Step 1: Write failing local routing tests**

Update the import in `tests/test_local_source.py`:

```python
from backend.sources.local import (
    fetch_local_context,
    is_gta_place,
    is_ontario_place,
    is_toronto_place,
)
```

Append:

```python
def test_detects_gta_municipalities_without_treating_them_as_toronto():
    pickering = Place(
        label="Pickering, Ontario, Canada",
        city="Pickering",
        state="Ontario",
        coordinates=Coordinates(lat=43.8384, lng=-79.0868),
    )
    richmond_hill = Place(
        label="Richmond Hill, Ontario, Canada",
        city="Richmond Hill",
        state="Ontario",
        coordinates=Coordinates(lat=43.8828, lng=-79.4403),
    )

    assert is_gta_place(pickering) is True
    assert is_gta_place(richmond_hill) is True
    assert is_toronto_place(pickering) is False
    assert is_toronto_place(richmond_hill) is False
```

Update the existing Pickering message expectation:

```python
    assert result.message == "No local GTA adapter is available yet for Pickering."
```

- [ ] **Step 2: Run local source tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_source.py -q -p no:cacheprovider
```

Expected: FAIL because `is_gta_place` does not exist and the Pickering message still says Ontario.

- [ ] **Step 3: Add GTA municipality registry and routing**

In `backend/sources/local.py`, add after imports:

```python
GTA_MUNICIPALITIES = {
    "toronto",
    "pickering",
    "ajax",
    "whitby",
    "oshawa",
    "clarington",
    "uxbridge",
    "scugog",
    "brock",
    "markham",
    "vaughan",
    "richmond hill",
    "newmarket",
    "aurora",
    "mississauga",
    "brampton",
    "caledon",
    "oakville",
    "burlington",
    "milton",
    "halton hills",
}
```

In `fetch_local_context`, replace the Ontario empty message block:

```python
    if is_ontario_place(place):
        municipality = place.city or _first_label_part(place.label)
        return SourceResult(
            data={},
            message=f"No local Ontario adapter is available yet for {municipality}.",
        )
```

with:

```python
    if is_ontario_place(place):
        municipality = place.city or _first_label_part(place.label)
        region = "GTA" if is_gta_place(place) else "Ontario"
        return SourceResult(
            data={},
            message=f"No local {region} adapter is available yet for {municipality}.",
        )
```

Add this function below `is_toronto_place`:

```python
def is_gta_place(place: Place) -> bool:
    text = _place_text(place)
    return any(municipality in text for municipality in GTA_MUNICIPALITIES)
```

Add this helper above `_place_tokens`:

```python
def _place_text(place: Place) -> str:
    raw_values = [place.label, place.city or "", place.state or ""]
    return " ".join(raw_values).lower().replace(",", " ")
```

Change `_place_tokens` to reuse `_place_text`:

```python
def _place_tokens(place: Place) -> set[str]:
    tokens: set[str] = set()
    for part in _place_text(place).split():
        stripped = part.strip()
        if stripped:
            tokens.add(stripped)
    return tokens
```

- [ ] **Step 4: Run local source tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_source.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Commit local routing update**

Run:

```powershell
git add backend\sources\local.py tests\test_local_source.py
git commit -m "Recognize GTA local routing"
```

Expected: commit succeeds.

---

### Task 6: Update Docs For Phase 2G

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`

- [ ] **Step 1: Update README project summary and phase summary**

In `README.md`, change the opening behavior line from:

```markdown
The app opens on a Mapbox 3D map. A user searches for a US or Canadian address/place, selects an autocomplete result, the map flies to that point, and the profile panel renders fit scoring, confidence, caveats, and source statuses.
```

to:

```markdown
The app opens on a Mapbox 3D map. A user searches for an address or place, selects an autocomplete result, the map flies to that point, and the profile panel renders fit scoring, confidence, caveats, and source statuses.
```

Add this bullet near the existing Phase 2 feature bullets:

```markdown
- GTA/Ontario-first backend score depth that uses Toronto local parks and amenity signals conservatively without changing the current UI.
```

In the phase history paragraph, append:

```markdown
Phase 2G keeps the UI unchanged while bridging Toronto local parks/amenity data into existing backend score and fit logic.
```

- [ ] **Step 2: Update PLAN build order**

In `PLAN.md`, under Phase 2 build order, add after the Phase 2F checkbox:

```markdown
- [x] Add GTA/Ontario-first backend score depth from Toronto parks and amenity signals without redesigning the UI.
```

Under Phase 3 Data Depth, keep broader adapters deferred and add:

```markdown
- [ ] Expand the Ontario/GTA municipal adapter set beyond Toronto after the local score bridge is stable.
```

- [ ] **Step 3: Inspect docs diff**

Run:

```powershell
git diff -- README.md PLAN.md
```

Expected: diff mentions backend score depth and avoids prominent user-facing coverage marketing copy.

- [ ] **Step 4: Commit docs**

Run:

```powershell
git add README.md PLAN.md
git commit -m "Document GTA local score bridge"
```

Expected: commit succeeds.

---

### Task 7: Final Verification

**Files:**
- Verify only; no expected source edits.

- [ ] **Step 1: Run targeted backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_score_signals.py tests/test_pipeline.py tests/test_scorer.py tests/test_provenance.py tests/test_local_source.py tests/test_main.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run full backend test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 3: Run Ruff**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check backend tests
```

Expected: `All checks passed!`.

- [ ] **Step 4: Run frontend build as regression check**

Run:

```powershell
npm run build --prefix frontend
```

Expected: build completes successfully.

- [ ] **Step 5: Inspect final git status**

Run:

```powershell
git status --short
```

Expected: no tracked files modified. Untracked `.tmp/` may remain.

- [ ] **Step 6: Manual smoke check with local servers**

Start backend and frontend using the project README commands. Analyze:

```text
Kensington Market, Toronto, ON
```

Expected:

- The current UI layout remains unchanged.
- The local source status is success when Toronto data is reachable.
- At least one existing visible score moves above `50` when local parks/amenity data is present.
- Transit and affordability remain neutral if no real transit or affordability signals are available.
- A parks/outdoors preference changes the fit explanation with parks/outdoors wording.
