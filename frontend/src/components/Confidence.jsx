export default function Confidence({ confidence, statuses }) {
  if (!confidence) return null;
  return (
    <section className="panel-section">
      <div className="section-heading">
        <p className="eyebrow">Confidence</p>
        <h2>{confidence.level}</h2>
      </div>
      {confidence.caveats?.length > 0 && (
        <ul className="caveat-list">
          {confidence.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      )}
      <div className="source-list">
        {statuses?.map((status) => (
          <div className={`source-row source-${status.status}`} key={status.source}>
            <span>
              {status.source}
              {status.updated_at && <small>Updated {formatSourceDate(status.updated_at)}</small>}
            </span>
            <strong>{status.status}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatSourceDate(value) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value));
}
