import { Download, FolderOpen, RefreshCw, Trash2, X } from 'lucide-react';
import { useDialogFocus } from '../hooks/useDialogFocus.js';

export default function SavedProfiles({ open = true, profiles = [], error, onClose, onOpen, onDelete, onRefresh }) {
  const dialogRef = useDialogFocus(open, onClose);
  if (!open) return null;

  function confirmDelete(profile) {
    if (window.confirm(`Delete the saved report for ${profile.place_label}?`)) onDelete(profile.id);
  }

  return (
    <section className="workspace-backdrop" role="dialog" aria-modal="true" aria-labelledby="saved-title">
      <div className="saved-workspace" ref={dialogRef}>
        <header className="workspace-title-row">
          <div><p className="eyebrow">Library</p><h1 id="saved-title">Saved reports</h1><p>Immutable snapshots of the lens and evidence used.</p></div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close saved reports"><X size={20} /></button>
        </header>
        <div className="workspace-toolbar">
          <button type="button" onClick={onRefresh}><RefreshCw size={17} /> Refresh list</button>
          <button type="button" onClick={() => window.print()}><Download size={17} /> Print / Save PDF</button>
        </div>
        {error && <p className="action-error" role="alert">{error}</p>}
        {profiles.length === 0 ? (
          <div className="empty-library">
            <FolderOpen size={32} aria-hidden="true" />
            <h2>No field notes saved yet</h2>
            <p>Analyze a place, then save the report to compare its evidence later.</p>
          </div>
        ) : (
          <div className="saved-list">
            {profiles.map((profile) => (
              <article className="saved-row" key={profile.id}>
                <button type="button" className="saved-open" onClick={() => onOpen(profile.id)}>
                  <span className="saved-date">{formatDate(profile.updated_at)}</span>
                  <strong>{profile.place_label}</strong>
                  <span>{profile.analysis_lens?.profile_name || 'Legacy report'}</span>
                  <div className="saved-meta">
                    {profile.fit_score != null && <b>{profile.fit_score} fit</b>}
                    <b>{profile.confidence_level} confidence</b>
                    {profile.coverage?.level && <b>{profile.coverage.level} coverage</b>}
                  </div>
                </button>
                <button type="button" className="icon-danger" aria-label={`Delete ${profile.place_label}`} onClick={() => confirmDelete(profile)}>
                  <Trash2 size={18} />
                </button>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function formatDate(value) {
  return new Intl.DateTimeFormat('en-CA', { dateStyle: 'medium' }).format(new Date(value));
}
