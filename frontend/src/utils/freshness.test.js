import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { formatGeneratedLabel, freshnessState } from './freshness.js';

const NOW = new Date('2026-05-07T12:00:00.000Z');

describe('freshnessState', () => {
  it('returns unknown without a timestamp', () => {
    assert.equal(freshnessState(null, { now: NOW }), 'unknown');
  });

  it('marks timestamps stale at seven days', () => {
    assert.equal(freshnessState('2026-05-01T12:00:00.000Z', { now: NOW }), 'fresh');
    assert.equal(freshnessState('2026-04-30T12:00:00.000Z', { now: NOW }), 'stale');
  });
});

describe('formatGeneratedLabel', () => {
  it('formats unknown and same-day labels', () => {
    assert.equal(formatGeneratedLabel(null, { now: NOW }), 'Generated time unknown');
    assert.equal(formatGeneratedLabel('2026-05-07T11:59:00.000Z', { now: NOW }), 'Generated just now');
    assert.equal(formatGeneratedLabel('2026-05-07T08:00:00.000Z', { now: NOW }), 'Generated today');
  });

  it('formats fresh and stale day counts', () => {
    assert.equal(formatGeneratedLabel('2026-05-04T12:00:00.000Z', { now: NOW }), 'Generated 3 days ago');
    assert.equal(formatGeneratedLabel('2026-04-25T12:00:00.000Z', { now: NOW }), 'Stale: generated 12 days ago');
  });
});
