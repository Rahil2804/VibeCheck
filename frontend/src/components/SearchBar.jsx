import { Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { MAPBOX_TOKEN, searchPlaces } from '../utils/mapbox.js';

export default function SearchBar({ onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;
    const timeout = setTimeout(async () => {
      if (!query.trim()) {
        setResults([]);
        return;
      }
      try {
        setError('');
        const nextResults = await searchPlaces(query);
        if (!ignore) setResults(nextResults);
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : 'Search failed');
      }
    }, 250);
    return () => {
      ignore = true;
      clearTimeout(timeout);
    };
  }, [query]);

  return (
    <div className="search-card">
      <label className="search-input-wrap">
        <Search size={18} aria-hidden="true" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={MAPBOX_TOKEN ? 'Search a US address or place' : 'Add VITE_MAPBOX_TOKEN to enable search'}
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
                setQuery(result.label);
                setResults([]);
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
