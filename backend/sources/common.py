from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from backend.models import AnalyzeRequest, Place


@dataclass(frozen=True)
class SourceContext:
    request: AnalyzeRequest
    place: Place


@dataclass(frozen=True)
class SourceResult:
    data: dict[str, Any]
    message: str | None = None
    updated_at: str | None = None


SourceFetcher = Callable[..., Awaitable[dict[str, Any] | SourceResult | None]]
