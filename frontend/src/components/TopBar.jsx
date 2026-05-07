import { Archive, Scale, UserRound } from 'lucide-react';
import SearchBar from './SearchBar.jsx';

export default function TopBar({
  activeProfile,
  preferenceProfileError,
  onProfileClick,
  onSavedReportsClick,
  onCompareClick,
  onSelectPlace,
}) {
  return (
    <header className="top-bar">
      <div className="brand-lockup">VibeCheck</div>
      <button type="button" className="active-profile-button" onClick={onProfileClick}>
        <UserRound size={15} aria-hidden="true" />
        <span>
          <small>Active Profile</small>
          {activeProfile?.name || 'Generic'}
        </span>
      </button>
      <div className="top-search">
        <SearchBar onSelect={onSelectPlace} />
      </div>
      <button type="button" className="compare-top-button" onClick={onCompareClick} aria-label="Compare places">
        <Scale size={16} aria-hidden="true" />
        <span>Compare</span>
      </button>
      <button type="button" className="top-icon-button" onClick={onSavedReportsClick} aria-label="Saved reports">
        <Archive size={17} aria-hidden="true" />
      </button>
      {preferenceProfileError && <p className="top-bar-error">{preferenceProfileError}</p>}
    </header>
  );
}
