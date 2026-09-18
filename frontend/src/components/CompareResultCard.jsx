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
          </div>
        ))}
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
