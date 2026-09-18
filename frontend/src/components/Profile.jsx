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
      <div id="evidence-card-access"><ScoreCards scores={profile.vibe_scores} /></div>
      <EvidenceCards profile={profile} />
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

function EvidenceCards({ profile }) {
  const transit = profile.transit_context;
  const cycling = profile.cycling_context;
  const rent = profile.who_lives_here?.rent_benchmark;
  if (!transit && !cycling && !rent) return null;
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
          <p className="eyebrow">Cycling access</p>
          <h2>{cycling.protected_network_km} km protected nearby</h2>
          <p>{cycling.total_network_km} km total network within 1 km · {cycling.bike_share_stations} Bike Share stations within 800 m.</p>
          <small>{cycling.scope} · station locations only, not live availability</small>
        </article>
      )}
      {rent && (
        <article className="evidence-card" id="evidence-card-rent">
          <p className="eyebrow">Purpose-built rent</p>
          <h2>{rent.suppressed || rent.monthly_rent == null ? 'Suppressed' : formatCad(rent.monthly_rent)}</h2>
          <p>{unitLabel(rent.unit_size)} · {rent.geography}</p>
          <small>{rent.edition} · quality {rent.quality_code || 'not supplied'} · {rent.market_scope}</small>
        </article>
      )}
    </section>
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
  }[id];
}

function formatEvidenceDate(value) {
  if (/^\d{4}$/.test(value)) return value;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('en-CA');
}
