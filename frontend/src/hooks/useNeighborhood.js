import { useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export function useNeighborhood() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [lastRequest, setLastRequest] = useState(null);

  async function analyze(payload) {
    setLoading(true);
    setError('');
    setData(null);
    setLastRequest(payload);
    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`Analyze failed with ${response.status}`);
      }
      const body = await response.json();
      setData(body);
      return body;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analyze failed');
      return null;
    } finally {
      setLoading(false);
    }
  }

  function retry() {
    if (!lastRequest) return Promise.resolve(null);
    return analyze(lastRequest);
  }

  return { analyze, retry, data, error, loading };
}
