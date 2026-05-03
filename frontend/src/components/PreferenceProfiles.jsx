import { useEffect, useMemo, useState } from 'react';

const EMPTY_FORM = {
  name: '',
  car_reliance: '',
  energy_preference: '',
  top_priority: '',
  budget_sensitivity: '',
  generic_mode: false,
  commute_anchor_label: '',
  commute_anchor_lat: '',
  commute_anchor_lng: '',
  max_monthly_rent: '',
  must_haves: [],
  deal_breakers: [],
  notes: '',
};

const CATEGORY_OPTIONS = [
  ['transit', 'Transit'],
  ['walkability', 'Walkability'],
  ['parks', 'Parks'],
  ['groceries', 'Groceries'],
  ['restaurants', 'Restaurants'],
  ['quiet', 'Quiet'],
  ['social_scene', 'Social scene'],
  ['lower_rent_pressure', 'Lower rent pressure'],
];

export default function PreferenceProfiles({
  profiles = [],
  selectedProfileId,
  onSelect,
  onCreate,
  onUpdate,
  onDelete,
  onSetDefault,
  error,
  isSaving,
}) {
  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) || null,
    [profiles, selectedProfileId],
  );
  const [editingProfile, setEditingProfile] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  useEffect(() => {
    if (isCreating) {
      setForm(EMPTY_FORM);
    } else if (editingProfile) {
      setForm(profileToForm(editingProfile));
    }
  }, [editingProfile, isCreating]);

  const formOpen = isCreating || Boolean(editingProfile);

  async function submitForm(event) {
    event.preventDefault();
    const payload = formToPayload(form);
    if (editingProfile) {
      await onUpdate(editingProfile.id, payload);
    } else {
      await onCreate(payload);
    }
    setIsCreating(false);
    setEditingProfile(null);
    setForm(EMPTY_FORM);
  }

  function toggleCategory(field, value) {
    setForm((current) => {
      const values = current[field];
      return {
        ...current,
        [field]: values.includes(value)
          ? values.filter((item) => item !== value)
          : [...values, value],
      };
    });
  }

  return (
    <section className="preference-profiles">
      <div className="saved-profiles-header">
        <div>
          <p className="eyebrow">Preference profile</p>
          <h2>{selectedProfile ? selectedProfile.name : 'Generic'}</h2>
        </div>
        <button type="button" onClick={() => setIsCreating(true)}>
          New
        </button>
      </div>

      {profiles.length > 0 ? (
        <div className="profile-switcher-row">
          <select value={selectedProfileId || ''} onChange={(event) => onSelect(event.target.value || null)}>
            <option value="">Generic analysis</option>
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}{profile.is_default ? ' (default)' : ''}
              </option>
            ))}
          </select>
          {selectedProfile && (
            <button type="button" onClick={() => setEditingProfile(selectedProfile)}>
              Edit
            </button>
          )}
        </div>
      ) : (
        <p className="saved-empty">Create a reusable profile or keep using generic analysis.</p>
      )}

      {selectedProfile && (
        <div className="profile-chip-row">
          {!selectedProfile.is_default && (
            <button type="button" onClick={() => onSetDefault(selectedProfile.id)}>
              Make default
            </button>
          )}
          <button type="button" className="icon-danger" onClick={() => onDelete(selectedProfile.id)}>
            Delete
          </button>
        </div>
      )}

      {error && <p className="save-error">{error}</p>}

      {formOpen && (
        <form className="preference-profile-form" onSubmit={submitForm}>
          <label className="field">
            <span>Name</span>
            <input
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              required
              maxLength={80}
            />
          </label>
          <label className="generic-toggle">
            <input
              type="checkbox"
              checked={form.generic_mode}
              onChange={(event) => setForm({ ...form, generic_mode: event.target.checked })}
            />
            Run this profile as generic
          </label>
          <label className="field">
            <span>Commute anchor</span>
            <input
              value={form.commute_anchor_label}
              onChange={(event) => setForm({ ...form, commute_anchor_label: event.target.value })}
              placeholder="Work, school, or general area"
            />
          </label>
          <label className="field">
            <span>Max monthly rent</span>
            <input
              type="number"
              min="0"
              value={form.max_monthly_rent}
              onChange={(event) => setForm({ ...form, max_monthly_rent: event.target.value })}
            />
          </label>
          <CategoryChecklist
            title="Must haves"
            values={form.must_haves}
            onToggle={(value) => toggleCategory('must_haves', value)}
          />
          <CategoryChecklist
            title="Deal breakers"
            values={form.deal_breakers}
            onToggle={(value) => toggleCategory('deal_breakers', value)}
          />
          <label className="field">
            <span>Notes</span>
            <textarea
              value={form.notes}
              onChange={(event) => setForm({ ...form, notes: event.target.value })}
              maxLength={1000}
            />
          </label>
          <div className="profile-form-actions">
            <button type="submit" className="primary-button" disabled={isSaving}>
              {isSaving ? 'Saving...' : editingProfile ? 'Update profile' : 'Create profile'}
            </button>
            <button
              type="button"
              onClick={() => {
                setIsCreating(false);
                setEditingProfile(null);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function CategoryChecklist({ title, values, onToggle }) {
  return (
    <fieldset className="category-checklist">
      <legend>{title}</legend>
      {CATEGORY_OPTIONS.map(([value, label]) => (
        <label key={value}>
          <input type="checkbox" checked={values.includes(value)} onChange={() => onToggle(value)} />
          {label}
        </label>
      ))}
    </fieldset>
  );
}

function profileToForm(profile) {
  return {
    name: profile.name || '',
    car_reliance: profile.car_reliance || '',
    energy_preference: profile.energy_preference || '',
    top_priority: profile.top_priority || '',
    budget_sensitivity: profile.budget_sensitivity || '',
    generic_mode: Boolean(profile.generic_mode),
    commute_anchor_label: profile.commute_anchor?.label || '',
    commute_anchor_lat: profile.commute_anchor?.lat ?? '',
    commute_anchor_lng: profile.commute_anchor?.lng ?? '',
    max_monthly_rent: profile.max_monthly_rent ?? '',
    must_haves: profile.must_haves || [],
    deal_breakers: profile.deal_breakers || [],
    notes: profile.notes || '',
  };
}

function formToPayload(form) {
  const payload = {
    name: form.name.trim(),
    generic_mode: form.generic_mode,
    must_haves: form.must_haves,
    deal_breakers: form.deal_breakers,
  };
  if (form.commute_anchor_label.trim()) {
    payload.commute_anchor = { label: form.commute_anchor_label.trim() };
  }
  if (form.max_monthly_rent !== '') {
    payload.max_monthly_rent = Number(form.max_monthly_rent);
  }
  payload.notes = form.notes.trim();
  return payload;
}
