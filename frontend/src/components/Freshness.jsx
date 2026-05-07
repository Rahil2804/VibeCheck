import { formatGeneratedLabel, freshnessState } from '../utils/freshness.js';

export default function Freshness({
  generatedAt,
  savedProfileId,
  isRefreshing,
  refreshError,
  onRefresh,
}) {
  const state = freshnessState(generatedAt);
  const label = formatGeneratedLabel(generatedAt);
  const buttonText = savedProfileId ? 'Refresh report' : 'Refresh analysis';

  return (
    <section className={`panel-section freshness-card freshness-${state}`}>
      <div className="section-heading">
        <p className="eyebrow">Freshness</p>
        <h2>{label}</h2>
      </div>
      {onRefresh && (
        <button type="button" className="primary-button" onClick={onRefresh} disabled={isRefreshing}>
          {isRefreshing ? 'Refreshing...' : buttonText}
        </button>
      )}
      {refreshError && <p className="save-error">{refreshError}</p>}
    </section>
  );
}
