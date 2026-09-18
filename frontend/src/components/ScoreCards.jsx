const LABELS = {
  walkability: 'Walkability',
  transit_access: 'Transit',
  daily_needs: 'Daily needs',
  dining_activity: 'Dining & activity',
  parks_outdoors: 'Parks & outdoors',
  affordability: 'Rent pressure',
  cycling_access: 'Cycling access',
};

export default function ScoreCards({ scores }) {
  if (!scores) return null;
  return (
    <div className="score-grid">
      {Object.entries(LABELS).filter(([key]) => scores[key] != null).map(([key, label]) => (
        <article className="score-card" key={key}>
          <span>{label}</span>
          <strong>{scores[key]}<small>/100</small></strong>
        </article>
      ))}
    </div>
  );
}
