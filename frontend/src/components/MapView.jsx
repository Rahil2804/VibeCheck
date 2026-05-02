import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { useEffect, useRef } from 'react';
import { MAPBOX_TOKEN } from '../utils/mapbox.js';

const DEFAULT_CENTER = [-98.5795, 39.8283];
const RADIUS_MILES = 0.5;

export default function MapView({ selectedPlace }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);

  useEffect(() => {
    if (!MAPBOX_TOKEN || !containerRef.current || mapRef.current) return undefined;
    mapboxgl.accessToken = MAPBOX_TOKEN;
    mapRef.current = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/standard',
      center: DEFAULT_CENTER,
      zoom: 3.2,
      pitch: 62,
      bearing: -18,
      projection: 'globe',
    });
    mapRef.current.addControl(new mapboxgl.NavigationControl({ visualizePitch: true }), 'bottom-right');
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedPlace?.coordinates) return;
    const center = [selectedPlace.coordinates.lng, selectedPlace.coordinates.lat];
    map.flyTo({ center, zoom: 14.2, pitch: 68, bearing: -24, duration: 1500, essential: true });
    markerRef.current?.remove();
    markerRef.current = new mapboxgl.Marker({ color: '#214d3f' }).setLngLat(center).addTo(map);

    function drawRadius() {
      const radius = circlePolygon(center, RADIUS_MILES, 96);
      const source = map.getSource('selected-radius');
      if (source) {
        source.setData(radius);
      } else {
        map.addSource('selected-radius', { type: 'geojson', data: radius });
        map.addLayer({
          id: 'selected-radius-fill',
          type: 'fill',
          source: 'selected-radius',
          paint: { 'fill-color': '#2f6b55', 'fill-opacity': 0.16 },
        });
        map.addLayer({
          id: 'selected-radius-line',
          type: 'line',
          source: 'selected-radius',
          paint: { 'line-color': '#214d3f', 'line-width': 2 },
        });
      }
    }

    if (map.isStyleLoaded()) drawRadius();
    else map.once('load', drawRadius);
  }, [selectedPlace]);

  if (!MAPBOX_TOKEN) {
    return <div className="map-token-state">Add VITE_MAPBOX_TOKEN to render the 3D map.</div>;
  }

  return <div className="map-view" ref={containerRef} />;
}

function circlePolygon(center, radiusMiles, points) {
  const [lng, lat] = center;
  const radiusKm = radiusMiles * 1.60934;
  const coordinates = [];
  for (let i = 0; i <= points; i += 1) {
    const angle = (i / points) * 2 * Math.PI;
    const dx = radiusKm * Math.cos(angle);
    const dy = radiusKm * Math.sin(angle);
    coordinates.push([lng + dx / (111.32 * Math.cos((lat * Math.PI) / 180)), lat + dy / 110.574]);
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [coordinates] }, properties: {} };
}
