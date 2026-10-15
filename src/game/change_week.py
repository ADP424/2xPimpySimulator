from __future__ import annotations

import random
from typing import Optional

from src.logger import get_logger

from .events.server_events import run_weekly_server_event_cycle
from .manage_global import advance_season

logger = get_logger("game/change_week")


async def run_week_change(
    rng: Optional[random.Random] = None,
) -> tuple[dict, list, dict[int, str]]:
    """
    Run all weekly server-level bookkeeping:
    - Advance the global season.
    - Resolve any active major server events and trigger new ones.

    Parameters
    ----------
    rng:
        Optional seeded Random for deterministic event selection.

    Returns
    -------
    tuple[dict[int, TriggeredServerEvent], list[ServerEventResolution], dict[int, str]]
        new_events, resolutions, season_advances — same shape as
        ``run_weekly_server_event_cycle``.
    """
    rng = rng if rng is not None else random.Random()

    logger.info("Running weekly change...")

    new_season = await advance_season()
    logger.info("Season advanced to %s.", new_season)

    new_events, resolutions, season_advances = await run_weekly_server_event_cycle(rng=rng, new_season=new_season)

    logger.info(
        "Week change complete. Season: %s, new events: %d, resolutions: %d.",
        new_season,
        len(new_events),
        len(resolutions),
    )
    return new_events, resolutions, season_advances
