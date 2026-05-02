import { useEffect, useMemo, useState } from 'react';
import MapView from './components/MapView.jsx';
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
    loadSavedProfiles,
    saveCurrentProfile,
    openSavedProfile,
    deleteSavedProfile,
  } = useNeighborhood();

  const analyzePayload = useMemo(
    () =>
      selectedPlace
        ? {
            query: selectedPlace.label,
            coordinates: selectedPlace.coordinates,
            preferences,
            generic_mode: genericMode,
          }
        : null,
    [genericMode, preferences, selectedPlace],
  );

  useEffect(() => {
    loadSavedProfiles().catch(() => null);
  }, []);

  return (
    <main className="app-shell">
      <section className="map-stage">
        <MapView selectedPlace={selectedPlace} />
        <div className="top-overlay">
          <p className="eyebrow">VibeCheck</p>
          <SearchBar onSelect={setSelectedPlace} />
          {!selectedPlace && <p className="hint-line">Select an autocomplete result to fly to the neighborhood.</p>}
        </div>
        {selectedPlace && (
          <aside className="analysis-panel">
            <div className="selected-place-card">
              <p className="eyebrow">Selected place</p>
              <h1>{selectedPlace.label}</h1>
              <p>Choose preferences or skip them, then analyze the neighborhood fit.</p>
            </div>
            <Questionnaire
              preferences={preferences}
              genericMode={genericMode}
              onChange={setPreferences}
              onGenericModeChange={setGenericMode}
              onAnalyze={() => analyzePayload && analyze(analyzePayload)}
              disabled={loading}
            />
            <SavedProfiles
              profiles={savedProfiles}
              onRefresh={() => loadSavedProfiles().catch(() => null)}
              onOpen={(profileId) => openSavedProfile(profileId).catch(() => null)}
              onDelete={(profileId) => deleteSavedProfile(profileId).catch(() => null)}
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
                onSave={() => saveCurrentProfile(data).catch(() => null)}
              />
            )}
          </aside>
        )}
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
