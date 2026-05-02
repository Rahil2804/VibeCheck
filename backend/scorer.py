from backend.models import (
    BudgetSensitivity,
    CarReliance,
    EnergyPreference,
    FitScore,
    NeighborhoodProfile,
    Preferences,
    TopPriority,
)


def _clamp(score: int) -> int:
    return max(0, min(100, score))


def _label(score: int) -> str:
    if score >= 75:
        return "Strong fit"
    if score >= 60:
        return "Good fit"
    if score >= 45:
        return "Mixed fit"
    return "Weak fit"


def score_fit(profile: NeighborhoodProfile, preferences: Preferences) -> FitScore:
    scores = profile.vibe_scores
    score = 50
    reasons: list[str] = []
    flags: list[str] = []

    if preferences.car_reliance == CarReliance.NO_CAR:
        access_average = (scores.walkability + scores.transit_access) / 2
        if access_average >= 70:
            score += 15
            flags.append("No car preference is supported by strong walkability and transit access.")
            reasons.append("getting around without a car looks practical")
        elif access_average < 45:
            score -= 18
            flags.append("No car preference may be strained by weak walkability or transit access.")
            reasons.append("weak access could make a no car lifestyle harder")
    elif preferences.car_reliance == CarReliance.DRIVE_DAILY:
        if scores.walkability < 45 and scores.transit_access < 45:
            score += 5
            reasons.append("daily driving is less penalized by weaker car-free access")

    if preferences.energy_preference == EnergyPreference.QUIET:
        if scores.quiet >= 70:
            score += 13
            reasons.append("quiet signals match your calmer energy preference")
        if scores.social_scene >= 75:
            score -= 12
            flags.append("The social scene may feel busier than your quiet preference.")
    elif preferences.energy_preference == EnergyPreference.LIVELY:
        if scores.social_scene >= 70:
            score += 13
            reasons.append("the social scene matches your livelier preference")
        if scores.quiet >= 80:
            score -= 8
            flags.append("The area may be calmer than your lively preference.")

    if preferences.top_priority == TopPriority.WALKABILITY_ERRANDS:
        if scores.walkability >= 70:
            score += 15
            reasons.append("walkability is a clear strength")
        elif scores.walkability < 45:
            score -= 12
            flags.append("Walkability is weak for an errands-first priority.")
    elif preferences.top_priority == TopPriority.TRANSIT_ACCESS:
        if scores.transit_access >= 70:
            score += 15
            reasons.append("transit access is a clear strength")
        elif scores.transit_access < 45:
            score -= 12
            flags.append("Transit access is weak for your stated priority.")
    elif preferences.top_priority == TopPriority.PARKS_OUTDOORS:
        if scores.quiet >= 60:
            score += 10
            reasons.append("outdoor and calmer-access signals are favorable")
    elif preferences.top_priority == TopPriority.RESTAURANTS_NIGHTLIFE:
        if scores.social_scene >= 70:
            score += 12
            reasons.append("restaurants and nightlife signals look strong")
    elif preferences.top_priority == TopPriority.LOWER_RENT_PRESSURE:
        if scores.affordability >= 65:
            score += 10
            reasons.append("affordability signals support lower rent pressure")
        elif scores.affordability < 45:
            score -= 12
            flags.append("Rent pressure may conflict with your lower-cost priority.")

    if preferences.budget_sensitivity == BudgetSensitivity.VERY_BUDGET_CONSCIOUS:
        if scores.affordability < 45:
            score -= 15
            flags.append("Budget sensitivity is a concern because affordability signals are weak.")
            reasons.append("budget pressure is the main caveat")
        elif scores.affordability >= 65:
            score += 10
            reasons.append("affordability signals support your budget sensitivity")
    elif preferences.budget_sensitivity == BudgetSensitivity.FLEXIBLE and scores.affordability < 45:
        score -= 3
        reasons.append("rent pressure is present but less central to your preferences")

    final_score = _clamp(score)
    explanation = (
        "This fit score reflects " + ", ".join(reasons) + "."
        if reasons
        else "This fit score is neutral because few lifestyle preferences were selected."
    )

    return FitScore(
        score=final_score,
        label=_label(final_score),
        explanation=explanation,
        flags=flags,
    )
