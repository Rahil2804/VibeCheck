from backend.models import Place
from backend.sources.common import SourceContext, SourceResult


async def fetch_local_context(context: SourceContext) -> SourceResult:
    place = context.place
    if place.coordinates is None:
        return SourceResult(
            data={},
            message="Local open-data lookup needs resolved coordinates.",
        )

    if is_toronto_place(place):
        from backend.sources.ontario.toronto import fetch_toronto_context

        return await fetch_toronto_context(context)

    if is_ontario_place(place):
        municipality = place.city or _first_label_part(place.label)
        return SourceResult(
            data={},
            message=f"No local Ontario adapter is available yet for {municipality}.",
        )

    return SourceResult(
        data={},
        message="No local open-data adapter is configured for this region.",
    )


def is_ontario_place(place: Place) -> bool:
    values = _place_tokens(place)
    return any(value in {"on", "ontario"} for value in values)


def is_toronto_place(place: Place) -> bool:
    values = _place_tokens(place)
    return "toronto" in values


def _place_tokens(place: Place) -> set[str]:
    raw_values = [place.label, place.city or "", place.state or ""]
    tokens: set[str] = set()
    for value in raw_values:
        lowered = value.lower().replace(",", " ")
        tokens.update(part.strip() for part in lowered.split() if part.strip())
    return tokens


def _first_label_part(label: str) -> str:
    return label.split(",", maxsplit=1)[0].strip() or "this municipality"
