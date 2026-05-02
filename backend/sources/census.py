import os
from typing import Any


async def fetch_census_context() -> dict[str, Any]:
    if not os.getenv("CENSUS_API_KEY"):
        return {}
    return {}
