from enum import StrEnum
from typing import Any
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


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class SourceName(StrEnum):
    MAPBOX = "mapbox"
    CENSUS = "census"
    HOUSING = "housing"
    REDDIT = "reddit"
    ACCESS = "access"


class SourceStatusCode(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    ERROR = "error"


class SynthesisStatusCode(StrEnum):
    USED = "used"
    SKIPPED = "skipped"
    FALLBACK = "fallback"


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


class CommuteAnchor(BaseModel):
    label: str = Field(min_length=1)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def require_both_coordinates(self) -> Self:
        if (self.lat is None) != (self.lng is None):
            raise ValueError("Provide both commute anchor latitude and longitude, or neither.")
        return self


class PreferenceProfileBase(Preferences):
    generic_mode: bool = False
    commute_anchor: CommuteAnchor | None = None
    max_monthly_rent: int | None = Field(default=None, ge=0)
    must_haves: list[PreferenceCategory] = Field(default_factory=list)
    deal_breakers: list[PreferenceCategory] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=1000)

    @property
    def preferences(self) -> Preferences:
        return Preferences(
            car_reliance=self.car_reliance,
            energy_preference=self.energy_preference,
            top_priority=self.top_priority,
            budget_sensitivity=self.budget_sensitivity,
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


class SourceStatus(BaseModel):
    source: SourceName
    status: SourceStatusCode
    message: str
    updated_at: str | None = None


class SynthesisStatus(BaseModel):
    status: SynthesisStatusCode
    model: str | None = None
    message: str


class Place(BaseModel):
    label: str
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    coordinates: Coordinates | None = None


class VibeScores(BaseModel):
    walkability: int = Field(ge=0, le=100)
    transit_access: int = Field(ge=0, le=100)
    affordability: int = Field(ge=0, le=100)
    quiet: int = Field(ge=0, le=100)
    social_scene: int = Field(ge=0, le=100)


class WhoLivesHere(BaseModel):
    median_age: float | None = None
    median_household_income: int | None = None
    population_density: float | None = None
    population_trend: str | None = None


class Trajectory(BaseModel):
    direction: TrajectoryDirection
    summary: str


class NeighborhoodProfile(BaseModel):
    overview: str
    vibe_scores: VibeScores
    who_lives_here: WhoLivesHere
    honest_pros: list[str]
    honest_cons: list[str]
    trajectory: Trajectory
    provenance: dict[str, Any] = Field(default_factory=dict)


class FitScore(BaseModel):
    score: int = Field(ge=0, le=100)
    label: str
    explanation: str
    flags: list[str] = Field(default_factory=list)


class Confidence(BaseModel):
    level: ConfidenceLevel
    available_sources: list[str]
    missing_sources: list[str]
    caveats: list[str]


class AnalyzeResponse(BaseModel):
    place: Place
    profile: NeighborhoodProfile
    fit: FitScore | None = None
    confidence: Confidence
    source_statuses: list[SourceStatus]
    synthesis: SynthesisStatus


class SavedProfileSummary(BaseModel):
    id: str
    place_label: str
    coordinates: Coordinates | None = None
    confidence_level: ConfidenceLevel
    source_statuses: list[SourceStatus]
    created_at: str
    updated_at: str


class SavedProfile(SavedProfileSummary):
    response: AnalyzeResponse


class DeleteProfileResponse(BaseModel):
    deleted: bool
