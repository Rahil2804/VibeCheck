import { useMemo, useState } from 'react';
import { analyzeNeighborhood } from '../utils/api.js';
import {
  MAX_COMPARE_SLOTS,
  MIN_COMPARE_SLOTS,
  buildComparePayload,
  canAddCompareSlot,
  canAnalyzeCompare,
  createCompareSlot,
} from '../utils/compareUtils.js';
import ComparePlaceSearch from './ComparePlaceSearch.jsx';
import CompareResultCard from './CompareResultCard.jsx';
import CompareSummary from './CompareSummary.jsx';

const INITIAL_SLOTS = [createCompareSlot('compare-1'), createCompareSlot('compare-2')];

export default function CompareMode({ activeProfile, onClose }) {
  const [slots, setSlots] = useState(INITIAL_SLOTS);
  const [nextSlotNumber, setNextSlotNumber] = useState(3);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);
  const selectedCount = slots.filter((slot) => slot.place).length;
  const isAnalyzing = slots.some((slot) => slot.status === 'loading');
  const ready = canAnalyzeCompare(slots) && !isAnalyzing;
  const lensLabel = activeProfile?.name || 'Generic neighborhood check';
  const successfulCount = slots.filter((slot) => slot.status === 'success').length;

  const helperText = useMemo(() => {
    if (selectedCount < MIN_COMPARE_SLOTS) return 'Add at least two places to compare.';
    if (isAnalyzing) return 'Checking each selected place independently.';
    if (hasAnalyzed && successfulCount < MIN_COMPARE_SLOTS) return 'At least two successful results are needed for highlights.';
    return 'Compare these places through the active lens.';
  }, [hasAnalyzed, isAnalyzing, selectedCount, successfulCount]);

  function updateSlot(slotId, patch) {
    setSlots((current) => current.map((slot) => (slot.id === slotId ? { ...slot, ...patch } : slot)));
  }

  function handleSelectPlace(slotId, place) {
    updateSlot(slotId, {
      place,
      status: 'idle',
      response: null,
      error: '',
    });
  }

  function handleAddSlot() {
    if (!canAddCompareSlot(slots)) return;
    setSlots((current) => [...current, createCompareSlot(`compare-${nextSlotNumber}`)]);
    setNextSlotNumber((current) => current + 1);
  }

  function handleRemoveSlot(slotId) {
    setSlots((current) => current.filter((slot) => slot.id !== slotId));
  }

  async function analyzeSlot(slot) {
    if (!slot.place) return null;
    updateSlot(slot.id, { status: 'loading', response: null, error: '' });
    try {
      const response = await analyzeNeighborhood(buildComparePayload(slot.place, activeProfile));
      updateSlot(slot.id, { status: 'success', response, error: '' });
      return response;
    } catch (err) {
      updateSlot(slot.id, {
        status: 'error',
        response: null,
        error: err instanceof Error ? err.message : 'Analyze failed',
      });
      return null;
    }
  }

  async function handleAnalyzeAll() {
    if (!ready) return;
    setHasAnalyzed(true);
    const selectedSlots = slots.filter((slot) => slot.place);
    await Promise.all(selectedSlots.map((slot) => analyzeSlot(slot)));
  }

  async function handleRetry(slotId) {
    const slot = slots.find((item) => item.id === slotId);
    if (slot) await analyzeSlot(slot);
  }

  return (
    <section className="compare-workspace" aria-label="Compare places">
      <header className="compare-header">
        <div>
          <p className="eyebrow">Compare mode</p>
          <h1>Compare places</h1>
          <p>{helperText}</p>
        </div>
        <div className="compare-header-actions">
          <span>{lensLabel}</span>
          <span>{selectedCount} of {MAX_COMPARE_SLOTS} places</span>
          <button type="button" className="primary-button" disabled={!ready} onClick={handleAnalyzeAll}>
            {hasAnalyzed ? 'Refresh Compare' : 'Analyze Compare'}
          </button>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </header>

      <div className="compare-place-slots">
        {slots.map((slot) => (
          <ComparePlaceSearch
            key={slot.id}
            slot={slot}
            canRemove={slots.length > MIN_COMPARE_SLOTS}
            onRemove={handleRemoveSlot}
            onSelect={(place) => handleSelectPlace(slot.id, place)}
          />
        ))}
        {canAddCompareSlot(slots) && (
          <button type="button" className="compare-add-slot" onClick={handleAddSlot}>
            Add place
          </button>
        )}
      </div>

      <CompareSummary slots={slots} />

      <div className="compare-results-grid">
        {slots.map((slot) => (
          <CompareResultCard key={slot.id} slot={slot} onRetry={handleRetry} />
        ))}
      </div>
    </section>
  );
}
