import { Download, RefreshCw } from 'lucide-react';
import Confidence from './Confidence.jsx';
import Freshness from './Freshness.jsx';
import Provenance from './Provenance.jsx';
import ScoreCards from './ScoreCards.jsx';

export default function Profile({
  response,
  lensIsStale,
  onSave,
  savedProfileId,
  saveError,
  isSaving,
  generatedAt,
  isRefreshing,
  refreshError,
  onRefresh,
}) {
  const {
    profile,
    fit,
    confidence,
    source_statuses: statuses,
    analysis_lens: lens,
    coverage,
    evidence_checks: evidenceChecks = [],
    synthesis,
  } = response;
  return (
    <section className="profile-stack">
      {lensIsStale && (
        <div className="stale-lens-banner" role="status">
          <RefreshCw size={17} aria-hidden="true" />
          <span><strong>Profile changed.</strong> Reanalyze to update this result.</span>
        </div>
      )}
      <header className="place-header">
        <div>
          <p className="eyebrow">{labelize(coverage?.region)} field note</p>
          <h1>{response.place.label}</h1>
          <p>Analyzed with <strong>{lens?.profile_name || 'Legacy report'}</strong></p>
        </div>
        <div className="report-actions">
          <button type="button" onClick={() => window.print()}>
            <Download size={17} aria-hidden="true" /> Print / Save PDF
          </button>
          <button type="button" className="primary-button" onClick={onSave} disabled={isSaving || Boolean(savedProfileId)}>
            {isSaving ? 'Saving…' : savedProfileId ? 'Report saved' : 'Save report'}
          </button>
        </div>
      </header>
      {saveError && <p className="action-error" role="alert">{saveError}</p>}
      <section className="coverage-summary">
        <div><span className={`coverage-level ${coverage?.level}`}>{labelize(coverage?.level)} coverage</span></div>
        <p>{coverage?.message}</p>
        {coverage?.unavailable_signals?.length > 0 && (
          <small>Unavailable: {coverage.unavailable_signals.join(', ')}</small>
        )}
      </section>
      <EvidenceSummary checks={evidenceChecks} />
      {fit && <FitBreakdown fit={fit} />}
      <article className="overview-card">
        <div className="overview-title-row">
          <p className="eyebrow">Field note</p>
          <SynthesisBadge synthesis={synthesis} />
        </div>
        <p>{profile.overview}</p>
        <CitationLinks citations={profile.narrative_citations} section="overview" checks={evidenceChecks} />
      </article>
      <div id="evidence-card-access">
        <ScoreCards scores={profile.vibe_scores} cyclingContext={profile.cycling_context} />
      </div>
      <EvidenceCards profile={profile} evidenceChecks={evidenceChecks} />
      <AreaContext context={profile.who_lives_here} />
      <div className="insight-list">
        <article>
          <h2>What works</h2>
          <ul>{profile.honest_pros.map((item, index) => (
            <li key={item}>
              {item}
              <CitationLinks citations={profile.narrative_citations?.filter((citation) => citation.item_index === index)} section="pro" checks={evidenceChecks} />
            </li>
          ))}</ul>
        </article>
        <article>
          <h2>Watch for</h2>
          <ul>{profile.honest_cons.map((item, index) => (
            <li key={item}>
              {item}
              <CitationLinks citations={profile.narrative_citations?.filter((citation) => citation.item_index === index)} section="con" checks={evidenceChecks} />
            </li>
          ))}</ul>
        </article>
      </div>
      <details className="evidence-details">
        <summary>Freshness and sources</summary>
        <Freshness
          generatedAt={generatedAt}
          savedProfileId={savedProfileId}
          isRefreshing={isRefreshing}
          refreshError={refreshError}
          onRefresh={onRefresh}
        />
        <Provenance provenance={profile.provenance} />
        <EvidenceChecklist checks={evidenceChecks} />
        <Confidence confidence={confidence} statuses={statuses} />
        <p className="analysis-version">
          Analysis {response.analysis_version || 'legacy'}
          {response.snapshot_id ? ` · Snapshot ${response.snapshot_id}` : ' · No bundled snapshot'}
        </p>
      </details>
    </section>
  );
}

function EvidenceSummary({ checks }) {
  if (!checks?.length) return null;
  const counts = checks.reduce((result, check) => {
    result[check.status] = (result[check.status] || 0) + 1;
    return result;
  }, {});
  return (
    <section className="evidence-summary" aria-label="Evidence check summary">
      <strong>{counts.supported || 0} supported</strong>
      {counts.fallback > 0 && <span>{counts.fallback} fallback</span>}
      {counts.stale > 0 && <span>{counts.stale} stale</span>}
      {(counts.unavailable || counts.error) > 0 && (
        <span>{(counts.unavailable || 0) + (counts.error || 0)} unavailable</span>
      )}
    </section>
  );
}

function EvidenceChecklist({ checks }) {
  if (!checks?.length) return null;
  return (
    <section className="panel-section evidence-checklist">
      <div className="section-heading"><p className="eyebrow">Evidence checks</p><h2>What completed</h2></div>
      <div className="source-list">
        {checks.map((check) => (
          <div className={`source-row check-${check.status}`} id={`evidence-${check.id}`} key={check.id}>
            <span>
              <strong>{check.label}</strong>
              <small>{check.summary}</small>
              {check.scope && <small>{check.scope}</small>}
              {check.edition && <small>{check.edition}</small>}
              {check.updated_at && <small>Updated {formatEvidenceDate(check.updated_at)}</small>}
              {check.source_fields?.length > 0 && <small>Fields: {check.source_fields.join(' · ')}</small>}
              {evidenceTarget(check.id) && <a href={`#${evidenceTarget(check.id)}`}>View evidence</a>}
            </span>
            <strong>{check.status}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function SynthesisBadge({ synthesis }) {
  const labels = {
    used: 'AI-grounded',
    partial: 'Partially AI-grounded',
    skipped: 'Deterministic',
    fallback: 'Deterministic fallback',
  };
  const status = synthesis?.status || 'skipped';
  return <span className={`synthesis-badge synthesis-${status}`}>{labels[status]}</span>;
}

function CitationLinks({ citations = [], section, checks }) {
  const ids = citations
    .filter((citation) => citation.section === section)
    .flatMap((citation) => citation.evidence_check_ids || []);
  if (!ids.length) return null;
  const labels = new Map(checks.map((check) => [check.id, check.label]));
  return (
    <small className="narrative-citations">
      Evidence: {[...new Set(ids)].map((id) => (
        <a href={`#evidence-${id}`} key={id}>{labels.get(id) || id}</a>
      ))}
    </small>
  );
}

function EvidenceCards({ profile, evidenceChecks = [] }) {
  const transit = profile.transit_context;
  const cycling = profile.cycling_context;
  const rent = profile.who_lives_here?.rent_benchmark;
  const collisions = profile.collision_context;
  const building = profile.building_context;
  const cyclingCheck = evidenceChecks.find((check) => check.id === 'cycling');
  const collisionCheck = evidenceChecks.find((check) => check.id === 'collisions');
  const buildingCheck = evidenceChecks.find((check) => check.id === 'building');
  if (!transit && !cycling && !rent && !collisions && !building && !cyclingCheck && !collisionCheck && !buildingCheck) return null;
  return (
    <section className="evidence-card-grid" aria-label="Decision evidence">
      {transit && (
        <article className="evidence-card" id="evidence-card-transit">
          <p className="eyebrow">{transit.fallback ? 'Transit fallback' : 'Scheduled transit'}</p>
          <h2>{transit.fallback ? `${transit.nearby_stop_count ?? 0} nearby OSM stops` : `${transit.scheduled_departures_per_hour} departures / peak hour`}</h2>
          <p>{transit.fallback ? 'Schedule frequency and route quality are unavailable.' : `${transit.nearby_route_count} nearby routes across ${transit.agencies.join(', ') || 'covered agencies'}.`}</p>
          {transit.nearby_routes?.length > 0 && <small>{transit.nearby_routes.slice(0, 8).join(' · ')}</small>}
          <small>{transit.scope}{!transit.fallback && ` · weekday schedule ${transit.service_date || 'date unavailable'}`}</small>
        </article>
      )}
      {cycling && (
        <article className="evidence-card" id="evidence-card-cycling">
          <div className="evidence-card-heading">
            <p className="eyebrow">{cycling.fallback ? 'OSM cycling estimate' : 'Official Toronto cycling'}</p>
            <span className={`evidence-state ${cyclingCheck?.status === 'stale' ? 'stale' : cycling.fallback ? 'fallback' : ''}`}>
              {cyclingCheck?.status === 'stale' ? 'Stale data' : cycling.fallback ? 'Fallback evidence' : 'Official evidence'}
            </span>
          </div>
          <h2>{cycling.protected_network_km} km protected or separated nearby</h2>
          <p>
            {cycling.total_network_km} km total mapped network within {(cycling.network_radius_m || 1000) / 1000} km.
          </p>
          {cycling.total_network_km === 0 && (
            <p>No mapped qualifying cycling infrastructure was found; this is different from a source failure.</p>
          )}
          {cycling.bike_share_stations != null && (
            <p>{cycling.bike_share_stations} Bike Share stations within 800 m; station locations only, not live availability.</p>
          )}
          {cycling.bicycle_parking_locations != null && (
            <p>{cycling.bicycle_parking_locations} mapped bicycle-parking locations within 800 m.</p>
          )}
          <small>{cycling.scope} · {cycling.edition}</small>
          {cycling.updated_at && <small>Evidence updated {formatEvidenceDate(cycling.updated_at)}</small>}
          <small>
            {cycling.fallback
              ? 'OSM completeness varies. This is not a route, traffic-stress, or safety score.'
              : 'Bike Share locations are context only and do not affect the cycling score.'}
          </small>
          {cycling.source_url && <a href={cycling.source_url} target="_blank" rel="noreferrer">View cycling source</a>}
        </article>
      )}
      {!cycling && cyclingCheck && (
        <UnavailableEvidenceCard id="evidence-card-cycling" label="Cycling access" check={cyclingCheck} />
      )}
      {rent && (
        <article className="evidence-card" id="evidence-card-rent">
          <p className="eyebrow">Purpose-built rent</p>
          <h2>{rent.suppressed || rent.monthly_rent == null ? 'Suppressed' : formatCad(rent.monthly_rent)}</h2>
          <p>{unitLabel(rent.unit_size)} · {rent.geography}</p>
          <small>{rent.edition} · quality {rent.quality_code || 'not supplied'} · {rent.market_scope}</small>
        </article>
      )}
      {collisions ? (
        <article className="evidence-card evidence-card-wide" id="evidence-card-collisions">
          <EvidenceCardHeading
            label="Reported collision history nearby"
            stale={collisions.stale || collisionCheck?.status === 'stale'}
          />
          <h2>{formatNumber(collisions.total_collisions)} reported collisions</h2>
          <p>Within {formatNumber(collisions.radius_m)} m. These counts describe reported history, not safety or future risk.</p>
          <dl className="evidence-stat-grid">
            <EvidenceStat label="Injury" value={collisions.injury_collisions} />
            <EvidenceStat label="Fatal" value={collisions.fatal_collisions} />
            <EvidenceStat label="Pedestrian-involved" value={collisions.pedestrian_involved_collisions} />
            <EvidenceStat label="Cyclist-involved" value={collisions.cyclist_involved_collisions} />
          </dl>
          <small>All reported collisions: {dateWindow(collisions.baseline_period_start, collisions.baseline_period_end)}</small>
          <div className="evidence-subsection">
            <strong>{formatNumber(collisions.ksi_collisions)} KSI collisions</strong>
            <span>{formatNumber(collisions.ksi_fatal_collisions)} fatal · {formatNumber(collisions.ksi_pedestrian_involved_collisions)} pedestrian-involved · {formatNumber(collisions.ksi_cyclist_involved_collisions)} cyclist-involved</span>
            <small>Killed-or-seriously-injured data: {dateWindow(collisions.ksi_period_start, collisions.ksi_period_end)}. Annual and daily counts are shown separately.</small>
            {collisions.severe_events?.length > 0 && <small>{collisions.severe_events.length} recent deduplicated KSI points are available on the map.</small>}
          </div>
          <SourceLinks links={[
            [collisions.baseline_source_url, 'Official all-collision dataset'],
            [collisions.ksi_source_url, 'Official KSI dataset'],
          ]} />
        </article>
      ) : collisionCheck ? (
        <UnavailableEvidenceCard id="evidence-card-collisions" label="Reported collision history nearby" check={collisionCheck} />
      ) : null}
      {building ? (
        <article className="evidence-card evidence-card-wide" id="evidence-card-building">
          <EvidenceCardHeading
            label="RentSafeTO building record"
            stale={building.stale || buildingCheck?.status === 'stale'}
          />
          <div className="building-score-row">
            <h2>{building.current_score == null ? 'Registered record' : `${formatNumber(building.current_score)} / 100`}</h2>
            {building.rating && <span className={`building-rating rating-${building.rating}`}>{building.rating}</span>}
          </div>
          <p><strong>{building.site_address}</strong>{building.property_type ? ` · ${building.property_type}` : ''}</p>
          <dl className="evidence-stat-grid building-facts">
            <EvidenceStat label="Year built" value={building.year_built} />
            <EvidenceStat label="Storeys" value={building.storeys} />
            <EvidenceStat label="Units" value={building.units} />
            <EvidenceStat label="Areas evaluated" value={building.areas_evaluated} />
            <EvidenceStat label="Proactive score" value={building.proactive_score} />
            <EvidenceStat label="Reactive deduction" value={building.reactive_deduction == null ? null : -building.reactive_deduction} />
          </dl>
          <small>{building.evaluation_date ? `Latest evaluation ${formatEvidenceDate(building.evaluation_date)}` : 'No evaluation is present in the bundled record.'} · RSN {building.rsn}</small>
          {building.low_rated_categories?.length > 0 && (
            <div className="low-rated-list">
              <strong>Common-area categories rated 1</strong>
              <span>{building.low_rated_categories.join(' · ')}</span>
            </div>
          )}
          <small>RentSafeTO covers registered apartment buildings and common-area/property-standard evaluations, not individual unit condition.</small>
          <SourceLinks links={[
            [building.registration_source_url, 'Official registration dataset'],
            [building.evaluation_source_url, 'Official evaluation dataset'],
          ]} />
        </article>
      ) : buildingCheck ? (
        <UnavailableEvidenceCard id="evidence-card-building" label="RentSafeTO building record" check={buildingCheck} />
      ) : null}
    </section>
  );
}

function EvidenceCardHeading({ label, stale }) {
  return (
    <div className="evidence-card-heading">
      <p className="eyebrow">{label}</p>
      <span className={stale ? 'evidence-state stale' : 'evidence-state'}>
        {stale ? 'Stale data' : 'Bundled official data'}
      </span>
    </div>
  );
}

function EvidenceStat({ label, value }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value == null ? 'Unavailable' : formatNumber(value)}</dd>
    </div>
  );
}

function UnavailableEvidenceCard({ id, label, check }) {
  return (
    <article className={`evidence-card evidence-card-unavailable check-${check.status}`} id={id}>
      <p className="eyebrow">{label}</p>
      <h2>{check.status === 'error' ? 'Source failed' : 'Unavailable'}</h2>
      <p>{check.summary}</p>
      {check.scope && <small>{check.scope}</small>}
    </article>
  );
}

function SourceLinks({ links }) {
  const available = links.filter(([url]) => url);
  if (!available.length) return null;
  return (
    <div className="evidence-source-links">
      {available.map(([url, label]) => (
        <a href={url} target="_blank" rel="noreferrer" key={url}>{label}</a>
      ))}
    </div>
  );
}

function FitBreakdown({ fit }) {
  const hasScore = fit.score != null;
  return (
    <section className="fit-card">
      <div className="fit-score">
        <strong>{hasScore ? fit.score : '—'}</strong>{hasScore && <span>/ 100</span>}
        <small>{fit.label}</small>
      </div>
      <div className="fit-copy">
        <p className="eyebrow">Your fit</p>
        <p>{fit.explanation}</p>
        {fit.factors?.length > 0 && (
          <div className="factor-list">
            {fit.factors.map((factor, index) => (
              <div className="factor-row" key={`${factor.signal}-${index}`}>
                <span><strong>{factor.signal}</strong><small>{factor.explanation}</small></span>
                <b className={factor.impact >= 0 ? 'positive' : 'negative'}>
                  {factor.impact > 0 ? '+' : ''}{factor.impact}
                </b>
              </div>
            ))}
          </div>
        )}
        {fit.flags?.map((flag) => <small className="fit-flag" key={flag}>{flag}</small>)}
      </div>
    </section>
  );
}

function AreaContext({ context }) {
  if (!context) return null;
  const rows = [
    ['Population density', context.population_density == null ? null : `${formatNumber(context.population_density)} / km²`],
    ['Median renter shelter cost', formatCad(context.median_renter_shelter_cost)],
    ['Rent-burdened tenant households', context.renter_cost_burden_percent == null ? null : `${context.renter_cost_burden_percent}%`],
    ['CMHC 2-bedroom context', context.rent_benchmark ? null : formatCad(context.regional_average_two_bedroom_rent)],
    ['Rental vacancy rate', context.rental_vacancy_rate == null ? null : `${context.rental_vacancy_rate}%`],
  ].filter(([, value]) => value != null);
  if (!rows.length) return null;
  return (
    <section className="context-card" id="evidence-card-census">
      <div>
        <p className="eyebrow">Area context</p>
        <h2>Numbers with a scope</h2>
        {context.rent_geographic_scope && <small>{context.rent_edition} · {context.rent_geographic_scope}</small>}
      </div>
      <dl>
        {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>
    </section>
  );
}

function formatCad(value) {
  if (value == null) return null;
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value) {
  return new Intl.NumberFormat('en-CA', { maximumFractionDigits: 0 }).format(value);
}

function labelize(value = 'Limited') {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function unitLabel(value) {
  return {
    studio: 'Studio',
    one_bedroom: '1 bedroom',
    two_bedroom: '2 bedrooms',
    three_bedroom_plus: '3+ bedrooms',
  }[value] || labelize(value);
}

function evidenceTarget(id) {
  return {
    access: 'evidence-card-access',
    census: 'evidence-card-census',
    local: 'evidence-card-census',
    rent: 'evidence-card-rent',
    transit: 'evidence-card-transit',
    cycling: 'evidence-card-cycling',
    collisions: 'evidence-card-collisions',
    building: 'evidence-card-building',
  }[id];
}

function dateWindow(start, end) {
  return `${formatEvidenceDate(start)}–${formatEvidenceDate(end)}`;
}

function formatEvidenceDate(value) {
  if (/^\d{4}$/.test(value)) return value;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('en-CA');
}
