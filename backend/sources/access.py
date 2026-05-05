from typing import Any


async def fetch_access_context() -> dict[str, Any]:
    return {
        "walkability": 50,
        "transit_access": 50,
        "daily_needs": 50,
        "food_social": 50,
        "parks_outdoors": 50,
        "nearby_categories": {
            "groceries": 0,
            "parks": 0,
            "restaurants": 0,
            "transit": 0,
        },
    }
