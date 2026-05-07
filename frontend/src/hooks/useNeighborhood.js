import { useRef, useState } from 'react';
import { API_BASE_URL, analyzeNeighborhood, parseResponse, refreshSavedProfile } from '../utils/api.js';
import { resolveSelectedPreferenceProfileId } from '../utils/preferenceProfiles.js';

export function useNeighborhood() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [saveError, setSaveError] = useState('');
  const [refreshError, setRefreshError] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [generatedAt, setGeneratedAt] = useState(null);
  const [savedProfileId, setSavedProfileId] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [preferenceProfiles, setPreferenceProfiles] = useState([]);
  const [selectedPreferenceProfileId, setSelectedPreferenceProfileId] = useState(null);
  const [preferenceProfileError, setPreferenceProfileError] = useState('');
  const [isSavingPreferenceProfile, setIsSavingPreferenceProfile] = useState(false);
  const [loading, setLoading] = useState(false);
  const [lastRequest, setLastRequest] = useState(null);
  const currentProfileRef = useRef(null);
  const analyzeRequestRef = useRef(0);
  const openRequestRef = useRef(0);
  const saveInFlightRef = useRef(false);
  const preferenceProfilesInitializedRef = useRef(false);

  function setCurrentData(nextData, nextGeneratedAt = nextData ? new Date().toISOString() : null) {
    currentProfileRef.current = nextData;
    setData(nextData);
    setGeneratedAt(nextGeneratedAt);
  }

  function invalidateAnalyzeRequest() {
    analyzeRequestRef.current += 1;
    setLoading(false);
  }

  function invalidateOpenRequest() {
    openRequestRef.current += 1;
  }

  async function analyze(payload) {
    invalidateOpenRequest();
    const requestId = analyzeRequestRef.current + 1;
    analyzeRequestRef.current = requestId;
    setLoading(true);
    setError('');
    setSaveError('');
    setRefreshError('');
    setCurrentData(null);
    setSavedProfileId(null);
    setLastRequest(payload);
    try {
      const body = await analyzeNeighborhood(payload);
      if (analyzeRequestRef.current !== requestId) {
        return null;
      }
      const timestamp = new Date().toISOString();
      setCurrentData(body, timestamp);
      return body;
    } catch (err) {
      if (analyzeRequestRef.current === requestId) {
        setError(err instanceof Error ? err.message : 'Analyze failed');
      }
      return null;
    } finally {
      if (analyzeRequestRef.current === requestId) {
        setLoading(false);
      }
    }
  }

  async function loadPreferenceProfiles() {
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles`);
      const body = await parseResponse(response, `Load preference profiles failed with ${response.status}`);
      setPreferenceProfiles(body);
      setPreferenceProfileError('');
      const preferDefault = !preferenceProfilesInitializedRef.current;
      setSelectedPreferenceProfileId((current) =>
        resolveSelectedPreferenceProfileId(body, current, { preferDefault }),
      );
      preferenceProfilesInitializedRef.current = true;
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Load preference profiles failed';
      setPreferenceProfileError(message);
      return [];
    }
  }

  async function createPreferenceProfile(profile) {
    setIsSavingPreferenceProfile(true);
    setPreferenceProfileError('');
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
      const body = await parseResponse(response, `Create preference profile failed with ${response.status}`);
      await loadPreferenceProfiles();
      setSelectedPreferenceProfileId(body.id);
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Create preference profile failed';
      setPreferenceProfileError(message);
      throw err;
    } finally {
      setIsSavingPreferenceProfile(false);
    }
  }

  async function updatePreferenceProfile(profileId, profile) {
    setIsSavingPreferenceProfile(true);
    setPreferenceProfileError('');
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles/${profileId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
      const body = await parseResponse(response, `Update preference profile failed with ${response.status}`);
      await loadPreferenceProfiles();
      setSelectedPreferenceProfileId(body.id);
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Update preference profile failed';
      setPreferenceProfileError(message);
      throw err;
    } finally {
      setIsSavingPreferenceProfile(false);
    }
  }

  async function deletePreferenceProfile(profileId) {
    setPreferenceProfileError('');
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles/${profileId}`, {
        method: 'DELETE',
      });
      const body = await parseResponse(response, `Delete preference profile failed with ${response.status}`);
      const profiles = await loadPreferenceProfiles();
      if (selectedPreferenceProfileId === profileId) {
        const defaultProfile = profiles.find((profile) => profile.is_default) || profiles[0] || null;
        setSelectedPreferenceProfileId(defaultProfile?.id || null);
      }
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete preference profile failed';
      setPreferenceProfileError(message);
      throw err;
    }
  }

  async function setDefaultPreferenceProfile(profileId) {
    setPreferenceProfileError('');
    try {
      const response = await fetch(`${API_BASE_URL}/preference-profiles/${profileId}/default`, {
        method: 'POST',
      });
      const body = await parseResponse(response, `Set default preference profile failed with ${response.status}`);
      await loadPreferenceProfiles();
      setSelectedPreferenceProfileId(body.id);
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Set default preference profile failed';
      setPreferenceProfileError(message);
      throw err;
    }
  }

  async function loadSavedProfiles() {
    const response = await fetch(`${API_BASE_URL}/profiles`);
    const body = await parseResponse(response, `Load saved profiles failed with ${response.status}`);
    setSavedProfiles(body);
    return body;
  }

  async function saveCurrentProfile(profileData = data) {
    if (saveInFlightRef.current) {
      return null;
    }

    setSaveError('');
    if (!profileData) {
      const message = 'No profile is available to save.';
      setSaveError(message);
      throw new Error(message);
    }

    saveInFlightRef.current = true;
    setIsSaving(true);
    const savingProfile = profileData;
    try {
      const response = await fetch(`${API_BASE_URL}/profiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          response: profileData,
          analyze_request: lastRequest,
        }),
      });
      const body = await parseResponse(response, `Save profile failed with ${response.status}`);
      await loadSavedProfiles();
      if (currentProfileRef.current === savingProfile) {
        setSavedProfileId(body.id);
      }
      return body;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Save profile failed';
      if (currentProfileRef.current === savingProfile) {
        setSaveError(message);
      }
      throw err;
    } finally {
      saveInFlightRef.current = false;
      setIsSaving(false);
    }
  }

  async function openSavedProfile(profileId) {
    const requestId = openRequestRef.current + 1;
    openRequestRef.current = requestId;
    invalidateAnalyzeRequest();
    setError('');
    setSaveError('');
    setRefreshError('');
    const response = await fetch(`${API_BASE_URL}/profiles/${profileId}`);
    const body = await parseResponse(response, `Open saved profile failed with ${response.status}`);
    if (openRequestRef.current !== requestId) {
      return null;
    }
    setCurrentData(body.response, body.updated_at);
    setSavedProfileId(body.id);
    return body;
  }

  async function deleteSavedProfile(profileId) {
    invalidateOpenRequest();
    const response = await fetch(`${API_BASE_URL}/profiles/${profileId}`, {
      method: 'DELETE',
    });
    const body = await parseResponse(response, `Delete saved profile failed with ${response.status}`);
    await loadSavedProfiles();
    if (savedProfileId === profileId) {
      setCurrentData(null);
      setSavedProfileId(null);
      setSaveError('');
      setRefreshError('');
    }
    return body;
  }

  function clearCurrentProfile() {
    invalidateOpenRequest();
    invalidateAnalyzeRequest();
    setCurrentData(null);
    setError('');
    setSaveError('');
    setRefreshError('');
    setSavedProfileId(null);
  }

  async function refreshCurrentProfile() {
    if (!data) return null;

    setRefreshError('');
    setIsRefreshing(true);
    try {
      if (savedProfileId) {
        const refreshed = await refreshSavedProfile(savedProfileId);
        await loadSavedProfiles();
        setCurrentData(refreshed.response, refreshed.updated_at);
        setSavedProfileId(refreshed.id);
        return refreshed.response;
      }
      if (!lastRequest) {
        throw new Error('No analysis request is available to refresh.');
      }

      const refreshed = await analyzeNeighborhood(lastRequest);
      setCurrentData(refreshed, new Date().toISOString());
      return refreshed;
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : 'Refresh failed');
      return null;
    } finally {
      setIsRefreshing(false);
    }
  }

  function retry() {
    if (!lastRequest) return Promise.resolve(null);
    return analyze(lastRequest);
  }

  return {
    analyze,
    retry,
    data,
    error,
    loading,
    savedProfiles,
    preferenceProfiles,
    selectedPreferenceProfileId,
    setSelectedPreferenceProfileId,
    preferenceProfileError,
    isSavingPreferenceProfile,
    saveError,
    refreshError,
    savedProfileId,
    isSaving,
    isRefreshing,
    generatedAt,
    loadPreferenceProfiles,
    createPreferenceProfile,
    updatePreferenceProfile,
    deletePreferenceProfile,
    setDefaultPreferenceProfile,
    loadSavedProfiles,
    saveCurrentProfile,
    openSavedProfile,
    deleteSavedProfile,
    clearCurrentProfile,
    refreshCurrentProfile,
  };
}
