from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class CarReliance(StrEnum):
    NO_CAR = "no_car"
    SOMETIMES_CAR = "sometimes_car"
    DRIVE_DAILY = "drive_daily"


class EnergyPreference(StrEnum):
    QUIET = "quiet"
    BALANCED = "balanced"
    LIVELY = "lively"


class TopPriority(StrEnum):
    WALKABILITY_ERRANDS = "walkability_errands"
    TRANSIT_ACCESS = "transit_access"
    PARKS_OUTDOORS = "parks_outdoors"
    RESTAURANTS_NIGHTLIFE = "restaurants_nightlife"
    LOWER_RENT_PRESSURE = "lower_rent_pressure"
    CYCLING_ACCESS = "cycling_access"


class BudgetSensitivity(StrEnum):
    VERY_BUDGET_CONSCIOUS = "very_budget_conscious"
    MODERATE = "moderate"
    FLEXIBLE = "flexible"


class PreferenceCategory(StrEnum):
    TRANSIT = "transit"
    WALKABILITY = "walkability"
    PARKS = "parks"
    GROCERIES = "groceries"
    RESTAURANTS = "restaurants"
    QUIET = "quiet"
    SOCIAL_SCENE = "social_scene"
    LOWER_RENT_PRESSURE = "lower_rent_pressure"
    CYCLING = "cycling"


class RentalUnitSize(StrEnum):
    STUDIO = "studio"
    ONE_BEDROOM = "one_bedroom"
    TWO_BEDROOM = "two_bedroom"
    THREE_BEDROOM_PLUS = "three_bedroom_plus"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class AnalysisLensMode(StrEnum):
    GENERIC = "generic"
    SAVED_PROFILE = "saved_profile"
    CUSTOM = "custom"
    LEGACY = "legacy"


class CoverageRegion(StrEnum):
    TORONTO = "toronto"
    GTA = "gta"
    OUTSIDE_GTA = "outside_gta"


class CoverageLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    LIMITED = "limited"


class SourceName(StrEnum):
    MAPBOX = "mapbox"
    CENSUS = "census"
    HOUSING = "housing"
    REDDIT = "reddit"
    ACCESS = "access"
    LOCAL = "local"
    TRANSIT = "transit"
    CYCLING = "cycling"
    COLLISIONS = "collisions"
    BUILDING = "building"


class SourceStatusCode(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    ERROR = "error"


class ProvenanceSupport(StrEnum):
    DIRECT = "direct"
    INFERRED = "inferred"
    UNAVAILABLE = "unavailable"


class SynthesisStatusCode(StrEnum):
    USED = "used"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FALLBACK = "fallback"


class EvidenceCheckStatus(StrEnum):
    SUPPORTED = "supported"
    FALLBACK = "fallback"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class CyclingEvidenceMethod(StrEnum):
    TORONTO_OFFICIAL = "toronto_official"
    OSM_FALLBACK = "osm_fallback"


class TrajectoryDirection(StrEnum):
    RISING = "rising"
    STABLE = "stable"
    FALLING = "falling"
    UNCERTAIN = "uncertain"


class Coordinates(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Preferences(BaseModel):
    car_reliance: CarReliance | None = None
    energy_preference: EnergyPreference | None = None
    top_priority: TopPriority | None = None
    budget_sensitivity: BudgetSensitivity | None = None
    max_monthly_rent: int | None = Field(default=None, ge=0)
    rental_unit_size: RentalUnitSize | None = None
    must_haves: list[PreferenceCategory] = Field(default_factory=list)
    deal_breakers: list[PreferenceCategory] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_disjoint_signal_lists(self) -> Self:
        overlap = set(self.must_haves) & set(self.deal_breakers)
        if overlap:
            labels = ", ".join(sorted(item.value for item in overlap))
            raise ValueError(
                "Important signals and non-negotiables must be disjoint: " + labels
            )
        return self


class CommuteAnchor(BaseModel):
    label: str = Field(min_length=1)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def require_both_coordinates(self) -> Self:
        if (self.lat is None) != (self.lng is None):
            raise ValueError(
                "Provide both commute anchor latitude and longitude, or neither."
            )
        return self


class PreferenceProfileBase(Preferences):
    generic_mode: bool = False
    commute_anchor: CommuteAnchor | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @property
    def preferences(self) -> Preferences:
        return Preferences(
            car_reliance=self.car_reliance,
            energy_preference=self.energy_preference,
            top_priority=self.top_priority,
            budget_sensitivity=self.budget_sensitivity,
            max_monthly_rent=self.max_monthly_rent,
            rental_unit_size=self.rental_unit_size,
            must_haves=self.must_haves,
            deal_breakers=self.deal_breakers,
        )


class PreferenceProfileCreate(PreferenceProfileBase):
    name: str = Field(min_length=1, max_length=80)


class PreferenceProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    car_reliance: CarReliance | None = None
    energy_preference: EnergyPreference | None = None
    top_priority: TopPriority | None = None
    budget_sensitivity: BudgetSensitivity | None = None
    generic_mode: bool | None = None
    commute_anchor: CommuteAnchor | None = None
    max_monthly_rent: int | None = Field(default=None, ge=0)
    rental_unit_size: RentalUnitSize | None = None
    must_haves: list[PreferenceCategory] | None = None
    deal_breakers: list[PreferenceCategory] | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @property
    def preferences(self) -> Preferences:
        return Preferences(
            car_reliance=self.car_reliance,
            energy_preference=self.energy_preference,
            top_priority=self.top_priority,
            budget_sensitivity=self.budget_sensitivity,
            max_monthly_rent=self.max_monthly_rent,
            rental_unit_size=self.rental_unit_size,
            must_haves=self.must_haves or [],
            deal_breakers=self.deal_breakers or [],
        )


class PreferenceProfile(PreferenceProfileCreate):
    id: str
    is_default: bool = False
    created_at: str
    updated_at: str


class DeletePreferenceProfileResponse(BaseModel):
    deleted: bool


class AnalyzeRequest(BaseModel):
    query: str | None = Field(default=None, min_length=1)
    coordinates: Coordinates | None = None
    preferences: Preferences = Field(default_factory=Preferences)
    generic_mode: bool = False
    preference_profile_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_query_or_coordinates(self) -> "AnalyzeRequest":
        if self.query is None and self.coordinates is None:
            raise ValueError("Provide either query or coordinates.")
        return self


class AnalysisLensSnapshot(BaseModel):
    mode: AnalysisLensMode
    profile_id: str | None = None
    profile_name: str
    preferences: Preferences = Field(default_factory=Preferences)


class CoverageSummary(BaseModel):
    region: CoverageRegion
    level: CoverageLevel
    supported_signals: list[str] = Field(default_factory=list)
    unavailable_signals: list[str] = Field(default_factory=list)
    message: str


class SourceStatus(BaseModel):
    source: SourceName
    status: SourceStatusCode
    message: str
    updated_at: str | None = None
    edition: str | None = None
    scope: str | None = None
    source_url: str | None = None
    stale: bool | None = None
    fallback: bool = False


class ProvenanceItem(BaseModel):
    claim_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    support: ProvenanceSupport
    sources: list[SourceName] = Field(default_factory=list)
    source_fields: list[str] = Field(default_factory=list)


class ProfileProvenance(BaseModel):
    items: list[ProvenanceItem] = Field(default_factory=list)


class SynthesisStatus(BaseModel):
    status: SynthesisStatusCode
    model: str | None = None
    message: str
    reason_code: str | None = None
    prompt_version: str | None = None
    evidence_count: int | None = Field(default=None, ge=0)
    accepted_claim_count: int | None = Field(default=None, ge=0)
    rejected_claim_count: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)


class Place(BaseModel):
    label: str
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    coordinates: Coordinates | None = None


class GeographyContext(BaseModel):
    country: str | None = None
    province: str | None = None
    census_subdivision_id: str | None = None
    census_subdivision_name: str | None = None
    toronto_neighbourhood_id: str | None = None
    toronto_neighbourhood_name: str | None = None
    is_toronto: bool = False
    is_gta: bool = False
    resolution: str = "unresolved"


class EvidenceCheck(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    status: EvidenceCheckStatus
    summary: str = Field(min_length=1)
    source: SourceName | None = None
    source_fields: list[str] = Field(default_factory=list)
    scope: str | None = None
    edition: str | None = None
    updated_at: str | None = None


class NarrativeCitation(BaseModel):
    section: str = Field(pattern="^(overview|pro|con)$")
    item_index: int | None = Field(default=None, ge=0)
    evidence_check_ids: list[str] = Field(default_factory=list)


class VibeScores(BaseModel):
    walkability: int | None = Field(default=None, ge=0, le=100)
    transit_access: int | None = Field(default=None, ge=0, le=100)
    affordability: int | None = Field(default=None, ge=0, le=100)
    quiet: int | None = Field(default=None, ge=0, le=100)
    social_scene: int | None = Field(default=None, ge=0, le=100)
    parks_outdoors: int | None = Field(default=None, ge=0, le=100)
    daily_needs: int | None = Field(default=None, ge=0, le=100)
    dining_activity: int | None = Field(default=None, ge=0, le=100)
    cycling_access: int | None = Field(default=None, ge=0, le=100)


class TransitContext(BaseModel):
    scheduled_departures_per_hour: float | None = Field(default=None, ge=0)
    nearby_route_count: int = Field(ge=0)
    nearby_stop_count: int | None = Field(default=None, ge=0)
    nearby_routes: list[str] = Field(default_factory=list)
    agencies: list[str] = Field(default_factory=list)
    nearest_stop_distance_m: int | None = Field(default=None, ge=0)
    rapid_or_regional_access: bool = False
    service_date: str | None = None
    scope: str
    edition: str
    fallback: bool = False


class CyclingContext(BaseModel):
    protected_network_km: float = Field(ge=0)
    total_network_km: float = Field(ge=0)
    bike_share_stations: int | None = Field(default=None, ge=0)
    bicycle_parking_locations: int | None = Field(default=None, ge=0)
    network_radius_m: int = Field(default=1_000, ge=1)
    scope: str
    edition: str
    method: CyclingEvidenceMethod = CyclingEvidenceMethod.TORONTO_OFFICIAL
    fallback: bool = False
    updated_at: str | None = None
    source_url: str | None = None


class RentBenchmark(BaseModel):
    monthly_rent: int | None = Field(default=None, ge=0)
    unit_size: RentalUnitSize
    geography: str
    geography_id: str | None = None
    market_scope: str = "Purpose-built rental apartments"
    vacancy_rate: float | None = Field(default=None, ge=0)
    quality_code: str | None = None
    vacancy_quality_code: str | None = None
    suppressed: bool = False
    edition: str
    reference_year: int
    currency: str = "CAD"
    source_url: str | None = None


class CollisionMapPoint(BaseModel):
    collision_id: str
    occurred_at: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    fatal: bool = False
    pedestrian_involved: bool = False
    cyclist_involved: bool = False
    other_road_user_involved: bool = False


class CollisionContext(BaseModel):
    radius_m: int = Field(default=1000, gt=0)
    baseline_period_start: str
    baseline_period_end: str
    total_collisions: int = Field(ge=0)
    injury_collisions: int = Field(ge=0)
    fatal_collisions: int = Field(ge=0)
    pedestrian_involved_collisions: int = Field(ge=0)
    cyclist_involved_collisions: int = Field(ge=0)
    ksi_period_start: str
    ksi_period_end: str
    ksi_collisions: int = Field(ge=0)
    ksi_fatal_collisions: int = Field(ge=0)
    ksi_pedestrian_involved_collisions: int = Field(ge=0)
    ksi_cyclist_involved_collisions: int = Field(ge=0)
    severe_events: list[CollisionMapPoint] = Field(default_factory=list)
    scope: str = "City of Toronto"
    edition: str
    stale: bool = False
    baseline_source_url: str | None = None
    ksi_source_url: str | None = None


class BuildingContext(BaseModel):
    rsn: str
    site_address: str
    property_type: str | None = None
    year_built: int | None = Field(default=None, ge=0)
    storeys: int | None = Field(default=None, ge=0)
    units: int | None = Field(default=None, ge=0)
    evaluation_date: str | None = None
    current_score: float | None = Field(default=None, ge=0, le=100)
    proactive_score: float | None = Field(default=None, ge=0, le=100)
    reactive_deduction: float | None = Field(default=None, ge=0)
    rating: str | None = Field(default=None, pattern="^(green|yellow|red)$")
    areas_evaluated: int | None = Field(default=None, ge=0)
    low_rated_categories: list[str] = Field(default_factory=list)
    scope: str = "RentSafeTO registered apartment buildings"
    edition: str
    stale: bool = False
    registration_source_url: str | None = None
    evaluation_source_url: str | None = None


class WhoLivesHere(BaseModel):
    median_age: float | None = None
    median_household_income: int | None = None
    population_density: float | None = None
    population_trend: str | None = None
    median_renter_shelter_cost: int | None = None
    renter_cost_burden_percent: float | None = None
    regional_average_two_bedroom_rent: int | None = None
    rental_vacancy_rate: float | None = None
    rent_geographic_scope: str | None = None
    rent_edition: str | None = None
    context_year: int | None = None
    rent_benchmark: RentBenchmark | None = None


class Trajectory(BaseModel):
    direction: TrajectoryDirection
    summary: str


class NeighborhoodProfile(BaseModel):
    overview: str
    vibe_scores: VibeScores
    who_lives_here: WhoLivesHere
    honest_pros: list[str]
    honest_cons: list[str]
    trajectory: Trajectory | None = None
    provenance: ProfileProvenance = Field(default_factory=ProfileProvenance)
    transit_context: TransitContext | None = None
    cycling_context: CyclingContext | None = None
    collision_context: CollisionContext | None = None
    building_context: BuildingContext | None = None
    narrative_citations: list[NarrativeCitation] = Field(default_factory=list)


class FitFactor(BaseModel):
    signal: str
    value: int | float | str | None = None
    impact: int = Field(ge=-15, le=15)
    explanation: str
    source_fields: list[str] = Field(default_factory=list)


class FitScore(BaseModel):
    score: int | None = Field(default=None, ge=0, le=100)
    label: str
    explanation: str
    flags: list[str] = Field(default_factory=list)
    factors: list[FitFactor] = Field(default_factory=list)


class Confidence(BaseModel):
    level: ConfidenceLevel
    available_sources: list[str]
    missing_sources: list[str]
    caveats: list[str]


class AnalyzeResponse(BaseModel):
    place: Place
    geography: GeographyContext | None = None
    profile: NeighborhoodProfile
    fit: FitScore | None = None
    confidence: Confidence
    source_statuses: list[SourceStatus]
    synthesis: SynthesisStatus
    analysis_version: str = "legacy"
    snapshot_id: str | None = None
    evidence_checks: list[EvidenceCheck] = Field(default_factory=list)
    analysis_lens: AnalysisLensSnapshot = Field(
        default_factory=lambda: AnalysisLensSnapshot(
            mode=AnalysisLensMode.LEGACY,
            profile_name="Legacy report",
        )
    )
    coverage: CoverageSummary = Field(
        default_factory=lambda: CoverageSummary(
            region=CoverageRegion.OUTSIDE_GTA,
            level=CoverageLevel.LIMITED,
            message="Coverage details were not stored for this legacy report.",
        )
    )


class SaveProfileRequest(BaseModel):
    response: AnalyzeResponse
    analyze_request: AnalyzeRequest | None = None


class SavedProfileSummary(BaseModel):
    id: str
    place_label: str
    coordinates: Coordinates | None = None
    confidence_level: ConfidenceLevel
    source_statuses: list[SourceStatus]
    created_at: str
    updated_at: str
    analyze_request: AnalyzeRequest | None = None
    analysis_lens: AnalysisLensSnapshot = Field(
        default_factory=lambda: AnalysisLensSnapshot(
            mode=AnalysisLensMode.LEGACY,
            profile_name="Legacy report",
        )
    )
    coverage: CoverageSummary | None = None
    fit_score: int | None = Field(default=None, ge=0, le=100)
    fit_label: str | None = None
    collision_count: int | None = Field(default=None, ge=0)
    ksi_collision_count: int | None = Field(default=None, ge=0)
    building_match: bool | None = None
    building_score: float | None = Field(default=None, ge=0, le=100)
    cycling_score: int | None = Field(default=None, ge=0, le=100)
    cycling_evidence_method: CyclingEvidenceMethod | None = None


class SavedProfile(SavedProfileSummary):
    response: AnalyzeResponse


class DeleteProfileResponse(BaseModel):
    deleted: bool
