from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Optional

from src.database import (
    add_mutation_to_pooch,
    add_pooch_breeds,
    add_pooch_to_kennel,
    add_pooch_to_strays,
    add_pooch_to_vendor_stock,
    create_pooch,
    get_pooch_aggressiveness,
    get_pooch_base_health,
    get_pooch_by_id,
    get_pooch_constitution,
    get_pooch_cuteness,
    get_pooch_dexterity,
    get_pooch_fertility,
    get_pooch_fluffiness,
    get_pooch_intelligence,
    get_pooch_size,
    get_pooch_strength,
    get_random_breed_ids,
    get_random_eligible_stray_event_for_server,
    get_stray_event_by_name,
    list_kennels_for_owner,
    list_matching_stray_pooch_ids,
    list_owners,
    list_pooch_breed_weights,
    list_pooch_mutations,
    list_pooches_for_kennel,
    list_servers,
    list_strays_for_server,
    list_vendors,
    modify_pooch_age,
    modify_pooch_base_health,
    remove_pooch_from_strays,
    rename_pooch,
    revive_pooch,
    set_pooch_breeding_cooldown,
    transfer_pooch_to_owner,
    transfer_pooch_to_vendor,
)

from .action_helpers.pooch_actions import (
    handle_add_breed,
    handle_add_mutation_by_name,
    handle_damn_pooch,
    handle_kill_pooch,
    handle_modify_age,
    handle_modify_breeding_cooldown,
    handle_modify_health,
    handle_modify_stat,
    handle_remove_breed,
    handle_remove_mutation_by_name,
    handle_rename_pooch,
)
from .breeding import breed_pooches as _breed_pooches
from .constants import STRAY_EVENT_TRIGGER_CHANCE
from .models import StrayEventContext, StrayEventResult

if TYPE_CHECKING:
    from src.database.models import StrayEvent, StrayEventAction, StrayEventOutcome
    from src.database.models.event_types import JsonObject, PoochFilterSpec

logger = logging.getLogger(__name__)


async def _resolve_stray_target_ids(
    context: StrayEventContext,
    selector: str,
    parameters: JsonObject,
    rng: random.Random,
) -> list[int]:
    """
    Resolve target stray pooch IDs for an action.

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

    # Build the candidate pool from strays matching the action-level filter
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
        # All strays NOT matched by the action filter
        all_stray_ids = await list_matching_stray_pooch_ids(context.server_discord_id, {})
        matched = set(pool)
        ids = [pid for pid in all_stray_ids if pid not in matched]
    else:
        ids = []

    # save_as
    save_as = parameters.get("save_as")
    if isinstance(save_as, str) and save_as:
        context.extra_data[save_as] = {"pooch_ids": ids}

    return ids


async def _deliver_stray_to_kennel(pooch_id: int, server_discord_id: int, rng: random.Random) -> bool:
    """
    Remove a pooch from strays and place it in a random kennel with free space.
    Returns True on success.
    """
    owners = await list_owners()
    # Shuffle to pick a random owner first
    rng.shuffle(owners)
    for owner in owners:
        kennels = await list_kennels_for_owner(owner.discord_id)
        for kennel in kennels:
            pooches_in = await list_pooches_for_kennel(kennel.id)
            if len(pooches_in) < kennel.pooch_limit:
                await remove_pooch_from_strays(pooch_id)
                await transfer_pooch_to_owner(pooch_id, owner.discord_id)
                await add_pooch_to_kennel(kennel.id, pooch_id)
                return True
    return False


async def _deliver_stray_to_vendor(pooch_id: int, server_discord_id: int, rng: random.Random) -> bool:
    """
    Remove a pooch from strays, assign it to a random vendor on the server,
    and add it to that vendor's stock.  Returns True on success.
    """
    vendors = await list_vendors(server_discord_id)
    if not vendors:
        return False
    vendor = rng.choice(vendors)
    await remove_pooch_from_strays(pooch_id)
    await transfer_pooch_to_vendor(pooch_id, vendor.id)
    await add_pooch_to_vendor_stock(vendor.id, pooch_id)
    return True


async def _execute_single_stray_action(
    server_discord_id: int,
    action: StrayEventAction,
    context: StrayEventContext,
    rng: random.Random,
) -> StrayEventResult:
    result = StrayEventResult()
    action_type: str = action.action_type
    parameters: JsonObject = action.parameters

    raw_selector = parameters.get("selector", "random")
    selector = str(raw_selector).strip().lower() if isinstance(raw_selector, str) else "random"

    try:
        if action_type in ("modify_base_health", "modify_pooch_health"):
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_modify_health(pooch_ids, parameters, rng, result)

        elif action_type == "modify_pooch_age":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_modify_age(pooch_ids, parameters, rng, result)

        elif action_type == "kill_pooch":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_kill_pooch(pooch_ids, parameters, rng, result)
            for pooch_id in result.pooches_killed:
                if pooch_id in context.candidate_stray_ids:
                    context.candidate_stray_ids.remove(pooch_id)

        elif action_type == "add_mutation":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_add_mutation_by_name(pooch_ids, parameters, rng, result)

        elif action_type == "remove_mutation":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_remove_mutation_by_name(pooch_ids, parameters, rng, result)

        elif action_type == "add_breed":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_add_breed(pooch_ids, parameters, rng, result)

        elif action_type == "remove_breed":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_remove_breed(pooch_ids, parameters, rng, result)

        elif action_type == "rename_pooch":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_rename_pooch(pooch_ids, parameters, rng, result)

        elif action_type in ("modify_breeding_cooldown", "set_breeding_cooldown"):
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_modify_breeding_cooldown(pooch_ids, parameters, rng, result)

        elif action_type in (
            "modify_strength",
            "modify_cuteness",
            "modify_fluffiness",
            "modify_intelligence",
            "modify_dexterity",
            "modify_fertility",
            "modify_aggressiveness",
            "modify_constitution",
        ):
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_modify_stat(action_type, pooch_ids, parameters, rng, result)

        elif action_type == "damn_pooch":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_damn_pooch(pooch_ids, parameters, rng, result, context, "candidate_stray_ids")

        elif action_type == "revive_pooch":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            destination = str(parameters.get("destination", "stray")).strip().lower()
            for pooch_id in pooch_ids:
                pooch = await revive_pooch(pooch_id)
                if pooch:
                    if destination == "kennel":
                        placed = await _deliver_stray_to_kennel(pooch_id, server_discord_id, rng)
                        if not placed:
                            await add_pooch_to_strays(pooch_id, server_discord_id)
                            context.candidate_stray_ids.append(pooch_id)
                    elif destination == "vendor":
                        placed = await _deliver_stray_to_vendor(pooch_id, server_discord_id, rng)
                        if not placed:
                            await add_pooch_to_strays(pooch_id, server_discord_id)
                            context.candidate_stray_ids.append(pooch_id)
                    else:
                        # "stray" or anything else — put back in strays
                        await add_pooch_to_strays(pooch_id, server_discord_id)
                        context.candidate_stray_ids.append(pooch_id)
                    result.pooches_affected.append(pooch_id)

        elif action_type == "create_pooch":
            kwargs: dict[str, object] = {"rng": rng}
            for key in (
                "name",
                "sex",
                "age",
                "base_health",
                "strength",
                "cuteness",
                "fluffiness",
                "intelligence",
                "dexterity",
                "fertility",
                "aggressiveness",
                "constitution",
                "breeding_cooldown",
            ):
                if key in parameters:
                    kwargs[key] = parameters[key]
            breeds_param = parameters.get("breeds")
            if isinstance(breeds_param, list):
                kwargs["breeds"] = breeds_param
            elif isinstance(breeds_param, int) and breeds_param > 0:
                kwargs["breeds"] = await get_random_breed_ids(breeds_param, rng=rng)

            mutations_param = parameters.get("mutations")
            if isinstance(mutations_param, list):
                kwargs["mutations"] = mutations_param

            pooch = await create_pooch(**kwargs)

            if pooch and isinstance(mutations_param, int) and mutations_param > 0:
                for _ in range(mutations_param):
                    await add_mutation_to_pooch(pooch.id, rng=rng)

            if pooch:
                # New pooch goes into the stray pool of this server
                await add_pooch_to_strays(pooch.id, server_discord_id)
                context.candidate_stray_ids.append(pooch.id)
                result.pooches_created.append(pooch.id)
                save_as = parameters.get("save_as")
                if isinstance(save_as, str) and save_as:
                    context.extra_data[save_as] = {"pooch_ids": [pooch.id]}

        elif action_type == "clone_pooch":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            source_id = pooch_ids[0] if pooch_ids else None
            if source_id is None:
                logger.warning("stray clone_pooch: no source pooch resolved; skipping")
            else:
                source = await get_pooch_by_id(source_id)
                if source is None:
                    logger.warning(f"stray clone_pooch: source {source_id} not found; skipping")
                else:
                    clone_kwargs: dict[str, object] = {
                        "rng": rng,
                        "name": parameters.get("name", source.name),
                        "sex": parameters.get("sex", source.sex),
                        "age": parameters.get("age", source.age),
                        "base_health": parameters.get("base_health", source.base_health),
                        "strength": parameters.get("strength", source.strength),
                        "cuteness": parameters.get("cuteness", source.cuteness),
                        "fluffiness": parameters.get("fluffiness", source.fluffiness),
                        "intelligence": parameters.get("intelligence", source.intelligence),
                        "dexterity": parameters.get("dexterity", source.dexterity),
                        "fertility": parameters.get("fertility", source.fertility),
                        "aggressiveness": parameters.get("aggressiveness", source.aggressiveness),
                        "constitution": parameters.get("constitution", source.constitution),
                        "breeding_cooldown": parameters.get("breeding_cooldown", source.breeding_cooldown),
                    }
                    clone = await create_pooch(**clone_kwargs)
                    if clone:
                        breed_weights = await list_pooch_breed_weights(source_id)
                        if breed_weights:
                            await add_pooch_breeds(clone.id, dict(breed_weights))
                        for mut in await list_pooch_mutations(source_id):
                            await add_mutation_to_pooch(clone.id, mutation_id=mut.id)
                        await add_pooch_to_strays(clone.id, server_discord_id)
                        context.candidate_stray_ids.append(clone.id)
                        result.pooches_created.append(clone.id)

                        save_as_raw = parameters.get("save_as")
                        if save_as_raw is not None:
                            if isinstance(save_as_raw, str):
                                specs: list[dict[str, str]] = [{"slot": save_as_raw, "target": "clone"}]
                            elif isinstance(save_as_raw, list):
                                specs = [s for s in save_as_raw if isinstance(s, dict)]
                            else:
                                specs = []
                            for spec in specs:
                                slot = spec.get("slot")
                                target = spec.get("target", "clone")
                                if not isinstance(slot, str) or not slot:
                                    continue
                                if target == "source":
                                    context.extra_data[slot] = {"pooch_ids": [source_id]}
                                else:
                                    context.extra_data[slot] = {"pooch_ids": [clone.id]}

        elif action_type == "breed_pooches":
            first_filter = parameters.get("first_filter", {})
            if not isinstance(first_filter, dict):
                first_filter = {}
            second_filter = parameters.get("second_filter", {})
            if not isinstance(second_filter, dict):
                second_filter = {}

            pool_first = (
                await list_matching_stray_pooch_ids(server_discord_id, first_filter)
                if first_filter
                else list(context.candidate_stray_ids)
            )
            pool_second = (
                await list_matching_stray_pooch_ids(server_discord_id, second_filter)
                if second_filter
                else list(context.candidate_stray_ids)
            )

            require_unique = bool(parameters.get("require_unique", True))
            require_same = bool(parameters.get("require_same", False))

            first_id: Optional[int] = rng.choice(pool_first) if pool_first else None

            if require_same:
                second_id: Optional[int] = first_id
            else:
                pool_s = [pid for pid in pool_second if pid != first_id] if require_unique else pool_second
                second_id = rng.choice(pool_s) if pool_s else None

            if first_id is None or second_id is None:
                logger.warning("stray breed_pooches: could not resolve one or both parents; skipping")
            else:
                try:
                    baby_ids = await _breed_pooches(
                        first_id, second_id, rng_seed=rng.randint(0, 2**31), skip_validation=True
                    )
                    for baby_id in baby_ids:
                        await add_pooch_to_strays(baby_id, server_discord_id)
                        context.candidate_stray_ids.append(baby_id)
                        if "baby_name" in parameters:
                            await rename_pooch(baby_id, str(parameters["baby_name"]))
                        if "baby_age" in parameters:
                            await modify_pooch_age(baby_id, parameters["baby_age"])
                        if "baby_base_health" in parameters:
                            await modify_pooch_base_health(baby_id, parameters["baby_base_health"])
                        if "baby_breeding_cooldown" in parameters:
                            await set_pooch_breeding_cooldown(baby_id, parameters["baby_breeding_cooldown"])
                    result.pooches_created.extend(baby_ids)

                    save_as_raw = parameters.get("save_as")
                    if save_as_raw is not None:
                        if isinstance(save_as_raw, str):
                            specs = [{"slot": save_as_raw, "target": "baby"}]
                        elif isinstance(save_as_raw, list):
                            specs = [s for s in save_as_raw if isinstance(s, dict)]
                        else:
                            specs = []
                        for spec in specs:
                            slot = spec.get("slot")
                            target = spec.get("target", "baby")
                            if not isinstance(slot, str) or not slot:
                                continue
                            if target == "first_parent":
                                context.extra_data[slot] = {"pooch_ids": [first_id]}
                            elif target == "second_parent":
                                context.extra_data[slot] = {"pooch_ids": [second_id]}
                            else:
                                context.extra_data[slot] = {"pooch_ids": list(baby_ids)}

                except ValueError as exc:
                    logger.warning(f"stray breed_pooches: breeding failed — {exc}")

        elif action_type == "enter_kennel":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            for pooch_id in pooch_ids:
                placed = await _deliver_stray_to_kennel(pooch_id, server_discord_id, rng)
                if placed:
                    result.pooches_affected.append(pooch_id)
                    if pooch_id in context.candidate_stray_ids:
                        context.candidate_stray_ids.remove(pooch_id)
                else:
                    logger.debug(f"enter_kennel: no free kennel space for pooch {pooch_id}; left as stray")

        elif action_type == "enter_vendor_stock":
            pooch_ids = await _resolve_stray_target_ids(context, selector, parameters, rng)
            for pooch_id in pooch_ids:
                placed = await _deliver_stray_to_vendor(pooch_id, server_discord_id, rng)
                if placed:
                    result.pooches_affected.append(pooch_id)
                    if pooch_id in context.candidate_stray_ids:
                        context.candidate_stray_ids.remove(pooch_id)
                else:
                    logger.debug(f"enter_vendor_stock: no vendor found for server {server_discord_id}")

        elif action_type == "start_stray_event":
            event_name = parameters.get("event")
            if isinstance(event_name, str) and event_name.strip():
                followup = await get_stray_event_by_name(event_name.strip())
                if followup is None:
                    logger.warning(f"start_stray_event: unknown stray event '{event_name}'; skipping")
                else:
                    followup_result = await _execute_stray_event_actions(
                        server_discord_id, followup.actions, context, rng
                    )
                    result.merge(followup_result)
                    followup_outcome = await _choose_stray_event_outcome(followup, context, rng)
                    if followup_outcome is not None:
                        outcome_result = await _execute_stray_event_actions(
                            server_discord_id, followup_outcome.actions, context, rng
                        )
                        result.merge(outcome_result)

        elif action_type == "select_pooch":
            # Resolves and saves pooches into a named slot; no other side effects
            await _resolve_stray_target_ids(context, selector, parameters, rng)

        else:
            logger.warning(f"Unknown stray action type: {action_type}")

    except Exception as exc:
        logger.error(f"Error executing stray action '{action_type}': {exc}", exc_info=True)
        result.success = False

    return result


async def _execute_stray_event_actions(
    server_discord_id: int,
    actions: list[StrayEventAction],
    context: StrayEventContext,
    rng: random.Random,
) -> StrayEventResult:
    result = StrayEventResult()
    for action in sorted(actions, key=lambda a: a.action_order):
        repeat = max(int(action.repeat), 1) if isinstance(action.repeat, int) else 1
        for _ in range(repeat):
            action_result = await _execute_single_stray_action(server_discord_id, action, context, rng)
            result.merge(action_result)
    return result


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


def _resolve_single_stat_pooch_id(
    selector: str,
    context: "StrayEventContext",
    rng: random.Random,
) -> Optional[int]:
    """Resolve a single pooch ID for a stat_weights entry selector."""
    if selector == "random":
        return rng.choice(context.candidate_stray_ids) if context.candidate_stray_ids else None
    slot = context.extra_data.get(selector)
    if isinstance(slot, dict):
        ids = slot.get("pooch_ids", [])
        return ids[0] if ids else None
    return None


async def _get_effective_pooch_stat(stat: str, pooch_id: int) -> Optional[float]:
    """Return the effective value of a named stat for a pooch. Returns None if stat is unknown."""
    if stat == "size":
        result = await get_pooch_size(pooch_id)
        return float(result) if result is not None else 10.0
    getter = _STAT_GETTERS.get(stat)
    if getter is None:
        return None
    result = await getter(pooch_id)
    return float(result) if result is not None else None


async def _compute_outcome_stat_multiplier(
    stat_weights: list,
    context: "StrayEventContext",
    rng: random.Random,
) -> float:
    """Compute the combined stat multiplier for a weighted outcome."""
    multiplier = 1.0
    for entry in stat_weights:
        if not isinstance(entry, dict):
            continue
        stat = str(entry.get("stat", "")).strip().lower()
        selector = str(entry.get("pooch", "random")).strip().lower()
        scale = float(entry.get("scale", 0.0))
        pivot = float(entry.get("pivot", 10.0))
        direction = float(entry.get("direction", 1.0))

        pooch_id = _resolve_single_stat_pooch_id(selector, context, rng)
        if pooch_id is None:
            continue

        effective = await _get_effective_pooch_stat(stat, pooch_id)
        if effective is None:
            logger.warning(f"stat_weights: unknown stat '{stat}'; skipping entry")
            continue

        entry_mult = 1.0 + (effective - pivot) * scale * direction
        multiplier *= max(0.0, entry_mult)
    return multiplier


async def _choose_stray_event_outcome(
    event: "StrayEvent",
    context: "StrayEventContext",
    rng: random.Random,
) -> "Optional[StrayEventOutcome]":
    """Pick one outcome from the event's outcomes list using weighted random selection.

    Outcomes are partitioned into three groups:
    - Fixed: explicit ``chance`` with no ``stat_weights`` — reserved probability, unchanged.
    - Weighted: have ``stat_weights`` (optionally also a base ``chance``) — compete for the
      remaining probability share after fixed outcomes are subtracted.
    - Implicit: no ``chance`` and no ``stat_weights`` — treated as weight-1 entries in the
      weighted pool.
    """
    if not event.outcomes:
        return None

    fixed = [o for o in event.outcomes if o.chance is not None and not o.stat_weights]
    dynamic = [o for o in event.outcomes if o.stat_weights or o.chance is None]

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

    # Compute raw scores for the dynamic pool
    raw_scores: list[float] = []
    for o in dynamic:
        if o.stat_weights:
            base = float(o.chance) if o.chance is not None else 1.0
            multiplier = await _compute_outcome_stat_multiplier(o.stat_weights, context, rng)
            raw_scores.append(max(0.0, base * multiplier))
        else:
            # Implicit: weight 1.0
            raw_scores.append(1.0)

    raw_sum = sum(raw_scores)
    if raw_sum <= 0:
        # All dynamic outcomes cancelled out — fall back to fixed or random
        return rng.choice(event.outcomes)

    # Build final probability table
    entries: list[tuple["StrayEventOutcome", float]] = []
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


async def _trigger_stray_event_for_server(
    server_discord_id: int,
    event: StrayEvent,
    rng: random.Random,
) -> Optional[StrayEventResult]:
    """
    Execute a stray event against the server's stray population.

    The event's top-level filter narrows which strays are in the initial
    candidate pool; event actions can further refine their targets.
    """
    filter_spec: JsonObject = event.filter or {}
    pooch_filters = filter_spec.get("pooches", [])

    # Build the initial candidate pool from the first pooch filter (if any), or all strays
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

    result = await _execute_stray_event_actions(server_discord_id, event.actions, context, rng)

    selected_outcome = await _choose_stray_event_outcome(event, context, rng)
    if selected_outcome is not None:
        outcome_result = await _execute_stray_event_actions(server_discord_id, selected_outcome.actions, context, rng)
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
    """
    Run the daily stray event check for all servers.

    For each alive stray on a server there is a 50% chance of triggering a
    random eligible stray event.  A single event is drawn per roll — multiple
    strays on the same server can trigger different events in the same cycle.

    Parameters
    ----------
    rng_seed: int, optional
        Seed for the random number generator.

    Returns
    -------
    dict[int, list[tuple[str, StrayEventResult]]]
        Mapping of server_discord_id → list of (event_name, result) pairs for
        every triggered event, in trigger order.
    """
    rng = random.Random(rng_seed) if rng_seed is not None else random.Random()

    servers = await list_servers()
    results: dict[int, list[tuple[str, StrayEventResult]]] = {}

    for server in servers:
        strays = await list_strays_for_server(server.discord_id)
        for _ in strays:
            if rng.random() > STRAY_EVENT_TRIGGER_CHANCE:
                continue

            event = await get_random_eligible_stray_event_for_server(server.discord_id, rng=rng)
            if event is None:
                logger.debug(f"No eligible stray events for server {server.discord_id}.")
                continue

            result = await _trigger_stray_event_for_server(server.discord_id, event, rng)
            if result is not None:
                results.setdefault(server.discord_id, []).append((event.name, result))

    total = sum(len(v) for v in results.values())
    logger.info("Daily stray event check complete. %d event(s) triggered across %d server(s).", total, len(results))
    return results
