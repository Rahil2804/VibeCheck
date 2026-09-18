import { useMemo, useReducer, useRef, useState } from 'react';
import { API_BASE_URL, analyzeNeighborhood, parseResponse, refreshSavedProfile } from '../utils/api.js';
import { resolveSelectedPreferenceProfileId } from '../utils/preferenceProfiles.js';

const GENERIC_LENS = {
  mode: 'generic',
  profile_id: null,
  profile_name: 'Generic',
  preferences: {},
};

export const INITIAL_ANALYSIS_SESSION = {
  selectedPlace: null,
  activeLens: GENERIC_LENS,
  request: null,
  returnedLens: null,
  response: null,
  freshness: null,
  savedReportId: null,
  loading: false,
  errors: { analyze: '', save: '', refresh: '', saved: '', profiles: '' },
};

export function analysisSessionReducer(state, action) {
  switch (action.type) {
    case 'select_place':
      return {
        ...state,
        selectedPlace: action.place,
        request: null,
        returnedLens: null,
        response: null,
        freshness: null,
        savedReportId: null,
        errors: { ...state.errors, analyze: '', save: '', refresh: '' },
      };
    case 'select_lens':
      return { ...state, activeLens: action.lens };
    case 'analyze_start':
      return {
        ...state,
        loading: true,
        request: action.request,
        response: null,
        returnedLens: null,
        savedReportId: null,
        errors: { ...state.errors, analyze: '', save: '', refresh: '' },
      };
    case 'analyze_success':
      return {
        ...state,
        loading: false,
        response: action.response,
        returnedLens: action.response.analysis_lens,
        freshness: action.freshness,
      };
    case 'analyze_error':
      return { ...state, loading: false, errors: { ...state.errors, analyze: action.message } };
    case 'open_saved':
      return {
        ...state,
        selectedPlace: action.saved.response.place,
        activeLens: action.saved.analysis_lens || action.saved.response.analysis_lens || GENERIC_LENS,
        request: action.saved.analyze_request,
        returnedLens: action.saved.analysis_lens || action.saved.response.analysis_lens,
        response: action.saved.response,
        freshness: action.saved.updated_at,
        savedReportId: action.saved.id,
        loading: false,
        errors: { ...state.errors, analyze: '', save: '', refresh: '' },
      };
    case 'saved':
      return { ...state, savedReportId: action.id, errors: { ...state.errors, save: '' } };
    case 'refreshed':
      return {
        ...state,
        response: action.saved.response,
        returnedLens: action.saved.analysis_lens || action.saved.response.analysis_lens,
        freshness: action.saved.updated_at,
        savedReportId: action.saved.id,
        errors: { ...state.errors, refresh: '' },
      };
    case 'clear_saved':
      return { ...state, savedReportId: null };
    case 'error':
      return { ...state, errors: { ...state.errors, [action.scope]: action.message } };
    default:
      return state;
  }
}

export function useNeighborhood() {
  const [session, dispatch] = useReducer(analysisSessionReducer, INITIAL_ANALYSIS_SESSION);
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [preferenceProfiles, setPreferenceProfiles] = useState([]);
  const [selectedPreferenceProfileId, setSelectedPreferenceProfileIdState] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSavingPreferenceProfile, setIsSavingPreferenceProfile] = useState(false);
  const analyzeControllerRef = useRef(null);
  const openControllerRef = useRef(null);
  const initializedProfilesRef = useRef(false);
  const saveInFlightRef = useRef(false);

  const lensIsStale = useMemo(
    () =>
      Boolean(session.response && session.returnedLens) &&
      JSON.stringify(session.activeLens) !== JSON.stringify(session.returnedLens),
    [session.activeLens, session.response, session.returnedLens],
  );

  function setSelectedPreferenceProfileId(profileId) {
    setSelectedPreferenceProfileIdState(profileId);
    const profile = preferenceProfiles.find((item) => item.id === profileId);
    dispatch({ type: 'select_lens', lens: profile ? profileLens(profile) : GENERIC_LENS });
  }

  function selectPlace(place) {
    analyzeControllerRef.current?.abort();
    openControllerRef.current?.abort();
    dispatch({ type: 'select_place', place });
  }

  async function analyze(payload) {
    openControllerRef.current?.abort();
    analyzeControllerRef.current?.abort();
    const controller = new AbortController();
    analyzeControllerRef.current = controller;
    dispatch({ type: 'analyze_start', request: payload });
    try {
      const body = await analyzeNeighborhood(payload, { signal: controller.signal });
      dispatch({ type: 'analyze_success', response: body, freshness: new Date().toISOString() });
      return body;
    } catch (error) {
      if (error.name !== 'AbortError') {
        dispatch({ type: 'analyze_error', message: error.message || 'Analyze failed' });
      }
      return null;
    }
  }

  async function loadPreferenceProfiles() {
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles`);
      const body = await parseResponse(response, `Load preference profiles failed with ${response.status}`);
      setPreferenceProfiles(body);
      dispatch({ type: 'error', scope: 'profiles', message: '' });
      if (!initializedProfilesRef.current) {
        const id = resolveSelectedPreferenceProfileId(body, null, { preferDefault: true });
        setSelectedPreferenceProfileIdState(id);
        const profile = body.find((item) => item.id === id);
        dispatch({ type: 'select_lens', lens: profile ? profileLens(profile) : GENERIC_LENS });
        initializedProfilesRef.current = true;
      }
      return body;
    } catch (error) {
      dispatch({ type: 'error', scope: 'profiles', message: error.message || 'Profiles failed' });
      return [];
    }
  }

  async function mutatePreference(path, method, payload) {
    setIsSavingPreferenceProfile(true);
    dispatch({ type: 'error', scope: 'profiles', message: '' });
    try {
      const response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: payload ? { 'Content-Type': 'application/json' } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
      });
      const body = await parseResponse(response, `Profile action failed with ${response.status}`);
      await loadPreferenceProfiles();
      return body;
    } catch (error) {
      dispatch({ type: 'error', scope: 'profiles', message: error.message || 'Profile action failed' });
      throw error;
    } finally {
      setIsSavingPreferenceProfile(false);
    }
  }

  async function createPreferenceProfile(profile) {
    const created = await mutatePreference('/preference-profiles', 'POST', profile);
    setSelectedPreferenceProfileIdState(created.id);
    dispatch({ type: 'select_lens', lens: profileLens(created) });
    return created;
  }

  async function updatePreferenceProfile(profileId, profile) {
    const updated = await mutatePreference(`/preference-profiles/${profileId}`, 'PUT', profile);
    setSelectedPreferenceProfileIdState(updated.id);
    dispatch({ type: 'select_lens', lens: profileLens(updated) });
    return updated;
  }

  async function deletePreferenceProfile(profileId) {
    const deleted = await mutatePreference(`/preference-profiles/${profileId}`, 'DELETE');
    const remaining = await loadPreferenceProfiles();
    if (selectedPreferenceProfileId === profileId) {
      const next = remaining.find((item) => item.is_default) || remaining[0] || null;
      setSelectedPreferenceProfileIdState(next?.id || null);
      dispatch({ type: 'select_lens', lens: next ? profileLens(next) : GENERIC_LENS });
    }
    return deleted;
  }

  async function setDefaultPreferenceProfile(profileId) {
    const updated = await mutatePreference(`/preference-profiles/${profileId}/default`, 'POST');
    setSelectedPreferenceProfileIdState(updated.id);
    dispatch({ type: 'select_lens', lens: profileLens(updated) });
    return updated;
  }

  async function loadSavedProfiles() {
    try {
      const response = await fetch(`${API_BASE_URL}/profiles`);
      const body = await parseResponse(response, `Load saved reports failed with ${response.status}`);
      setSavedProfiles(body);
      dispatch({ type: 'error', scope: 'saved', message: '' });
      return body;
    } catch (error) {
      dispatch({ type: 'error', scope: 'saved', message: error.message || 'Saved reports failed' });
      return [];
    }
  }

  async function saveCurrentProfile() {
    if (saveInFlightRef.current || !session.response) return null;
    saveInFlightRef.current = true;
    setIsSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/profiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ response: session.response, analyze_request: session.request }),
      });
      const saved = await parseResponse(response, `Save report failed with ${response.status}`);
      dispatch({ type: 'saved', id: saved.id });
      await loadSavedProfiles();
      return saved;
    } catch (error) {
      dispatch({ type: 'error', scope: 'save', message: error.message || 'Save failed' });
      return null;
    } finally {
      saveInFlightRef.current = false;
      setIsSaving(false);
    }
  }

  async function openSavedProfile(profileId) {
    analyzeControllerRef.current?.abort();
    openControllerRef.current?.abort();
    const controller = new AbortController();
    openControllerRef.current = controller;
    try {
      const response = await fetch(`${API_BASE_URL}/profiles/${profileId}`, {
        signal: controller.signal,
      });
      const saved = await parseResponse(response, `Open saved report failed with ${response.status}`);
      dispatch({ type: 'open_saved', saved });
      setSelectedPreferenceProfileIdState(saved.analysis_lens?.profile_id || null);
      return saved;
    } catch (error) {
      if (error.name !== 'AbortError') {
        dispatch({ type: 'error', scope: 'saved', message: error.message || 'Open failed' });
      }
      return null;
    }
  }

  async function deleteSavedProfile(profileId) {
    try {
      const response = await fetch(`${API_BASE_URL}/profiles/${profileId}`, { method: 'DELETE' });
      await parseResponse(response, `Delete saved report failed with ${response.status}`);
      if (session.savedReportId === profileId) dispatch({ type: 'clear_saved' });
      await loadSavedProfiles();
    } catch (error) {
      dispatch({ type: 'error', scope: 'saved', message: error.message || 'Delete failed' });
    }
  }

  async function refreshCurrentProfile() {
    if (!session.savedReportId) {
      return session.request ? analyze(session.request) : null;
    }
    setIsRefreshing(true);
    try {
      const saved = await refreshSavedProfile(session.savedReportId);
      dispatch({ type: 'refreshed', saved });
      await loadSavedProfiles();
      return saved.response;
    } catch (error) {
      dispatch({ type: 'error', scope: 'refresh', message: error.message || 'Refresh failed' });
      return null;
    } finally {
      setIsRefreshing(false);
    }
  }

  return {
    ...session,
    data: session.response,
    error: session.errors.analyze,
    saveError: session.errors.save,
    refreshError: session.errors.refresh,
    preferenceProfileError: session.errors.profiles,
    savedProfilesError: session.errors.saved,
    savedProfileId: session.savedReportId,
    generatedAt: session.freshness,
    lensIsStale,
    savedProfiles,
    preferenceProfiles,
    selectedPreferenceProfileId,
    setSelectedPreferenceProfileId,
    selectPlace,
    loading: session.loading,
    isSaving,
    isRefreshing,
    isSavingPreferenceProfile,
    analyze,
    retry: () => (session.request ? analyze(session.request) : Promise.resolve(null)),
    loadPreferenceProfiles,
    createPreferenceProfile,
    updatePreferenceProfile,
    deletePreferenceProfile,
    setDefaultPreferenceProfile,
    loadSavedProfiles,
    saveCurrentProfile,
    openSavedProfile,
    deleteSavedProfile,
    refreshCurrentProfile,
  };
}

function profileLens(profile) {
  return {
    mode: profile.generic_mode ? 'generic' : 'saved_profile',
    profile_id: profile.id,
    profile_name: profile.name,
    preferences: {
      car_reliance: profile.car_reliance,
      energy_preference: profile.energy_preference,
      top_priority: profile.top_priority,
      budget_sensitivity: profile.budget_sensitivity,
      max_monthly_rent: profile.max_monthly_rent,
      rental_unit_size: profile.rental_unit_size,
      must_haves: profile.must_haves || [],
      deal_breakers: profile.deal_breakers || [],
    },
  };
}
