import { useEffect, useMemo, useState } from 'react';
import MapView from './components/MapView.jsx';
import PreferenceProfiles from './components/PreferenceProfiles.jsx';
import Profile from './components/Profile.jsx';
import SavedProfiles from './components/SavedProfiles.jsx';
import TopBar from './components/TopBar.jsx';
import { useNeighborhood } from './hooks/useNeighborhood.js';
import { buildAnalyzePayload } from './utils/preferenceProfiles.js';

export default function App() {
  const [selectedPlace, setSelectedPlace] = useState(null);
  const [activeWorkspace, setActiveWorkspace] = useState(null);
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
    () => buildAnalyzePayload(selectedPlace, selectedPreferenceProfile),
    [selectedPlace, selectedPreferenceProfile],
  );

  useEffect(() => {
    loadSavedProfiles().catch(() => null);
    loadPreferenceProfiles().catch(() => null);
  }, []);

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
        <TopBar
          activeProfile={selectedPreferenceProfile}
          preferenceProfileError={preferenceProfileError}
          onProfileClick={() => setActiveWorkspace('profiles')}
          onSavedReportsClick={() => setActiveWorkspace('savedReports')}
          onSelectPlace={handleSelectPlace}
        />
        <PreferenceProfiles
          open={activeWorkspace === 'profiles'}
          profiles={preferenceProfiles}
          selectedProfileId={selectedPreferenceProfileId}
          onClose={() => setActiveWorkspace(null)}
          onSelect={setSelectedPreferenceProfileId}
          onCreate={createPreferenceProfile}
          onUpdate={updatePreferenceProfile}
          onDelete={(profileId) => deletePreferenceProfile(profileId).catch(() => null)}
          onSetDefault={(profileId) => setDefaultPreferenceProfile(profileId).catch(() => null)}
          error={preferenceProfileError}
          isSaving={isSavingPreferenceProfile}
        />
        <SavedProfiles
          open={activeWorkspace === 'savedReports'}
          profiles={savedProfiles}
          onClose={() => setActiveWorkspace(null)}
          onRefresh={() => loadSavedProfiles().catch(() => null)}
          onOpen={(profileId) => {
            handleOpenSavedProfile(profileId).catch(() => null);
            setActiveWorkspace(null);
          }}
          onDelete={(profileId) => handleDeleteSavedProfile(profileId).catch(() => null)}
        />
        <aside className="analysis-panel">
          {selectedPlace && (
            <div className="selected-place-card">
              <p className="eyebrow">Selected place</p>
              <h1>{selectedPlace.label}</h1>
              <p>{selectedPreferenceProfile ? `Analyzing for ${selectedPreferenceProfile.name}.` : 'Running a generic neighborhood check.'}</p>
              <button className="primary-button" type="button" disabled={loading} onClick={() => analyzePayload && analyze(analyzePayload)}>
                {loading ? 'Analyzing...' : 'Analyze neighborhood'}
              </button>
            </div>
          )}
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
              <strong>{selectedPlace ? 'Ready to analyze.' : 'Choose a place to begin.'}</strong>
              <p>
                {selectedPlace
                  ? 'The profile will show fit, confidence, caveats, source statuses, and neighborhood context.'
                  : 'Select a saved lifestyle profile or keep Generic active, then search for an address or neighborhood.'}
              </p>
            </div>
          )}
          {data && (
            <Profile
              response={data}
              activePreferenceProfile={selectedPreferenceProfile}
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
