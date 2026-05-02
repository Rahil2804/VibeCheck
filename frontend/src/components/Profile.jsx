import Confidence from './Confidence.jsx';
import ScoreCards from './ScoreCards.jsx';

export default function Profile({ response }) {
  if (!response) return null;
  const { profile, fit, confidence, source_statuses: statuses } = response;
  return (
    <section className="profile-stack">
      <div className="section-heading">
        <p className="eyebrow">Neighborhood profile</p>
        <h2>{response.place.label}</h2>
      </div>
      <p className="overview">{profile.overview}</p>
      <ScoreCards scores={profile.vibe_scores} />
      <WhoLivesHere context={profile.who_lives_here} />
      {fit && (
        <article className="fit-card">
          <span>{fit.label}</span>
          <strong>{fit.score}</strong>
          <p>{fit.explanation}</p>
          {fit.flags?.map((flag) => <small key={flag}>{flag}</small>)}
        </article>
      )}
      <div className="pros-cons-grid">
        <div>
          <h3>Pros</h3>
          <ul>{profile.honest_pros.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
        <div>
          <h3>Cons</h3>
          <ul>{profile.honest_cons.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
      <article className="trajectory-card">
        <span>{profile.trajectory.direction}</span>
        <p>{profile.trajectory.summary}</p>
      </article>
      <Confidence confidence={confidence} statuses={statuses} />
    </section>
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
