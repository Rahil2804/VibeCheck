const SUPPORT_LABELS = {
  direct: 'Supported',
  inferred: 'Inferred',
  unavailable: 'Unavailable',
};

export default function Provenance({ provenance }) {
  const items = provenance?.items || [];
  if (items.length === 0) return null;

  return (
    <section className="panel-section provenance-section">
      <div className="section-heading">
        <p className="eyebrow">Source support</p>
        <h2>Why these claims appear</h2>
      </div>
      <div className="provenance-list">
        {items.map((item) => (
          <article className={`provenance-row provenance-${item.support}`} key={item.claim_id}>
            <div>
              <strong>{item.label}</strong>
              <span>{SUPPORT_LABELS[item.support] || item.support}</span>
            </div>
            <p>{item.summary}</p>
            {item.sources?.length > 0 && (
              <div className="source-chip-row">
                {item.sources.map((source) => (
                  <small key={source}>{source}</small>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
