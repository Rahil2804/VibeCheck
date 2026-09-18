import { Archive, Scale, SlidersHorizontal } from 'lucide-react';
import SearchBar from './SearchBar.jsx';

export default function TopBar({
  activeLens,
  onProfileClick,
  onSavedReportsClick,
  onCompareClick,
  onSelectPlace,
}) {
  return (
    <header className="command-bar">
      <a className="brand-lockup" href="/" aria-label="VibeCheck home">
        <i aria-hidden="true">V</i>
        <span>VibeCheck</span>
      </a>
      <button
        type="button"
        className="lens-button"
        aria-label={`Analysis lens: ${activeLens?.profile_name || 'Generic'}`}
        onClick={onProfileClick}
      >
        <SlidersHorizontal size={17} aria-hidden="true" />
        <span><small>Analysis lens</small>{activeLens?.profile_name || 'Generic'}</span>
      </button>
      <div className="command-search"><SearchBar onSelect={onSelectPlace} /></div>
      <button type="button" className="command-action" aria-label="Compare" onClick={onCompareClick}>
        <Scale size={17} aria-hidden="true" /><span>Compare</span>
      </button>
      <button type="button" className="command-action" aria-label="Saved reports" onClick={onSavedReportsClick}>
        <Archive size={17} aria-hidden="true" /><span>Saved reports</span>
      </button>
    </header>
  );
}
