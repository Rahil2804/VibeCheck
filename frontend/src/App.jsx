import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Archive, Map as MapIcon, Scale, SlidersHorizontal } from 'lucide-react';
import Profile from './components/Profile.jsx';
import TopBar from './components/TopBar.jsx';
import { useNeighborhood } from './hooks/useNeighborhood.js';
import { getHealth } from './utils/api.js';
import { buildAnalyzePayloadForLens } from './utils/preferenceProfiles.js';

const MapView = lazy(() => import('./components/MapView.jsx'));
const PreferenceProfiles = lazy(() => import('./components/PreferenceProfiles.jsx'));
const SavedProfiles = lazy(() => import('./components/SavedProfiles.jsx'));
const CompareMode = lazy(() => import('./components/CompareMode.jsx'));

export default function App() {
  const [workspace, setWorkspace] = useState(null);
  const [setupHealth, setSetupHealth] = useState(null);
  const [setupHealthError, setSetupHealthError] = useState('');
  const neighborhood = useNeighborhood();
  const {
    activeLens,
    analyze,
    data,
    error,
    errors,
    generatedAt,
    isRefreshing,
    isSaving,
    isSavingPreferenceProfile,
    lensIsStale,
    loading,
    preferenceProfiles,
    refreshCurrentProfile,
    savedProfileId,
    savedProfiles,
    selectPlace,
    selectedPlace,
    selectedPreferenceProfileId,
    setSelectedPreferenceProfileId,
  } = neighborhood;

  const selectedPreferenceProfile = useMemo(
    () => preferenceProfiles.find((profile) => profile.id === selectedPreferenceProfileId) || null,
    [preferenceProfiles, selectedPreferenceProfileId],
  );
  const analyzePayload = useMemo(
    () => buildAnalyzePayloadForLens(selectedPlace, activeLens, preferenceProfiles),
    [activeLens, preferenceProfiles, selectedPlace],
  );

  useEffect(() => {
    neighborhood.loadSavedProfiles();
    neighborhood.loadPreferenceProfiles();
    if (import.meta.env.DEV) {
      getHealth()
        .then(setSetupHealth)
        .catch((healthError) => setSetupHealthError(healthError.message || 'Backend health check failed'));
    }
  }, []);

  async function openSaved(id) {
    const saved = await neighborhood.openSavedProfile(id);
    if (saved) setWorkspace(null);
  }

  const coverageLabel = data?.coverage
    ? `${labelize(data.coverage.region)} · ${labelize(data.coverage.level)} coverage`
    : 'GTA-first coverage';

  return (
    <main className="app-shell">
      <TopBar
        activeLens={activeLens}
        onProfileClick={() => setWorkspace('profiles')}
        onSavedReportsClick={() => setWorkspace('saved')}
        onCompareClick={() => setWorkspace('compare')}
        onSelectPlace={selectPlace}
      />
      {import.meta.env.DEV && (setupHealthError || setupHealth?.status === 'degraded') && (
        <div className="setup-warning" role="alert">
          <strong>Local setup needs attention.</strong>
          <span>{setupHealthError || summarizeHealth(setupHealth)}</span>
        </div>
      )}
      <section className="map-stage">
        <Suspense fallback={<div className="map-loading">Loading map…</div>}>
          <MapView
            selectedPlace={selectedPlace}
            collisionContext={data?.profile?.collision_context}
          />
        </Suspense>

        <div className="coverage-chip" aria-live="polite">
          <span aria-hidden="true" />
          {coverageLabel}
        </div>

        {!selectedPlace && !data && !loading && (
          <section className="landing-card">
            <p className="eyebrow">Toronto neighbourhood field guide</p>
            <h1>Find a place that fits your actual day.</h1>
            <p>
              Search any Canadian address. Toronto gets the deepest local context; the rest of
              the GTA gets regional rent and access evidence, with limitations shown plainly.
            </p>
            <div className="coverage-legend" aria-label="Coverage levels">
              <span><i className="coverage-dot full" /> Toronto · detailed</span>
              <span><i className="coverage-dot partial" /> GTA · regional</span>
              <span><i className="coverage-dot limited" /> Elsewhere · limited</span>
            </div>
            <button type="button" onClick={() => setWorkspace('profiles')}>
              <SlidersHorizontal size={18} aria-hidden="true" />
              Personalize the lens
            </button>
          </section>
        )}

        {(selectedPlace || data || loading || error) && (
          <aside className="analysis-sheet" aria-label="Neighbourhood analysis">
            {selectedPlace && !data && !loading && !error && (
              <section className="selected-place-card">
                <div>
                  <p className="eyebrow">Ready to check</p>
                  <h1>{selectedPlace.label}</h1>
                  <p>Using {activeLens.profile_name}. Unsupported evidence will stay unavailable.</p>
                </div>
                <button
                  className="primary-button"
                  type="button"
                  disabled={!analyzePayload}
                  onClick={() => analyzePayload && analyze(analyzePayload)}
                >
                  Analyze this place
                </button>
              </section>
            )}
            {loading && <LoadingState />}
            {error && (
              <div className="action-error" role="alert">
                <strong>Analysis could not finish</strong>
                <p>{error}</p>
                <button type="button" onClick={neighborhood.retry}>Try again</button>
              </div>
            )}
            {data && (
              <Profile
                response={data}
                lensIsStale={lensIsStale}
                onSave={neighborhood.saveCurrentProfile}
                savedProfileId={savedProfileId}
                saveError={errors.save}
                isSaving={isSaving}
                generatedAt={generatedAt}
                isRefreshing={isRefreshing}
                refreshError={errors.refresh}
                onRefresh={refreshCurrentProfile}
              />
            )}
          </aside>
        )}

        <Suspense fallback={null}>
          <PreferenceProfiles
            open={workspace === 'profiles'}
            profiles={preferenceProfiles}
            selectedProfileId={selectedPreferenceProfileId}
            onClose={() => setWorkspace(null)}
            onSelect={setSelectedPreferenceProfileId}
            onCreate={neighborhood.createPreferenceProfile}
            onUpdate={neighborhood.updatePreferenceProfile}
            onDelete={neighborhood.deletePreferenceProfile}
            onSetDefault={neighborhood.setDefaultPreferenceProfile}
            error={errors.profiles}
            isSaving={isSavingPreferenceProfile}
          />
          <SavedProfiles
            open={workspace === 'saved'}
            profiles={savedProfiles}
            error={errors.saved}
            onClose={() => setWorkspace(null)}
            onRefresh={neighborhood.loadSavedProfiles}
            onOpen={openSaved}
            onDelete={neighborhood.deleteSavedProfile}
          />
          {workspace === 'compare' && (
            <CompareMode activeProfile={selectedPreferenceProfile} activeLens={activeLens} onClose={() => setWorkspace(null)} />
          )}
        </Suspense>
      </section>
      <nav className="mobile-nav" aria-label="Primary">
        <button type="button" onClick={() => setWorkspace(null)}><MapIcon size={20} />Map</button>
        <button type="button" onClick={() => setWorkspace('profiles')}><SlidersHorizontal size={20} />Lens</button>
        <button type="button" onClick={() => setWorkspace('compare')}><Scale size={20} />Compare</button>
        <button type="button" onClick={() => setWorkspace('saved')}><Archive size={20} />Saved</button>
      </nav>
    </main>
  );
}

function summarizeHealth(health) {
  const issues = [];
  if (!health?.mapbox?.configured) issues.push('Mapbox is not configured');
  if (!health?.snapshot?.ready) issues.push(health?.snapshot?.errors?.[0] || 'snapshot is unavailable');
  if (!health?.sqlite?.ready) issues.push('SQLite is unavailable');
  return issues.join(' · ') || 'Run python -m backend.doctor for details.';
}

function LoadingState() {
  return (
    <div className="loading-state" aria-live="polite">
      <div className="loading-mark" aria-hidden="true" />
      <strong>Reading the neighbourhood</strong>
      <p>Checking access, rent context, local open data, and source freshness.</p>
    </div>
  );
}

function labelize(value = '') {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
