import { useRef, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export function useNeighborhood() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [savedProfiles, setSavedProfiles] = useState([]);
  const [saveError, setSaveError] = useState('');
  const [savedProfileId, setSavedProfileId] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [lastRequest, setLastRequest] = useState(null);
  const currentProfileRef = useRef(null);
  const analyzeRequestRef = useRef(0);
  const openRequestRef = useRef(0);
  const saveInFlightRef = useRef(false);

  function setCurrentData(nextData) {
    currentProfileRef.current = nextData;
    setData(nextData);
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
    setCurrentData(null);
    setSavedProfileId(null);
    setLastRequest(payload);
    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const body = await parseResponse(response, `Analyze failed with ${response.status}`);
      if (analyzeRequestRef.current !== requestId) {
        return null;
      }
      setCurrentData(body);
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
        body: JSON.stringify(profileData),
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
    const response = await fetch(`${API_BASE_URL}/profiles/${profileId}`);
    const body = await parseResponse(response, `Open saved profile failed with ${response.status}`);
    if (openRequestRef.current !== requestId) {
      return null;
    }
    setCurrentData(body.response);
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
    }
    return body;
  }

  function clearCurrentProfile() {
    invalidateOpenRequest();
    invalidateAnalyzeRequest();
    setCurrentData(null);
    setError('');
    setSaveError('');
    setSavedProfileId(null);
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
    saveError,
    savedProfileId,
    isSaving,
    loadSavedProfiles,
    saveCurrentProfile,
    openSavedProfile,
    deleteSavedProfile,
    clearCurrentProfile,
  };
}

async function parseResponse(response, fallbackMessage) {
  if (response.ok) {
    return response.json();
  }

  let message = fallbackMessage;
  try {
    const body = await response.json();
    message = body.detail || body.message || message;
  } catch {
    // Keep the status-based fallback when the server did not return JSON.
  }
  throw new Error(message);
}
