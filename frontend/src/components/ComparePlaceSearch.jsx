import SearchBar from './SearchBar.jsx';

export default function ComparePlaceSearch({ slot, canRemove, onRemove, onSelect }) {
  return (
    <article className={`compare-place-slot ${slot.place ? 'compare-place-selected' : ''}`}>
      <div className="compare-slot-topline">
        <span>{slot.place?.label || 'Add a place'}</span>
        {canRemove && (
          <button type="button" onClick={() => onRemove(slot.id)} aria-label={`Remove ${slot.place?.label || 'empty place slot'}`}>
            Remove
          </button>
        )}
      </div>
      <SearchBar onSelect={onSelect} />
    </article>
  );
}
