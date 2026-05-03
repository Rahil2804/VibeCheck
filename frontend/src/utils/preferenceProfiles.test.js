import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  buildAnalyzePayload,
  formToPreferenceProfilePayload,
  getActiveProfileLabel,
  profileToForm,
  resolveSelectedPreferenceProfileId,
} from './preferenceProfiles.js';

const PLACE = {
  label: 'Mission District, San Francisco, CA',
  coordinates: { lat: 37.7599, lng: -122.4148 },
};

const PROFILES = [
  {
    id: 'profile-1',
    name: 'Budget walker',
    is_default: false,
    car_reliance: 'no_car',
    energy_preference: 'balanced',
    top_priority: 'walkability_errands',
    budget_sensitivity: 'very_budget_conscious',
    generic_mode: false,
    commute_anchor: { label: 'Union Station', lat: 43.645, lng: -79.38 },
    max_monthly_rent: 2200,
    must_haves: ['transit', 'groceries'],
    deal_breakers: ['lower_rent_pressure'],
    notes: 'Local only.',
  },
  {
    id: 'profile-2',
    name: 'Default profile',
    is_default: true,
    generic_mode: false,
    must_haves: [],
    deal_breakers: [],
  },
];

describe('resolveSelectedPreferenceProfileId', () => {
  it('keeps the current profile when it still exists', () => {
    assert.equal(resolveSelectedPreferenceProfileId(PROFILES, 'profile-1'), 'profile-1');
  });

  it('falls back to the default profile when the current profile is missing', () => {
    assert.equal(resolveSelectedPreferenceProfileId(PROFILES, 'missing-profile'), 'profile-2');
  });

  it('falls back to generic when no profiles exist', () => {
    assert.equal(resolveSelectedPreferenceProfileId([], 'profile-1'), null);
  });
});

describe('getActiveProfileLabel', () => {
  it('formats a saved active profile', () => {
    assert.equal(getActiveProfileLabel(PROFILES[0]), 'Active profile: Budget walker');
  });

  it('formats generic mode', () => {
    assert.equal(getActiveProfileLabel(null), 'Active profile: Generic');
  });
});

describe('buildAnalyzePayload', () => {
  it('sends profile id for saved profile analysis', () => {
    assert.deepEqual(buildAnalyzePayload(PLACE, PROFILES[0]), {
      query: 'Mission District, San Francisco, CA',
      coordinates: { lat: 37.7599, lng: -122.4148 },
      generic_mode: false,
      preference_profile_id: 'profile-1',
    });
  });

  it('sends generic mode without profile id when no saved profile is active', () => {
    assert.deepEqual(buildAnalyzePayload(PLACE, null), {
      query: 'Mission District, San Francisco, CA',
      coordinates: { lat: 37.7599, lng: -122.4148 },
      preferences: {},
      generic_mode: true,
    });
  });

  it('returns null when no place is selected', () => {
    assert.equal(buildAnalyzePayload(null, PROFILES[0]), null);
  });
});

describe('profile form serialization', () => {
  it('converts an API profile to string-backed form state', () => {
    assert.deepEqual(profileToForm(PROFILES[0]), {
      name: 'Budget walker',
      car_reliance: 'no_car',
      energy_preference: 'balanced',
      top_priority: 'walkability_errands',
      budget_sensitivity: 'very_budget_conscious',
      generic_mode: false,
      commute_anchor_label: 'Union Station',
      commute_anchor_lat: '43.645',
      commute_anchor_lng: '-79.38',
      max_monthly_rent: '2200',
      must_haves: ['transit', 'groceries'],
      deal_breakers: ['lower_rent_pressure'],
      notes: 'Local only.',
    });
  });

  it('converts form state to API payload and omits blank optional values', () => {
    assert.deepEqual(
      formToPreferenceProfilePayload({
        name: ' Transit person ',
        car_reliance: 'no_car',
        energy_preference: '',
        top_priority: 'transit_access',
        budget_sensitivity: '',
        generic_mode: false,
        commute_anchor_label: ' Downtown ',
        commute_anchor_lat: '',
        commute_anchor_lng: '',
        max_monthly_rent: '',
        must_haves: ['transit'],
        deal_breakers: [],
        notes: '  ',
      }),
      {
        name: 'Transit person',
        car_reliance: 'no_car',
        top_priority: 'transit_access',
        generic_mode: false,
        commute_anchor: { label: 'Downtown' },
        must_haves: ['transit'],
        deal_breakers: [],
      },
    );
  });
});
