const OPTIONS = {
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

export default function Questionnaire({
  preferences,
  genericMode,
  onChange,
  onGenericModeChange,
  onAnalyze,
  disabled,
}) {
  function update(field, value) {
    onChange({ ...preferences, [field]: value });
  }

  return (
    <section className="panel-section">
      <div className="section-heading">
        <p className="eyebrow">Preferences</p>
        <h2>Lifestyle fit</h2>
      </div>
      <label className="generic-toggle">
        <input
          type="checkbox"
          checked={genericMode}
          onChange={(event) => onGenericModeChange(event.target.checked)}
        />
        Skip preferences and run a generic profile
      </label>
      {!genericMode &&
        Object.entries(OPTIONS).map(([field, options]) => (
          <label className="field" key={field}>
            <span>{field.replaceAll('_', ' ')}</span>
            <select value={preferences[field] || ''} onChange={(event) => update(field, event.target.value)}>
              <option value="">No preference</option>
              {options.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        ))}
      <button className="primary-button" type="button" disabled={disabled} onClick={onAnalyze}>
        Analyze fit
      </button>
    </section>
  );
}
