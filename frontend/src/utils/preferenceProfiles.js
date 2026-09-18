export const EMPTY_PROFILE_FORM = {
  name: '',
  car_reliance: '',
  energy_preference: '',
  top_priority: '',
  budget_sensitivity: '',
  generic_mode: false,
  commute_anchor_label: '',
  commute_anchor_lat: '',
  commute_anchor_lng: '',
  max_monthly_rent: '',
  rental_unit_size: '',
  must_haves: [],
  deal_breakers: [],
  notes: '',
};

export function resolveSelectedPreferenceProfileId(
  profiles = [],
  currentProfileId = null,
  { preferDefault = true } = {},
) {
  if (currentProfileId && profiles.some((profile) => profile.id === currentProfileId)) {
    return currentProfileId;
  }
  if (!preferDefault) {
    return null;
  }
  const defaultProfile = profiles.find((profile) => profile.is_default) || profiles[0] || null;
  return defaultProfile?.id || null;
}

export function getActiveProfileLabel(profile) {
  return `Active profile: ${profile?.name || 'Generic'}`;
}

export function buildAnalyzePayload(place, activeProfile) {
  if (!place) return null;
  const basePayload = {
    query: place.label,
    coordinates: place.coordinates,
  };
  if (activeProfile?.id) {
    return {
      ...basePayload,
      generic_mode: Boolean(activeProfile.generic_mode),
      preference_profile_id: activeProfile.id,
    };
  }
  return {
    ...basePayload,
    preferences: {},
    generic_mode: true,
  };
}

export function buildAnalyzePayloadForLens(place, lens, profiles = []) {
  if (!place) return null;
  const basePayload = { query: place.label, coordinates: place.coordinates };
  const liveProfile = profiles.find((profile) => profile.id === lens?.profile_id);
  if (liveProfile) return buildAnalyzePayload(place, liveProfile);
  if (!lens || lens.mode === 'generic' || lens.mode === 'legacy') {
    return { ...basePayload, preferences: {}, generic_mode: true };
  }
  return {
    ...basePayload,
    preferences: lens.preferences || {},
    generic_mode: false,
  };
}

export function profileToForm(profile) {
  if (!profile) return { ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] };
  return {
    name: profile.name || '',
    car_reliance: profile.car_reliance || '',
    energy_preference: profile.energy_preference || '',
    top_priority: profile.top_priority || '',
    budget_sensitivity: profile.budget_sensitivity || '',
    generic_mode: Boolean(profile.generic_mode),
    commute_anchor_label: profile.commute_anchor?.label || '',
    commute_anchor_lat: numberToInput(profile.commute_anchor?.lat),
    commute_anchor_lng: numberToInput(profile.commute_anchor?.lng),
    max_monthly_rent: numberToInput(profile.max_monthly_rent),
    rental_unit_size: profile.rental_unit_size || '',
    must_haves: profile.must_haves || [],
    deal_breakers: profile.deal_breakers || [],
    notes: profile.notes || '',
  };
}

export function formToPreferenceProfilePayload(form, { mode = 'create' } = {}) {
  const includeClears = mode === 'update';
  const payload = {
    name: form.name.trim(),
    generic_mode: Boolean(form.generic_mode),
    must_haves: form.must_haves || [],
    deal_breakers: form.deal_breakers || [],
  };

  copyOptional(payload, 'car_reliance', form.car_reliance, includeClears);
  copyOptional(payload, 'energy_preference', form.energy_preference, includeClears);
  copyOptional(payload, 'top_priority', form.top_priority, includeClears);
  copyOptional(payload, 'budget_sensitivity', form.budget_sensitivity, includeClears);
  copyOptional(payload, 'rental_unit_size', form.rental_unit_size, includeClears);

  const commuteLabel = form.commute_anchor_label.trim();
  const commuteLat = form.commute_anchor_lat === '' ? null : Number(form.commute_anchor_lat);
  const commuteLng = form.commute_anchor_lng === '' ? null : Number(form.commute_anchor_lng);
  if (commuteLabel) {
    payload.commute_anchor = { label: commuteLabel };
    if (commuteLat !== null && commuteLng !== null) {
      payload.commute_anchor.lat = commuteLat;
      payload.commute_anchor.lng = commuteLng;
    }
  } else if (includeClears) {
    payload.commute_anchor = null;
  }

  if (form.max_monthly_rent !== '') {
    payload.max_monthly_rent = Number(form.max_monthly_rent);
  } else if (includeClears) {
    payload.max_monthly_rent = null;
  }
  if (form.notes.trim()) {
    payload.notes = form.notes.trim();
  } else if (includeClears) {
    payload.notes = null;
  }
  return payload;
}

function copyOptional(target, key, value, includeClears) {
  if (value) {
    target[key] = value;
  } else if (includeClears) {
    target[key] = null;
  }
}

function numberToInput(value) {
  return value === null || value === undefined ? '' : String(value);
}
