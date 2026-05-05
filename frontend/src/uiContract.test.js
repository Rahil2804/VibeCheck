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
