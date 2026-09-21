import Confidence from './Confidence.jsx';
import Provenance from './Provenance.jsx';

const SCORE_LABELS = [
  ['walkability', 'Walkability'],
  ['transit_access', 'Transit'],
  ['daily_needs', 'Daily needs'],
  ['dining_activity', 'Dining & activity'],
  ['parks_outdoors', 'Parks'],
  ['affordability', 'Rent pressure'],
  ['cycling_access', 'Cycling access'],
];

export default function CompareResultCard({ slot, onRetry }) {
  if (slot.status === 'loading') {
    return (
      <article className="compare-result-card compare-result-loading" aria-live="polite">
        <span className="eyebrow">{slot.place?.label || 'Selected place'}</span>
        <h3>Analyzing...</h3>
        <p>Checking available signals for this place.</p>
      </article>
    );
  }

  if (slot.status === 'error') {
    return (
      <article className="compare-result-card compare-result-error" role="alert">
        <span className="eyebrow">{slot.place?.label || 'Selected place'}</span>
        <h3>Analysis failed</h3>
        <p>{slot.error}</p>
        <button type="button" onClick={() => onRetry(slot.id)}>
          Retry
        </button>
      </article>
    );
  }

  const response = slot.response;
  if (!response) return null;
  const scores = response.profile?.vibe_scores || {};
  const cycling = response.profile?.cycling_context;
  const collisions = response.profile?.collision_context;
  const building = response.profile?.building_context;

  return (
    <article className="compare-result-card">
      <div className="compare-card-header">
        <span className="eyebrow">Compared place</span>
        <h3>{response.place.label}</h3>
      </div>
      {response.fit && (
        <div className="compare-fit">
          <strong>{response.fit.score == null ? 'Unavailable' : `${response.fit.score}%`}</strong>
          <span>{response.fit.label}</span>
          <p>{response.fit.explanation}</p>
        </div>
      )}
      <div className="compare-score-list">
        {SCORE_LABELS.map(([key, label]) => (
          <div className="compare-score-row" key={key}>
            <span>{label}</span>
            <div className={scores[key] == null ? 'is-unavailable' : ''}>
              {scores[key] != null && <i style={{ width: `${Math.max(0, Math.min(100, scores[key]))}%` }} />}
            </div>
            <strong>{scores[key] ?? 'Unavailable'}</strong>
            {key === 'cycling_access' && cycling && (
              <small>{cycling.fallback ? 'OSM estimate' : 'Official Toronto'}</small>
            )}
          </div>
        ))}
      </div>
      <div className="compare-evidence-list" aria-label="Context evidence">
        <div>
          <span>Reported collisions · 1 km</span>
          <strong>{collisions ? formatNumber(collisions.total_collisions) : 'Unavailable'}</strong>
          <small>{collisions ? `${collisions.baseline_period_start}–${collisions.baseline_period_end}` : 'Toronto bundled data only'}</small>
        </div>
        <div>
          <span>KSI collisions · separate series</span>
          <strong>{collisions ? formatNumber(collisions.ksi_collisions) : 'Unavailable'}</strong>
          <small>{collisions ? `${collisions.ksi_period_start}–${collisions.ksi_period_end}` : 'Not a safety score'}</small>
        </div>
        <div>
          <span>RentSafeTO exact match</span>
          <strong>{building ? (building.current_score == null ? 'Registered' : `${formatNumber(building.current_score)} / 100`) : 'Unavailable'}</strong>
          <small>{building ? building.site_address : 'No exact record in this report'}</small>
        </div>
      </div>
      <div className="compare-pros-cons">
        <div>
          <h4>Pros</h4>
          <ul>{response.profile?.honest_pros?.slice(0, 2).map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
        <div>
          <h4>Cons</h4>
          <ul>{response.profile?.honest_cons?.slice(0, 2).map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
      <Confidence confidence={response.confidence} statuses={response.source_statuses} />
      <Provenance provenance={response.profile?.provenance} />
    </article>
  );
}

function formatNumber(value) {
  return new Intl.NumberFormat('en-CA', { maximumFractionDigits: 1 }).format(value);
}
