import { expect, test } from '@playwright/test';

const analysis = {
  place: { label: 'The Annex, Toronto, Ontario', coordinates: { lat: 43.67, lng: -79.4 } },
  analysis_lens: { mode: 'saved_profile', profile_id: 'p1', profile_name: 'Transit first', preferences: { top_priority: 'transit_access', must_haves: [], deal_breakers: [] } },
  coverage: { region: 'toronto', level: 'full', supported_signals: ['Transit access', 'Daily needs'], unavailable_signals: ['Quiet'], message: 'Toronto coverage combines local and regional evidence.' },
  profile: {
    overview: 'A connected Toronto neighbourhood with source-backed daily-needs evidence.',
    vibe_scores: { walkability: 82, transit_access: 86, affordability: null, quiet: null, social_scene: null, parks_outdoors: 67, daily_needs: 78, dining_activity: 75 },
    who_lives_here: { population_density: 9650, median_renter_shelter_cost: 1750, renter_cost_burden_percent: 39.2, regional_average_two_bedroom_rent: 2034, rental_vacancy_rate: 3, rent_geographic_scope: 'Greater Toronto Area', rent_edition: '2025 Rental Market Report' },
    honest_pros: ['Daily needs and transit are well represented nearby.'],
    honest_cons: ['Quiet is unavailable and is not scored.'],
    narrative_citations: [{ section: 'overview', evidence_check_ids: ['access'] }],
    trajectory: null,
    provenance: { items: [{ claim_id: 'vibe.transit_access', label: 'Transit access', summary: 'Based on access.transit_access.', support: 'inferred', sources: ['access'], source_fields: ['access.transit_access'] }] },
  },
  fit: { score: 71, label: 'Good fit', explanation: 'Two evidence-backed factors moved this fit.', flags: [], factors: [{ signal: 'Transit access', value: 86, impact: 15, explanation: 'Transit is strongly supported.', source_fields: ['access.transit_access'] }] },
  confidence: { level: 'high', available_sources: ['census', 'housing', 'access', 'local'], missing_sources: [], caveats: [] },
  source_statuses: [{ source: 'access', status: 'success', message: 'OSM returned.', updated_at: '2026-09-16T00:00:00Z' }],
  synthesis: { status: 'used', model: 'test-model', message: 'Validated evidence narrative.' },
  evidence_checks: [
    { id: 'access', label: 'Everyday access', status: 'supported', summary: 'OSM access returned.', source_fields: ['access.daily_needs'] },
    { id: 'census', label: 'Census context', status: 'supported', summary: 'Bundled Census context returned.' },
    { id: 'rent', label: 'Unit-matched rent', status: 'supported', summary: 'CMHC rent context returned.' },
    { id: 'transit', label: 'Scheduled transit', status: 'supported', summary: 'Scheduled service returned.' },
    { id: 'cycling', label: 'Cycling access', status: 'unavailable', summary: 'Cycling is unavailable here.' },
  ],
};

async function mockApi(page, fixture = analysis, health = { status: 'ok', mapbox: { configured: true }, snapshot: { ready: true }, sqlite: { ready: true } }) {
  await page.route('http://127.0.0.1:8000/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    if (path === '/health') body = health;
    if (path === '/analyze') body = fixture;
    if (path === '/preference-profiles') body = [{ id: 'p1', name: 'Transit first', is_default: true, generic_mode: false, top_priority: 'transit_access', must_haves: [], deal_breakers: [], created_at: '2026-09-16T00:00:00Z', updated_at: '2026-09-16T00:00:00Z' }];
    if (path === '/profiles') body = [{ id: 'r1', place_label: fixture.place.label, confidence_level: 'high', source_statuses: fixture.source_statuses, analysis_lens: fixture.analysis_lens, coverage: fixture.coverage, fit_score: 71, fit_label: 'Good fit', cycling_score: fixture.profile.vibe_scores.cycling_access, cycling_evidence_method: fixture.profile.cycling_context?.method, collision_count: fixture.profile.collision_context?.total_collisions, building_match: fixture.evidence_checks?.some((check) => check.id === 'building') ? Boolean(fixture.profile.building_context) : null, building_score: fixture.profile.building_context?.current_score, created_at: '2026-09-16T00:00:00Z', updated_at: '2026-09-16T00:00:00Z' }];
    if (path === '/profiles/r1') body = { id: 'r1', place_label: fixture.place.label, confidence_level: 'high', source_statuses: fixture.source_statuses, analysis_lens: fixture.analysis_lens, coverage: fixture.coverage, created_at: '2026-09-16T00:00:00Z', updated_at: '2026-09-16T00:00:00Z', analyze_request: { query: fixture.place.label }, response: fixture };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

async function mockMapboxSearch(page) {
  await page.route('https://api.mapbox.com/search/geocode/v6/forward**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        features: [
          {
            id: 'address.79-thorncliffe',
            properties: {
              mapbox_id: 'address.79-thorncliffe',
              full_address: '79 Thorncliffe Park Drive, Toronto, Ontario M4H 1L4, Canada',
            },
            geometry: { coordinates: [-79.341499, 43.706134] },
          },
          {
            id: 'address.27-thorncliffe',
            properties: {
              mapbox_id: 'address.27-thorncliffe',
              full_address: '27 Thorncliffe Park Drive, Toronto, Ontario M4H 1J8, Canada',
            },
            geometry: { coordinates: [-79.3446, 43.7052] },
          },
        ],
      }),
    });
  });
}

for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 390, height: 844 }]) {
  test(`landing and workspaces fit ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mockApi(page);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Find a place/i })).toBeVisible();
    const mapSurface = page.locator('.map-view, .map-token-state').first();
    await expect(mapSurface).toBeVisible();
    const mapBox = await mapSurface.boundingBox();
    expect(mapBox.width).toBeGreaterThan(300);
    expect(mapBox.height).toBeGreaterThan(300);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

    const lensButton = viewport.width <= 720
      ? page.getByRole('button', { name: 'Lens', exact: true })
      : page.getByRole('button', { name: /Analysis lens/i });
    await lensButton.click();
    const profiles = page.getByRole('dialog', { name: /Create analysis lens|Edit analysis lens/i });
    await expect(profiles).toBeVisible();
    await expect(profiles.getByLabel(/Rental unit size/i)).toBeVisible();
    await expect(profiles.getByRole('checkbox', { name: 'Cycling access' }).first()).toBeVisible();
    const box = await profiles.boundingBox();
    expect(box.y).toBeGreaterThanOrEqual(0);
    expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
    await page.keyboard.press('Escape');
    await expect(profiles).toBeHidden();

    const savedButton = viewport.width <= 720
      ? page.getByRole('button', { name: 'Saved', exact: true })
      : page.getByRole('button', { name: 'Saved reports', exact: true });
    await savedButton.click();
    await page.locator('.saved-open').click();
    await expect(page.getByRole('heading', { name: analysis.place.label })).toBeVisible();
    await expect(page.getByText(/Analyzed with/)).toContainText('Transit first');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

    await page.getByRole('button', { name: 'Compare' }).click();
    const compare = page.getByRole('dialog', { name: 'Compare places' });
    await expect(compare).toBeVisible();
    const compareBox = await compare.boundingBox();
    expect(compareBox.y).toBeGreaterThanOrEqual(0);
    expect(compareBox.y + compareBox.height).toBeLessThanOrEqual(viewport.height);
  });
}

test('saved report restores its immutable lens and supports print', async ({ page }) => {
  await mockApi(page);
  await page.goto('/');
  await page.getByRole('button', { name: /Saved reports/i }).click();
  await page.locator('.saved-open').click();
  await expect(page.getByRole('heading', { name: analysis.place.label })).toBeVisible();
  await expect(page.getByText(/Analyzed with/)).toContainText('Transit first');
  await expect(page.locator('#evidence-card-cycling')).toContainText('Unavailable');
  await expect(page.getByRole('button', { name: /Print \/ Save PDF/i })).toBeVisible();
  await expect(page.locator('.analysis-sheet')).toHaveScreenshot('analysis-sheet.png');
});

test('compare opens with shared lens context', async ({ page }) => {
  await mockApi(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Compare' }).click();
  await expect(page.getByRole('dialog', { name: 'Compare places' })).toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Compare places' }).getByText('Transit first', { exact: true })).toBeVisible();
});

test('compare address suggestions expand beyond the slot and preserve the full address', async ({ page }) => {
  await mockApi(page);
  await mockMapboxSearch(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Compare' }).click();

  const compare = page.getByRole('dialog', { name: 'Compare places' });
  const slots = compare.locator('.compare-place-slots');
  const firstSlot = slots.locator('.compare-place-slot').first();
  const input = firstSlot.getByRole('textbox');
  await input.fill('79 Thorncliffe');

  const results = firstSlot.locator('.search-results');
  await expect(results).toBeVisible();
  await expect(results.getByRole('button')).toHaveCount(2);
  expect(await slots.evaluate((element) => getComputedStyle(element).overflowY)).toBe('visible');

  const slotBox = await firstSlot.boundingBox();
  const resultsBox = await results.boundingBox();
  expect(resultsBox.y + resultsBox.height).toBeGreaterThan(slotBox.y + slotBox.height);

  const fullAddress = '79 Thorncliffe Park Drive, Toronto, Ontario M4H 1L4, Canada';
  await results.getByRole('button', { name: fullAddress }).click();
  await expect(input).toHaveValue(fullAddress);
  await expect(firstSlot.locator('.compare-slot-topline')).toContainText(fullAddress);
  await expect(compare.getByText('1 of 4 places')).toBeVisible();
});

test('analyzed compare results use the framed desktop grid without clipping', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mockApi(page);
  await mockMapboxSearch(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Compare' }).click();

  const compare = page.getByRole('dialog', { name: 'Compare places' });
  const inputs = compare.locator('.compare-place-slot input');
  await inputs.nth(0).fill('79 Thorncliffe');
  await compare.locator('.compare-place-slot').nth(0).locator('.search-results button').nth(0).click();
  await inputs.nth(1).fill('27 Thorncliffe');
  await compare.locator('.compare-place-slot').nth(1).locator('.search-results button').nth(1).click();
  await compare.getByRole('button', { name: 'Analyze Compare' }).click();

  const results = compare.locator('.compare-results-grid');
  await expect(results.locator('.compare-result-card')).toHaveCount(2);
  expect(await results.evaluate((element) => getComputedStyle(element).display)).toBe('grid');
  expect(await compare.evaluate((element) => getComputedStyle(element).backgroundColor)).toBe('rgb(232, 236, 230)');
  const evidenceLabel = results.locator('.compare-evidence-list span').first();
  await expect(evidenceLabel).toBeVisible();
  expect(await evidenceLabel.evaluate((element) => getComputedStyle(element).color)).toBe('rgb(255, 255, 255)');

  const firstCard = results.locator('.compare-result-card').first();
  const provenanceDetails = firstCard.locator('.compare-detail-panel').filter({ hasText: 'Evidence behind this result' });
  await expect(provenanceDetails).not.toHaveAttribute('open', '');
  await provenanceDetails.locator('summary').click();
  await expect(provenanceDetails).toHaveAttribute('open', '');
  await expect(provenanceDetails.locator('.provenance-row')).toBeVisible();
  expect(await firstCard.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);

  const viewportWidth = page.viewportSize().width;
  for (const card of await results.locator('.compare-result-card').all()) {
    const box = await card.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(viewportWidth);
  }
});

test('saved report exposes scheduled transit, cycling, and unit-matched rent evidence', async ({ page }) => {
  const fixture = structuredClone(analysis);
  fixture.analysis_version = '2026.09-gta-snapshot-v1';
  fixture.snapshot_id = 'gta-fixture';
  fixture.profile.vibe_scores.cycling_access = 82;
  fixture.profile.transit_context = { scheduled_departures_per_hour: 18, nearby_route_count: 4, nearby_routes: ['1', '2'], agencies: ['TTC'], service_date: '2026-09-15', scope: 'TTC' };
  fixture.profile.cycling_context = { protected_network_km: 2.4, total_network_km: 4.1, bike_share_stations: 5, bicycle_parking_locations: null, network_radius_m: 1000, scope: 'City of Toronto', edition: 'Toronto Open Data 2026', method: 'toronto_official', fallback: false };
  fixture.evidence_checks = fixture.evidence_checks.map((check) => (
    check.id === 'cycling'
      ? { ...check, status: 'supported', summary: 'Official Toronto cycling evidence returned.' }
      : check
  ));
  fixture.profile.who_lives_here.rent_benchmark = { monthly_rent: 1763, unit_size: 'one_bedroom', geography: 'Toronto', edition: 'CMHC 2025', quality_code: 'a', market_scope: 'Purpose-built rental apartments' };
  await mockApi(page, fixture);
  await page.goto('/');
  await page.getByRole('button', { name: /Saved reports/i }).click();
  await page.locator('.saved-open').click();
  await expect(page.getByText(/18 departures/i)).toBeVisible();
  await expect(page.getByText(/2.4 km protected/i)).toBeVisible();
  await expect(page.getByText(/Official Toronto/i).first()).toBeVisible();
  await expect(page.getByText('$1,763')).toBeVisible();
});

test('saved report labels stale OSM cycling evidence and preserves a real zero', async ({ page }) => {
  const fixture = structuredClone(analysis);
  fixture.place = { label: 'Ottawa, Ontario', coordinates: { lat: 45.4215, lng: -75.6972 } };
  fixture.coverage = { region: 'outside_gta', level: 'limited', supported_signals: ['Cycling access'], unavailable_signals: [], message: 'Limited non-GTA evidence with a labelled OSM cycling estimate.' };
  fixture.profile.vibe_scores.cycling_access = 0;
  fixture.profile.cycling_context = {
    protected_network_km: 0,
    total_network_km: 0,
    bike_share_stations: null,
    bicycle_parking_locations: 2,
    network_radius_m: 1000,
    scope: 'OpenStreetMap mapped cycling infrastructure',
    edition: 'OpenStreetMap live proximity query',
    method: 'osm_fallback',
    fallback: true,
    updated_at: '2026-09-14T00:00:00Z',
    source_url: 'https://www.openstreetmap.org/copyright',
  };
  fixture.evidence_checks = fixture.evidence_checks.map((check) => (
    check.id === 'cycling'
      ? { ...check, status: 'stale', summary: 'Using stale cached OSM cycling evidence.' }
      : check
  ));
  await mockApi(page, fixture);
  await page.goto('/');
  await page.getByRole('button', { name: /Saved reports/i }).click();
  await expect(page.getByText(/0 cycling · OSM estimate/i)).toBeVisible();
  await page.locator('.saved-open').click();
  const cyclingCard = page.locator('#evidence-card-cycling');
  await expect(cyclingCard).toContainText('Stale data');
  await expect(cyclingCard).toContainText('No mapped qualifying cycling infrastructure');
  await expect(cyclingCard).toContainText('2 mapped bicycle-parking locations');
  await expect(cyclingCard).toContainText('not a route, traffic-stress, or safety score');
  await expect(page.locator('.score-card').filter({ hasText: 'Cycling access' })).toContainText('0/100');
});

test('saved report exposes collision history and an exact RentSafeTO record', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const fixture = structuredClone(analysis);
  fixture.profile.collision_context = {
    radius_m: 1000,
    baseline_period_start: '2021-01-01',
    baseline_period_end: '2025-12-31',
    total_collisions: 42,
    injury_collisions: 8,
    fatal_collisions: 1,
    pedestrian_involved_collisions: 5,
    cyclist_involved_collisions: 3,
    ksi_period_start: '2021-01-01',
    ksi_period_end: '2026-08-29',
    ksi_collisions: 6,
    ksi_fatal_collisions: 1,
    ksi_pedestrian_involved_collisions: 2,
    ksi_cyclist_involved_collisions: 1,
    severe_events: [{ collision_id: 'ksi-1', occurred_at: '2026-08-01', latitude: 43.67, longitude: -79.4 }],
    stale: false,
  };
  fixture.profile.building_context = {
    rsn: '4154972',
    site_address: '210 WYCHWOOD AVE',
    property_type: 'PRIVATE',
    year_built: 1930,
    storeys: 4,
    units: 40,
    evaluation_date: '2025-07-09',
    current_score: 98,
    proactive_score: 98,
    reactive_deduction: 0,
    rating: 'green',
    areas_evaluated: 36,
    low_rated_categories: [],
    stale: false,
  };
  fixture.evidence_checks.push(
    { id: 'collisions', label: 'Reported collision history', status: 'supported', summary: 'Reported history returned.' },
    { id: 'building', label: 'RentSafeTO building record', status: 'supported', summary: 'Exact address matched.' },
  );
  await mockApi(page, fixture);
  await page.goto('/');
  await page.getByRole('button', { name: 'Saved', exact: true }).click();
  await expect(page.getByText('42 reported collisions / 1 km')).toBeVisible();
  await page.locator('.saved-open').click();
  await expect(page.getByText('42 reported collisions')).toBeVisible();
  await expect(page.getByText('6 KSI collisions')).toBeVisible();
  await expect(page.getByText(/210 WYCHWOOD AVE/)).toBeVisible();
  await expect(page.getByText(/not safety or future risk/i)).toBeVisible();
  await expect(page.locator('.analysis-sheet')).toHaveScreenshot('road-building-mobile.png');
});

test('saved report shows a clear no-exact-building-match state', async ({ page }) => {
  const fixture = structuredClone(analysis);
  fixture.profile.building_context = null;
  fixture.evidence_checks.push({
    id: 'building',
    label: 'RentSafeTO building record',
    status: 'unavailable',
    summary: 'No exact RentSafeTO record matched this address; this does not prove the building is unregistered.',
  });
  await mockApi(page, fixture);
  await page.goto('/');
  await page.getByRole('button', { name: /Saved reports/i }).click();
  await expect(page.getByText('No exact RentSafeTO match')).toBeVisible();
  await page.locator('.saved-open').click();
  await expect(page.locator('#evidence-card-building')).toContainText('Unavailable');
  await expect(page.locator('#evidence-card-building')).toContainText('does not prove');
});

test('partial evidence and grounded synthesis states stay explicit', async ({ page }) => {
  const fixture = structuredClone(analysis);
  fixture.fit = { score: null, label: 'Not enough evidence', explanation: 'No evidence-backed factor was available.', flags: [], factors: [] };
  fixture.synthesis = { status: 'partial', model: 'test-model', message: 'One claim was replaced.' };
  fixture.evidence_checks = [
    { id: 'access', label: 'Everyday access', status: 'fallback', summary: 'Using stale OSM evidence.' },
    { id: 'census', label: 'Census context', status: 'unavailable', summary: 'No Census context.' },
  ];
  await mockApi(page, fixture);
  await page.goto('/');
  await page.getByRole('button', { name: /Saved reports/i }).click();
  await page.locator('.saved-open').click();
  await expect(page.getByText('Partially AI-grounded')).toBeVisible();
  await expect(page.getByText('1 fallback')).toBeVisible();
  await expect(page.getByText('1 unavailable')).toBeVisible();
  await expect(page.getByText('Not enough evidence')).toBeVisible();
  await expect(page.getByText('50', { exact: true })).toHaveCount(0);
});

test('development setup failures are separate from neighbourhood evidence', async ({ page }) => {
  await mockApi(page, analysis, {
    status: 'degraded',
    mapbox: { configured: true },
    snapshot: { ready: false, errors: ['Snapshot database is not readable by the backend process.'] },
    sqlite: { ready: true },
  });
  await page.goto('/');
  const warning = page.getByRole('alert');
  await expect(warning).toContainText('Local setup needs attention');
  await expect(warning).toContainText('Snapshot database is not readable');
});
