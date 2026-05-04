import Confidence from './Confidence.jsx';
import ScoreCards from './ScoreCards.jsx';

export default function Profile({ response, activePreferenceProfile, onSave, savedProfileId, saveError, isSaving }) {
  if (!response) return null;
  const { profile, fit, confidence, source_statuses: statuses, synthesis } = response;
  const saveButtonText = isSaving ? 'Saving...' : savedProfileId ? 'Saved report' : 'Save report';
  return (
    <section className="profile-stack precision-panel">
      <div className="profile-actions">
        <div className="section-heading">
          <h2>{response.place.label}</h2>
          <p className="analysis-lens-line">
            {activePreferenceProfile ? `Analyzed for ${activePreferenceProfile.name}` : 'Generic neighborhood check'}
          </p>
        </div>
        <button type="button" className="primary-button" onClick={onSave} disabled={isSaving || Boolean(savedProfileId)}>
          {saveButtonText}
        </button>
      </div>
      {saveError && <p className="save-error">{saveError}</p>}
      {fit && <FitGauge fit={fit} />}
      <article className="vibe-overview">
        <span>Vibe Overview</span>
        <p>{profile.overview}</p>
      </article>
      <ScoreCards scores={profile.vibe_scores} />
      <div className="insight-list">
        <article>
          <h3>Pros</h3>
          <ul>{profile.honest_pros.map((item) => <li key={item}>{item}</li>)}</ul>
        </article>
        <article>
          <h3>Cons</h3>
          <ul>{profile.honest_cons.map((item) => <li key={item}>{item}</li>)}</ul>
        </article>
      </div>
      {synthesis && (
        <article className={`synthesis-card synthesis-${synthesis.status}`}>
          <span>AI synthesis: {synthesis.status}</span>
          <p>{synthesis.message}</p>
        </article>
      )}
      <WhoLivesHere context={profile.who_lives_here} />
      <article className="trajectory-card">
        <span>{profile.trajectory.direction}</span>
        <p>{profile.trajectory.summary}</p>
      </article>
      <Confidence confidence={confidence} statuses={statuses} />
    </section>
  );
}

function FitGauge({ fit }) {
  const score = Math.max(0, Math.min(100, fit.score));
  return (
    <article className="fit-gauge-card">
      <div className="fit-gauge" style={{ '--score': `${score * 3.6}deg` }}>
        <strong>{score}%</strong>
        <span>Fit Score</span>
      </div>
      <p>{fit.explanation}</p>
      {fit.flags?.map((flag) => <small key={flag}>{flag}</small>)}
    </article>
  );
}

function WhoLivesHere({ context }) {
  if (!context) return null;
  const rows = [
    ['Median age', context.median_age],
    ['Median household income', formatCurrency(context.median_household_income)],
    ['Population density', formatNumber(context.population_density)],
    ['Population trend', context.population_trend],
  ].filter(([_label, value]) => value !== null && value !== undefined && value !== '');

  if (rows.length === 0) return null;

  return (
    <article className="context-card">
      <h3>Context</h3>
      <dl>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function formatCurrency(value) {
  if (value === null || value === undefined) return value;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value) {
  if (value === null || value === undefined) return value;
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value);
}
