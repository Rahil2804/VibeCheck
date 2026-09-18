import { useEffect, useMemo, useState } from 'react';
import { Plus, Star, Trash2, X } from 'lucide-react';
import {
  EMPTY_PROFILE_FORM,
  formToPreferenceProfilePayload,
  profileToForm,
} from '../utils/preferenceProfiles.js';
import { useDialogFocus } from '../hooks/useDialogFocus.js';

const CATEGORY_OPTIONS = [
  ['transit', 'Transit', 'T'],
  ['walkability', 'Walkability', 'W'],
  ['parks', 'Green spaces', 'G'],
  ['groceries', 'Groceries', 'R'],
  ['restaurants', 'Dining', 'D'],
  ['quiet', 'Quiet', 'Q'],
  ['social_scene', 'Nightlife', 'N'],
  ['lower_rent_pressure', 'Rent pressure', '$'],
  ['cycling', 'Cycling access', 'C'],
];

const SELECT_OPTIONS = {
  car_reliance: [
    ['no_car', 'No car'],
    ['sometimes_car', 'Sometimes use a car'],
    ['drive_daily', 'Drive daily (stored, not scored)'],
  ],
  energy_preference: [
    ['quiet', 'Quiet and calm (stored, not scored)'],
    ['balanced', 'Balanced'],
    ['lively', 'Lively and social'],
  ],
  top_priority: [
    ['walkability_errands', 'Walkability and errands'],
    ['transit_access', 'Transit access'],
    ['parks_outdoors', 'Parks and outdoors'],
    ['restaurants_nightlife', 'Restaurants and nightlife'],
    ['lower_rent_pressure', 'Lower rent pressure'],
    ['cycling_access', 'Cycling access'],
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
  const dialogRef = useDialogFocus(open, onClose);

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
      const otherField = field === 'must_haves' ? 'deal_breakers' : 'must_haves';
      return {
        ...current,
        [field]: values.includes(value)
          ? values.filter((item) => item !== value)
          : [...values, value],
        [otherField]: current[otherField].filter((item) => item !== value),
      };
    });
  }

  function confirmDelete(profile) {
    if (window.confirm(`Delete the “${profile.name}” lens?`)) onDelete(profile.id);
  }

  return (
    <section className="workspace-backdrop" role="dialog" aria-modal="true" aria-labelledby="profiles-title">
      <div className="profile-workspace" ref={dialogRef}>
        <div className="profile-workspace-main">
          <div className="workspace-title-row">
            <div>
              <p className="eyebrow">Lifestyle Profile</p>
              <h1 id="profiles-title">{isEditingExisting ? 'Edit analysis lens' : 'Create analysis lens'}</h1>
              <p>Only preferences backed by available evidence affect the fit score.</p>
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
              <button type="button" className="icon-danger" onClick={() => confirmDelete(selectedProfile)}>
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
        <span>Maximum monthly rent <small>CAD</small></span>
        <div className="money-input"><span>C$</span><input type="number" min="0" step="50" value={form.max_monthly_rent} onChange={(event) => setForm({ ...form, max_monthly_rent: event.target.value })} /></div>
      </label>
      <label className="field">
        <span>Rental unit size <small>Required for rent fit</small></span>
        <select value={form.rental_unit_size} onChange={(event) => setForm({ ...form, rental_unit_size: event.target.value })}>
          <option value="">No unit selected</option>
          <option value="studio">Studio</option>
          <option value="one_bedroom">1 bedroom</option>
          <option value="two_bedroom">2 bedrooms</option>
          <option value="three_bedroom_plus">3+ bedrooms</option>
        </select>
      </label>
      <p className="field-help">Driving and quiet preferences are kept in this local lens but remain unscored until defensible evidence exists.</p>
      <CategoryChecklist
        title="Important signals"
        description="Adds up to 6 points when source evidence is strong."
        values={form.must_haves}
        onToggle={(value) => toggleCategory('must_haves', value)}
      />
      <CategoryChecklist
        title="Non-negotiables"
        description="A positive requirement; missing evidence is skipped, weak evidence is strongly penalized."
        values={form.deal_breakers}
        onToggle={(value) => toggleCategory('deal_breakers', value)}
      />
      <label className="field notes-field">
        <span>Private notes <small>Stored locally · never scored or sent to AI</small></span>
        <textarea
          value={form.notes}
          onChange={(event) => setForm({ ...form, notes: event.target.value })}
          maxLength={1000}
        />
      </label>
    </>
  );
}

function CategoryChecklist({ title, description, values, onToggle }) {
  return (
    <fieldset className="category-checklist">
      <legend>{title}<small>{description}</small></legend>
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
