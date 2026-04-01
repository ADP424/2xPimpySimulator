"""
Shared weighted outcome selection logic used by all three event systems.

Outcomes are partitioned into three groups:
- Fixed: explicit ``chance`` with no ``stat_weights`` — reserved probability, unchanged.
- Dynamic: have ``stat_weights`` (optionally also a base ``chance``) — compete for the
  remaining probability share after fixed outcomes are subtracted.
- Implicit: no ``chance`` and no ``stat_weights`` — treated as weight-1 entries in the
  dynamic pool.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Optional

from src.database import (
    get_pooch_aggressiveness,
    get_pooch_base_health,
    get_pooch_constitution,
    get_pooch_cuteness,
    get_pooch_dexterity,
    get_pooch_fertility,
    get_pooch_fluffiness,
    get_pooch_intelligence,
    get_pooch_size,
    get_pooch_strength,
)

logger = logging.getLogger(__name__)

_STAT_GETTERS = {
    "strength": get_pooch_strength,
    "cuteness": get_pooch_cuteness,
    "fluffiness": get_pooch_fluffiness,
    "intelligence": get_pooch_intelligence,
    "dexterity": get_pooch_dexterity,
    "fertility": get_pooch_fertility,
    "aggressiveness": get_pooch_aggressiveness,
    "constitution": get_pooch_constitution,
    "base_health": get_pooch_base_health,
}


async def get_effective_pooch_stat(stat: str, pooch_id: int) -> Optional[float]:
    """Return the effective value of a named stat for a pooch. Returns None if stat is unknown."""
    if stat == "size":
        result = await get_pooch_size(pooch_id)
        return float(result) if result is not None else 10.0
    getter = _STAT_GETTERS.get(stat)
    if getter is None:
        return None
    result = await getter(pooch_id)
    return float(result) if result is not None else None


async def compute_outcome_stat_multiplier(
    stat_weights: list,
    resolve_pooch_id: Any,  # callable(selector: str) -> Optional[int]
    rng: random.Random,
) -> float:
    """Compute the combined stat multiplier for a weighted outcome.

    ``resolve_pooch_id`` is a callable that takes a selector string and returns
    a pooch ID (or None). Each event system passes its own context-aware resolver.
    """
    multiplier = 1.0
    for entry in stat_weights:
        if not isinstance(entry, dict):
            continue
        stat = str(entry.get("stat", "")).strip().lower()
        selector = str(entry.get("pooch", "random")).strip().lower()
        scale = float(entry.get("scale", 0.0))
        pivot = float(entry.get("pivot", 10.0))
        direction = float(entry.get("direction", 1.0))

        pooch_id = resolve_pooch_id(selector)
        if pooch_id is None:
            continue

        effective = await get_effective_pooch_stat(stat, pooch_id)
        if effective is None:
            logger.warning(f"stat_weights: unknown stat '{stat}'; skipping entry")
            continue

        entry_mult = 1.0 + (effective - pivot) * scale * direction
        multiplier *= max(0.0, entry_mult)
    return multiplier


async def choose_weighted_outcome(
    outcomes: list,
    resolve_pooch_id: Any,  # callable(selector: str) -> Optional[int]
    rng: random.Random,
) -> Optional[Any]:
    """Pick one outcome from a list using weighted random selection with optional stat-based weighting.

    Works with any outcome objects that have: ``.chance``, ``.stat_weights`` attributes.
    Used by stray events (StrayEventOutcome), owner events (EventOutcome), and server events.
    """
    if not outcomes:
        return None

    fixed = [o for o in outcomes if o.chance is not None and not o.stat_weights]
    dynamic = [o for o in outcomes if o.stat_weights or o.chance is None]

    if not dynamic:
        # All outcomes are fixed — standard weighted roll
        roll = rng.random()
        cumulative = 0.0
        for o in fixed:
            cumulative += float(o.chance)
            if roll < cumulative:
                return o
        return fixed[-1]

    fixed_total = sum(float(o.chance) for o in fixed)
    remaining = max(0.0, 1.0 - fixed_total)

    raw_scores: list[float] = []
    for o in dynamic:
        if o.stat_weights:
            base = float(o.chance) if o.chance is not None else 1.0
            multiplier = await compute_outcome_stat_multiplier(o.stat_weights, resolve_pooch_id, rng)
            raw_scores.append(max(0.0, base * multiplier))
        else:
            raw_scores.append(1.0)

    raw_sum = sum(raw_scores)
    if raw_sum <= 0:
        return rng.choice(outcomes)

    entries: list[tuple[Any, float]] = []
    for o, raw in zip(dynamic, raw_scores):
        entries.append((o, (raw / raw_sum) * remaining))
    for o in fixed:
        entries.append((o, float(o.chance)))

    roll = rng.random()
    cumulative = 0.0
    for outcome, weight in entries:
        cumulative += weight
        if roll < cumulative:
            return outcome
    return entries[-1][0]
