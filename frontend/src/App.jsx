import { useEffect, useMemo, useState } from 'react';
import MapView from './components/MapView.jsx';
import PreferenceProfiles from './components/PreferenceProfiles.jsx';
import Profile from './components/Profile.jsx';
import Questionnaire from './components/Questionnaire.jsx';
import SavedProfiles from './components/SavedProfiles.jsx';
import SearchBar from './components/SearchBar.jsx';
import { useNeighborhood } from './hooks/useNeighborhood.js';

export default function App() {
  const [selectedPlace, setSelectedPlace] = useState(null);
  const [preferences, setPreferences] = useState({});
  const [genericMode, setGenericMode] = useState(false);
  const {
    analyze,
    data,
    error,
    loading,
    retry,
    savedProfiles,
    savedProfileId,
    saveError,
    isSaving,
    preferenceProfiles,
    selectedPreferenceProfileId,
    setSelectedPreferenceProfileId,
    preferenceProfileError,
    isSavingPreferenceProfile,
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
  } = useNeighborhood();

  const selectedPreferenceProfile = useMemo(
    () => preferenceProfiles.find((profile) => profile.id === selectedPreferenceProfileId) || null,
    [preferenceProfiles, selectedPreferenceProfileId],
  );

  const analyzePayload = useMemo(
    () =>
      selectedPlace
        ? {
            query: selectedPlace.label,
            coordinates: selectedPlace.coordinates,
            preferences,
            generic_mode: genericMode,
            preference_profile_id: selectedPreferenceProfileId,
          }
        : null,
    [genericMode, preferences, selectedPlace, selectedPreferenceProfileId],
  );

  useEffect(() => {
    loadSavedProfiles().catch(() => null);
    loadPreferenceProfiles().catch(() => null);
  }, []);

  useEffect(() => {
    if (!selectedPreferenceProfile) return;
    setPreferences({
      car_reliance: selectedPreferenceProfile.car_reliance || '',
      energy_preference: selectedPreferenceProfile.energy_preference || '',
      top_priority: selectedPreferenceProfile.top_priority || '',
      budget_sensitivity: selectedPreferenceProfile.budget_sensitivity || '',
    });
    setGenericMode(Boolean(selectedPreferenceProfile.generic_mode));
  }, [selectedPreferenceProfile]);

  function handleSelectPlace(place) {
    setSelectedPlace(place);
    clearCurrentProfile();
  }

  async function handleOpenSavedProfile(profileId) {
    const saved = await openSavedProfile(profileId);
    if (saved?.response?.place) {
      setSelectedPlace(saved.response.place);
    }
  }

  async function handleDeleteSavedProfile(profileId) {
    const deletingActiveProfile = savedProfileId === profileId;
    await deleteSavedProfile(profileId);
    if (deletingActiveProfile) {
      setSelectedPlace(null);
    }
  }

  return (
    <main className="app-shell">
      <section className="map-stage">
        <MapView selectedPlace={selectedPlace} />
        <div className="top-overlay">
          <p className="eyebrow">VibeCheck</p>
          <SearchBar onSelect={handleSelectPlace} />
          {!selectedPlace && <p className="hint-line">Select an autocomplete result to fly to the neighborhood.</p>}
        </div>
        <aside className="analysis-panel">
          {selectedPlace && (
            <div className="selected-place-card">
              <p className="eyebrow">Selected place</p>
              <h1>{selectedPlace.label}</h1>
              <p>Choose preferences or skip them, then analyze the neighborhood fit.</p>
            </div>
          )}
          {selectedPlace && (
            <PreferenceProfiles
              profiles={preferenceProfiles}
              selectedProfileId={selectedPreferenceProfileId}
              onSelect={setSelectedPreferenceProfileId}
              onCreate={(profile) => createPreferenceProfile({ ...preferences, generic_mode: genericMode, ...profile })}
              onUpdate={(profileId, profile) =>
                updatePreferenceProfile(profileId, { ...preferences, generic_mode: genericMode, ...profile })}
              onDelete={(profileId) => deletePreferenceProfile(profileId).catch(() => null)}
              onSetDefault={(profileId) => setDefaultPreferenceProfile(profileId).catch(() => null)}
              error={preferenceProfileError}
              isSaving={isSavingPreferenceProfile}
            />
          )}
          {selectedPlace && (
            <Questionnaire
              preferences={preferences}
              genericMode={genericMode}
              selectedPreferenceProfile={selectedPreferenceProfile}
              profileManaged={Boolean(selectedPreferenceProfileId)}
              onChange={setPreferences}
              onGenericModeChange={setGenericMode}
              onAnalyze={() => analyzePayload && analyze(analyzePayload)}
              disabled={loading}
            />
          )}
          <SavedProfiles
            profiles={savedProfiles}
            onRefresh={() => loadSavedProfiles().catch(() => null)}
            onOpen={(profileId) => handleOpenSavedProfile(profileId).catch(() => null)}
            onDelete={(profileId) => handleDeleteSavedProfile(profileId).catch(() => null)}
          />
          {loading && <LoadingState />}
          {error && (
            <div className="panel-error" role="alert">
              <strong>Analysis could not finish.</strong>
              <p>{error}</p>
              <button type="button" onClick={retry}>Retry</button>
            </div>
          )}
          {!loading && !error && !data && (
            <div className="empty-profile-state">
              <strong>Ready when you are.</strong>
              <p>The profile will show fit, confidence, caveats, source statuses, and neighborhood context.</p>
            </div>
          )}
          {data && (
            <Profile
              response={data}
              savedProfileId={savedProfileId}
              saveError={saveError}
              isSaving={isSaving}
              onSave={() => saveCurrentProfile(data).catch(() => null)}
            />
          )}
        </aside>
      </section>
    </main>
  );
}

function LoadingState() {
  return (
    <div className="loading-state" aria-live="polite">
      <strong>Checking available signals...</strong>
      <ul>
        <li>Resolving place context</li>
        <li>Checking demographic context</li>
        <li>Reviewing access and affordability signals</li>
        <li>Preparing confidence and fit explanation</li>
      </ul>
    </div>
  );
}
