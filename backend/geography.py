from __future__ import annotations

from backend.census_bundle import lookup_bundled_census_subdivision
from backend.models import GeographyContext, Place
from backend.sources.ontario.toronto_profiles import lookup_bundled_toronto_profile

TORONTO_BOUNDS = (43.58, 43.86, -79.64, -79.11)
GTA_BOUNDS = (43.40, 44.25, -80.15, -78.75)
TORONTO_ALIASES = {
    "toronto",
    "east york",
    "north york",
    "scarborough",
    "etobicoke",
    "york",
}
CSD_BY_MUNICIPALITY = {
    "ajax": ("3518005", "Ajax"),
    "aurora": ("3519046", "Aurora"),
    "brampton": ("3521010", "Brampton"),
    "brock": ("3518039", "Brock"),
    "burlington": ("3524002", "Burlington"),
    "caledon": ("3521024", "Caledon"),
    "clarington": ("3518017", "Clarington"),
    "halton hills": ("3524015", "Halton Hills"),
    "king": ("3519049", "King"),
    "markham": ("3519036", "Markham"),
    "milton": ("3524009", "Milton"),
    "mississauga": ("3521005", "Mississauga"),
    "newmarket": ("3519048", "Newmarket"),
    "oakville": ("3524001", "Oakville"),
    "oshawa": ("3518013", "Oshawa"),
    "pickering": ("3518001", "Pickering"),
    "richmond hill": ("3519038", "Richmond Hill"),
    "scugog": ("3518020", "Scugog"),
    "toronto": ("3520005", "Toronto"),
    "east york": ("3520005", "Toronto"),
    "north york": ("3520005", "Toronto"),
    "scarborough": ("3520005", "Toronto"),
    "etobicoke": ("3520005", "Toronto"),
    "east gwillimbury": ("3519054", "East Gwillimbury"),
    "georgina": ("3519070", "Georgina"),
    "york": ("3520005", "Toronto"),
    "uxbridge": ("3518029", "Uxbridge"),
    "vaughan": ("3519028", "Vaughan"),
    "whitby": ("3518009", "Whitby"),
    "whitchurch-stouffville": ("3519044", "Whitchurch-Stouffville"),
}


def resolve_geography(place: Place) -> GeographyContext:
    text = _place_text(place)
    coordinates = place.coordinates
    subdivision = (
        lookup_bundled_census_subdivision(coordinates)
        if coordinates is not None
        else {}
    )
    neighbourhood = (
        lookup_bundled_toronto_profile(coordinates) if coordinates is not None else {}
    )
    coordinate_toronto = subdivision.get("census_subdivision_id") == "3520005" or bool(
        neighbourhood
    )
    if not subdivision and not neighbourhood:
        coordinate_toronto = bool(
            coordinates and _inside(coordinates.lat, coordinates.lng, TORONTO_BOUNDS)
        )
    alias = _municipality_alias(text)
    text_fallback_allowed = coordinates is None
    is_toronto = coordinate_toronto or (
        text_fallback_allowed and alias in TORONTO_ALIASES
    )
    coordinate_gta = bool(subdivision) or bool(
        coordinates
        and not subdivision
        and _inside(coordinates.lat, coordinates.lng, GTA_BOUNDS)
    )
    is_gta = is_toronto or coordinate_gta or (
        text_fallback_allowed and alias in CSD_BY_MUNICIPALITY
    )

    csd_id: str | None = None
    csd_name: str | None = None
    resolution = "unresolved"
    if subdivision:
        csd_id = str(subdivision["census_subdivision_id"])
        csd_name = str(subdivision["census_subdivision_name"])
        resolution = "bundled official boundary"
    elif is_toronto:
        csd_id, csd_name = CSD_BY_MUNICIPALITY["toronto"]
        resolution = "coordinates" if coordinate_toronto else "place context"
    elif text_fallback_allowed and alias in CSD_BY_MUNICIPALITY:
        csd_id, csd_name = CSD_BY_MUNICIPALITY[alias]
        resolution = "place context"
    elif coordinate_gta:
        resolution = "coordinates"

    province = place.state
    if province is None and (is_gta or "ontario" in text or " on " in f" {text} "):
        province = "Ontario"
    country = "Canada" if is_gta or "canada" in text else None
    return GeographyContext(
        country=country,
        province=province,
        census_subdivision_id=csd_id,
        census_subdivision_name=csd_name,
        toronto_neighbourhood_id=neighbourhood.get("neighbourhood_id"),
        toronto_neighbourhood_name=neighbourhood.get("neighbourhood_name"),
        is_toronto=is_toronto,
        is_gta=is_gta,
        resolution=resolution,
    )


def _municipality_alias(text: str) -> str | None:
    return next(
        (
            name
            for name in sorted(CSD_BY_MUNICIPALITY, key=len, reverse=True)
            if name in text
        ),
        None,
    )


def _place_text(place: Place) -> str:
    return " ".join(
        value.casefold().replace(",", " ")
        for value in (
            place.label,
            place.city or "",
            place.state or "",
            place.neighborhood or "",
        )
    )


def _inside(lat: float, lng: float, bounds: tuple[float, float, float, float]) -> bool:
    min_lat, max_lat, min_lng, max_lng = bounds
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng
