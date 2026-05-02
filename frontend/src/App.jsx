import { useMemo, useState } from 'react';
import Questionnaire from './components/Questionnaire.jsx';
import { useNeighborhood } from './hooks/useNeighborhood.js';

const DEMO_PLACE = {
  label: 'East Austin, Austin, TX',
  coordinates: { lat: 30.2636, lng: -97.7114 },
};

export default function App() {
  const [selectedPlace, setSelectedPlace] = useState(DEMO_PLACE);
  const [preferences, setPreferences] = useState({});
  const [genericMode, setGenericMode] = useState(false);
  const { analyze, data, error, loading, retry } = useNeighborhood();

  const analyzePayload = useMemo(
    () => ({
      query: selectedPlace.label,
      coordinates: selectedPlace.coordinates,
      preferences,
      generic_mode: genericMode,
    }),
    [genericMode, preferences, selectedPlace],
  );

  return (
    <main className="app-shell">
      <section className="map-stage">
        <div className="setup-panel">
          <p className="eyebrow">VibeCheck</p>
          <h1>{selectedPlace.label}</h1>
          <p>Mapbox search lands here in the next task. This temporary place keeps the analyze flow testable.</p>
          <button type="button" onClick={() => setSelectedPlace(DEMO_PLACE)}>Use demo place</button>
        </div>
        <aside className="analysis-panel">
          <Questionnaire
            preferences={preferences}
            genericMode={genericMode}
            onChange={setPreferences}
            onGenericModeChange={setGenericMode}
            onAnalyze={() => analyze(analyzePayload)}
            disabled={loading}
          />
          {loading && <p className="status-line">Checking source availability...</p>}
          {error && (
            <div className="panel-error">
              <p>{error}</p>
              <button type="button" onClick={retry}>Retry</button>
            </div>
          )}
          {data && <pre className="debug-response">{JSON.stringify(data.profile, null, 2)}</pre>}
        </aside>
      </section>
    </main>
  );
}
