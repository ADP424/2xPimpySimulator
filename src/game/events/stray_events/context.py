"""
StrayEventContext and target resolution for stray events.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from src.database import list_matching_stray_pooch_ids

if TYPE_CHECKING:
    from src.database.models.event_types import JsonObject, PoochFilterSpec

# Re-export the model so callers can import from here
from src.game.models import StrayEventContext


async def resolve_stray_target_ids(
    context: StrayEventContext,
    selector: str,
    parameters: JsonObject,
    rng: random.Random,
) -> list[int]:
    """Resolve target stray pooch IDs for an action.

    If "use_saved" is set, IDs are drawn from a context slot instead.
    A "filter" in parameters further narrows the eligible pool.
    """
    use_saved = parameters.get("use_saved")
    if isinstance(use_saved, str) and use_saved:
        slot = context.extra_data.get(use_saved, {})
        if isinstance(slot, dict):
            return list(slot.get("pooch_ids", []))
        return []

    action_filter = parameters.get("filter", {})
    filter_spec: PoochFilterSpec = action_filter if isinstance(action_filter, dict) else {}
    count_param = parameters.get("count")
    count = int(count_param) if isinstance(count_param, int) and count_param > 0 else None

    if filter_spec:
        pool = await list_matching_stray_pooch_ids(context.server_discord_id, filter_spec)
    else:
        pool = list(context.candidate_stray_ids)

    selector = selector.strip().lower()

    if selector == "random":
        if count is not None:
            ids = rng.sample(pool, min(count, len(pool))) if pool else []
        else:
            ids = [rng.choice(pool)] if pool else []
    elif selector == "all":
        ids = pool
    elif selector == "random_exclude":
        if count is not None and count < len(pool):
            excluded = set(rng.sample(pool, count))
            ids = [pid for pid in pool if pid not in excluded]
        else:
            ids = []
    elif selector == "all_exclude":
        all_stray_ids = await list_matching_stray_pooch_ids(context.server_discord_id, {})
        matched = set(pool)
        ids = [pid for pid in all_stray_ids if pid not in matched]
    else:
        ids = []

    save_as = parameters.get("save_as")
    if isinstance(save_as, str) and save_as:
        slot: dict = {"pooch_ids": ids}
        if parameters.get("save_owner"):
            from src.database import get_pooch_by_id as _get_pooch_by_id

            owner_ids: list[int] = []
            for pid in ids:
                pooch = await _get_pooch_by_id(pid)
                if pooch is not None and pooch.owner_discord_id not in owner_ids:
                    owner_ids.append(pooch.owner_discord_id)
            slot["owner_ids"] = owner_ids
        context.extra_data[save_as] = slot

    return ids
