"""
Stray event triggering logic and the daily event check.
"""

from __future__ import annotations

import logging
import random
from typing import Optional

from src.database import (
    get_current_season,
    get_random_eligible_stray_event_for_server,
    get_stray_event_by_name,
    list_matching_stray_pooch_ids,
    list_servers,
    list_strays_for_server,
)
from src.game.constants import STRAY_EVENT_TRIGGER_CHANCE
from src.game.models import StrayEventContext, StrayEventResult

from .actions import choose_stray_event_outcome, execute_stray_event_actions

logger = logging.getLogger(__name__)


async def trigger_stray_event_for_server(
    server_discord_id: int,
    event,
    rng: random.Random,
    season: Optional[str] = None,
) -> Optional[StrayEventResult]:
    """Execute a stray event against the server's stray population."""
    filter_spec = event.filter or {}
    pooch_filters = filter_spec.get("pooches", [])

    if pooch_filters:
        first_filter = {k: v for k, v in pooch_filters[0].items() if k not in {"min_count", "max_count", "description"}}
        candidate_ids = await list_matching_stray_pooch_ids(server_discord_id, first_filter)
    else:
        stray_pooches = await list_strays_for_server(server_discord_id)
        candidate_ids = [p.id for p in stray_pooches]

    if not candidate_ids:
        logger.debug(f"No eligible strays for event '{event.name}' on server {server_discord_id}; skipping")
        return None

    context = StrayEventContext(
        server_discord_id=server_discord_id,
        candidate_stray_ids=list(candidate_ids),
    )

    result = await execute_stray_event_actions(server_discord_id, event.actions, context, rng, season=season)

    selected_outcome = await choose_stray_event_outcome(event, context, rng)
    if selected_outcome is not None:
        outcome_result = await execute_stray_event_actions(
            server_discord_id, selected_outcome.actions, context, rng, season=season
        )
        result.merge(outcome_result)

    logger.info(
        "Stray event '%s' ran on server %s — affected %d pooches",
        event.name,
        server_discord_id,
        len(result.pooches_affected),
    )
    return result


async def run_daily_stray_event_check(
    rng_seed: Optional[int] = None,
) -> dict[int, list[tuple[str, StrayEventResult]]]:
    """Run the daily stray event check for all servers.

    For each alive stray on a server there is a 50% chance of triggering a
    random eligible stray event.
    """
    rng = random.Random(rng_seed) if rng_seed is not None else random.Random()

    servers = await list_servers()
    results: dict[int, list[tuple[str, StrayEventResult]]] = {}
    _season = await get_current_season()

    for server in servers:
        strays = await list_strays_for_server(server.discord_id)
        for _ in strays:
            if rng.random() > STRAY_EVENT_TRIGGER_CHANCE:
                continue

            event = await get_random_eligible_stray_event_for_server(server.discord_id, rng=rng, season=_season)
            if event is None:
                logger.debug(f"No eligible stray events for server {server.discord_id}.")
                continue

            result = await trigger_stray_event_for_server(server.discord_id, event, rng, season=_season)
            if result is not None:
                results.setdefault(server.discord_id, []).append((event.name, result))

    total = sum(len(v) for v in results.values())
    logger.info("Daily stray event check complete. %d event(s) triggered across %d server(s).", total, len(results))
    return results


async def trigger_stray_event_by_name(
    server_discord_id: int,
    name: str,
    rng: Optional[random.Random] = None,
) -> Optional[StrayEventResult]:
    """Trigger a specific stray event by name on a server. Returns None if the event doesn't exist."""
    rng = rng if rng is not None else random.Random()
    event = await get_stray_event_by_name(name)
    if event is None:
        return None
    return await trigger_stray_event_for_server(server_discord_id, event, rng)
