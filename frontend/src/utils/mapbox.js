export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || '';

export async function searchPlaces(query) {
  if (!MAPBOX_TOKEN || query.trim().length < 3) return [];
  const params = new URLSearchParams({
    q: query,
    country: 'us',
    limit: '5',
    access_token: MAPBOX_TOKEN,
  });
  const response = await fetch(`https://api.mapbox.com/search/geocode/v6/forward?${params}`);
  if (!response.ok) throw new Error('Mapbox search failed');
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
