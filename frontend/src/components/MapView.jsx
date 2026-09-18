import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { useEffect, useRef, useState } from 'react';
import { MAPBOX_TOKEN } from '../utils/mapbox.js';

const DEFAULT_CENTER = [-79.3832, 43.6532];
const RADIUS_MILES = 0.5;

export default function MapView({ selectedPlace }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const [loadState, setLoadState] = useState(MAPBOX_TOKEN ? 'loading' : 'missing');
  const [loadError, setLoadError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!MAPBOX_TOKEN || !containerRef.current || mapRef.current) return undefined;
    if (!mapboxgl.supported()) {
      setLoadState('error');
      setLoadError('This browser does not have WebGL enabled, which Mapbox needs to render the map.');
      return undefined;
    }

    setLoadState('loading');
    setLoadError('');
    mapboxgl.accessToken = MAPBOX_TOKEN;
    let map;
    let initialLoadComplete = false;
    let loadTimeout;
    try {
      map = new mapboxgl.Map({
        container: containerRef.current,
        style: 'mapbox://styles/mapbox/standard',
        center: DEFAULT_CENTER,
        zoom: 10.25,
        pitch: 0,
        bearing: 0,
        config: {
          basemap: {
            theme: 'faded',
            lightPreset: 'day',
            show3dObjects: false,
          },
        },
      });
      mapRef.current = map;
      map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right');
      map.once('load', () => {
        initialLoadComplete = true;
        clearTimeout(loadTimeout);
        map.resize();
        setLoadState('ready');
      });
      map.on('error', (event) => {
        if (initialLoadComplete) return;
        const message = readableMapError(event.error);
        if (message) {
          clearTimeout(loadTimeout);
          setLoadState('error');
          setLoadError(message);
        }
      });
      loadTimeout = setTimeout(() => {
        if (!initialLoadComplete) {
          setLoadState('error');
          setLoadError('The map did not load. Check browser privacy extensions and allow requests to api.mapbox.com.');
        }
      }, 15_000);
    } catch (error) {
      setLoadState('error');
      setLoadError(readableMapError(error) || 'Mapbox could not initialize in this browser.');
    }
    return () => {
      clearTimeout(loadTimeout);
      map?.remove();
      mapRef.current = null;
    };
  }, [attempt]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedPlace?.coordinates) return;
    const center = [selectedPlace.coordinates.lng, selectedPlace.coordinates.lat];
    map.flyTo({ center, zoom: 14, pitch: 0, bearing: 0, duration: 900, essential: false });
    markerRef.current?.remove();
    markerRef.current = new mapboxgl.Marker({ color: '#2457F5' }).setLngLat(center).addTo(map);

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
          paint: { 'fill-color': '#2457F5', 'fill-opacity': 0.1 },
        });
        map.addLayer({
          id: 'selected-radius-line',
          type: 'line',
          source: 'selected-radius',
          paint: { 'line-color': '#2457F5', 'line-width': 2 },
        });
      }
    }

    if (map.isStyleLoaded()) drawRadius();
    else map.once('load', drawRadius);
  }, [attempt, selectedPlace]);

  if (!MAPBOX_TOKEN) {
    return <div className="map-token-state">Add VITE_MAPBOX_TOKEN to render the Toronto map.</div>;
  }

  return (
    <>
      <div className="map-view" ref={containerRef} aria-hidden="true" />
      {loadState === 'loading' && <div className="map-loading" role="status">Loading the Toronto map…</div>}
      {loadState === 'error' && (
        <div className="map-error-state" role="alert">
          <div>
            <strong>Map unavailable</strong>
            <p>{loadError}</p>
            <button type="button" onClick={() => setAttempt((value) => value + 1)}>Retry map</button>
          </div>
        </div>
      )}
    </>
  );
}

function readableMapError(error) {
  const message = String(error?.message || error || '').toLowerCase();
  if (!message) return '';
  if (message.includes('401') || message.includes('403') || message.includes('unauthorized') || message.includes('token')) {
    return 'Mapbox rejected the public token. Check its scopes and allowed URL restrictions for localhost and 127.0.0.1.';
  }
  if (message.includes('failed to fetch') || message.includes('network') || message.includes('load failed')) {
    return 'The browser could not reach Mapbox. Disable blocking for api.mapbox.com and try again.';
  }
  return '';
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
