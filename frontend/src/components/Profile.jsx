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
