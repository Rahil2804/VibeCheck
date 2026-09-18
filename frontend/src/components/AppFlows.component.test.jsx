import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Profile from './Profile.jsx';
import SavedProfiles from './SavedProfiles.jsx';
import { analysisSessionReducer, INITIAL_ANALYSIS_SESSION } from '../hooks/useNeighborhood.js';
import { buildAnalyzePayloadForLens } from '../utils/preferenceProfiles.js';

const response = {
  place: { label: 'The Annex, Toronto', coordinates: { lat: 43.67, lng: -79.4 } },
  analysis_lens: { mode: 'saved_profile', profile_id: 'p1', profile_name: 'Transit first', preferences: {} },
  coverage: { region: 'toronto', level: 'full', supported_signals: ['Transit'], unavailable_signals: ['Quiet'], message: 'Toronto coverage.' },
  profile: {
    overview: 'A source-backed field note.',
    vibe_scores: { walkability: 80, transit_access: 75, affordability: 58, daily_needs: 72, dining_activity: 60, parks_outdoors: 66, cycling_access: 82 },
    who_lives_here: {
      population_density: 9000,
      regional_average_two_bedroom_rent: 2034,
      rent_geographic_scope: 'Toronto',
      rent_edition: '2025 Rental Market Report',
      rent_benchmark: { monthly_rent: 1763, unit_size: 'one_bedroom', geography: 'Toronto', edition: 'CMHC 2025', quality_code: 'a', market_scope: 'Purpose-built rental apartments' },
    },
    transit_context: { scheduled_departures_per_hour: 18, nearby_route_count: 4, nearby_routes: ['1', '2'], agencies: ['TTC'], service_date: '2026-09-15', scope: 'TTC' },
    cycling_context: { protected_network_km: 2.4, total_network_km: 4.1, bike_share_stations: 5, scope: 'City of Toronto' },
    honest_pros: ['Daily needs are close.'],
    honest_cons: ['Quiet is unavailable.'],
    narrative_citations: [{ section: 'overview', evidence_check_ids: ['access'] }],
    provenance: { items: [] },
  },
  fit: { score: 70, label: 'Good fit', explanation: 'Evidence-backed fit.', flags: [], factors: [{ signal: 'Transit', value: 75, impact: 15, explanation: 'Transit is strong.', source_fields: ['access.transit_access'] }] },
  confidence: { level: 'medium', caveats: [] },
  source_statuses: [],
  synthesis: { status: 'used', model: 'gpt-4o-mini', message: 'Grounded narrative.' },
  evidence_checks: [
    { id: 'access', label: 'Everyday access', status: 'supported', summary: 'OSM access returned.', updated_at: '2026-09-16T00:00:00Z', source_fields: ['access.daily_needs'] },
    { id: 'transit', label: 'Scheduled transit', status: 'stale', summary: 'Schedule is expired.' },
    { id: 'census', label: 'Census context', status: 'unavailable', summary: 'Census is unavailable.' },
  ],
};

describe('portfolio flows', () => {
  it('keeps the returned lens immutable and marks a changed lens stale', () => {
    const analyzed = analysisSessionReducer(INITIAL_ANALYSIS_SESSION, {
      type: 'analyze_success',
      response,
      freshness: '2026-09-16T00:00:00Z',
    });
    const changed = analysisSessionReducer(analyzed, {
      type: 'select_lens',
      lens: { ...response.analysis_lens, profile_name: 'Renamed' },
    });
    expect(changed.returnedLens.profile_name).toBe('Transit first');
    expect(changed.activeLens.profile_name).toBe('Renamed');
  });

  it('builds a generic request without setup', () => {
    const payload = buildAnalyzePayloadForLens(response.place, { mode: 'generic', profile_name: 'Generic' });
    expect(payload.generic_mode).toBe(true);
    expect(payload.preferences).toEqual({});
  });

  it('renders supported metrics only and warns about a stale lens', () => {
    render(<Profile response={response} lensIsStale onSave={vi.fn()} />);
    expect(screen.getByText(/Profile changed/i)).toBeInTheDocument();
    expect(screen.getAllByText('Transit').length).toBeGreaterThan(0);
    expect(screen.queryByText(/^Quiet$/)).not.toBeInTheDocument();
    expect(screen.queryByText('$2,034')).not.toBeInTheDocument();
    expect(screen.getByText(/18 departures/i)).toBeInTheDocument();
    expect(screen.getByText(/2.4 km protected/i)).toBeInTheDocument();
    expect(screen.getByText('$1,763')).toBeInTheDocument();
    expect(screen.getByText('AI-grounded')).toBeInTheDocument();
    expect(screen.getByText('1 supported')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Everyday access' })).toHaveAttribute('href', '#evidence-access');
    fireEvent.click(screen.getByText('Freshness and sources'));
    expect(screen.getByText('What completed')).toBeInTheDocument();
    expect(screen.getByText('Schedule is expired.')).toBeInTheDocument();
    expect(screen.getByText('Fields: access.daily_needs')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'View evidence' }).some((link) => link.getAttribute('href') === '#evidence-card-access')).toBe(true);
  });

  it('renders nullable fit and partially grounded synthesis honestly', () => {
    const partial = structuredClone(response);
    partial.fit = { score: null, label: 'Not enough evidence', explanation: 'No evidence-backed factor was available.', flags: [], factors: [] };
    partial.synthesis = { status: 'partial', model: 'gpt-4o-mini', message: 'One claim was replaced.' };
    render(<Profile response={partial} lensIsStale={false} onSave={vi.fn()} />);
    expect(screen.getByText('Partially AI-grounded')).toBeInTheDocument();
    expect(screen.getByText('Not enough evidence')).toBeInTheDocument();
    expect(screen.queryByText('/ 100')).not.toBeInTheDocument();
  });

  it('prints and confirms saved-report deletion', () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const onDelete = vi.fn();
    render(
      <SavedProfiles
        open
        profiles={[{ id: 'r1', place_label: 'The Annex', updated_at: '2026-09-16T00:00:00Z', confidence_level: 'medium', analysis_lens: { profile_name: 'Transit first' }, coverage: { level: 'full' }, fit_score: 70 }]}
        onClose={vi.fn()}
        onOpen={vi.fn()}
        onDelete={onDelete}
        onRefresh={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Print/i }));
    expect(print).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Delete The Annex/i }));
    expect(confirm).toHaveBeenCalled();
    expect(onDelete).toHaveBeenCalledWith('r1');
  });
});
