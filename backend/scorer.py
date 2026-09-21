from backend.models import (
    BudgetSensitivity,
    CarReliance,
    EnergyPreference,
    FitFactor,
    FitScore,
    NeighborhoodProfile,
    PreferenceCategory,
    Preferences,
    ProvenanceSupport,
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
    factors: list[FitFactor] = []
    flags: list[str] = []
    unavailable: set[str] = set()

    def add(
        signal: str,
        value: int | float | str,
        impact: int,
        explanation: str,
        *claim_ids: str,
    ) -> None:
        nonlocal score
        score += impact
        factors.append(
            FitFactor(
                signal=signal,
                value=value,
                impact=impact,
                explanation=explanation,
                source_fields=_source_fields(profile, *claim_ids),
            )
        )
        if impact < 0:
            flags.append(explanation)

    if preferences.car_reliance == CarReliance.NO_CAR:
        access = _average(scores.walkability, scores.transit_access)
        if access is None:
            unavailable.add("car-free access")
        elif access >= 70:
            add(
                "Car-free access",
                round(access),
                15,
                "Walkability and transit support getting around without a car.",
                "vibe.walkability",
                "vibe.transit_access",
            )
        elif access < 45:
            add(
                "Car-free access",
                round(access),
                -15,
                "Weak walking or transit evidence may strain a no-car lifestyle.",
                "vibe.walkability",
                "vibe.transit_access",
            )
    elif preferences.car_reliance == CarReliance.DRIVE_DAILY:
        unavailable.add("driving conditions (stored preference; not scored)")

    if preferences.energy_preference == EnergyPreference.QUIET:
        if scores.quiet is None:
            unavailable.add("quiet (stored preference; not scored)")
        elif scores.quiet >= 70:
            add(
                "Quiet",
                scores.quiet,
                12,
                "Measured quiet evidence fits your preference.",
                "vibe.quiet",
            )
        elif scores.quiet < 45:
            add(
                "Quiet",
                scores.quiet,
                -12,
                "Measured quiet evidence conflicts with your preference.",
                "vibe.quiet",
            )
    elif preferences.energy_preference == EnergyPreference.LIVELY:
        if scores.dining_activity is None:
            unavailable.add("dining and activity")
        elif scores.dining_activity >= 70:
            add(
                "Dining and activity",
                scores.dining_activity,
                12,
                "Nearby dining and activity support a livelier preference.",
                "vibe.dining_activity",
            )
        elif scores.dining_activity < 45:
            add(
                "Dining and activity",
                scores.dining_activity,
                -10,
                "Nearby activity evidence is light for a lively preference.",
                "vibe.dining_activity",
            )

    priority = _priority_signal(profile, preferences.top_priority)
    if preferences.top_priority is not None:
        if priority is None:
            unavailable.add(preferences.top_priority.value)
        else:
            signal, value, claim_id = priority
            impact = 15 if value >= 70 else -15 if value < 45 else 0
            fallback_cycling = (
                preferences.top_priority == TopPriority.CYCLING_ACCESS
                and _cycling_is_fallback(profile)
            )
            if fallback_cycling:
                impact = _half_impact(impact)
            add(
                signal,
                value,
                impact,
                (
                    f"{signal} is strongly supported for your top priority."
                    if impact > 0
                    else f"{signal} is weak for your top priority."
                    if impact < 0
                    else f"{signal} has mixed support for your top priority."
                )
                + (
                    " The OSM estimate receives reduced fit weight."
                    if fallback_cycling
                    else ""
                ),
                claim_id,
            )

    if preferences.budget_sensitivity is not None:
        affordability = scores.affordability
        if affordability is None:
            unavailable.add("rent pressure")
        elif preferences.budget_sensitivity == BudgetSensitivity.VERY_BUDGET_CONSCIOUS:
            impact = 12 if affordability >= 65 else -15 if affordability < 45 else 0
            add(
                "Rent pressure",
                affordability,
                impact,
                "Rent evidence supports your budget."
                if impact > 0
                else "Rent evidence may conflict with your budget."
                if impact < 0
                else "Rent evidence is mixed for your budget.",
                "vibe.affordability",
            )
        elif (
            preferences.budget_sensitivity == BudgetSensitivity.FLEXIBLE
            and affordability < 45
        ):
            add(
                "Rent pressure",
                affordability,
                -3,
                "Rent pressure is present, though budget flexibility softens its impact.",
                "vibe.affordability",
            )

    benchmark = profile.who_lives_here.rent_benchmark
    if preferences.max_monthly_rent is not None:
        if preferences.rental_unit_size is None:
            unavailable.add("monthly rent (select a unit size)")
        elif (
            benchmark is None
            or benchmark.monthly_rent is None
            or benchmark.unit_size != preferences.rental_unit_size
        ):
            unavailable.add(f"monthly rent for {preferences.rental_unit_size.value}")
        else:
            difference = preferences.max_monthly_rent - benchmark.monthly_rent
            impact = 15 if difference >= 250 else 8 if difference >= 0 else -15
            add(
                "Monthly rent (CAD)",
                benchmark.monthly_rent,
                impact,
                (
                    f"The matching CMHC benchmark is within your CAD {preferences.max_monthly_rent:,} ceiling."
                    if difference >= 0
                    else f"The matching CMHC benchmark exceeds your CAD {preferences.max_monthly_rent:,} ceiling."
                ),
                "context.rent_benchmark",
            )

    important_total = 0
    for category in preferences.must_haves:
        resolved = _category_signal(profile, category)
        if resolved is None:
            unavailable.add(category.value)
            continue
        signal, value, claim_id = resolved
        impact = 6 if value >= 60 else -4
        fallback_cycling = (
            category == PreferenceCategory.CYCLING
            and _cycling_is_fallback(profile)
        )
        if fallback_cycling:
            impact = _half_impact(impact)
        impact = max(-18 - important_total, min(18 - important_total, impact))
        important_total += impact
        add(
            f"Important: {signal}",
            value,
            impact,
            f"{signal} {'is supported' if value >= 60 else 'has weak support'} as an important signal."
            + (
                " The OSM estimate receives reduced fit weight."
                if fallback_cycling
                else ""
            ),
            claim_id,
        )

    non_negotiable_total = 0
    for category in preferences.deal_breakers:
        resolved = _category_signal(profile, category)
        if resolved is None:
            unavailable.add(category.value)
            continue
        signal, value, claim_id = resolved
        fallback_cycling = (
            category == PreferenceCategory.CYCLING
            and _cycling_is_fallback(profile)
        )
        if fallback_cycling and value >= 60:
            impact = 3
            explanation = (
                f"{signal} clears your non-negotiable threshold using reduced-weight "
                "OSM fallback evidence."
            )
        elif fallback_cycling:
            impact = 0
            explanation = (
                f"{signal} has weak mapped support, but OSM fallback evidence cannot "
                "conclusively fail a non-negotiable."
            )
        elif value >= 60:
            impact = 5
            explanation = f"{signal} clears your non-negotiable threshold."
        else:
            impact = max(-15, -30 - non_negotiable_total)
            explanation = f"{signal} fails your non-negotiable threshold."
        non_negotiable_total += impact
        add(f"Non-negotiable: {signal}", value, impact, explanation, claim_id)

    if unavailable:
        flags.append(
            "Not scored because evidence is unavailable: "
            + ", ".join(sorted(unavailable))
            + "."
        )
    final_score = _clamp(score) if factors else None
    scored = [factor for factor in factors if factor.impact]
    explanation = (
        f"{len(scored)} evidence-backed factor{'s' if len(scored) != 1 else ''} "
        f"moved this fit from the 50-point baseline: "
        + "; ".join(factor.explanation for factor in scored)
        if scored
        else "No evidence-backed preference factor was available, so no numeric fit score was calculated."
    )
    return FitScore(
        score=final_score,
        label=_label(final_score) if final_score is not None else "Not enough evidence",
        explanation=explanation,
        flags=flags,
        factors=factors,
    )


def _priority_signal(
    profile: NeighborhoodProfile,
    priority: TopPriority | None,
) -> tuple[str, int, str] | None:
    if priority is None:
        return None
    daily_needs = (
        profile.vibe_scores.daily_needs
        if profile.vibe_scores.daily_needs is not None
        else profile.vibe_scores.walkability
    )
    mapping: dict[TopPriority, tuple[str, int | None, str]] = {
        TopPriority.WALKABILITY_ERRANDS: (
            "Daily needs",
            daily_needs,
            "vibe.daily_needs",
        ),
        TopPriority.TRANSIT_ACCESS: (
            "Transit access",
            profile.vibe_scores.transit_access,
            "vibe.transit_access",
        ),
        TopPriority.PARKS_OUTDOORS: (
            "Parks and outdoors",
            profile.vibe_scores.parks_outdoors,
            "vibe.parks_outdoors",
        ),
        TopPriority.RESTAURANTS_NIGHTLIFE: (
            "Dining and activity",
            profile.vibe_scores.dining_activity,
            "vibe.dining_activity",
        ),
        TopPriority.LOWER_RENT_PRESSURE: (
            "Rent context",
            profile.vibe_scores.affordability,
            "vibe.affordability",
        ),
        TopPriority.CYCLING_ACCESS: (
            "Cycling access",
            profile.vibe_scores.cycling_access,
            "vibe.cycling_access",
        ),
    }
    label, value, claim_id = mapping[priority]
    return (label, value, claim_id) if value is not None else None


def _category_signal(
    profile: NeighborhoodProfile,
    category: PreferenceCategory,
) -> tuple[str, int, str] | None:
    scores = profile.vibe_scores
    mapping: dict[PreferenceCategory, tuple[str, int | None, str]] = {
        PreferenceCategory.TRANSIT: (
            "Transit access",
            scores.transit_access,
            "vibe.transit_access",
        ),
        PreferenceCategory.WALKABILITY: (
            "Walkability",
            scores.walkability,
            "vibe.walkability",
        ),
        PreferenceCategory.PARKS: (
            "Parks and outdoors",
            scores.parks_outdoors,
            "vibe.parks_outdoors",
        ),
        PreferenceCategory.GROCERIES: (
            "Daily needs",
            scores.daily_needs,
            "vibe.daily_needs",
        ),
        PreferenceCategory.RESTAURANTS: (
            "Dining and activity",
            scores.dining_activity,
            "vibe.dining_activity",
        ),
        PreferenceCategory.QUIET: ("Quiet", scores.quiet, "vibe.quiet"),
        PreferenceCategory.SOCIAL_SCENE: (
            "Dining and activity",
            scores.dining_activity,
            "vibe.dining_activity",
        ),
        PreferenceCategory.LOWER_RENT_PRESSURE: (
            "Rent context",
            scores.affordability,
            "vibe.affordability",
        ),
        PreferenceCategory.CYCLING: (
            "Cycling access",
            scores.cycling_access,
            "vibe.cycling_access",
        ),
    }
    label, value, claim_id = mapping[category]
    return (label, value, claim_id) if value is not None else None


def _average(*values: int | None) -> float | None:
    available = [value for value in values if value is not None]
    return sum(available) / len(available) if available else None


def _cycling_is_fallback(profile: NeighborhoodProfile) -> bool:
    return bool(profile.cycling_context and profile.cycling_context.fallback)


def _half_impact(impact: int) -> int:
    if impact == 0:
        return 0
    magnitude = (abs(impact) + 1) // 2
    return magnitude if impact > 0 else -magnitude


def _source_fields(profile: NeighborhoodProfile, *claim_ids: str) -> list[str]:
    fields: list[str] = []
    for item in profile.provenance.items:
        if item.claim_id in claim_ids and item.support != ProvenanceSupport.UNAVAILABLE:
            fields.extend(item.source_fields)
    return list(dict.fromkeys(fields))
