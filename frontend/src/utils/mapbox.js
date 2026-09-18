export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || '';

export async function searchPlaces(query, { signal } = {}) {
  if (!MAPBOX_TOKEN || query.trim().length < 3) return [];
  const params = new URLSearchParams({
    q: query,
    country: 'ca',
    limit: '5',
    access_token: MAPBOX_TOKEN,
  });
  let response;
  try {
    response = await fetch(`https://api.mapbox.com/search/geocode/v6/forward?${params}`, { signal });
  } catch (error) {
    if (error?.name === 'AbortError') throw error;
    throw new Error('Address search could not reach Mapbox. Check browser privacy or ad-blocking settings.');
  }
  if (response.status === 401 || response.status === 403) {
    throw new Error('Mapbox rejected the public token or this local URL is not allowed.');
  }
  if (response.status === 429) {
    throw new Error('Mapbox search is temporarily rate limited. Try again shortly.');
  }
  if (!response.ok) throw new Error(`Mapbox search failed (${response.status}).`);
  const body = await response.json();
  return (body.features || []).map((feature) => ({
    id: feature.properties?.mapbox_id || feature.id,
    label: feature.properties?.full_address || feature.properties?.name || 'Selected place',
    coordinates: {
      lng: feature.geometry.coordinates[0],
      lat: feature.geometry.coordinates[1],
    },
  }));
}
