from __future__ import annotations

from src.database import (
    advance_global_season,
    get_current_season,
)


async def advance_season() -> str:
    """Advance the global season to the next one in the cycle and return the new season name."""
    return await advance_global_season()


async def get_season() -> str:
    """Return the current global season."""
    return await get_current_season()
