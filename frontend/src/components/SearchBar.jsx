import { Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { MAPBOX_TOKEN, searchPlaces } from '../utils/mapbox.js';
import { shouldSearchPlaces } from '../utils/searchState.js';

export default function SearchBar({ onSelect }) {
  const [query, setQuery] = useState('');
  const [selectedQuery, setSelectedQuery] = useState('');
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;
    const controller = new AbortController();
    const timeout = setTimeout(async () => {
      if (!shouldSearchPlaces(query, selectedQuery)) {
        setResults([]);
        return;
      }
      try {
        setError('');
        const nextResults = await searchPlaces(query, { signal: controller.signal });
        if (!ignore) setResults(nextResults);
      } catch (err) {
        if (!ignore && err.name !== 'AbortError') setError(err instanceof Error ? err.message : 'Search failed');
      }
    }, 250);
    return () => {
      ignore = true;
      controller.abort();
      clearTimeout(timeout);
    };
  }, [query, selectedQuery]);

  return (
    <div className="search-card">
      <label className="search-input-wrap">
        <Search size={18} aria-hidden="true" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={MAPBOX_TOKEN ? 'Search Toronto or the GTA' : 'Add VITE_MAPBOX_TOKEN to enable search'}
          disabled={!MAPBOX_TOKEN}
        />
      </label>
      {error && <p className="search-error">{error}</p>}
      {results.length > 0 && (
        <div className="search-results">
          {results.map((result) => (
            <button
              key={result.id}
              type="button"
              onClick={() => {
                setSelectedQuery(result.label);
                setQuery(result.label);
                setResults([]);
                setError('');
                onSelect(result);
              }}
            >
              {result.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
