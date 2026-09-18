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
  synthesis: { status: 'used', model: 'gpt-4o-mini', message: 'Validated evidence narrative.' },
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
    if (path === '/preference-profiles') body = [{ id: 'p1', name: 'Transit first', is_default: true, generic_mode: false, top_priority: 'transit_access', must_haves: [], deal_breakers: [], created_at: '2026-09-16T00:00:00Z', updated_at: '2026-09-16T00:00:00Z' }];
    if (path === '/profiles') body = [{ id: 'r1', place_label: fixture.place.label, confidence_level: 'high', source_statuses: fixture.source_statuses, analysis_lens: fixture.analysis_lens, coverage: fixture.coverage, fit_score: 71, fit_label: 'Good fit', created_at: '2026-09-16T00:00:00Z', updated_at: '2026-09-16T00:00:00Z' }];
    if (path === '/profiles/r1') body = { id: 'r1', place_label: fixture.place.label, confidence_level: 'high', source_statuses: fixture.source_statuses, analysis_lens: fixture.analysis_lens, coverage: fixture.coverage, created_at: '2026-09-16T00:00:00Z', updated_at: '2026-09-16T00:00:00Z', analyze_request: { query: fixture.place.label }, response: fixture };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
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

test('saved report exposes scheduled transit, cycling, and unit-matched rent evidence', async ({ page }) => {
  const fixture = structuredClone(analysis);
  fixture.analysis_version = '2026.09-gta-snapshot-v1';
  fixture.snapshot_id = 'gta-fixture';
  fixture.profile.vibe_scores.cycling_access = 82;
  fixture.profile.transit_context = { scheduled_departures_per_hour: 18, nearby_route_count: 4, nearby_routes: ['1', '2'], agencies: ['TTC'], service_date: '2026-09-15', scope: 'TTC' };
  fixture.profile.cycling_context = { protected_network_km: 2.4, total_network_km: 4.1, bike_share_stations: 5, scope: 'City of Toronto' };
  fixture.profile.who_lives_here.rent_benchmark = { monthly_rent: 1763, unit_size: 'one_bedroom', geography: 'Toronto', edition: 'CMHC 2025', quality_code: 'a', market_scope: 'Purpose-built rental apartments' };
  await mockApi(page, fixture);
  await page.goto('/');
  await page.getByRole('button', { name: /Saved reports/i }).click();
  await page.locator('.saved-open').click();
  await expect(page.getByText(/18 departures/i)).toBeVisible();
  await expect(page.getByText(/2.4 km protected/i)).toBeVisible();
  await expect(page.getByText('$1,763')).toBeVisible();
});

test('partial evidence and grounded synthesis states stay explicit', async ({ page }) => {
  const fixture = structuredClone(analysis);
  fixture.fit = { score: null, label: 'Not enough evidence', explanation: 'No evidence-backed factor was available.', flags: [], factors: [] };
  fixture.synthesis = { status: 'partial', model: 'gpt-4o-mini', message: 'One claim was replaced.' };
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
