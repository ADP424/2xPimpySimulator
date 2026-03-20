import random
from typing import TYPE_CHECKING, Any

from src.database import (
    get_pooch_kennel,
    get_random_matching_kennel_id,
    list_matching_kennel_ids,
    list_matching_pooch_ids,
    list_matching_pooch_ids_in_kennel,
)

if TYPE_CHECKING:
    from ..models import OwnerEventContext


async def get_target_pooch_ids(
    owner_discord_id: int,
    context: "OwnerEventContext",
    rng: random.Random,
    target_type: str,
    selector: str,
    parameters: dict[str, Any],
) -> list[int]:
    """Resolve the list of pooch IDs that an owner event action should target.

    Handles all target_type / selector combinations for pooch actions, including
    kennel-scoped resolution (``target_type="kennel"``), ``use_saved`` slot reads,
    ``pooch_selector`` / ``pooch_count`` sub-selection within kennels, and writing
    the result into a named ``save_as`` slot.

    Parameters
    ----------
    owner_discord_id:
        Discord ID of the owner whose pooches/kennels are searched.
    context:
        The active event context; used for ``selected_*`` IDs and named slot storage.
    rng:
        Seeded random instance for all random selections.
    target_type:
        One of ``"pooch"``, ``"kennel"``, or ``"owner"``.
    selector:
        One of ``"random"``, ``"selected"``, ``"all"``, ``"random_exclude"``, ``"all_exclude"``.
    parameters:
        The raw action parameters dict from the event JSON.

    Returns
    -------
    list[int]
        Resolved pooch IDs to act on (may be empty).
    """
    action_filter = parameters.get("filter", {})
    filter_spec = action_filter if isinstance(action_filter, dict) else {}
    count_param = parameters.get("count")
    count = int(count_param) if isinstance(count_param, int) and count_param > 0 else None

    # _exclude_ids: internal list of pooch IDs to exclude from random resolution (used by exclude_claimed preflight)
    exclude_ids_raw = parameters.get("_exclude_ids", [])
    exclude_ids: set[int] = set(exclude_ids_raw) if isinstance(exclude_ids_raw, list) else set()

    # use_saved: pull IDs from a named slot
    use_saved = parameters.get("use_saved")
    if isinstance(use_saved, str) and use_saved:
        slot = context.extra_data.get(use_saved, {})
        if not isinstance(slot, dict):
            return []
        if target_type == "kennel":
            # Slot stores kennel_ids; enumerate pooches within those kennels
            saved_kennel_ids = list(slot.get("kennel_ids", []))
            pooch_filter_raw = parameters.get("pooch_filter", {})
            pooch_filter = pooch_filter_raw if isinstance(pooch_filter_raw, dict) else {}
            pooch_ids: list[int] = []
            for kid in saved_kennel_ids:
                pooch_ids.extend(await list_matching_pooch_ids_in_kennel(owner_discord_id, kid, pooch_filter))
            return pooch_ids
        return list(slot.get("pooch_ids", []))

    if target_type == "owner":
        pooch_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
        if exclude_ids:
            pooch_ids = [pid for pid in pooch_ids if pid not in exclude_ids]
    elif target_type == "pooch":
        if selector == "selected":
            pooch_ids = [context.selected_pooch_id] if context.selected_pooch_id else []
        elif selector == "random":
            all_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
            if exclude_ids:
                all_ids = [pid for pid in all_ids if pid not in exclude_ids]
            if count is not None:
                pooch_ids = rng.sample(all_ids, min(count, len(all_ids))) if all_ids else []
            else:
                pooch_ids = [rng.choice(all_ids)] if all_ids else []
        elif selector == "all":
            all_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
            pooch_ids = [pid for pid in all_ids if pid not in exclude_ids] if exclude_ids else all_ids
        elif selector == "random_exclude":
            all_ids = await list_matching_pooch_ids(owner_discord_id, filter_spec)
            if exclude_ids:
                all_ids = [pid for pid in all_ids if pid not in exclude_ids]
            if count is not None and count < len(all_ids):
                excluded = set(rng.sample(all_ids, count))
                pooch_ids = [pid for pid in all_ids if pid not in excluded]
            else:
                pooch_ids = []
        elif selector == "all_exclude":
            # "all_exclude" with a filter: targets every pooch NOT matched by the filter
            all_owner_ids = await list_matching_pooch_ids(owner_discord_id, {})
            matched_ids = set(await list_matching_pooch_ids(owner_discord_id, filter_spec))
            pooch_ids = [pid for pid in all_owner_ids if pid not in matched_ids]
            if exclude_ids:
                pooch_ids = [pid for pid in pooch_ids if pid not in exclude_ids]
        else:
            pooch_ids = []
    else:
        # target_type == "kennel": resolve kennel(s), then return all pooches in them
        kennel_filter = filter_spec
        pooch_filter_raw = parameters.get("pooch_filter", {})
        pooch_filter = pooch_filter_raw if isinstance(pooch_filter_raw, dict) else {}

        if selector == "selected":
            kennel_ids = [context.selected_kennel_id] if context.selected_kennel_id else []
        elif selector == "random":
            all_kennel_ids = await list_matching_kennel_ids(owner_discord_id, kennel_filter)
            if count is not None:
                kennel_ids = rng.sample(all_kennel_ids, min(count, len(all_kennel_ids))) if all_kennel_ids else []
            else:
                kennel_id = await get_random_matching_kennel_id(owner_discord_id, kennel_filter, rng)
                kennel_ids = [kennel_id] if kennel_id is not None else []
        elif selector == "all":
            kennel_ids = await list_matching_kennel_ids(owner_discord_id, kennel_filter)
        elif selector == "random_exclude":
            all_kennel_ids = await list_matching_kennel_ids(owner_discord_id, kennel_filter)
            if count is not None and count < len(all_kennel_ids):
                excluded = set(rng.sample(all_kennel_ids, count))
                kennel_ids = [kid for kid in all_kennel_ids if kid not in excluded]
            else:
                kennel_ids = []
        elif selector == "all_exclude":
            # targets every kennel NOT matched by the filter
            all_owner_kennel_ids = await list_matching_kennel_ids(owner_discord_id, {})
            matched_kennel_ids = set(await list_matching_kennel_ids(owner_discord_id, kennel_filter))
            kennel_ids = [kid for kid in all_owner_kennel_ids if kid not in matched_kennel_ids]
        else:
            kennel_ids = []

        # pooch_selector/pooch_count: control which pooches within the resolved kennels are targeted
        raw_pooch_selector = parameters.get("pooch_selector")
        pooch_selector = str(raw_pooch_selector).strip().lower() if isinstance(raw_pooch_selector, str) else None
        pooch_count_raw = parameters.get("pooch_count")
        pooch_count = int(pooch_count_raw) if isinstance(pooch_count_raw, int) and pooch_count_raw > 0 else None

        pooch_ids = []
        for kennel_id in kennel_ids:
            kennel_pooches = await list_matching_pooch_ids_in_kennel(owner_discord_id, kennel_id, pooch_filter)
            if pooch_selector == "random":
                n = pooch_count if pooch_count is not None else 1
                pooch_ids.extend(rng.sample(kennel_pooches, min(n, len(kennel_pooches))) if kennel_pooches else [])
            elif pooch_selector == "random_exclude":
                n = pooch_count if pooch_count is not None else 1
                if n < len(kennel_pooches):
                    excluded = set(rng.sample(kennel_pooches, n))
                    pooch_ids.extend(pid for pid in kennel_pooches if pid not in excluded)
                # if count >= len, nothing survives the exclusion — pooch_ids stays empty for this kennel
            else:
                pooch_ids.extend(kennel_pooches)

    # save_as: store resolved IDs (and optionally kennel IDs) into a named slot
    save_as = parameters.get("save_as")
    if isinstance(save_as, str) and save_as:
        slot: dict[str, Any] = {"pooch_ids": pooch_ids}
        if parameters.get("save_kennel"):
            kennel_ids_for_slot: list[int] = []
            for pid in pooch_ids:
                kennel = await get_pooch_kennel(pid)
                if kennel is not None and kennel.id not in kennel_ids_for_slot:
                    kennel_ids_for_slot.append(kennel.id)
            slot["kennel_ids"] = kennel_ids_for_slot
        context.extra_data[save_as] = slot

    return pooch_ids


async def get_target_kennel_ids(
    owner_discord_id: int,
    context: "OwnerEventContext",
    rng: random.Random,
    target_type: str,
    selector: str,
    parameters: dict[str, Any],
) -> list[int]:
    """Resolve the list of kennel IDs that an owner event action should target.

    Handles all target_type / selector combinations for kennel actions, including
    ``use_saved`` slot reads and writing the result into a named ``save_as`` slot.

    Parameters
    ----------
    owner_discord_id:
        Discord ID of the owner whose kennels are searched.
    context:
        The active event context; used for ``selected_kennel_id`` and named slot storage.
    rng:
        Seeded random instance for all random selections.
    target_type:
        ``"owner"`` targets all owner kennels; any other value uses ``selector``.
    selector:
        One of ``"random"``, ``"selected"``, ``"all"``, ``"random_exclude"``, ``"all_exclude"``.
    parameters:
        The raw action parameters dict from the event JSON.

    Returns
    -------
    list[int]
        Resolved kennel IDs to act on (may be empty).
    """
    action_filter = parameters.get("filter", {})
    filter_spec = action_filter if isinstance(action_filter, dict) else {}
    count_param = parameters.get("count")
    count = int(count_param) if isinstance(count_param, int) and count_param > 0 else None

    # use_saved: pull kennel IDs from a named slot
    use_saved = parameters.get("use_saved")
    if isinstance(use_saved, str) and use_saved:
        slot = context.extra_data.get(use_saved, {})
        return list(slot.get("kennel_ids", [])) if isinstance(slot, dict) else []

    if target_type == "owner":
        kennel_ids = await list_matching_kennel_ids(owner_discord_id, filter_spec)
    elif selector == "selected":
        kennel_ids = [context.selected_kennel_id] if context.selected_kennel_id else []
    elif selector == "random":
        all_kennel_ids = await list_matching_kennel_ids(owner_discord_id, filter_spec)
        if count is not None:
            kennel_ids = rng.sample(all_kennel_ids, min(count, len(all_kennel_ids))) if all_kennel_ids else []
        else:
            kennel_id = await get_random_matching_kennel_id(owner_discord_id, filter_spec, rng)
            kennel_ids = [kennel_id] if kennel_id is not None else []
    elif selector == "all":
        kennel_ids = await list_matching_kennel_ids(owner_discord_id, filter_spec)
    elif selector == "random_exclude":
        all_kennel_ids = await list_matching_kennel_ids(owner_discord_id, filter_spec)
        if count is not None and count < len(all_kennel_ids):
            excluded = set(rng.sample(all_kennel_ids, count))
            kennel_ids = [kid for kid in all_kennel_ids if kid not in excluded]
        else:
            kennel_ids = []
    elif selector == "all_exclude":
        all_owner_kennel_ids = await list_matching_kennel_ids(owner_discord_id, {})
        matched_kennel_ids = set(await list_matching_kennel_ids(owner_discord_id, filter_spec))
        kennel_ids = [kid for kid in all_owner_kennel_ids if kid not in matched_kennel_ids]
    else:
        kennel_ids = []

    # save_as: store resolved kennel IDs into a named slot
    save_as = parameters.get("save_as")
    if isinstance(save_as, str) and save_as:
        context.extra_data[save_as] = {"kennel_ids": kennel_ids}

    return kennel_ids
