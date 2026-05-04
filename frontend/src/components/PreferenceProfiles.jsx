import { useEffect, useMemo, useState } from 'react';
import { Plus, Star, Trash2, X } from 'lucide-react';
import {
  EMPTY_PROFILE_FORM,
  formToPreferenceProfilePayload,
  profileToForm,
} from '../utils/preferenceProfiles.js';

const CATEGORY_OPTIONS = [
  ['transit', 'Transit', 'T'],
  ['walkability', 'Walkability', 'W'],
  ['parks', 'Green spaces', 'G'],
  ['groceries', 'Retail access', 'R'],
  ['restaurants', 'Dining', 'D'],
  ['quiet', 'Quiet', 'Q'],
  ['social_scene', 'Nightlife', 'N'],
  ['lower_rent_pressure', 'Rent pressure', '$'],
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
    if (!open) return;
    if (isCreating) {
      setForm({ ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] });
      return;
    }
    if (editingProfile) {
      setForm(profileToForm(editingProfile));
      return;
    }
    if (selectedProfile) {
      setForm(profileToForm(selectedProfile));
      return;
    }
    setForm({ ...EMPTY_PROFILE_FORM, must_haves: [], deal_breakers: [] });
  }, [editingProfile, isCreating, open, selectedProfile]);

  if (!open) return null;

  const activeEditorProfile = editingProfile || selectedProfile;
  const isEditingExisting = Boolean(activeEditorProfile) && !isCreating;

  async function submitForm(event) {
    event.preventDefault();
    const payload = formToPreferenceProfilePayload(form, { mode: isEditingExisting ? 'update' : 'create' });
    if (isEditingExisting) {
      await onUpdate(activeEditorProfile.id, payload);
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
              <h1>{isEditingExisting ? 'Edit analysis lens' : 'Create analysis lens'}</h1>
              <p>Configure reusable preferences before choosing a neighborhood.</p>
            </div>
            <button type="button" className="top-icon-button" onClick={onClose} aria-label="Close profiles">
              <X size={18} aria-hidden="true" />
            </button>
          </div>

          {error && <p className="save-error">{error}</p>}

          <form className="preference-profile-form workspace-form" onSubmit={submitForm}>
            <ProfileFormFields form={form} setForm={setForm} toggleCategory={toggleCategory} />
            <div className="profile-form-actions">
              <button type="button" onClick={onClose}>Cancel</button>
              <button type="submit" className="primary-button" disabled={isSaving}>
                {isSaving ? 'Saving...' : isEditingExisting ? 'Save Profile' : 'Create Profile'}
              </button>
            </div>
          </form>
        </div>

        <aside className="profile-workspace-nav">
          <div>
            <p className="eyebrow">Neighborhood Analysis</p>
            <span>Active lens</span>
            <strong>{selectedProfile ? selectedProfile.name : 'Generic'}</strong>
          </div>
          <div className="profile-rail-list">
            <button
              type="button"
              className={`profile-rail-item ${selectedProfileId ? '' : 'is-active'}`}
              onClick={() => {
                setIsCreating(false);
                setEditingProfile(null);
                onSelect(null);
              }}
            >
              <strong>Generic</strong>
              <span>General check</span>
            </button>
            {profiles.map((profile) => (
              <button
                type="button"
                key={profile.id}
                className={`profile-rail-item ${profile.id === selectedProfileId ? 'is-active' : ''}`}
                onClick={() => {
                  setIsCreating(false);
                  setEditingProfile(profile);
                  onSelect(profile.id);
                }}
              >
                <strong>{profile.name}</strong>
                <span>{profile.is_default ? 'Default' : 'Saved profile'}</span>
              </button>
            ))}
          </div>
          <div className="profile-rail-actions">
            <button
              type="button"
              onClick={() => {
                setIsCreating(true);
                setEditingProfile(null);
                onSelect(null);
              }}
            >
              <Plus size={16} aria-hidden="true" />
              New
            </button>
            {selectedProfile && !selectedProfile.is_default && (
              <button type="button" onClick={() => onSetDefault(selectedProfile.id)}>
                <Star size={16} aria-hidden="true" />
                Default
              </button>
            )}
            {selectedProfile && (
              <button type="button" className="icon-danger" onClick={() => onDelete(selectedProfile.id)}>
                <Trash2 size={16} aria-hidden="true" />
                Delete
              </button>
            )}
          </div>
          <button type="button" className="primary-button" onClick={onClose}>Return to map</button>
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
      <div className="profile-form-section preference-select-grid">
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
      </div>
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
        <input
          type="range"
          min="0"
          max="6000"
          step="100"
          value={form.max_monthly_rent || 0}
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
      {CATEGORY_OPTIONS.map(([value, label, icon]) => (
        <label key={value}>
          <input type="checkbox" checked={values.includes(value)} onChange={() => onToggle(value)} />
          <span>{icon}</span>
          {label}
        </label>
      ))}
    </fieldset>
  );
}
