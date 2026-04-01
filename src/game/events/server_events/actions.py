"""
Server-scoped action execution for server events.
"""

from __future__ import annotations

import logging
import random
from typing import Optional

from src.database import (
    add_pooch_to_strays,
    create_pooch,
    get_pooch_by_id,
    get_stray_event_by_name,
    list_matching_stray_pooch_ids,
    remove_pooch_from_kennel,
    revive_pooch,
    session_scope,
)
from src.game.breeding import breed_pooches as _breed_pooches
from src.game.constants import FIGHT_DEFENDER_STRENGTH_BONUS, FIGHT_ROUNDS
from src.game.events.shared import (
    apply_baby_overrides,
    apply_random_mutations,
    build_clone_kwargs,
    build_pooch_kwargs,
    copy_pooch_genetics,
    deliver_to_any_kennel,
    deliver_to_vendor,
)
from src.game.events.shared import get_amount_from_parameters as _get_amount
from src.game.events.shared import (
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
from src.game.models.events import OwnerEventResult, ServerEventContext

logger = logging.getLogger(__name__)


async def _deliver_server_pooch(
    pooch_id: int,
    server_discord_id: int,
    destination: str,
    rng: random.Random,
) -> None:
    """Route a pooch to its destination in a server event context."""
    dest = destination.strip().lower()
    if dest == "town":
        await add_pooch_to_strays(pooch_id, server_discord_id)
    elif dest == "kennel":
        placed = await deliver_to_any_kennel(pooch_id, server_discord_id, rng)
        if not placed:
            await add_pooch_to_strays(pooch_id, server_discord_id)
    elif dest == "vendor":
        placed = await deliver_to_vendor(pooch_id, server_discord_id, rng)
        if not placed:
            await add_pooch_to_strays(pooch_id, server_discord_id)


async def resolve_server_pool(
    server_discord_id: int,
    pool: str,
    filter_spec: dict | None,
    rng: random.Random,
    server_context: ServerEventContext | None = None,
    use_saved: str | None = None,
) -> list[int]:
    """Resolve a named pool + optional PoochFilterSpec into a list of pooch IDs.

    pool values: "stray" | "dead" | "in_hell" | "all_alive" | "all" | "saved"
    """
    from src.database import list_strays_for_server
    from src.database.utils import get_matching_stray_pooch_ids_for_server_filtered

    pool_key = str(pool).strip().lower()
    base_filter = dict(filter_spec or {})
    base_filter.pop("min_count", None)
    base_filter.pop("max_count", None)
    base_filter.pop("description", None)

    if pool_key == "saved":
        if server_context is not None and use_saved:
            return list(server_context.saved_slots.get(use_saved, []))
        return []

    if pool_key == "stray":
        async with session_scope() as session:
            if base_filter:
                return await get_matching_stray_pooch_ids_for_server_filtered(session, server_discord_id, base_filter)
            strays = await list_strays_for_server(server_discord_id)
            return [p.id for p in strays if p.alive]

    if pool_key == "dead":
        from src.database.utils import (
            get_matching_dead_pooch_ids_for_server,
        )

        async with session_scope() as session:
            return await get_matching_dead_pooch_ids_for_server(session, server_discord_id, base_filter or None)

    if pool_key == "in_hell":
        from src.database.utils import (
            get_matching_hell_pooch_ids_for_server,
        )

        async with session_scope() as session:
            return await get_matching_hell_pooch_ids_for_server(session, server_discord_id, base_filter or None)

    if pool_key in ("all_alive", "all"):
        from sqlalchemy import select

        from src.database import list_living_pooches
        from src.database.models import OwnerServer as OwnerServerModel

        async with session_scope() as session:
            owner_ids_result = await session.execute(
                select(OwnerServerModel.owner_discord_id).where(OwnerServerModel.server_discord_id == server_discord_id)
            )
            owner_ids = set(owner_ids_result.scalars().all())
        pooches = await list_living_pooches()
        return [p.id for p in pooches if p.owner_discord_id in owner_ids]

    logger.warning("resolve_server_pool: unknown pool '%s'; returning empty", pool)
    return []


async def resolve_server_owner_pool(
    server_discord_id: int,
    pool: str,
    rng: random.Random,
    server_context: ServerEventContext | None = None,
    use_saved: str | None = None,
    selector: str = "all",
    count: int = 1,
) -> list[int]:
    """Resolve a named owner pool into a list of owner discord IDs."""
    from sqlalchemy import select

    from src.database.models import OwnerServer as OwnerServerModel

    pool_key = str(pool).strip().lower()

    if pool_key == "saved_owner":
        if server_context is not None and use_saved:
            return list(server_context.saved_owner_slots.get(use_saved, []))
        return []

    if pool_key == "owner":
        async with session_scope() as session:
            result = await session.execute(
                select(OwnerServerModel.owner_discord_id).where(OwnerServerModel.server_discord_id == server_discord_id)
            )
            all_owner_ids = list(result.scalars().all())

        if selector == "all":
            return all_owner_ids
        elif selector in ("random", "random_exclude"):
            return rng.sample(all_owner_ids, min(count, len(all_owner_ids))) if all_owner_ids else []
        elif selector == "first":
            return all_owner_ids[:count]
        return all_owner_ids

    logger.warning("resolve_server_owner_pool: unknown pool '%s'; returning empty", pool)
    return []


async def execute_server_actions(
    server_discord_id: int,
    actions: list,
    server_context: ServerEventContext,
    rng: random.Random,
    season: Optional[str] = None,
) -> OwnerEventResult:
    """Execute a list of server-scoped action specs (plain dicts, not ORM EventAction objects)."""
    combined = OwnerEventResult()
    _owner_pool_keys = {"owner", "saved_owner"}

    for action_spec in actions:
        action_type = str(action_spec.get("action_type", "")).strip().lower()
        parameters = action_spec.get("parameters", {}) or {}
        pool = str(parameters.get("pool", "stray")).strip().lower()
        selector = str(parameters.get("selector", "all")).strip().lower()
        count = int(parameters.get("count", 1))
        filter_spec = parameters.get("filter") or {}
        save_as = parameters.get("save_as")
        use_saved = parameters.get("use_saved")
        destination = str(parameters.get("destination", "stray")).strip().lower()

        try:
            # ----------------------------------------------------------------
            # Owner-pool actions (modify_money / modify_bloodskulls)
            # ----------------------------------------------------------------
            if pool in _owner_pool_keys:
                owner_ids = await resolve_server_owner_pool(
                    server_discord_id, pool, rng, server_context, use_saved, selector, count
                )
                if save_as and isinstance(save_as, str):
                    server_context.saved_owner_slots[save_as] = list(owner_ids)

                if action_type == "modify_money":
                    from src.database import give_money_to_owner

                    roll_once = bool(parameters.get("roll_once", False))
                    if roll_once:
                        amount = _get_amount(parameters, rng)
                        for oid in owner_ids:
                            await give_money_to_owner(oid, amount)
                        combined.money_changed += amount * len(owner_ids)
                    else:
                        for oid in owner_ids:
                            amount = _get_amount(parameters, rng)
                            await give_money_to_owner(oid, amount)
                            combined.money_changed += amount

                elif action_type == "modify_bloodskulls":
                    from src.database import give_bloodskulls_to_owner

                    roll_once = bool(parameters.get("roll_once", False))
                    if roll_once:
                        amount = _get_amount(parameters, rng)
                        for oid in owner_ids:
                            await give_bloodskulls_to_owner(oid, amount)
                        combined.bloodskulls_changed += amount * len(owner_ids)
                    else:
                        for oid in owner_ids:
                            amount = _get_amount(parameters, rng)
                            await give_bloodskulls_to_owner(oid, amount)
                            combined.bloodskulls_changed += amount
                else:
                    logger.warning(
                        "execute_server_actions: action_type '%s' is not supported for owner pools; skipping",
                        action_type,
                    )
                continue

            candidate_ids = await resolve_server_pool(
                server_discord_id, pool, filter_spec, rng, server_context, use_saved
            )

            if selector == "all":
                target_ids = candidate_ids
            elif selector in ("random", "random_exclude"):
                target_ids = rng.sample(candidate_ids, min(count, len(candidate_ids))) if candidate_ids else []
            elif selector == "first":
                target_ids = candidate_ids[:count]
            else:
                target_ids = candidate_ids

            if save_as and isinstance(save_as, str):
                server_context.saved_slots[save_as] = list(target_ids)

            if parameters.get("save_owner") and save_as and isinstance(save_as, str):
                owner_ids_for_slot: list[int] = []
                for pid in target_ids:
                    pooch = await get_pooch_by_id(pid)
                    if pooch is not None and pooch.owner_discord_id not in owner_ids_for_slot:
                        owner_ids_for_slot.append(pooch.owner_discord_id)
                server_context.saved_owner_slots[save_as] = owner_ids_for_slot

            # ----------------------------------------------------------------
            # Shared pooch action handlers
            # ----------------------------------------------------------------
            if action_type == "modify_base_health":
                await handle_modify_health(target_ids, parameters, rng, combined)
            elif action_type == "injure_pooch":
                await handle_injure_pooch(target_ids, parameters, rng, combined)
            elif action_type in ("modify_pooch_age", "set_pooch_age"):
                await handle_modify_age(target_ids, parameters, rng, combined)
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
                await handle_modify_stat(action_type, target_ids, parameters, rng, combined)
            elif action_type == "kill_pooch":
                await handle_kill_pooch(target_ids, parameters, rng, combined)
            elif action_type == "damn_pooch":
                _stub_ctx = type("_Ctx", (), {"extra_data": {}, "candidate_ids": list(target_ids)})()
                await handle_damn_pooch(target_ids, parameters, rng, combined, _stub_ctx, "candidate_ids")

            # ----------------------------------------------------------------
            # Mutation / breed management
            # ----------------------------------------------------------------
            elif action_type == "add_mutation":
                mutation_names_raw = parameters.get("mutations") or parameters.get("mutation") or []
                if isinstance(mutation_names_raw, str):
                    mutation_names_raw = [mutation_names_raw]
                if not mutation_names_raw:
                    await handle_add_mutation(target_ids, parameters, rng, combined)
                else:
                    for mut_name in mutation_names_raw:
                        params_with_name = dict(parameters)
                        params_with_name["mutation"] = mut_name
                        await handle_add_mutation(target_ids, params_with_name, rng, combined)
            elif action_type == "remove_mutation":
                await handle_remove_mutation(target_ids, parameters, rng, combined)
            elif action_type == "add_breed":
                await handle_add_breed(target_ids, parameters, rng, combined)
            elif action_type == "remove_breed":
                await handle_remove_breed(target_ids, parameters, rng, combined)
            elif action_type == "rename_pooch":
                await handle_rename_pooch(target_ids, parameters, rng, combined)
            elif action_type == "modify_breeding_cooldown":
                await handle_modify_breeding_cooldown(target_ids, parameters, rng, combined)

            # ----------------------------------------------------------------
            # Placement / transfers
            # ----------------------------------------------------------------
            elif action_type == "release_stray":
                for pid in target_ids:
                    await remove_pooch_from_kennel(pid)
                    await add_pooch_to_strays(pid, server_discord_id)
                    combined.pooches_affected.append(pid)

            elif action_type == "revive_pooch":
                revive_destination = str(parameters.get("destination", "kennel")).strip().lower()
                for pid in target_ids:
                    pooch = await revive_pooch(pid)
                    if pooch:
                        await _deliver_server_pooch(pid, server_discord_id, revive_destination, rng)
                        combined.pooches_affected.append(pid)

            elif action_type == "enter_kennel":
                for pid in target_ids:
                    placed = await deliver_to_any_kennel(pid, server_discord_id, rng)
                    if placed:
                        combined.pooches_affected.append(pid)

            elif action_type == "enter_vendor_stock":
                for pid in target_ids:
                    placed = await deliver_to_vendor(pid, server_discord_id, rng)
                    if placed:
                        combined.pooches_affected.append(pid)

            # ----------------------------------------------------------------
            # Pooch creation
            # ----------------------------------------------------------------
            elif action_type == "create_pooch":
                kwargs = await build_pooch_kwargs(parameters, rng, season=season)
                mutations_param = parameters.get("mutations")
                pooch = await create_pooch(**kwargs)
                if pooch:
                    await apply_random_mutations(pooch.id, mutations_param, rng, season=season)
                    await _deliver_server_pooch(pooch.id, server_discord_id, destination, rng)
                    combined.pooches_created.append(pooch.id)
                    combined.pooches_affected.append(pooch.id)
                    if save_as and isinstance(save_as, str):
                        server_context.saved_slots[save_as] = [pooch.id]

            elif action_type == "clone_pooch":
                source_id = target_ids[0] if target_ids else None
                if source_id is None:
                    logger.warning("execute_server_actions: clone_pooch — no source resolved; skipping")
                else:
                    source = await get_pooch_by_id(source_id)
                    if source is None:
                        logger.warning("execute_server_actions: clone_pooch — source %s not found", source_id)
                    else:
                        clone_kwargs = build_clone_kwargs(source, parameters, rng)
                        clone = await create_pooch(**clone_kwargs)
                        if clone:
                            await copy_pooch_genetics(source_id, clone.id)
                            await _deliver_server_pooch(clone.id, server_discord_id, destination, rng)
                            combined.pooches_created.append(clone.id)
                            combined.pooches_affected.append(clone.id)
                            for spec in resolve_save_as_specs(parameters.get("save_as")):
                                slot = spec.get("slot")
                                target = spec.get("target", "clone")
                                if isinstance(slot, str) and slot:
                                    server_context.saved_slots[slot] = [source_id] if target == "source" else [clone.id]

            elif action_type == "breed_pooches":
                first_filter = parameters.get("first_filter") or {}
                second_filter = parameters.get("second_filter") or {}
                pool_first = (
                    await list_matching_stray_pooch_ids(server_discord_id, first_filter)
                    if first_filter
                    else list(candidate_ids)
                )
                pool_second = (
                    await list_matching_stray_pooch_ids(server_discord_id, second_filter)
                    if second_filter
                    else list(candidate_ids)
                )
                require_unique = bool(parameters.get("require_unique", True))
                require_same = bool(parameters.get("require_same", False))
                first_id = rng.choice(pool_first) if pool_first else None
                if require_same:
                    second_id = first_id
                else:
                    pool_s = [p for p in pool_second if p != first_id] if require_unique else pool_second
                    second_id = rng.choice(pool_s) if pool_s else None
                if first_id is None or second_id is None:
                    logger.warning("execute_server_actions: breed_pooches — could not resolve parents; skipping")
                else:
                    try:
                        baby_ids = await _breed_pooches(
                            first_id, second_id, rng_seed=rng.randint(0, 2**31), skip_validation=True
                        )
                        for baby_id in baby_ids:
                            await _deliver_server_pooch(baby_id, server_discord_id, destination, rng)
                            await apply_baby_overrides(baby_id, parameters)
                        combined.pooches_created.extend(baby_ids)
                        combined.pooches_affected.extend(baby_ids)
                        for spec in resolve_save_as_specs(parameters.get("save_as")):
                            slot = spec.get("slot")
                            t = spec.get("target", "baby")
                            if isinstance(slot, str) and slot:
                                if t == "first_parent":
                                    server_context.saved_slots[slot] = [first_id]
                                elif t == "second_parent":
                                    server_context.saved_slots[slot] = [second_id]
                                else:
                                    server_context.saved_slots[slot] = list(baby_ids)
                    except ValueError as exc:
                        logger.warning("execute_server_actions: breed_pooches failed — %s", exc)

            # ----------------------------------------------------------------
            # Select (no side-effects)
            # ----------------------------------------------------------------
            elif action_type == "select_pooch":
                if save_as and isinstance(save_as, str):
                    server_context.saved_slots[save_as] = list(target_ids)

            # ----------------------------------------------------------------
            # Event chaining
            # ----------------------------------------------------------------
            elif action_type == "start_stray_event":
                event_name = parameters.get("event")
                if isinstance(event_name, str) and event_name.strip():
                    stray_event = await get_stray_event_by_name(event_name.strip())
                    if stray_event is None:
                        logger.warning("execute_server_actions: start_stray_event — unknown '%s'", event_name)
                    else:
                        from src.database import list_strays_for_server as _list_strays
                        from src.game.events.stray_events import (
                            choose_stray_event_outcome,
                            execute_stray_event_actions,
                        )
                        from src.game.models import StrayEventContext

                        strays = await _list_strays(server_discord_id)
                        stray_ctx = StrayEventContext(
                            server_discord_id=server_discord_id,
                            candidate_stray_ids=[p.id for p in strays if p.alive],
                        )
                        stray_result = await execute_stray_event_actions(
                            server_discord_id, stray_event.actions, stray_ctx, rng
                        )
                        combined.merge(stray_result)
                        outcome = await choose_stray_event_outcome(stray_event, stray_ctx, rng)
                        if outcome is not None:
                            outcome_result = await execute_stray_event_actions(
                                server_discord_id, outcome.actions, stray_ctx, rng
                            )
                            combined.merge(outcome_result)

            elif action_type == "start_server_event":
                event_name = parameters.get("event")
                if isinstance(event_name, str) and event_name.strip():
                    from src.database import get_server_event_by_name

                    server_event = await get_server_event_by_name(event_name.strip())
                    if server_event is None:
                        logger.warning("execute_server_actions: start_server_event — unknown '%s'", event_name)
                    else:
                        chained_actions = [
                            {"action_type": a.action_type, "parameters": a.parameters or {}}
                            for a in server_event.actions
                        ]
                        chained_result = await execute_server_actions(
                            server_discord_id, chained_actions, server_context, rng, season=season
                        )
                        combined.merge(chained_result)

            elif action_type == "fight_pooches":
                from src.game.events.shared import handle_fight_pooches

                attacker_slot = parameters.get("attacker_slot")
                defender_slot = parameters.get("defender_slot")

                def _ids_from_saved(slot_name: str) -> list[int]:
                    return list(server_context.saved_slots.get(slot_name, []))

                attacker_id = None
                defender_id = None
                if isinstance(attacker_slot, str) and attacker_slot:
                    ids = _ids_from_saved(attacker_slot)
                    attacker_id = ids[0] if ids else None
                if isinstance(defender_slot, str) and defender_slot:
                    ids = _ids_from_saved(defender_slot)
                    defender_id = ids[0] if ids else None

                if attacker_id is None or defender_id is None:
                    if len(target_ids) >= 2:
                        chosen = rng.sample(list(target_ids), 2)
                        attacker_id, defender_id = chosen[0], chosen[1]

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
                    combined.extra_data["fight_result"] = fight_result
                    combined.pooches_affected.extend(
                        pid for pid in [attacker_id, defender_id] if pid not in combined.pooches_affected
                    )
                    if fight_result.get("attacker_died"):
                        combined.pooches_killed.append(attacker_id)
                    if fight_result.get("defender_died"):
                        combined.pooches_killed.append(defender_id)
                    fight_save_as = parameters.get("save_as")
                    if isinstance(fight_save_as, str) and fight_save_as and fight_result.get("winner_id"):
                        server_context.saved_slots[fight_save_as] = [fight_result["winner_id"]]
                else:
                    logger.warning("execute_server_actions: fight_pooches — could not resolve both pooches; skipping")

            else:
                logger.warning("execute_server_actions: unknown action_type '%s'; skipping", action_type)

        except Exception as exc:
            logger.error("execute_server_actions: error in action '%s': %s", action_type, exc, exc_info=True)

    return combined
