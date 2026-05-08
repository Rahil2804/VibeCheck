from backend.sources.common import SourceContext, SourceResult


async def fetch_toronto_context(_context: SourceContext) -> SourceResult:
    return SourceResult(
        data={},
        message="Toronto local open-data adapter is configured but returned no usable data.",
    )
