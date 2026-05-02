# Phase 1C Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Phase 1 polish and documentation so Phase 2 can start from a clean MVP baseline.

**Architecture:** Keep the existing FastAPI and Vite React architecture. Add frontend presentation states and documentation only; avoid Phase 2 persistence, comparison, sharing, or provenance features.

**Tech Stack:** FastAPI, pytest, ruff, React, Vite, Mapbox GL JS, plain CSS.

---

### Task 1: Frontend Polish States

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Profile.jsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/hooks/useNeighborhood.js`

- [ ] Clear stale profile data when a new analysis starts.
- [ ] Add a selected-place panel heading and explanatory empty state before analysis.
- [ ] Add a loading source checklist instead of a single loading line.
- [ ] Make API errors more visible and retryable.
- [ ] Render who-lives-here context in the profile.
- [ ] Improve mobile bottom-sheet spacing and top overlay spacing.
- [ ] Run `npm.cmd run build` from `frontend/`.
- [ ] Commit frontend polish.

### Task 2: Phase 1 Docs And Handoff

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`

- [ ] Update README to describe Phase 1 MVP, architecture, setup, env vars, data caveats, fair-housing guardrails, verification commands, and resume bullets.
- [ ] Update PLAN to mark Phase 1A, Phase 1B, and Phase 1C completed and leave Phase 2 unchecked as next work.
- [ ] Keep screenshots/GIFs explicitly out of Phase 1C.
- [ ] Run full backend tests, ruff, and frontend build.
- [ ] Commit docs and plan closeout.
- [ ] Push `main`.
