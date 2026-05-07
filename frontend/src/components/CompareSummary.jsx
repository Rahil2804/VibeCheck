import { buildCompareHighlights } from '../utils/compareUtils.js';

export default function CompareSummary({ slots }) {
  const highlights = buildCompareHighlights(slots);
  if (highlights.length === 0) return null;

  return (
    <section className="compare-summary" aria-label="Compare highlights">
      <div className="section-heading">
        <p className="eyebrow">Compare highlights</p>
        <h2>Standout signals</h2>
      </div>
      <div className="compare-summary-grid">
        {highlights.map((highlight) => (
          <article className="compare-highlight" key={highlight.id}>
            <span>{highlight.label}</span>
            <strong>{highlight.placeLabel}</strong>
            <small>{highlight.value}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
