const LABELS = {
  walkability: 'Walkability',
  transit_access: 'Transit',
  affordability: 'Affordability',
  quiet: 'Quiet',
  social_scene: 'Social scene',
};

export default function ScoreCards({ scores }) {
  if (!scores) return null;
  return (
    <div className="score-grid">
      {Object.entries(LABELS).map(([key, label]) => (
        <article className="score-card" key={key}>
          <span>{label}</span>
          <strong>{scores[key]}</strong>
        </article>
      ))}
    </div>
  );
}
