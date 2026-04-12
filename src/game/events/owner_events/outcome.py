from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.database.models import EventOption, EventOutcome
    from src.game.models import OwnerEventContext

from src.game.events.outcome import choose_weighted_outcome


def _make_resolver(context: "OwnerEventContext", rng: random.Random):
    """Return a pooch ID resolver for the owner event context."""

    def resolve(selector: str) -> Optional[int]:
        if selector == "random":
            return rng.choice(context.affected_pooch_ids) if context.affected_pooch_ids else None
        slot = context.extra_data.get(selector)
        if isinstance(slot, dict):
            ids = slot.get("pooch_ids", [])
            return ids[0] if ids else None
        return None

    return resolve


async def choose_option_outcome(
    option: "EventOption", context: "OwnerEventContext", rng: random.Random
) -> "Optional[EventOutcome]":
    """Pick one outcome using weighted random selection with optional stat-based weighting."""
    return await choose_weighted_outcome(option.outcomes, _make_resolver(context, rng), rng)
