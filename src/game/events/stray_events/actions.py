from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Optional

from src.database import (
    add_pooch_to_strays,
    create_pooch,
    get_pooch_by_id,
    get_stray_event_by_name,
    list_matching_stray_pooch_ids,
    revive_pooch,
)
from src.game.breeding import breed_pooches as _breed_pooches
from src.game.constants import FIGHT_DEFENDER_STRENGTH_BONUS, FIGHT_ROUNDS
from src.game.events.outcome import choose_weighted_outcome
from src.game.events.shared import (
    apply_baby_overrides,
    apply_random_mutations,
    build_clone_kwargs,
    build_pooch_kwargs,
    copy_pooch_genetics,
    deliver_to_any_kennel,
    deliver_to_vendor,
    handle_add_breed,
    handle_add_mutation,
    handle_damn_pooch,
    handle_injure_pooch,
    handle_kill_pooch,
    handle_modify_age,
    handle_modify_breeding_cooldown,
    handle_modify_health,
    handle_modify_stat,
    handle_remove_breed,
    handle_remove_mutation,
    handle_rename_pooch,
    resolve_save_as_specs,
)

from .context import StrayEventContext, resolve_stray_target_ids

if TYPE_CHECKING:
    from src.database.models import StrayEvent, StrayEventAction, StrayEventOutcome

logger = logging.getLogger(__name__)


async def execute_stray_event_actions(
    server_discord_id: int,
    actions: list[StrayEventAction],
    context: StrayEventContext,
    rng: random.Random,
    season: Optional[str] = None,
) -> None:
    """Execute a sorted list of stray event actions, mutating context in place."""
    from src.game.models import StrayEventResult

    result = StrayEventResult()
    for action in sorted(actions, key=lambda a: a.action_order):
        repeat = max(int(action.repeat), 1) if isinstance(action.repeat, int) else 1
        for _ in range(repeat):
            action_result = await _execute_single_stray_action(server_discord_id, action, context, rng, season=season)
            result.merge(action_result)
    return result


async def _execute_single_stray_action(
    server_discord_id: int,
    action: StrayEventAction,
    context: StrayEventContext,
    rng: random.Random,
    season: Optional[str] = None,
):
    from src.game.models import StrayEventResult

    result = StrayEventResult()
    action_type: str = action.action_type
    parameters = action.parameters

    raw_selector = parameters.get("selector", "random")
    selector = str(raw_selector).strip().lower() if isinstance(raw_selector, str) else "random"

    try:
        if action_type == "modify_base_health":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_modify_health(pooch_ids, parameters, rng, result)

        elif action_type == "injure_pooch":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_injure_pooch(pooch_ids, parameters, rng, result)

        elif action_type == "modify_pooch_age":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_modify_age(pooch_ids, parameters, rng, result)

        elif action_type == "kill_pooch":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_kill_pooch(pooch_ids, parameters, rng, result)
            for pooch_id in result.pooches_killed:
                if pooch_id in context.candidate_stray_ids:
                    context.candidate_stray_ids.remove(pooch_id)

        elif action_type == "add_mutation":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_add_mutation(pooch_ids, parameters, rng, result)

        elif action_type == "remove_mutation":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_remove_mutation(pooch_ids, parameters, rng, result)

        elif action_type == "add_breed":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_add_breed(pooch_ids, parameters, rng, result)

        elif action_type == "remove_breed":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_remove_breed(pooch_ids, parameters, rng, result)

        elif action_type == "rename_pooch":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_rename_pooch(pooch_ids, parameters, rng, result)

        elif action_type == "modify_breeding_cooldown":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
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
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_modify_stat(action_type, pooch_ids, parameters, rng, result)

        elif action_type == "damn_pooch":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            await handle_damn_pooch(pooch_ids, parameters, rng, result, context, "candidate_stray_ids")

        elif action_type == "revive_pooch":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            destination = str(parameters.get("destination", "town")).strip().lower()
            for pooch_id in pooch_ids:
                pooch = await revive_pooch(pooch_id)
                if pooch:
                    if destination == "kennel":
                        placed = await deliver_to_any_kennel(pooch_id, server_discord_id, rng)
                        if not placed:
                            await add_pooch_to_strays(pooch_id, server_discord_id)
                            context.candidate_stray_ids.append(pooch_id)
                    elif destination == "vendor":
                        placed = await deliver_to_vendor(pooch_id, server_discord_id, rng)
                        if not placed:
                            await add_pooch_to_strays(pooch_id, server_discord_id)
                            context.candidate_stray_ids.append(pooch_id)
                    else:
                        await add_pooch_to_strays(pooch_id, server_discord_id)
                        context.candidate_stray_ids.append(pooch_id)
                    result.pooches_affected.append(pooch_id)

        elif action_type == "create_pooch":
            kwargs = await build_pooch_kwargs(parameters, rng, season=season)
            mutations_param = parameters.get("mutations")
            pooch = await create_pooch(**kwargs)
            if pooch:
                await apply_random_mutations(pooch.id, mutations_param, rng, season=season)
                await add_pooch_to_strays(pooch.id, server_discord_id)
                context.candidate_stray_ids.append(pooch.id)
                result.pooches_created.append(pooch.id)
                save_as = parameters.get("save_as")
                if isinstance(save_as, str) and save_as:
                    context.extra_data[save_as] = {"pooch_ids": [pooch.id]}

        elif action_type == "clone_pooch":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            source_id = pooch_ids[0] if pooch_ids else None
            if source_id is None:
                logger.warning("stray clone_pooch: no source pooch resolved; skipping")
            else:
                source = await get_pooch_by_id(source_id)
                if source is None:
                    logger.warning(f"stray clone_pooch: source {source_id} not found; skipping")
                else:
                    clone_kwargs = build_clone_kwargs(source, parameters, rng)
                    clone = await create_pooch(**clone_kwargs)
                    if clone:
                        await copy_pooch_genetics(source_id, clone.id)
                        await add_pooch_to_strays(clone.id, server_discord_id)
                        context.candidate_stray_ids.append(clone.id)
                        result.pooches_created.append(clone.id)
                        for spec in resolve_save_as_specs(parameters.get("save_as")):
                            slot = spec.get("slot")
                            target = spec.get("target", "clone")
                            if isinstance(slot, str) and slot:
                                context.extra_data[slot] = {
                                    "pooch_ids": [source_id if target == "source" else clone.id]
                                }

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
                        await apply_baby_overrides(baby_id, parameters)
                    result.pooches_created.extend(baby_ids)

                    for spec in resolve_save_as_specs(parameters.get("save_as")):
                        slot = spec.get("slot")
                        target = spec.get("target", "baby")
                        if isinstance(slot, str) and slot:
                            if target == "first_parent":
                                context.extra_data[slot] = {"pooch_ids": [first_id]}
                            elif target == "second_parent":
                                context.extra_data[slot] = {"pooch_ids": [second_id]}
                            else:
                                context.extra_data[slot] = {"pooch_ids": list(baby_ids)}
                except ValueError as exc:
                    logger.warning(f"stray breed_pooches: breeding failed — {exc}")

        elif action_type == "enter_kennel":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            for pooch_id in pooch_ids:
                placed = await deliver_to_any_kennel(pooch_id, server_discord_id, rng)
                if placed:
                    result.pooches_affected.append(pooch_id)
                    if pooch_id in context.candidate_stray_ids:
                        context.candidate_stray_ids.remove(pooch_id)
                else:
                    logger.debug(f"enter_kennel: no free kennel space for pooch {pooch_id}; left as stray")

        elif action_type == "enter_vendor_stock":
            pooch_ids = await resolve_stray_target_ids(context, selector, parameters, rng)
            for pooch_id in pooch_ids:
                placed = await deliver_to_vendor(pooch_id, server_discord_id, rng)
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
                    followup_result = await execute_stray_event_actions(
                        server_discord_id, followup.actions, context, rng
                    )
                    result.merge(followup_result)
                    followup_outcome = await choose_stray_event_outcome(followup, context, rng)
                    if followup_outcome is not None:
                        outcome_result = await execute_stray_event_actions(
                            server_discord_id, followup_outcome.actions, context, rng
                        )
                        result.merge(outcome_result)

        elif action_type == "select_pooch":
            await resolve_stray_target_ids(context, selector, parameters, rng)

        elif action_type == "fight_pooches":
            from src.game.events.shared import handle_fight_pooches

            attacker_slot = parameters.get("attacker_slot")
            defender_slot = parameters.get("defender_slot")

            def _ids_from_slot(slot_name: str) -> list[int]:
                slot_data = context.extra_data.get(slot_name, {})
                return slot_data.get("pooch_ids", []) if isinstance(slot_data, dict) else []

            attacker_id = None
            defender_id = None

            if isinstance(attacker_slot, str) and attacker_slot:
                ids = _ids_from_slot(attacker_slot)
                attacker_id = ids[0] if ids else None
            if isinstance(defender_slot, str) and defender_slot:
                ids = _ids_from_slot(defender_slot)
                defender_id = ids[0] if ids else None

            if attacker_id is None or defender_id is None:
                stray_ids = list(context.candidate_stray_ids)
                if len(stray_ids) >= 2:
                    rng.shuffle(stray_ids)
                    attacker_id, defender_id = stray_ids[0], stray_ids[1]

            if attacker_id is not None and defender_id is not None:
                fight_result = await handle_fight_pooches(
                    attacker_id,
                    defender_id,
                    rounds=int(parameters.get("rounds", FIGHT_ROUNDS)),
                    defender_strength_bonus=int(
                        parameters.get("defender_strength_bonus", FIGHT_DEFENDER_STRENGTH_BONUS)
                    ),
                    rng=rng,
                )
                result.extra_data["fight_result"] = fight_result
                result.pooches_affected.extend(
                    pid for pid in [attacker_id, defender_id] if pid not in result.pooches_affected
                )
                if fight_result.get("attacker_died"):
                    result.pooches_killed.append(attacker_id)
                if fight_result.get("defender_died"):
                    result.pooches_killed.append(defender_id)
                save_as = parameters.get("save_as")
                if isinstance(save_as, str) and save_as and fight_result.get("winner_id"):
                    context.extra_data[save_as] = {"pooch_ids": [fight_result["winner_id"]]}
            else:
                logger.warning("fight_pooches: could not resolve both pooches for stray event; skipping")

        else:
            logger.warning(f"Unknown stray action type: {action_type}")

    except Exception as exc:
        logger.error(f"Error executing stray action '{action_type}': {exc}", exc_info=True)
        result.success = False

    return result


async def choose_stray_event_outcome(
    event: StrayEvent,
    context: StrayEventContext,
    rng: random.Random,
) -> Optional[StrayEventOutcome]:
    """Pick one outcome from the stray event's outcomes list using weighted random selection."""

    def _resolve_pooch_id(selector: str) -> Optional[int]:
        if selector == "random":
            return rng.choice(context.candidate_stray_ids) if context.candidate_stray_ids else None
        slot = context.extra_data.get(selector)
        if isinstance(slot, dict):
            ids = slot.get("pooch_ids", [])
            return ids[0] if ids else None
        return None

    return await choose_weighted_outcome(event.outcomes, _resolve_pooch_id, rng)
