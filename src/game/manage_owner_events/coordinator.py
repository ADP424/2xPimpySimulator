import logging
import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from src.database import (
    add_mutation_to_pooch,
    add_pooch_breeds,
    add_pooch_to_kennel,
    add_pooch_to_strays,
    add_pooch_to_vendor_stock,
    archive_active_event,
    create_active_owner_event,
    create_pooch,
    damn_pooch,
    delete_pooch,
    get_kennel_by_id,
    get_mutation_by_name,
    get_owner_by_discord_id,
)
from src.database import get_owner_event_by_name as db_get_owner_event_by_name
from src.database import (
    get_random_breed_ids,
    get_random_eligible_owner_event_for_owner,
    get_stray_event_by_name,
    give_bloodskulls_to_owner,
    give_bones_to_owner,
    give_money_to_owner,
    list_matching_pooch_ids,
    list_matching_stray_pooch_ids,
    list_pooch_breed_weights,
    list_pooch_mutations,
    list_pooches_for_kennel,
    list_servers_for_owner,
    list_strays_for_server,
    list_vendor_pooch_stock,
    list_vendors,
    modify_kennel_pooch_limit,
    modify_pooch_age,
    modify_pooch_base_health,
    remove_pooch_from_kennel,
    remove_pooch_from_strays,
    remove_pooch_from_vendor_stock,
    rename_pooch,
    revive_pooch,
    set_kennel_pooch_limit,
    set_owner_bloodskulls,
    set_owner_dollars,
    set_pooch_breeding_cooldown,
    set_pooch_dead,
    transfer_pooch_to_owner,
    transfer_pooch_to_vendor,
    update_active_event_context,
    update_active_event_result,
)

from ..action_helpers.amount import get_amount_from_parameters, get_mode, resolve_amount
from ..action_helpers.pooch_actions import (
    handle_add_breed,
    handle_add_mutation,
    handle_damn_pooch,
    handle_kill_pooch,
    handle_modify_age,
    handle_modify_breeding_cooldown,
    handle_modify_health,
    handle_modify_stat,
    handle_remove_breed,
    handle_remove_mutation,
    handle_rename_pooch,
    handle_select_pooch,
)
from ..breeding import breed_pooches
from ..constants import (
    NUM_BREEDS_PER_SUMMON_POOCH_RANGE,
    POOCH_STAT_RANGE,
    POOCH_STATS,
)
from ..manage_hell import get_pooch_bloodskull_value
from ..manage_vendors import get_pooch_buy_price, get_pooch_sell_price
from ..models import (
    OwnerEventContext,
    OwnerEventResult,
    StrayEventContext,
    TriggeredOwnerEvent,
    to_triggered_owner_event,
)
from .context import create_event_context, deliver_pooch
from .outcome import choose_option_outcome
from .resolvers import get_target_kennel_ids, get_target_pooch_ids

if TYPE_CHECKING:
    from src.database.models import Event as EventDB
    from src.database.models import EventAction

logger = logging.getLogger(__name__)


async def _execute_single_action(
    owner_discord_id: int, action: "EventAction", context: OwnerEventContext, rng: random.Random
) -> OwnerEventResult:
    """
    Execute a single event action.
    """
    result = OwnerEventResult()
    action_type = action.action_type
    target_type = action.target_type
    parameters = action.parameters

    # Resolve selector (default to "random")
    raw_selector = parameters.get("selector", "random")
    selector = str(raw_selector).strip().lower() if isinstance(raw_selector, str) else "random"

    try:
        # Owner Actions
        if action_type == "modify_money":
            amount = get_amount_from_parameters(parameters, rng)
            if get_mode(parameters) == "set":
                await set_owner_dollars(owner_discord_id, amount)
            else:
                await give_money_to_owner(owner_discord_id, amount)
            result.money_changed = amount
            result.message = f"{amount:+d} dollars"

        elif action_type == "modify_bloodskulls":
            amount = get_amount_from_parameters(parameters, rng)
            if get_mode(parameters) == "set":
                await set_owner_bloodskulls(owner_discord_id, amount)
            else:
                await give_bloodskulls_to_owner(owner_discord_id, amount)
            result.bloodskulls_changed = amount
            result.message = f"{amount:+d} bloodskulls"

        elif action_type == "create_pooch":
            create_pooch_kwargs: dict[str, Any] = {
                "owner_discord_id": owner_discord_id,
                "rng": rng,
            }
            for _key in (
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
                if _key in parameters:
                    create_pooch_kwargs[_key] = parameters[_key]
            breeds_param = parameters.get("breeds")
            if isinstance(breeds_param, list):
                create_pooch_kwargs["breeds"] = breeds_param
            elif isinstance(breeds_param, int) and breeds_param > 0:
                create_pooch_kwargs["breeds"] = await get_random_breed_ids(breeds_param, rng=rng)

            mutations_param = parameters.get("mutations")
            if isinstance(mutations_param, list):
                create_pooch_kwargs["mutations"] = mutations_param

            pooch = await create_pooch(**create_pooch_kwargs)

            if pooch and isinstance(mutations_param, int) and mutations_param > 0:
                for _ in range(mutations_param):
                    await add_mutation_to_pooch(pooch.id, rng=rng)
            if pooch:
                context.selected_pooch_id = pooch.id
                candidate_pooch_ids = context.extra_data.setdefault("candidate_pooch_ids", [])
                if isinstance(candidate_pooch_ids, list) and pooch.id not in candidate_pooch_ids:
                    candidate_pooch_ids.append(pooch.id)
                if pooch.id not in context.affected_pooch_ids:
                    context.affected_pooch_ids.append(pooch.id)
                result.pooches_created.append(pooch.id)
                result.pooches_affected.append(pooch.id)

                if target_type == "kennel":
                    kennel_ids = await get_target_kennel_ids(
                        owner_discord_id, context, rng, target_type, selector, parameters
                    )
                    kennel_id = kennel_ids[0] if kennel_ids else None
                    if kennel_id is not None:
                        kennel = await get_kennel_by_id(kennel_id)
                        pooches_in = await list_pooches_for_kennel(kennel_id)
                        if kennel is not None and len(pooches_in) < kennel.pooch_limit:
                            await add_pooch_to_kennel(kennel_id, pooch.id)
                            result.message = f"A new pooch has appeared and was placed in {kennel.name}!"
                        else:
                            result.message = "A new pooch has appeared but there was no space in the kennel!"
                    else:
                        result.message = "A new pooch has appeared!"
                else:
                    destination_str = parameters.get("destination", "kennel")
                    dest_key, kennel_name = await deliver_pooch(owner_discord_id, pooch.id, destination_str)
                    if dest_key == "kennel":
                        result.message = f"A new pooch has appeared and was placed in {kennel_name}!"
                    elif dest_key == "graveyard":
                        result.message = "A new pooch has appeared and was placed in the graveyard!"
                    elif dest_key == "hell":
                        result.message = "A new pooch has appeared and was sent to Hell!"
                    else:
                        result.message = "A new pooch has appeared!"

                save_as = parameters.get("save_as")
                if isinstance(save_as, str) and save_as:
                    context.extra_data[save_as] = {"pooch_ids": [pooch.id]}

        elif action_type == "clone_pooch":
            # Resolve the source pooch
            from src.database import get_pooch_by_id

            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            source_id = pooch_ids[0] if pooch_ids else None
            if source_id is None:
                logger.warning("clone_pooch: could not resolve source pooch; skipping")
            else:
                source = await get_pooch_by_id(source_id)
                if source is None:
                    logger.warning(f"clone_pooch: source pooch {source_id} not found; skipping")
                else:
                    clone_kwargs: dict[str, Any] = {
                        "owner_discord_id": owner_discord_id,
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
                        # Copy breeds (raw integer weights) and mutations from source
                        breed_weights = await list_pooch_breed_weights(source_id)
                        if breed_weights:
                            await add_pooch_breeds(clone.id, dict(breed_weights))
                        for mutation in await list_pooch_mutations(source_id):
                            await add_mutation_to_pooch(clone.id, mutation_id=mutation.id)

                        context.selected_pooch_id = clone.id
                        candidate_pooch_ids = context.extra_data.setdefault("candidate_pooch_ids", [])
                        if isinstance(candidate_pooch_ids, list) and clone.id not in candidate_pooch_ids:
                            candidate_pooch_ids.append(clone.id)
                        if clone.id not in context.affected_pooch_ids:
                            context.affected_pooch_ids.append(clone.id)
                        result.pooches_created.append(clone.id)
                        result.pooches_affected.append(clone.id)

                        destination_str = parameters.get("destination", "kennel")
                        dest_key, kennel_name = await deliver_pooch(owner_discord_id, clone.id, destination_str)
                        if dest_key == "kennel":
                            result.message = f"A clone of {source.name} appeared and was placed in {kennel_name}!"
                        elif dest_key == "graveyard":
                            result.message = f"A clone of {source.name} appeared and was placed in the graveyard!"
                        elif dest_key == "hell":
                            result.message = f"A clone of {source.name} appeared and was sent to Hell!"
                        else:
                            result.message = f"A clone of {source.name} has appeared!"

                        # save_as: supports "source" or "clone" (or plain string → clone)
                        save_as_raw = parameters.get("save_as")
                        if save_as_raw is not None:
                            save_specs: list[dict[str, str]]
                            if isinstance(save_as_raw, str):
                                save_specs = [{"slot": save_as_raw, "target": "clone"}]
                            elif isinstance(save_as_raw, list):
                                save_specs = [s for s in save_as_raw if isinstance(s, dict)]
                            else:
                                save_specs = []
                            for spec in save_specs:
                                slot = spec.get("slot")
                                target = spec.get("target", "clone")
                                if not isinstance(slot, str) or not slot:
                                    continue
                                if target == "source":
                                    context.extra_data[slot] = {"pooch_ids": [source_id]}
                                else:  # "clone"
                                    context.extra_data[slot] = {"pooch_ids": [clone.id]}

        # Kennel Actions
        elif action_type == "modify_kennel_capacity":
            kennel_ids = await get_target_kennel_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            pre_rolled, roll_once = resolve_amount(parameters, rng)
            mode = get_mode(parameters)
            for kennel_id in kennel_ids:
                amount = pre_rolled if roll_once else get_amount_from_parameters(parameters, rng)
                if mode == "set":
                    kennel = await set_kennel_pooch_limit(kennel_id, amount)
                else:
                    kennel = await modify_kennel_pooch_limit(kennel_id, amount)
                if kennel:
                    if kennel_id not in context.affected_kennel_ids:
                        context.affected_kennel_ids.append(kennel_id)
                    result.extra_data.setdefault("kennel_capacity_changes", {})[kennel_id] = amount

        # Pooch Actions
        elif action_type in ("modify_base_health", "modify_pooch_health"):
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_modify_health(pooch_ids, parameters, rng, result)

        elif action_type == "modify_pooch_age":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_modify_age(pooch_ids, parameters, rng, result)

        elif action_type == "kill_pooch":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_kill_pooch(pooch_ids, parameters, rng, result)

        elif action_type == "release_stray":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            servers = await list_servers_for_owner(owner_discord_id)
            if not servers:
                logger.warning("release_stray: owner has no servers; skipping")
            else:
                server = rng.choice(servers)
                for pooch_id in pooch_ids:
                    stray = await add_pooch_to_strays(pooch_id, server.discord_id)
                    if stray:
                        result.pooches_affected.append(pooch_id)

        elif action_type == "receive_stray":
            servers = await list_servers_for_owner(owner_discord_id)
            if not servers:
                logger.warning("receive_stray: owner has no servers; skipping")
            else:
                server = rng.choice(servers)
                use_saved = parameters.get("use_saved")
                if isinstance(use_saved, str) and use_saved:
                    saved = context.extra_data.get(use_saved, {})
                    saved_ids = list(saved.get("pooch_ids", [])) if isinstance(saved, dict) else []
                    pool_objs = [p for p in await list_strays_for_server(server.discord_id) if p.id in saved_ids]
                else:
                    candidates = await list_strays_for_server(server.discord_id)
                    count = int(parameters.get("count", 1))
                    pool_objs = rng.sample(candidates, min(count, len(candidates))) if candidates else []
                if not pool_objs:
                    logger.warning("receive_stray: no strays available on server %s; skipping", server.discord_id)
                else:
                    chosen = rng.choice(pool_objs)
                    await remove_pooch_from_strays(chosen.id)
                    await transfer_pooch_to_owner(chosen.id, owner_discord_id)

                    if target_type == "kennel":
                        kennel_ids = await get_target_kennel_ids(
                            owner_discord_id, context, rng, target_type, selector, parameters
                        )
                        recv_kennel_id = kennel_ids[0] if kennel_ids else None
                        if recv_kennel_id is not None:
                            kennel = await get_kennel_by_id(recv_kennel_id)
                            pooches_in = await list_pooches_for_kennel(recv_kennel_id)
                            if kennel is not None and len(pooches_in) < kennel.pooch_limit:
                                await add_pooch_to_kennel(recv_kennel_id, chosen.id)
                                dest_key, kennel_name = "kennel", kennel.name
                            else:
                                dest_key, kennel_name = "town", None
                        else:
                            dest_key, kennel_name = "town", None
                    else:
                        destination_str = str(parameters.get("destination", "kennel")).strip().lower()
                        dest_key, kennel_name = await deliver_pooch(owner_discord_id, chosen.id, destination_str)

                    result.pooches_created.append(chosen.id)
                    result.extra_data.setdefault("created_pooches", []).append(
                        {
                            "pooch_id": chosen.id,
                            "pooch_name": chosen.name,
                            "sex": chosen.sex,
                            "age": chosen.age,
                            "kennel_name": kennel_name,
                        }
                    )
                    save_as = parameters.get("save_as")
                    if isinstance(save_as, str) and save_as:
                        context.extra_data[save_as] = {"pooch_ids": [chosen.id]}

        elif action_type == "add_mutation":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_add_mutation(pooch_ids, parameters, rng, result)

        elif action_type == "remove_mutation":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_remove_mutation(pooch_ids, parameters, rng, result)

        elif action_type == "add_breed":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_add_breed(pooch_ids, parameters, rng, result)

        elif action_type == "remove_breed":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_remove_breed(pooch_ids, parameters, rng, result)

        elif action_type == "transfer_pooch":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            new_owner_id = parameters.get("new_owner_discord_id")
            vendor_id = parameters.get("vendor_id")
            for pooch_id in pooch_ids:
                if new_owner_id:
                    await transfer_pooch_to_owner(pooch_id, new_owner_id)
                elif vendor_id:
                    await transfer_pooch_to_vendor(pooch_id, vendor_id)
                result.pooches_affected.append(pooch_id)

        elif action_type in ("modify_breeding_cooldown", "set_breeding_cooldown"):
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_modify_breeding_cooldown(pooch_ids, parameters, rng, result)

        elif action_type == "rename_pooch":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_rename_pooch(pooch_ids, parameters, rng, result)

        elif action_type == "breed_pooches":
            from src.database import list_matching_pooch_ids_in_kennel

            raw_first_selector = parameters.get("first_pooch_selector", "random")
            first_selector = (
                str(raw_first_selector).strip().lower() if isinstance(raw_first_selector, str) else "random"
            )
            raw_second_selector = parameters.get("second_pooch_selector", "random")
            second_selector = (
                str(raw_second_selector).strip().lower() if isinstance(raw_second_selector, str) else "random"
            )

            first_filter_raw = parameters.get("first_filter", {})
            first_filter = first_filter_raw if isinstance(first_filter_raw, dict) else {}
            second_filter_raw = parameters.get("second_filter", {})
            second_filter = second_filter_raw if isinstance(second_filter_raw, dict) else {}

            # When target_type is "kennel", restrict both parent pools to that kennel's pooches
            breed_kennel_id: int | None = None
            if target_type == "kennel":
                kennel_ids = await get_target_kennel_ids(
                    owner_discord_id, context, rng, target_type, selector, parameters
                )
                breed_kennel_id = kennel_ids[0] if kennel_ids else None
                if breed_kennel_id is None:
                    logger.warning("breed_pooches: no kennel resolved for kennel target_type; skipping")
                    breed_kennel_id = None  # will skip below

            async def _resolve_breed_pooch_id(sel: str, filt: dict, exclude_id: int | None = None) -> int | None:
                if sel == "selected":
                    pid = context.selected_pooch_id
                    return None if (exclude_id is not None and pid == exclude_id) else pid
                if breed_kennel_id is not None:
                    ids = await list_matching_pooch_ids_in_kennel(owner_discord_id, breed_kennel_id, filt)
                else:
                    ids = await list_matching_pooch_ids(owner_discord_id, filt)
                if exclude_id is not None:
                    ids = [i for i in ids if i != exclude_id]
                return rng.choice(ids) if ids else None

            require_unique = bool(parameters.get("require_unique", True))
            require_same = bool(parameters.get("require_same", False))

            if target_type == "kennel" and breed_kennel_id is None:
                first_pooch_id = None
                second_pooch_id = None
            else:
                first_pooch_id = await _resolve_breed_pooch_id(first_selector, first_filter)
                if require_same:
                    second_pooch_id = first_pooch_id
                else:
                    exclude = first_pooch_id if require_unique else None
                    second_pooch_id = await _resolve_breed_pooch_id(second_selector, second_filter, exclude_id=exclude)

            if first_pooch_id is None or second_pooch_id is None:
                logger.warning("breed_pooches: could not resolve one or both pooches; skipping")
            else:
                try:
                    baby_ids = await breed_pooches(
                        first_pooch_id, second_pooch_id, rng_seed=rng.randint(0, 2**31), skip_validation=True
                    )
                    result.pooches_created.extend(baby_ids)
                    result.pooches_affected.extend(baby_ids)

                    for baby_id in baby_ids:
                        if "baby_name" in parameters:
                            await rename_pooch(baby_id, str(parameters["baby_name"]))
                        if "baby_age" in parameters:
                            await modify_pooch_age(baby_id, parameters["baby_age"])
                        if "baby_base_health" in parameters:
                            await modify_pooch_base_health(baby_id, parameters["baby_base_health"])
                        if "baby_breeding_cooldown" in parameters:
                            await set_pooch_breeding_cooldown(baby_id, parameters["baby_breeding_cooldown"])

                    count = len(baby_ids)
                    result.message = "A puppy was born!" if count == 1 else f"{count} puppies were born!"

                    # save_as: supports "first_parent", "second_parent", "baby" (or list of those)
                    # Each save_as entry is a dict: { "slot": str, "target": "first_parent"|"second_parent"|"baby" }
                    # For convenience, a plain string defaults to saving the baby/babies.
                    save_as_raw = parameters.get("save_as")
                    if save_as_raw is not None:
                        save_specs: list[dict[str, str]]
                        if isinstance(save_as_raw, str):
                            save_specs = [{"slot": save_as_raw, "target": "baby"}]
                        elif isinstance(save_as_raw, list):
                            save_specs = [s for s in save_as_raw if isinstance(s, dict)]
                        else:
                            save_specs = []
                        for spec in save_specs:
                            slot = spec.get("slot")
                            target = spec.get("target", "baby")
                            if not isinstance(slot, str) or not slot:
                                continue
                            if target == "first_parent":
                                context.extra_data[slot] = {"pooch_ids": [first_pooch_id]}
                            elif target == "second_parent":
                                context.extra_data[slot] = {"pooch_ids": [second_pooch_id]}
                            else:  # "baby"
                                context.extra_data[slot] = {"pooch_ids": list(baby_ids)}

                except ValueError as e:
                    logger.warning(f"breed_pooches: breeding failed — {e}")

        elif action_type == "sell_pooch":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            vendor_id = parameters.get("vendor_id")
            vendor_selector = str(parameters.get("vendor_selector", "random")).strip().lower()
            value_multiplier = parameters.get("value_multiplier")
            multiplier = float(value_multiplier) if isinstance(value_multiplier, (int, float)) else 1.0

            # Resolve vendor if not explicitly specified
            resolved_vendor_id: int | None = vendor_id if isinstance(vendor_id, int) else None
            if resolved_vendor_id is None and vendor_selector == "random":
                servers = await list_servers_for_owner(owner_discord_id)
                all_vendors = []
                for server in servers:
                    all_vendors.extend(await list_vendors(server.discord_id))
                if all_vendors:
                    resolved_vendor_id = rng.choice(all_vendors).id

            for pooch_id in pooch_ids:
                from src.database import get_pooch_by_id

                pooch = await get_pooch_by_id(pooch_id)
                if pooch is None or not pooch.alive:
                    continue
                if resolved_vendor_id is not None:
                    price = round((await get_pooch_sell_price(pooch_id, resolved_vendor_id)) * multiplier)
                    await give_money_to_owner(owner_discord_id, price)
                    await transfer_pooch_to_vendor(pooch_id, resolved_vendor_id)
                    await remove_pooch_from_kennel(pooch_id)
                    await add_pooch_to_vendor_stock(resolved_vendor_id, pooch_id)
                    result.money_changed += price
                else:
                    price = round((await get_pooch_sell_price(pooch_id)) * multiplier)
                    await give_money_to_owner(owner_discord_id, price)
                    result.money_changed += price
                result.pooches_affected.append(pooch_id)

        elif action_type == "buy_pooch":
            vendor_id = parameters.get("vendor_id")
            vendor_selector = str(parameters.get("vendor_selector", "random")).strip().lower()
            pooch_selector = str(parameters.get("pooch_selector", "random")).strip().lower()
            pooch_filter_raw = parameters.get("pooch_filter", {})
            pooch_filter = pooch_filter_raw if isinstance(pooch_filter_raw, dict) else {}
            value_multiplier = parameters.get("value_multiplier")
            multiplier = float(value_multiplier) if isinstance(value_multiplier, (int, float)) else 1.0

            # Resolve delivery kennel when target_type is "kennel"
            buy_kennel_id: int | None = None
            if target_type == "kennel":
                kennel_ids = await get_target_kennel_ids(
                    owner_discord_id, context, rng, target_type, selector, parameters
                )
                buy_kennel_id = kennel_ids[0] if kennel_ids else None

            destination_str = parameters.get("destination", "kennel")

            # Resolve vendor
            resolved_vendor_id = vendor_id if isinstance(vendor_id, int) else None
            if resolved_vendor_id is None and vendor_selector == "random":
                servers = await list_servers_for_owner(owner_discord_id)
                all_vendors = []
                for server in servers:
                    all_vendors.extend(await list_vendors(server.discord_id))
                if all_vendors:
                    resolved_vendor_id = rng.choice(all_vendors).id

            if resolved_vendor_id is None:
                logger.warning("buy_pooch: no vendor available; skipping")
            else:
                stock = await list_vendor_pooch_stock(resolved_vendor_id)
                if pooch_filter:
                    filter_ids = await list_matching_pooch_ids(owner_discord_id, pooch_filter)
                    stock = [p for p in stock if p.id in set(filter_ids)]
                if not stock:
                    logger.warning("buy_pooch: no pooches available from vendor; skipping")
                else:
                    pooch_db = rng.choice(stock) if pooch_selector == "random" else stock[0]
                    price = round((await get_pooch_buy_price(pooch_db.id, resolved_vendor_id)) * multiplier)
                    owner = await get_owner_by_discord_id(owner_discord_id)
                    if owner is None or owner.dollars < price:
                        logger.warning("buy_pooch: owner cannot afford the pooch; skipping")
                    else:
                        await remove_pooch_from_vendor_stock(resolved_vendor_id, pooch_db.id)
                        await give_money_to_owner(owner_discord_id, -price)
                        await transfer_pooch_to_owner(pooch_db.id, owner_discord_id)

                        if buy_kennel_id is not None:
                            kennel = await get_kennel_by_id(buy_kennel_id)
                            pooches_in = await list_pooches_for_kennel(buy_kennel_id)
                            if kennel is not None and len(pooches_in) < kennel.pooch_limit:
                                await add_pooch_to_kennel(buy_kennel_id, pooch_db.id)
                                dest_key, kennel_name = "kennel", kennel.name
                            else:
                                dest_key, kennel_name = "town", None
                        else:
                            dest_key, kennel_name = await deliver_pooch(owner_discord_id, pooch_db.id, destination_str)

                        result.money_changed -= price
                        result.pooches_created.append(pooch_db.id)
                        result.pooches_affected.append(pooch_db.id)

                        save_as = parameters.get("save_as")
                        if isinstance(save_as, str) and save_as:
                            context.extra_data[save_as] = {"pooch_ids": [pooch_db.id]}

                        if dest_key == "kennel":
                            result.message = f"{pooch_db.name} was purchased and placed in {kennel_name}!"
                        else:
                            result.message = f"{pooch_db.name} was purchased!"

        # Other Actions
        elif action_type == "start_event":
            if bool(parameters.get("random_event", False)):
                followup_event = await get_random_eligible_owner_event_for_owner(owner_discord_id, rng=rng)
            else:
                event_name = parameters.get("event")
                followup_event = await db_get_owner_event_by_name(event_name.strip())
                if followup_event is None:
                    logger.warning(f"Unknown event '{event_name}' triggered. Skipping...")
                    result.message = "Error starting followup event."
                    return result

            if followup_event is not None:
                if followup_event.requires_response:
                    # Response-required events run as independent active events but inherit named slots
                    _internal_keys = {"candidate_pooch_ids", "candidate_kennel_ids", "suppressed_option_ids"}
                    slots_to_forward = {
                        k: v for k, v in context.extra_data.items() if not k.startswith("_") and k not in _internal_keys
                    }
                    from .public import trigger_specific_event

                    started_event = await trigger_specific_event(
                        owner_discord_id, followup_event.id, rng=rng, inherited_slots=slots_to_forward
                    )
                    if started_event is not None:
                        started_events = result.extra_data.setdefault("started_events", [])
                        started_events.append(
                            {
                                "active_owner_event_id": started_event.active_owner_event_id,
                                "event_id": started_event.event_id,
                                "name": started_event.name,
                            }
                        )
                        result.message = f"Started event '{started_event.name}'."
                else:
                    # Instant events run inline, sharing the current context so save_as/use_saved slots carry over
                    followup_result = await execute_event_actions(
                        owner_discord_id, followup_event.actions, context, rng
                    )
                    result.merge(followup_result)
                    default_option = next((opt for opt in followup_event.options if opt.is_default), None)
                    if default_option is not None:
                        option_result = await execute_event_actions(
                            owner_discord_id, default_option.actions, context, rng
                        )
                        result.merge(option_result)
                        selected_outcome = await choose_option_outcome(default_option, context, rng)
                        if selected_outcome is not None:
                            outcome_result = await execute_event_actions(
                                owner_discord_id, selected_outcome.actions, context, rng
                            )
                            result.merge(outcome_result)

        elif action_type == "start_stray_event":
            from ..manage_stray_events import (
                _choose_stray_event_outcome,
                _execute_stray_event_actions,
            )

            event_name = parameters.get("event")
            if not isinstance(event_name, str) or not event_name.strip():
                logger.warning("start_stray_event: missing 'event' parameter; skipping")
            else:
                stray_event = await get_stray_event_by_name(event_name.strip())
                if stray_event is None:
                    logger.warning(f"start_stray_event: unknown stray event '{event_name}'; skipping")
                else:
                    servers = await list_servers_for_owner(owner_discord_id)
                    if not servers:
                        logger.warning(f"start_stray_event: owner {owner_discord_id} has no servers; skipping")
                    else:
                        server = rng.choice(servers)
                        stray_filter: dict = stray_event.filter or {}
                        pooch_filters = stray_filter.get("pooches", [])
                        if pooch_filters:
                            first_f = {
                                k: v
                                for k, v in pooch_filters[0].items()
                                if k not in {"min_count", "max_count", "description"}
                            }
                            candidate_ids = await list_matching_stray_pooch_ids(server.discord_id, first_f)
                        else:
                            candidate_ids = [p.id for p in await list_strays_for_server(server.discord_id)]
                        stray_context = StrayEventContext(
                            server_discord_id=server.discord_id,
                            candidate_stray_ids=list(candidate_ids),
                        )
                        stray_result = await _execute_stray_event_actions(
                            server.discord_id, stray_event.actions, stray_context, rng
                        )
                        result.merge(stray_result)
                        stray_outcome = await _choose_stray_event_outcome(stray_event, stray_context, rng)
                        if stray_outcome is not None:
                            outcome_result = await _execute_stray_event_actions(
                                server.discord_id, stray_outcome.actions, stray_context, rng
                            )
                            result.merge(outcome_result)

        elif action_type == "select_pooch":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_select_pooch(pooch_ids, parameters, rng, result)

        # Stat modify/set actions
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
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_modify_stat(action_type, pooch_ids, parameters, rng, result)

        # Hell / soul actions
        elif action_type == "damn_pooch":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            await handle_damn_pooch(pooch_ids, parameters, rng, result, context, "affected_pooch_ids")
            if result.pooches_killed:
                count = len(result.pooches_killed)
                result.message = (
                    "A pooch has been damned to Hell!" if count == 1 else f"{count} pooches have been damned to Hell!"
                )

        elif action_type == "revive_pooch":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            destination_str = str(parameters.get("destination", "kennel")).strip().lower()
            for pooch_id in pooch_ids:
                pooch = await revive_pooch(pooch_id)
                if pooch:
                    dest_key, kennel_name = await deliver_pooch(owner_discord_id, pooch_id, destination_str)
                    result.pooches_affected.append(pooch_id)
                    if dest_key == "kennel":
                        result.message = f"{pooch.name} has been revived and placed in {kennel_name}!"
                    elif dest_key == "hell":
                        result.message = f"{pooch.name} has been revived and sent back to Hell..."
                    elif dest_key == "graveyard":
                        result.message = f"{pooch.name} has been revived and placed in the graveyard."
                    else:
                        result.message = f"{pooch.name} has been revived!"
                    save_as = parameters.get("save_as")
                    if isinstance(save_as, str) and save_as:
                        context.extra_data.setdefault(save_as, {}).setdefault("pooch_ids", []).append(pooch_id)

        elif action_type == "conjure_pooch":
            # Create a new pooch from Hell ritual — does NOT charge bloodskulls (handle with modify_bloodskulls)
            num_rolls = int(parameters.get("num_rolls", 1))
            num_rolls = max(1, num_rolls)
            destination_str = str(parameters.get("destination", "kennel")).strip().lower()

            conjured: Any = None
            for _ in range(num_rolls):
                num_breeds = rng.randint(NUM_BREEDS_PER_SUMMON_POOCH_RANGE[0], NUM_BREEDS_PER_SUMMON_POOCH_RANGE[1])
                ritual_breed_ids = await get_random_breed_ids(num_breeds, rng=rng, from_ritual=True)
                pooch = await create_pooch(
                    owner_discord_id=owner_discord_id,
                    age=0,
                    base_health=rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]),
                    **{stat: rng.randint(POOCH_STAT_RANGE[0], POOCH_STAT_RANGE[1]) for stat in POOCH_STATS},
                    breeds=ritual_breed_ids,
                    rng=rng,
                )

                if conjured is None or (
                    await get_pooch_bloodskull_value(pooch.id) > await get_pooch_bloodskull_value(conjured.id)
                ):
                    if conjured is not None:
                        await delete_pooch(conjured.id)
                    conjured = pooch
                else:
                    await delete_pooch(pooch.id)

            if conjured:
                mark = await get_mutation_by_name("Mark of the Beast")
                if mark is not None:
                    await add_mutation_to_pooch(conjured.id, mutation_id=mark.id)

                dest_key, kennel_name = await deliver_pooch(owner_discord_id, conjured.id, destination_str)
                context.selected_pooch_id = conjured.id
                candidate_pooch_ids = context.extra_data.setdefault("candidate_pooch_ids", [])
                if isinstance(candidate_pooch_ids, list) and conjured.id not in candidate_pooch_ids:
                    candidate_pooch_ids.append(conjured.id)
                if conjured.id not in context.affected_pooch_ids:
                    context.affected_pooch_ids.append(conjured.id)
                result.pooches_created.append(conjured.id)
                result.pooches_affected.append(conjured.id)
                if dest_key == "kennel":
                    result.message = f"{conjured.name} was conjured and placed in {kennel_name}!"
                else:
                    result.message = f"{conjured.name} was conjured!"
                save_as = parameters.get("save_as")
                if isinstance(save_as, str) and save_as:
                    context.extra_data[save_as] = {"pooch_ids": [conjured.id]}

        elif action_type == "sacrifice_pooch":
            pooch_ids = await get_target_pooch_ids(owner_discord_id, context, rng, target_type, selector, parameters)
            value_multiplier = parameters.get("value_multiplier")
            multiplier = float(value_multiplier) if isinstance(value_multiplier, (int, float)) else 1.0
            for pooch_id in pooch_ids:
                from src.database import get_pooch_by_id

                pooch = await get_pooch_by_id(pooch_id)
                if pooch is None or not pooch.alive:
                    continue
                value = round((await get_pooch_bloodskull_value(pooch_id)) * multiplier)
                await give_bloodskulls_to_owner(owner_discord_id, value)
                await give_bones_to_owner(owner_discord_id, 1)
                await set_pooch_dead(pooch_id)
                await remove_pooch_from_kennel(pooch_id)
                await damn_pooch(pooch_id)
                result.bloodskulls_changed += value
                result.pooches_killed.append(pooch_id)
            if result.pooches_killed:
                count = len(result.pooches_killed)
                result.message = (
                    "A pooch has been sacrificed!" if count == 1 else f"{count} pooches have been sacrificed!"
                )

        elif target_type == "server":
            # Delegate to server-scoped action executor
            servers = await list_servers_for_owner(owner_discord_id)
            if not servers:
                logger.warning("server-scoped action: owner %s has no servers; skipping", owner_discord_id)
            else:
                server_discord_id = rng.choice(servers).discord_id
                from ..manage_server_events import _execute_server_actions
                from ..models.events import ServerEventContext

                server_ctx = ServerEventContext(server_discord_id=server_discord_id)
                action_dict = {"action_type": action_type, "parameters": parameters}
                server_result = await _execute_server_actions(server_discord_id, [action_dict], server_ctx, rng)
                result.merge(server_result)

        else:
            logger.warning(f"Unknown action type: {action_type}")

    except Exception as e:
        logger.error(f"Error executing action {action_type}: {e}", exc_info=True)
        result.success = False
        result.message = f"Error: {str(e)}"

    return result


async def execute_event_actions(
    owner_discord_id: int, actions: list["EventAction"], context: OwnerEventContext, rng: random.Random
) -> OwnerEventResult:
    """
    Execute a list of event actions.
    """

    result = OwnerEventResult()

    for action in sorted(actions, key=lambda a: a.action_order):
        repeat = max(int(action.repeat), 1) if isinstance(action.repeat, int) else 1
        for _ in range(repeat):
            action_result = await _execute_single_action(owner_discord_id, action, context, rng)
            result.merge(action_result)

    return result


async def create_and_execute_event(
    owner_discord_id: int,
    event: "EventDB",
    rng: random.Random,
    inherited_slots: Optional[dict] = None,
) -> Optional[TriggeredOwnerEvent]:
    """
    Create an active event and execute it if it doesn't require a response.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner.

    event: OwnerEvent
        The event to trigger.

    rng: Random
        Random number generator.

    Returns
    -------
    TriggeredOwnerEvent, optional
        The triggered event, or None if creation failed.
    """

    context = await create_event_context(owner_discord_id, event, rng)
    if inherited_slots:
        context.extra_data.update(inherited_slots)

    expires_at = None
    if event.requires_response:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=event.response_timeout)

    active_event = await create_active_owner_event(
        event_id=event.id,
        owner_discord_id=owner_discord_id,
        context=context.to_dict(),
        expires_at=expires_at,
    )

    if active_event is None:
        logger.error(f"Failed to create active event for owner {owner_discord_id}")
        return None

    logger.info(f"Triggered event '{event.name}' for owner {owner_discord_id}")

    # OwnerEvent-level actions always fire immediately at trigger time (before the user picks)
    result = await execute_event_actions(owner_discord_id, event.actions, context, rng)
    await update_active_event_result(active_event.id, result.to_dict())

    # Preflight: pre-resolve exclude_claimed targets for visible options so that each option
    # gets a unique pooch and options with no valid target are suppressed.
    if event.requires_response:
        claimed_ids: set[int] = set()
        suppressed_option_ids: list[int] = []

        for option in sorted(event.options, key=lambda o: o.option_order):
            if not option.is_visible:
                continue
            option_suppressed = False
            for action_order, action in enumerate(sorted(option.actions, key=lambda a: a.action_order)):
                if not action.parameters.get("exclude_claimed", False):
                    continue
                # Resolve candidate pooch IDs for this action, excluding already-claimed IDs
                action_filter_raw = action.parameters.get("filter", {})
                action_filter_spec = action_filter_raw if isinstance(action_filter_raw, dict) else {}
                try:
                    candidate_ids = await list_matching_pooch_ids(owner_discord_id, action_filter_spec)
                    candidate_ids = [pid for pid in candidate_ids if pid not in claimed_ids]
                except Exception:
                    candidate_ids = []

                if not candidate_ids:
                    option_suppressed = True
                    break
                chosen_id = rng.choice(candidate_ids)
                claimed_ids.add(chosen_id)
                slot_key = f"_claimed_{option.id}_{action_order}"
                context.extra_data[slot_key] = chosen_id

            if option_suppressed:
                suppressed_option_ids.append(option.id)

        if suppressed_option_ids:
            context.extra_data["suppressed_option_ids"] = suppressed_option_ids

    # Persist the updated context so named slots written by trigger-time actions
    # (via save_as) survive to response/expiry time when context is reloaded from DB.
    if event.requires_response:
        await update_active_event_context(active_event.id, context.to_dict())

    if not event.requires_response:
        await archive_active_event(active_event.id)

    active_event.result_summary = result.to_dict()
    active_event.context = context.to_dict()
    active_event.expires_at = expires_at
    return await to_triggered_owner_event(active_event)
