import { Archive, UserRound } from 'lucide-react';
import SearchBar from './SearchBar.jsx';
import { getActiveProfileLabel } from '../utils/preferenceProfiles.js';

export default function TopBar({
  activeProfile,
  preferenceProfileError,
  onProfileClick,
  onSavedReportsClick,
  onSelectPlace,
}) {
  return (
    <header className="top-bar">
      <div className="brand-lockup">VibeCheck</div>
      <button type="button" className="active-profile-button" onClick={onProfileClick}>
        <UserRound size={16} aria-hidden="true" />
        <span>{getActiveProfileLabel(activeProfile)}</span>
      </button>
      <div className="top-search">
        <SearchBar onSelect={onSelectPlace} />
      </div>
      <button type="button" className="top-icon-button" onClick={onSavedReportsClick} aria-label="Saved reports">
        <Archive size={17} aria-hidden="true" />
      </button>
      {preferenceProfileError && <p className="top-bar-error">{preferenceProfileError}</p>}
    </header>
  );
}
