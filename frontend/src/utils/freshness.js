export const STALE_AFTER_DAYS = 7;

export function freshnessState(timestamp, { now = new Date() } = {}) {
  const generated = parseTimestamp(timestamp);
  if (!generated) return 'unknown';
  return daysBetween(generated, now) >= STALE_AFTER_DAYS ? 'stale' : 'fresh';
}

export function formatGeneratedLabel(timestamp, { now = new Date() } = {}) {
  const generated = parseTimestamp(timestamp);
  if (!generated) return 'Generated time unknown';

  const days = daysBetween(generated, now);
  if (days >= STALE_AFTER_DAYS) return `Stale: generated ${days} days ago`;
  if (days === 0) {
    const minutes = Math.floor((now.getTime() - generated.getTime()) / 60000);
    return minutes < 5 ? 'Generated just now' : 'Generated today';
  }
  return `Generated ${days} ${days === 1 ? 'day' : 'days'} ago`;
}

function parseTimestamp(timestamp) {
  if (!timestamp) return null;
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? null : date;
}

function daysBetween(start, end) {
  return Math.max(0, Math.floor((end.getTime() - start.getTime()) / 86400000));
}
