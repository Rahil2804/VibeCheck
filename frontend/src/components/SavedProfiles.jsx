export default function SavedProfiles({ profiles = [], onOpen, onDelete, onRefresh }) {
  return (
    <section className="saved-profiles">
      <div className="saved-profiles-header">
        <div>
          <p className="eyebrow">Saved</p>
          <h2>Profiles</h2>
        </div>
        <button type="button" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      {profiles.length === 0 ? (
        <p className="saved-empty">Saved profiles will appear here.</p>
      ) : (
        <div className="saved-list">
          {profiles.map((profile) => (
            <div className="saved-row" key={profile.id}>
              <button type="button" onClick={() => onOpen(profile.id)}>
                <strong>{profile.place_label}</strong>
                <span>{profile.confidence_level} confidence</span>
              </button>
              <button
                type="button"
                className="icon-danger"
                aria-label={`Delete ${profile.place_label}`}
                onClick={() => onDelete(profile.id)}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
