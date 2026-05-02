import { useMemo, useState } from 'react';
import MapView from './components/MapView.jsx';
import Profile from './components/Profile.jsx';
import Questionnaire from './components/Questionnaire.jsx';
import SearchBar from './components/SearchBar.jsx';
import { useNeighborhood } from './hooks/useNeighborhood.js';

export default function App() {
  const [selectedPlace, setSelectedPlace] = useState(null);
  const [preferences, setPreferences] = useState({});
  const [genericMode, setGenericMode] = useState(false);
  const { analyze, data, error, loading, retry } = useNeighborhood();

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
            <Questionnaire
              preferences={preferences}
              genericMode={genericMode}
              onChange={setPreferences}
              onGenericModeChange={setGenericMode}
              onAnalyze={() => analyzePayload && analyze(analyzePayload)}
              disabled={loading}
            />
            {loading && <p className="status-line">Checking source availability...</p>}
            {error && (
              <div className="panel-error">
                <p>{error}</p>
                <button type="button" onClick={retry}>Retry</button>
              </div>
            )}
            {data && <Profile response={data} />}
          </aside>
        )}
      </section>
    </main>
  );
}
