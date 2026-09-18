from backend.models import (
    BudgetSensitivity,
    CarReliance,
    EnergyPreference,
    NeighborhoodProfile,
    Preferences,
    RentBenchmark,
    RentalUnitSize,
    TopPriority,
    Trajectory,
    TrajectoryDirection,
    VibeScores,
    WhoLivesHere,
)
from backend.scorer import score_fit


def _profile(**score_overrides) -> NeighborhoodProfile:
    scores = {
        "walkability": 50,
        "transit_access": 50,
        "affordability": 50,
        "quiet": 50,
        "social_scene": 50,
        "parks_outdoors": None,
        "daily_needs": None,
        "dining_activity": None,
    }
    scores.update(score_overrides)
    return NeighborhoodProfile(
        overview="Balanced neighborhood.",
        vibe_scores=VibeScores(**scores),
        who_lives_here=WhoLivesHere(
            median_age=31,
            median_household_income=58000,
            population_density=5200,
            population_trend="growing",
        ),
        honest_pros=["Useful amenities nearby."],
        honest_cons=["Rent pressure may be noticeable."],
        trajectory=Trajectory(
            direction=TrajectoryDirection.STABLE,
            summary="Signals look stable.",
        ),
    )


def test_no_car_user_rewards_walkable_transit_rich_places():
    fit = score_fit(
        _profile(walkability=82, transit_access=78),
        Preferences(car_reliance=CarReliance.NO_CAR),
    )

    assert fit.score > 60
    assert any("car-free" in factor.signal.lower() for factor in fit.factors)


def test_no_car_user_penalizes_weak_access():
    fit = score_fit(
        _profile(walkability=25, transit_access=30),
        Preferences(car_reliance=CarReliance.NO_CAR),
    )

    assert fit.score < 40
    assert "weak" in fit.explanation.lower()


def test_quiet_and_lively_preferences_use_only_supported_signals():
    quiet_fit = score_fit(
        _profile(quiet=82, social_scene=35),
        Preferences(energy_preference=EnergyPreference.QUIET),
    )
    lively_fit = score_fit(
        _profile(quiet=35, dining_activity=84),
        Preferences(energy_preference=EnergyPreference.LIVELY),
    )

    assert quiet_fit.score > 60
    assert lively_fit.score > 60


def test_top_priority_changes_score_and_explanation():
    fit = score_fit(
        _profile(walkability=88, transit_access=35),
        Preferences(top_priority=TopPriority.WALKABILITY_ERRANDS),
    )

    assert fit.score >= 65
    assert "daily needs" in fit.explanation.lower()


def test_budget_sensitive_user_penalizes_low_affordability():
    fit = score_fit(
        _profile(affordability=28),
        Preferences(budget_sensitivity=BudgetSensitivity.VERY_BUDGET_CONSCIOUS),
    )

    assert fit.score < 45
    assert any("budget" in flag.lower() for flag in fit.flags)


def test_parks_priority_rewards_supported_parks_outdoors_signal():
    fit = score_fit(
        _profile(quiet=45, parks_outdoors=82),
        Preferences(top_priority=TopPriority.PARKS_OUTDOORS),
    )

    assert fit.score >= 62
    assert "parks" in fit.explanation.lower()


def test_parks_priority_no_longer_uses_quiet_as_proxy_when_parks_signal_is_missing():
    fit = score_fit(
        _profile(quiet=82, parks_outdoors=None),
        Preferences(top_priority=TopPriority.PARKS_OUTDOORS),
    )

    assert fit.score is None
    assert fit.label == "Not enough evidence"
    assert "no numeric fit score" in fit.explanation.lower()


def test_demographic_context_does_not_change_fit_score():
    preferences = Preferences(top_priority=TopPriority.TRANSIT_ACCESS)
    first = _profile(transit_access=80)
    second = _profile(transit_access=80)
    second.who_lives_here = WhoLivesHere(
        median_age=67,
        median_household_income=200000,
        population_density=900,
        population_trend="declining",
    )

    assert score_fit(first, preferences).score == score_fit(second, preferences).score


def test_non_negotiables_penalize_weak_evidence_and_skip_missing_evidence():
    fit = score_fit(
        _profile(transit_access=35, parks_outdoors=None),
        Preferences(deal_breakers=["transit", "parks"]),
    )

    assert fit.score == 35
    assert any("fails" in factor.explanation for factor in fit.factors)
    assert any("parks" in flag for flag in fit.flags)


def test_max_rent_uses_source_backed_cad_context():
    profile = _profile()
    profile.who_lives_here.rent_benchmark = RentBenchmark(
        monthly_rent=2100,
        unit_size=RentalUnitSize.ONE_BEDROOM,
        geography="Toronto",
        edition="CMHC 2025 Rental Market Report",
        reference_year=2025,
    )

    fit = score_fit(
        profile,
        Preferences(
            max_monthly_rent=1900,
            rental_unit_size=RentalUnitSize.ONE_BEDROOM,
        ),
    )

    assert fit.score == 35
    assert fit.factors[0].signal == "Monthly rent (CAD)"


def test_max_rent_never_substitutes_historical_shelter_cost_or_wrong_unit():
    profile = _profile()
    profile.who_lives_here.median_renter_shelter_cost = 1200
    profile.who_lives_here.rent_benchmark = RentBenchmark(
        monthly_rent=2100,
        unit_size=RentalUnitSize.TWO_BEDROOM,
        geography="Toronto",
        edition="CMHC 2025 Rental Market Report",
        reference_year=2025,
    )

    fit = score_fit(
        profile,
        Preferences(
            max_monthly_rent=1900,
            rental_unit_size=RentalUnitSize.ONE_BEDROOM,
        ),
    )

    assert fit.score is None
    assert fit.factors == []
