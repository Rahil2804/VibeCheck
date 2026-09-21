const LABELS = {
  walkability: 'Walkability',
  transit_access: 'Transit',
  daily_needs: 'Daily needs',
  dining_activity: 'Dining & activity',
  parks_outdoors: 'Parks & outdoors',
  affordability: 'Rent pressure',
  cycling_access: 'Cycling access',
};

export default function ScoreCards({ scores, cyclingContext }) {
  if (!scores) return null;
  return (
    <div className="score-grid">
      {Object.entries(LABELS).filter(([key]) => scores[key] != null).map(([key, label]) => (
        <article className="score-card" key={key}>
          <span>{label}</span>
          {key === 'cycling_access' && cyclingContext && (
            <small className={`evidence-tier ${cyclingContext.fallback ? 'is-fallback' : 'is-official'}`}>
              {cyclingContext.fallback ? 'OSM estimate' : 'Official Toronto'}
            </small>
          )}
          <strong>{scores[key]}<small>/100</small></strong>
        </article>
      ))}
    </div>
  );
}
