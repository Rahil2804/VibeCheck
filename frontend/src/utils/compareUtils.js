import { buildAnalyzePayload } from './preferenceProfiles.js';

export const MIN_COMPARE_SLOTS = 2;
export const MAX_COMPARE_SLOTS = 4;

const CONFIDENCE_RISK = {
  high: 0,
  medium: 1,
  low: 2,
  none: 3,
};

export function createCompareSlot(id) {
  return {
    id,
    place: null,
    status: 'idle',
    response: null,
    error: '',
  };
}

export function canAddCompareSlot(slots) {
  return slots.length < MAX_COMPARE_SLOTS;
}

export function canAnalyzeCompare(slots) {
  return slots.filter((slot) => Boolean(slot.place)).length >= MIN_COMPARE_SLOTS;
}

export function buildComparePayload(place, activeProfile) {
  return buildAnalyzePayload(place, activeProfile);
}

export function getSuccessfulCompareResults(slots) {
  return slots.filter((slot) => slot.status === 'success' && slot.response);
}

export function buildCompareHighlights(slots) {
  const successful = getSuccessfulCompareResults(slots);
  if (successful.length < MIN_COMPARE_SLOTS) return [];

  const highlights = [];
  const bestFit = bestBy(successful, (slot) => slot.response.fit?.score);
  if (bestFit) {
    highlights.push({
      id: 'best-fit',
      label: 'Best fit',
      placeLabel: bestFit.response.place.label,
      value: `${bestFit.response.fit.score}%`,
    });
  }

  const bestWalkability = bestBy(successful, (slot) => slot.response.profile?.vibe_scores?.walkability);
  if (bestWalkability) {
    highlights.push({
      id: 'best-walkability',
      label: 'Best walkability',
      placeLabel: bestWalkability.response.place.label,
      value: String(bestWalkability.response.profile.vibe_scores.walkability),
    });
  }

  const bestTransit = bestBy(successful, (slot) => slot.response.profile?.vibe_scores?.transit_access);
  if (bestTransit) {
    highlights.push({
      id: 'best-transit',
      label: 'Best transit',
      placeLabel: bestTransit.response.place.label,
      value: String(bestTransit.response.profile.vibe_scores.transit_access),
    });
  }

  const lowestRisk = [...successful].sort(compareConfidenceRisk)[0];
  if (lowestRisk) {
    highlights.push({
      id: 'lowest-confidence-risk',
      label: 'Lowest data risk',
      placeLabel: lowestRisk.response.place.label,
      value: `${lowestRisk.response.confidence?.level || 'unknown'} confidence`,
    });
  }

  return highlights;
}

function bestBy(slots, getValue) {
  return slots.reduce((best, slot) => {
    const value = getValue(slot);
    if (!Number.isFinite(value)) return best;
    if (!best) return slot;
    return value > getValue(best) ? slot : best;
  }, null);
}

function compareConfidenceRisk(left, right) {
  const leftLevel = left.response.confidence?.level || 'none';
  const rightLevel = right.response.confidence?.level || 'none';
  const levelDifference = (CONFIDENCE_RISK[leftLevel] ?? 3) - (CONFIDENCE_RISK[rightLevel] ?? 3);
  if (levelDifference !== 0) return levelDifference;
  return missingSourceCount(left) - missingSourceCount(right);
}

function missingSourceCount(slot) {
  return slot.response.confidence?.missing_sources?.length || 0;
}
