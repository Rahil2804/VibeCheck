import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const ROOT = resolve(import.meta.dirname, '..');

function source(path) {
  return readFileSync(resolve(ROOT, path), 'utf8');
}

test('frontend source does not contain mojibake glyphs', () => {
  const files = [
    'src/App.jsx',
    'src/components/PreferenceProfiles.jsx',
    'src/components/SavedProfiles.jsx',
    'src/styles.css',
  ];

  for (const file of files) {
    assert.equal(source(file).includes('â'), false, `${file} contains mojibake`);
  }
});

test('workspace overlays sit above the top rail and use viewport-safe sizing', () => {
  const css = source('src/styles.css');

  assert.match(css, /--layer-top-bar:\s*20;/);
  assert.match(css, /--layer-workspace:\s*40;/);
  assert.match(css, /\.top-bar\s*{[^}]*z-index:\s*var\(--layer-top-bar\)/s);
  assert.match(css, /\.workspace-backdrop\s*{[^}]*z-index:\s*var\(--layer-workspace\)/s);
  assert.match(css, /\.profile-workspace\s*{[^}]*max-height:\s*calc\(100vh - 112px\)/s);
  assert.match(css, /\.profile-workspace-main\s*{[^}]*overflow-y:\s*auto/s);
});

test('profile workspace has a definite scrollable sheet height', () => {
  const css = source('src/styles.css');

  assert.match(css, /\.profile-workspace\s*{[^}]*height:\s*min\(760px,\s*calc\(100vh - 112px\)\)/s);
  assert.match(css, /\.profile-workspace-main\s*{[^}]*overflow-y:\s*auto/s);
  assert.match(css, /\.profile-workspace-nav\s*{[^}]*overflow-y:\s*auto/s);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.profile-workspace\s*{[^}]*height:\s*calc\(100vh - 116px\)/s);
});

test('profile renders source support without raw payload output', () => {
  const profile = source('src/components/Profile.jsx');
  const provenance = source('src/components/Provenance.jsx');

  assert.match(profile, /<Provenance provenance=\{profile\.provenance\} \/>/);
  assert.match(provenance, /Source support/);
  assert.match(provenance, /Supported/);
  assert.match(provenance, /Inferred/);
  assert.match(provenance, /Unavailable/);
  assert.equal(provenance.includes('JSON.stringify'), false);
});

test('profile renders freshness and source updated dates', () => {
  const profile = source('src/components/Profile.jsx');
  const freshness = source('src/components/Freshness.jsx');
  const confidence = source('src/components/Confidence.jsx');

  assert.match(profile, /<Freshness/);
  assert.match(freshness, /Refresh report/);
  assert.match(freshness, /Refresh analysis/);
  assert.match(freshness, /formatGeneratedLabel/);
  assert.match(confidence, /updated_at/);
  assert.match(confidence, /formatSourceDate/);
});

test('compare result components show summaries without raw payload output', () => {
  const summary = source('src/components/CompareSummary.jsx');
  const resultCard = source('src/components/CompareResultCard.jsx');

  assert.match(summary, /Compare highlights/);
  assert.match(summary, /buildCompareHighlights/);
  assert.match(resultCard, /CompareResultCard/);
  assert.match(resultCard, /<Confidence confidence=\{response\.confidence\} statuses=\{response\.source_statuses\} \/>/);
  assert.match(resultCard, /<Provenance provenance=\{response\.profile\?\.provenance\} \/>/);
  assert.equal(resultCard.includes('JSON.stringify'), false);
});

test('compare workspace supports ad hoc 2 to 4 place analysis', () => {
  const compareMode = source('src/components/CompareMode.jsx');
  const compareSearch = source('src/components/ComparePlaceSearch.jsx');

  assert.match(compareMode, /Compare places/);
  assert.match(compareMode, /Analyze Compare/);
  assert.match(compareMode, /MAX_COMPARE_SLOTS/);
  assert.match(compareMode, /MIN_COMPARE_SLOTS/);
  assert.match(compareMode, /analyzeNeighborhood/);
  assert.match(compareMode, /Promise\.all/);
  assert.match(compareMode, /CompareResultCard/);
  assert.match(compareMode, /CompareSummary/);
  assert.match(compareSearch, /<SearchBar onSelect=\{onSelect\} \/>/);
});

test('app exposes top-level compare mode without replacing profile management', () => {
  const app = source('src/App.jsx');
  const topBar = source('src/components/TopBar.jsx');

  assert.match(topBar, /onCompareClick/);
  assert.match(topBar, /aria-label="Compare places"/);
  assert.match(topBar, />Compare</);
  assert.match(app, /import CompareMode from '\.\/components\/CompareMode\.jsx';/);
  assert.match(app, /activeWorkspace === 'compare'/);
  assert.match(app, /onCompareClick=\{\(\) => setActiveWorkspace\('compare'\)\}/);
  assert.match(app, /activeProfile=\{selectedPreferenceProfile\}/);
});

test('compare mode has viewport-safe responsive styling', () => {
  const css = source('src/styles.css');

  assert.match(css, /\.compare-workspace\s*{[^}]*position:\s*absolute/s);
  assert.match(css, /\.compare-workspace\s*{[^}]*max-height:\s*calc\(100vh - 112px\)/s);
  assert.match(css, /\.compare-results-grid\s*{[^}]*grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(260px,\s*1fr\)\)/s);
  assert.match(css, /\.compare-place-slots\s*{[^}]*grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(220px,\s*1fr\)\)/s);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.compare-workspace\s*{[^}]*inset:\s*92px 12px 16px/s);
});
