import os
from typing import Any


async def fetch_reddit_context() -> dict[str, Any]:
    required = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"]
    if not all(os.getenv(name) for name in required):
        return {}
    return {}
