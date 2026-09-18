from backend.models import Place
from backend.geography import resolve_geography
from backend.sources.common import SourceContext, SourceResult

GTA_MUNICIPALITIES = {
    "toronto",
    "pickering",
    "ajax",
    "whitby",
    "oshawa",
    "clarington",
    "uxbridge",
    "scugog",
    "brock",
    "markham",
    "vaughan",
    "richmond hill",
    "newmarket",
    "aurora",
    "mississauga",
    "brampton",
    "caledon",
    "oakville",
    "burlington",
    "milton",
    "halton hills",
}


async def fetch_local_context(context: SourceContext) -> SourceResult:
    place = context.place
    if place.coordinates is None:
        return SourceResult(
            data={},
            message="Local open-data lookup needs resolved coordinates.",
        )

    geography = context.geography or resolve_geography(place)
    if geography.is_toronto:
        from backend.sources.ontario.toronto import fetch_toronto_context

        return await fetch_toronto_context(context)

    if is_ontario_place(place):
        municipality = place.city or _first_label_part(place.label)
        region = "GTA" if is_gta_place(place) else "Ontario"
        return SourceResult(
            data={},
            message=f"No local {region} adapter is available yet for {municipality}.",
        )

    return SourceResult(
        data={},
        message="No local open-data adapter is configured for this region.",
    )


def is_ontario_place(place: Place) -> bool:
    geography = resolve_geography(place)
    if geography.province and geography.province.casefold() in {"on", "ontario"}:
        return True
    values = _place_tokens(place)
    return any(value in {"on", "ontario"} for value in values)


def is_toronto_place(place: Place) -> bool:
    return resolve_geography(place).is_toronto


def is_gta_place(place: Place) -> bool:
    return resolve_geography(place).is_gta


def _place_text(place: Place) -> str:
    raw_values = [place.label, place.city or "", place.state or ""]
    return " ".join(raw_values).lower().replace(",", " ")


def _place_tokens(place: Place) -> set[str]:
    tokens: set[str] = set()
    for part in _place_text(place).split():
        stripped = part.strip()
        if stripped:
            tokens.add(stripped)
    return tokens


def _first_label_part(label: str) -> str:
    return label.split(",", maxsplit=1)[0].strip() or "this municipality"
