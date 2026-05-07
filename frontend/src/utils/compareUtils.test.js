import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  MAX_COMPARE_SLOTS,
  MIN_COMPARE_SLOTS,
  buildCompareHighlights,
  buildComparePayload,
  canAddCompareSlot,
  canAnalyzeCompare,
  createCompareSlot,
  getSuccessfulCompareResults,
} from './compareUtils.js';

const PLACE = {
  label: 'East Austin, Austin, TX',
  coordinates: { lat: 30.2636, lng: -97.7114 },
};

const PROFILE = {
  id: 'profile-1',
  name: 'Transit walker',
  generic_mode: false,
};

function response(label, { fit = 70, walkability = 60, transit = 55, confidence = 'medium', missing = [] } = {}) {
  return {
    place: { label },
    fit: fit === null ? null : { score: fit, label: 'Good fit', explanation: `${label} explanation.`, flags: [] },
    profile: {
      vibe_scores: {
        walkability,
        transit_access: transit,
        affordability: 50,
        quiet: 50,
        social_scene: 50,
      },
      honest_pros: [`${label} pro.`],
      honest_cons: [`${label} con.`],
      provenance: { items: [] },
    },
    confidence: {
      level: confidence,
      missing_sources: missing,
      caveats: [],
    },
    source_statuses: [],
  };
}

describe('compare slot helpers', () => {
  it('creates empty compare slots with stable shape', () => {
    assert.deepEqual(createCompareSlot('slot-1'), {
      id: 'slot-1',
      place: null,
      status: 'idle',
      response: null,
      error: '',
    });
  });

  it('enforces the 2 to 4 slot range', () => {
    assert.equal(MIN_COMPARE_SLOTS, 2);
    assert.equal(MAX_COMPARE_SLOTS, 4);
    assert.equal(canAddCompareSlot([1, 2, 3]), true);
    assert.equal(canAddCompareSlot([1, 2, 3, 4]), false);
  });

  it('requires at least two selected places before analysis', () => {
    const slots = [
      { ...createCompareSlot('slot-1'), place: PLACE },
      createCompareSlot('slot-2'),
    ];

    assert.equal(canAnalyzeCompare(slots), false);
    assert.equal(canAnalyzeCompare(slots.map((slot) => (slot.id === 'slot-2' ? { ...slot, place: PLACE } : slot))), true);
  });
});

describe('buildComparePayload', () => {
  it('uses the current saved profile lens', () => {
    assert.deepEqual(buildComparePayload(PLACE, PROFILE), {
      query: 'East Austin, Austin, TX',
      coordinates: { lat: 30.2636, lng: -97.7114 },
      generic_mode: false,
      preference_profile_id: 'profile-1',
    });
  });

  it('uses generic mode when no saved profile is active', () => {
    assert.deepEqual(buildComparePayload(PLACE, null), {
      query: 'East Austin, Austin, TX',
      coordinates: { lat: 30.2636, lng: -97.7114 },
      preferences: {},
      generic_mode: true,
    });
  });
});

describe('compare result helpers', () => {
  it('returns only successful compare results', () => {
    const slots = [
      { ...createCompareSlot('slot-1'), status: 'success', response: response('East Austin') },
      { ...createCompareSlot('slot-2'), status: 'error', error: 'Analyze failed' },
      { ...createCompareSlot('slot-3'), status: 'success', response: response('Kensington Market') },
    ];

    assert.deepEqual(
      getSuccessfulCompareResults(slots).map((item) => item.response.place.label),
      ['East Austin', 'Kensington Market'],
    );
  });

  it('builds useful highlights from successful results', () => {
    const slots = [
      { ...createCompareSlot('slot-1'), status: 'success', response: response('East Austin', { fit: 82, walkability: 75, transit: 60, confidence: 'medium', missing: ['reddit'] }) },
      { ...createCompareSlot('slot-2'), status: 'success', response: response('Kensington Market', { fit: 74, walkability: 92, transit: 88, confidence: 'high', missing: [] }) },
      { ...createCompareSlot('slot-3'), status: 'success', response: response('Thin Data Place', { fit: 61, walkability: 50, transit: 42, confidence: 'low', missing: ['census', 'housing'] }) },
    ];

    assert.deepEqual(buildCompareHighlights(slots), [
      { id: 'best-fit', label: 'Best fit', placeLabel: 'East Austin', value: '82%' },
      { id: 'best-walkability', label: 'Best walkability', placeLabel: 'Kensington Market', value: '92' },
      { id: 'best-transit', label: 'Best transit', placeLabel: 'Kensington Market', value: '88' },
      { id: 'lowest-confidence-risk', label: 'Lowest data risk', placeLabel: 'Kensington Market', value: 'high confidence' },
    ]);
  });

  it('omits best fit in generic mode when no fit scores exist', () => {
    const slots = [
      { ...createCompareSlot('slot-1'), status: 'success', response: response('East Austin', { fit: null, walkability: 75, transit: 60 }) },
      { ...createCompareSlot('slot-2'), status: 'success', response: response('Kensington Market', { fit: null, walkability: 92, transit: 88 }) },
    ];

    assert.deepEqual(
      buildCompareHighlights(slots).map((highlight) => highlight.id),
      ['best-walkability', 'best-transit', 'lowest-confidence-risk'],
    );
  });
});
