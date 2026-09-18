export const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export async function analyzeNeighborhood(payload, { signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  return parseResponse(response, `Analyze failed with ${response.status}`);
}

export async function refreshSavedProfile(profileId) {
  const response = await fetch(`${API_BASE_URL}/profiles/${profileId}/refresh`, {
    method: 'POST',
  });
  return parseResponse(response, `Refresh saved profile failed with ${response.status}`);
}

export async function getHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);
  return parseResponse(response, `Health check failed with ${response.status}`);
}

export async function parseResponse(response, fallbackMessage) {
  if (response.ok) {
    return response.json();
  }

  let message = fallbackMessage;
  try {
    const body = await response.json();
    message = body.detail || body.message || message;
  } catch {
    // Keep the status-based fallback when the server did not return JSON.
  }
  throw new Error(message);
}
