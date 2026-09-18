from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from backend.models import AnalyzeRequest, GeographyContext, Place


@dataclass(frozen=True)
class SourceContext:
    request: AnalyzeRequest
    place: Place
    geography: GeographyContext | None = None


@dataclass(frozen=True)
class SourceResult:
    data: dict[str, Any]
    message: str | None = None
    updated_at: str | None = None
    edition: str | None = None
    scope: str | None = None
    source_url: str | None = None
    stale: bool | None = None


SourceFetcher = Callable[..., Awaitable[dict[str, Any] | SourceResult | None]]
