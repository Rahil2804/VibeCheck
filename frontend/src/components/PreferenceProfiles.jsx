import { useEffect, useMemo, useState } from 'react';
import { Check, Plus, Star, Trash2, X } from 'lucide-react';
import {
  EMPTY_PROFILE_FORM,
  formToPreferenceProfilePayload,
  profileToForm,
} from '../utils/preferenceProfiles.js';

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

const SELECT_OPTIONS = {
  car_reliance: [
    ['no_car', 'No car'],
    ['sometimes_car', 'Sometimes use a car'],
    ['drive_daily', 'Drive daily'],
  ],
  energy_preference: [
    ['quiet', 'Quiet and calm'],
    ['balanced', 'Balanced'],
    ['lively', 'Lively and social'],
  ],
  top_priority: [
    ['walkability_errands', 'Walkability and errands'],
    ['transit_access', 'Transit access'],
    ['parks_outdoors', 'Parks and outdoors'],
    ['restaurants_nightlife', 'Restaurants and nightlife'],
    ['lower_rent_pressure', 'Lower rent pressure'],
  ],
  budget_sensitivity: [
    ['very_budget_conscious', 'Very budget conscious'],
    ['moderate', 'Moderate'],
    ['flexible', 'Flexible'],
  ],
};

export default function PreferenceProfiles({
  open,
  profiles = [],
  selectedProfileId,
  onClose,
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
  const [form, setForm] = useState(EMPTY_PROFILE_FORM);

  useEffect(() => {
    if (isCreating) {
      setForm({ ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] });
    } else if (editingProfile) {
      setForm(profileToForm(editingProfile));
    }
  }, [editingProfile, isCreating]);

  if (!open) return null;

  const formOpen = isCreating || Boolean(editingProfile);

  async function submitForm(event) {
    event.preventDefault();
    const payload = formToPreferenceProfilePayload(form, { mode: editingProfile ? 'update' : 'create' });
    if (editingProfile) {
      await onUpdate(editingProfile.id, payload);
    } else {
      await onCreate(payload);
    }
    setIsCreating(false);
    setEditingProfile(null);
    setForm({ ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] });
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
    <section className="workspace-backdrop" aria-label="Lifestyle profile workspace">
      <div className="profile-workspace">
        <div className="profile-workspace-main">
          <div className="workspace-title-row">
            <div>
              <p className="eyebrow">Lifestyle Profile</p>
              <h1>Configure your analysis lens</h1>
              <p>Set reusable preferences before choosing a neighborhood.</p>
            </div>
            <button type="button" className="top-icon-button" onClick={onClose} aria-label="Close profiles">
              <X size={18} aria-hidden="true" />
            </button>
          </div>

          <div className="profile-selection-grid">
            <button
              type="button"
              className={`profile-choice-card ${selectedProfileId ? '' : 'is-active'}`}
              onClick={() => onSelect(null)}
            >
              <strong>Generic</strong>
              <span>Run a general neighborhood check without personal fit scoring.</span>
              {!selectedProfileId && <Check size={18} aria-hidden="true" />}
            </button>
            {profiles.map((profile) => (
              <button
                type="button"
                key={profile.id}
                className={`profile-choice-card ${profile.id === selectedProfileId ? 'is-active' : ''}`}
                onClick={() => onSelect(profile.id)}
              >
                <strong>{profile.name}</strong>
                <span>{profile.is_default ? 'Default profile' : 'Saved lifestyle profile'}</span>
                {profile.id === selectedProfileId && <Check size={18} aria-hidden="true" />}
              </button>
            ))}
          </div>

          <div className="profile-workspace-actions">
            <button type="button" className="primary-button" onClick={() => setIsCreating(true)}>
              <Plus size={16} aria-hidden="true" />
              New profile
            </button>
            {selectedProfile && (
              <>
                <button type="button" onClick={() => setEditingProfile(selectedProfile)}>
                  Edit selected
                </button>
                {!selectedProfile.is_default && (
                  <button type="button" onClick={() => onSetDefault(selectedProfile.id)}>
                    <Star size={16} aria-hidden="true" />
                    Make default
                  </button>
                )}
                <button type="button" className="icon-danger" onClick={() => onDelete(selectedProfile.id)}>
                  <Trash2 size={16} aria-hidden="true" />
                  Delete
                </button>
              </>
            )}
          </div>

          {error && <p className="save-error">{error}</p>}

          {formOpen && (
            <form className="preference-profile-form workspace-form" onSubmit={submitForm}>
              <ProfileFormFields form={form} setForm={setForm} toggleCategory={toggleCategory} />
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
        </div>

        <aside className="profile-workspace-nav">
          <p className="eyebrow">Neighborhood Analysis</p>
          <span>Preference Profile</span>
          <strong>{selectedProfile ? selectedProfile.name : 'Generic'}</strong>
          <button type="button" onClick={onClose}>Return to map</button>
        </aside>
      </div>
    </section>
  );
}

function ProfileFormFields({ form, setForm, toggleCategory }) {
  return (
    <>
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
        Run this saved profile as generic
      </label>
      {Object.entries(SELECT_OPTIONS).map(([field, options]) => (
        <label className="field" key={field}>
          <span>{field.replaceAll('_', ' ')}</span>
          <select value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })}>
            <option value="">No preference</option>
            {options.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      ))}
      <label className="field">
        <span>Commute anchor</span>
        <input
          value={form.commute_anchor_label}
          onChange={(event) => setForm({ ...form, commute_anchor_label: event.target.value })}
          placeholder="Work, school, or general area"
        />
      </label>
      <div className="coordinate-grid">
        <label className="field">
          <span>Anchor latitude</span>
          <input
            type="number"
            step="any"
            value={form.commute_anchor_lat}
            onChange={(event) => setForm({ ...form, commute_anchor_lat: event.target.value })}
          />
        </label>
        <label className="field">
          <span>Anchor longitude</span>
          <input
            type="number"
            step="any"
            value={form.commute_anchor_lng}
            onChange={(event) => setForm({ ...form, commute_anchor_lng: event.target.value })}
          />
        </label>
      </div>
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
      <label className="field notes-field">
        <span>Notes</span>
        <textarea
          value={form.notes}
          onChange={(event) => setForm({ ...form, notes: event.target.value })}
          maxLength={1000}
        />
      </label>
    </>
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
