from backend.models import (
    BudgetSensitivity,
    CarReliance,
    EnergyPreference,
    NeighborhoodProfile,
    Preferences,
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
    assert any("no car" in flag.lower() for flag in fit.flags)


def test_no_car_user_penalizes_weak_access():
    fit = score_fit(
        _profile(walkability=25, transit_access=30),
        Preferences(car_reliance=CarReliance.NO_CAR),
    )

    assert fit.score < 40
    assert "weak" in fit.explanation.lower()


def test_quiet_and_lively_preferences_use_neutral_vibe_signals():
    quiet_fit = score_fit(
        _profile(quiet=82, social_scene=35),
        Preferences(energy_preference=EnergyPreference.QUIET),
    )
    lively_fit = score_fit(
        _profile(quiet=35, social_scene=84),
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
    assert "walkability" in fit.explanation.lower()


def test_budget_sensitive_user_penalizes_low_affordability():
    fit = score_fit(
        _profile(affordability=28),
        Preferences(budget_sensitivity=BudgetSensitivity.VERY_BUDGET_CONSCIOUS),
    )

    assert fit.score < 45
    assert any("budget" in flag.lower() for flag in fit.flags)


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
