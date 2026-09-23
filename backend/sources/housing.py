from __future__ import annotations

from typing import Any

from backend.models import RentalUnitSize
from backend.snapshot import load_manifest, snapshot_connection
from backend.sources.common import SourceContext, SourceResult
from backend.sources.local import is_gta_place

CMHC_SOURCE_URL = (
    "https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/"
    "market-reports/rental-market-reports-major-centres?ap=a1-p1"
)
CITY_TO_CSD = {
    "ajax": "3518005",
    "aurora": "3519046",
    "brampton": "3521010",
    "burlington": "3524002",
    "caledon": "3521024",
    "clarington": "3518017",
    "halton hills": "3524015",
    "king": "3519049",
    "markham": "3519036",
    "milton": "3524009",
    "mississauga": "3521005",
    "newmarket": "3519048",
    "oakville": "3524001",
    "oshawa": "3518013",
    "pickering": "3518001",
    "richmond hill": "3519038",
    "scugog": "3518020",
    "toronto": "3520005",
    "uxbridge": "3518029",
    "vaughan": "3519028",
    "whitby": "3518009",
    "whitchurch-stouffville": "3519044",
}


async def fetch_housing_context(context: SourceContext) -> SourceResult:
    geography = context.geography
    if (
        not (geography and geography.is_gta)
        and not is_gta_place(context.place)
        and not _coordinates_in_gta(context)
    ):
        return SourceResult(
            data={},
            message="CMHC GTA rent context is not applied outside the GTA.",
            source_url=CMHC_SOURCE_URL,
        )

    manifest = load_manifest()
    connection = snapshot_connection()
    if connection is None or manifest is None:
        return SourceResult(
            data={},
            message="The bundled CMHC rental snapshot is unavailable.",
            source_url=CMHC_SOURCE_URL,
        )
    unit_size = (
        context.request.preferences.rental_unit_size or RentalUnitSize.TWO_BEDROOM
    )
    geography_id = (
        geography.census_subdivision_id
        if geography is not None and geography.census_subdivision_id
        else _geography_id(context.place.city, context.place.label)
    )
    try:
        benchmark = lookup_rent_benchmark(connection, geography_id, unit_size)
        if benchmark is None:
            return SourceResult(
                data={},
                message=(
                    f"No CMHC {unit_size.value.replace('_', ' ')} purpose-built benchmark "
                    "matches this census subdivision."
                ),
                updated_at=manifest.get("created_at"),
                edition="CMHC 2025 Rental Market Report",
                scope="GTA census subdivisions",
                source_url=CMHC_SOURCE_URL,
            )
        two_bedroom = lookup_rent_benchmark(
            connection, geography_id, RentalUnitSize.TWO_BEDROOM
        )
        rents = [
            int(row[0])
            for row in connection.execute(
                """
                SELECT monthly_rent FROM rent_benchmarks
                WHERE unit_size = ? AND monthly_rent IS NOT NULL
                """,
                (unit_size.value,),
            ).fetchall()
        ]
        data = {
            "rent_benchmark": benchmark,
            "affordability": _rent_pressure_score(benchmark.get("monthly_rent"), rents),
            "average_two_bedroom_rent": (
                two_bedroom.get("monthly_rent") if two_bedroom else None
            ),
            "vacancy_rate": benchmark.get("vacancy_rate"),
            "geographic_scope": benchmark["geography"],
            "edition": benchmark["edition"],
            "reference_year": benchmark["reference_year"],
            "source_url": benchmark.get("source_url") or CMHC_SOURCE_URL,
            "benchmark_matches_preference": context.request.preferences.rental_unit_size
            is not None,
        }
        return SourceResult(
            data=data,
            message=(
                "CMHC 2025 unit-matched purpose-built rental benchmark returned."
                if context.request.preferences.rental_unit_size is not None
                else "CMHC 2025 two-bedroom context returned; no unit size was assumed for fit."
            ),
            updated_at=manifest.get("created_at"),
            edition=benchmark["edition"],
            scope=benchmark["geography"],
            source_url=data["source_url"],
            stale=bool(manifest.get("stale", False)),
        )
    finally:
        connection.close()


def lookup_rent_benchmark(
    connection: Any,
    geography_id: str | None,
    unit_size: RentalUnitSize,
) -> dict[str, Any] | None:
    if geography_id is None:
        return None
    row = connection.execute(
        """
        SELECT geography_id, geography_name, unit_size, monthly_rent, vacancy_rate,
               quality_code, vacancy_quality_code, suppressed, edition,
               reference_year, source_url
        FROM rent_benchmarks
        WHERE geography_id = ? AND unit_size = ?
        """,
        (geography_id, unit_size.value),
    ).fetchone()
    if row is None:
        return None
    return {
        "monthly_rent": row["monthly_rent"],
        "unit_size": row["unit_size"],
        "geography": row["geography_name"],
        "geography_id": row["geography_id"],
        "market_scope": "Purpose-built rental apartments",
        "vacancy_rate": row["vacancy_rate"],
        "quality_code": row["quality_code"],
        "vacancy_quality_code": row["vacancy_quality_code"],
        "suppressed": bool(row["suppressed"]),
        "edition": row["edition"],
        "reference_year": row["reference_year"],
        "currency": "CAD",
        "source_url": row["source_url"],
    }


def rent_context_for_geography(
    geography_id: str,
    unit_size: RentalUnitSize | None,
) -> dict[str, Any] | None:
    """Resolve a CMHC benchmark by Statistics Canada CSD, without a network call."""
    connection = snapshot_connection()
    if connection is None:
        return None
    selected_unit = unit_size or RentalUnitSize.TWO_BEDROOM
    try:
        benchmark = lookup_rent_benchmark(connection, geography_id, selected_unit)
        if benchmark is None:
            return None
        two_bedroom = lookup_rent_benchmark(
            connection, geography_id, RentalUnitSize.TWO_BEDROOM
        )
        rents = [
            int(row[0])
            for row in connection.execute(
                """
                SELECT monthly_rent FROM rent_benchmarks
                WHERE unit_size = ? AND monthly_rent IS NOT NULL
                """,
                (selected_unit.value,),
            ).fetchall()
        ]
        return {
            "rent_benchmark": benchmark,
            "affordability": _rent_pressure_score(benchmark.get("monthly_rent"), rents),
            "average_two_bedroom_rent": (
                two_bedroom.get("monthly_rent") if two_bedroom else None
            ),
            "vacancy_rate": benchmark.get("vacancy_rate"),
            "geographic_scope": benchmark["geography"],
            "edition": benchmark["edition"],
            "reference_year": benchmark["reference_year"],
            "source_url": benchmark.get("source_url") or CMHC_SOURCE_URL,
            "benchmark_matches_preference": unit_size is not None,
        }
    finally:
        connection.close()


def _rent_pressure_score(monthly_rent: int | None, rents: list[int]) -> int | None:
    if monthly_rent is None or not rents:
        return None
    ordered = sorted(rents)
    if len(ordered) == 1:
        return 50
    rank = sum(value < monthly_rent for value in ordered) / (len(ordered) - 1)
    return max(0, min(100, round(100 - rank * 100)))


def _geography_id(city: str | None, label: str) -> str | None:
    haystack = f"{city or ''} {label}".lower()
    for name, geography_id in sorted(
        CITY_TO_CSD.items(), key=lambda item: -len(item[0])
    ):
        if name in haystack:
            return geography_id
    return None


def _coordinates_in_gta(context: SourceContext) -> bool:
    coordinates = context.place.coordinates
    return bool(
        coordinates
        and 43.40 <= coordinates.lat <= 44.25
        and -80.15 <= coordinates.lng <= -78.75
    )


# Kept for compatibility with old imports; runtime analysis uses the bundled artifact.
CMHC_GTA_SNAPSHOT = {
    "edition": "2025 Rental Market Report",
    "reference_year": 2025,
    "geographic_scope": "Greater Toronto Area",
    "currency": "CAD",
    "purpose_built_average_two_bedroom_rent": 2034,
    "purpose_built_vacancy_rate": 3.0,
    "source_url": CMHC_SOURCE_URL,
}


def normalize_cmhc_snapshot(payload: dict[str, object]) -> dict[str, object]:
    required = (
        "edition",
        "reference_year",
        "geographic_scope",
        "currency",
        "purpose_built_average_two_bedroom_rent",
        "purpose_built_vacancy_rate",
        "source_url",
    )
    missing = [field for field in required if payload.get(field) is None]
    if missing:
        raise ValueError("CMHC snapshot is missing: " + ", ".join(missing))
    return {
        **payload,
        "average_two_bedroom_rent": payload["purpose_built_average_two_bedroom_rent"],
        "vacancy_rate": payload["purpose_built_vacancy_rate"],
    }
