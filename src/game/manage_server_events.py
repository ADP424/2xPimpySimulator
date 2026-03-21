from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from src.database import (
    append_server_event_submission,
    create_server_event_occurrence,
    create_server_event_participation,
    finalize_server_event_participation,
    get_active_server_event_occurrence,
    get_owner_by_discord_id,
    get_owner_server,
)
from src.database import get_pooch_by_id as db_get_pooch_by_id
from src.database import (
    get_server_by_discord_id,
    get_server_event_menu_option_by_id,
    get_server_event_occurrence_by_id,
    get_server_event_participation,
    list_active_server_event_occurrences,
    list_all_server_events_with_weights,
    list_kennels_for_owner,
    list_pooches_for_kennel,
    list_servers,
    list_strays_for_server,
    resolve_server_event_occurrence,
    session_scope,
    set_server_event_occurrence_message_discord_id,
)
from src.database.utils import check_server_event_filter, weighted_choice
from src.logger import get_logger

from .manage_owner_events import _execute_event_actions
from .manage_owners import get_or_create_owner
from .models.events import (
    OwnerEventContext,
    OwnerEventResult,
    ServerEventContext,
    ServerEventParticipationSummary,
    ServerEventResolution,
    TriggeredServerEvent,
    to_server_event_participation_summary,
    to_triggered_server_event,
)

if TYPE_CHECKING:
    from src.database.models import ServerEventOccurrence, ServerEventParticipation

logger = get_logger("game/manage_server_events")

SERVER_EVENT_DURATION = timedelta(days=1)


def _roll_outcome_chance(chance: float | None, rng: random.Random) -> bool:
    if chance is None:
        return True
    return rng.random() <= float(chance)


def _matches_rank(min_rank: int | None, max_rank: int | None, rank: int | None) -> bool:
    if rank is None:
        return min_rank is None and max_rank is None
    if min_rank is not None and rank < min_rank:
        return False
    if max_rank is not None and rank > max_rank:
        return False
    return True


async def _build_owner_event_context(owner_discord_id: int, selected_pooch_id: int | None = None) -> OwnerEventContext:
    context = OwnerEventContext(owner_discord_id=owner_discord_id)
    kennels = await list_kennels_for_owner(owner_discord_id)
    candidate_kennel_ids = [kennel.id for kennel in kennels]
    candidate_pooch_ids: list[int] = []
    for kennel in kennels:
        pooches = await list_pooches_for_kennel(kennel.id)
        candidate_pooch_ids.extend([pooch.id for pooch in pooches if pooch.alive])

    context.extra_data["candidate_kennel_ids"] = candidate_kennel_ids
    context.extra_data["candidate_pooch_ids"] = candidate_pooch_ids
    if selected_pooch_id is not None:
        context.selected_pooch_id = selected_pooch_id
        if selected_pooch_id not in context.affected_pooch_ids:
            context.affected_pooch_ids.append(selected_pooch_id)
    return context


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


async def _compute_submission_score(
    submission: dict,
    scoring: dict,
    rng: random.Random,
) -> float:
    """Evaluate a ScoringSpec against a single submission, returning the raw score."""
    sources: list[dict] = scoring.get("sources", [])
    if not sources:
        return 0.0

    total = 0.0
    for source in sources:
        source_type = str(source.get("type", "random")).strip().lower()

        if source_type == "random":
            lo = float(source.get("min", 0.0))
            hi = float(source.get("max", 1.0))
            total += rng.uniform(lo, hi)

        elif source_type == "constant":
            total += float(source.get("value", 0.0))

        elif source_type == "pooch_stat":
            pooch_id = submission.get("selected_pooch_id")
            if pooch_id is not None:
                pooch = await db_get_pooch_by_id(pooch_id)
                if pooch is not None:
                    stat = str(source.get("stat", "base_health"))
                    raw = float(getattr(pooch, stat, 0) or 0)
                    pivot = float(source.get("pivot", 0.0))
                    scale = float(source.get("scale", 1.0))
                    direction = float(source.get("direction", 1.0))
                    total += (raw - pivot) * scale * direction

        elif source_type == "owner_stat":
            owner_discord_id = submission.get("owner_discord_id")
            if owner_discord_id is not None:
                owner = await get_owner_by_discord_id(owner_discord_id)
                if owner is not None:
                    stat = str(source.get("stat", "money"))
                    raw_val = getattr(owner, stat, None)
                    if raw_val is None and stat == "money":
                        raw_val = owner.dollars
                    raw = float(raw_val or 0)
                    pivot = float(source.get("pivot", 0.0))
                    scale = float(source.get("scale", 1.0))
                    direction = float(source.get("direction", 1.0))
                    total += (raw - pivot) * scale * direction

    return total


def _aggregate_player_score(per_submission_scores: list[float], aggregate: str) -> float:
    """Combine multiple submission scores using the given aggregation method."""
    if not per_submission_scores:
        return 0.0
    if aggregate == "average":
        return sum(per_submission_scores) / len(per_submission_scores)
    if aggregate == "max":
        return max(per_submission_scores)
    # default: "sum"
    return sum(per_submission_scores)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


async def _rank_participations(
    occurrence: ServerEventOccurrence, rng: random.Random
) -> list[tuple[ServerEventParticipation, float, int]]:
    """Score and rank all participations for an occurrence.

    Scoring is based on the ScoringSpec attached to the menu option for each submission.
    If multiple submissions exist from the same player, they are aggregated per the
    ScoringSpec.aggregate field (default: sum).
    """
    scored: list[tuple[ServerEventParticipation, float, float]] = []

    for participation in occurrence.participations:
        submissions = list(participation.submissions or [])
        if not submissions:
            scored.append((participation, 0.0, rng.random()))
            continue

        # Group per-option submission scores by option's scoring.aggregate setting.
        # Use the aggregate from the first submission that has a scoring spec, or fallback to "sum".
        # In practice all submissions for a participation use the same option/scoring.
        per_scores: list[float] = []
        aggregate = "sum"
        for sub in submissions:
            scoring_spec = sub.get("scoring") or {}
            aggregate = str(scoring_spec.get("aggregate", aggregate)).strip().lower()
            score = await _compute_submission_score(sub, scoring_spec, rng)
            per_scores.append(score)

        total_score = _aggregate_player_score(per_scores, aggregate)
        scored.append((participation, total_score, rng.random()))

    ordered = sorted(scored, key=lambda item: (item[1], item[2]), reverse=True)
    return [(participation, score, index + 1) for index, (participation, score, _) in enumerate(ordered)]


# ---------------------------------------------------------------------------
# Server-scoped action execution
# ---------------------------------------------------------------------------


async def _resolve_server_pool(
    server_discord_id: int,
    pool: str,
    filter_spec: dict | None,
    rng: random.Random,
    server_context: ServerEventContext | None = None,
    save_slot: str | None = None,
) -> list[int]:
    """Resolve a named pool + optional PoochFilterSpec into a list of pooch IDs.

    pool values: "stray" | "dead" | "in_hell" | "all_alive" | "all" | "saved"
    When pool is "saved", save_slot names the server_context.saved_slots key to use.
    """
    from src.database.utils import get_matching_stray_pooch_ids_for_server_filtered

    pool_key = str(pool).strip().lower()

    # Build a stripped filter (no count metadata)
    base_filter = dict(filter_spec or {})
    base_filter.pop("min_count", None)
    base_filter.pop("max_count", None)
    base_filter.pop("description", None)

    if pool_key == "saved":
        if server_context is not None and save_slot:
            return list(server_context.saved_slots.get(save_slot, []))
        return []

    if pool_key == "stray":
        async with session_scope() as session:
            if base_filter:
                return await get_matching_stray_pooch_ids_for_server_filtered(session, server_discord_id, base_filter)
            strays = await list_strays_for_server(server_discord_id)
            return [p.id for p in strays if p.alive]

    if pool_key == "dead":
        from src.database.utils.owner_event_filters import (
            _get_matching_dead_pooch_ids_for_server,
        )

        async with session_scope() as session:
            return await _get_matching_dead_pooch_ids_for_server(session, server_discord_id, base_filter or None)

    if pool_key == "in_hell":
        from src.database.utils.owner_event_filters import (
            _get_matching_hell_pooch_ids_for_server,
        )

        async with session_scope() as session:
            return await _get_matching_hell_pooch_ids_for_server(session, server_discord_id, base_filter or None)

    # all_alive / all: living pooches owned by anyone in this server
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
        candidates = [p.id for p in pooches if p.owner_discord_id in owner_ids]
        return candidates

    logger.warning("_resolve_server_pool: unknown pool '%s'; returning empty", pool)
    return []


async def _deliver_server_pooch(
    pooch_id: int,
    server_discord_id: int,
    destination: str,
    rng: random.Random,
) -> None:
    """Route a pooch to its destination after creation or revival in a server event context."""
    from src.database import add_pooch_to_strays

    dest = destination.strip().lower()
    if dest == "stray" or dest == "town":
        await add_pooch_to_strays(pooch_id, server_discord_id)
    elif dest == "kennel":
        from src.game.manage_stray_events import _deliver_stray_to_kennel

        placed = await _deliver_stray_to_kennel(pooch_id, server_discord_id, rng)
        if not placed:
            await add_pooch_to_strays(pooch_id, server_discord_id)
    elif dest == "vendor":
        from src.game.manage_stray_events import _deliver_stray_to_vendor

        placed = await _deliver_stray_to_vendor(pooch_id, server_discord_id, rng)
        if not placed:
            await add_pooch_to_strays(pooch_id, server_discord_id)
    # "graveyard" / "hell" left as-is (no placement needed; pooch already dead/damned)


async def _execute_server_actions(
    server_discord_id: int,
    actions: list,
    server_context: ServerEventContext,
    rng: random.Random,
) -> OwnerEventResult:
    """Execute a list of server-scoped action specs (plain dicts, not ORM EventAction objects)."""
    from src.database import (
        add_mutation_to_pooch,
        add_pooch_breeds,
        add_pooch_to_strays,
        create_pooch,
        get_pooch_by_id,
        get_random_breed_ids,
        get_stray_event_by_name,
        list_matching_stray_pooch_ids,
        list_pooch_breed_weights,
        list_pooch_mutations,
        remove_pooch_from_kennel,
        rename_pooch,
        revive_pooch,
    )
    from src.game.action_helpers.pooch_actions import (
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
    from src.game.breeding import breed_pooches as _breed_pooches

    combined = OwnerEventResult()

    for action_spec in actions:
        action_type = str(action_spec.get("action_type", "")).strip().lower()
        parameters = action_spec.get("parameters", {}) or {}
        pool = str(parameters.get("pool", "stray")).strip().lower()
        selector = str(parameters.get("selector", "all")).strip().lower()
        count = int(parameters.get("count", 1))
        filter_spec = parameters.get("filter") or {}
        save_as = parameters.get("save_as")
        save_slot = parameters.get("save_slot")
        destination = str(parameters.get("destination", "stray")).strip().lower()

        try:
            candidate_ids = await _resolve_server_pool(
                server_discord_id, pool, filter_spec, rng, server_context, save_slot
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

            # ----------------------------------------------------------------
            # Health, age, stats — delegate to shared pooch_actions helpers
            # ----------------------------------------------------------------
            if action_type in ("modify_base_health", "modify_pooch_health"):
                await handle_modify_health(target_ids, parameters, rng, combined)

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
                # Use a minimal stub context so handle_damn_pooch can remove from a candidate pool
                _stub_ctx = type("_Ctx", (), {"extra_data": {}, "candidate_ids": list(target_ids)})()
                await handle_damn_pooch(target_ids, parameters, rng, combined, _stub_ctx, "candidate_ids")

            # ----------------------------------------------------------------
            # Mutation / breed management
            # ----------------------------------------------------------------
            elif action_type == "add_mutation":
                # Server events use "mutation" (name) or "mutations" (list of names)
                # Normalise into a single "mutation" key pointing at one name for the helper,
                # or loop if multiple names were given.
                mutation_names_raw = parameters.get("mutations") or parameters.get("mutation") or []
                if isinstance(mutation_names_raw, str):
                    mutation_names_raw = [mutation_names_raw]
                if not mutation_names_raw:
                    # Random mutation — delegate directly
                    await handle_add_mutation_by_name(target_ids, parameters, rng, combined)
                else:
                    for mut_name in mutation_names_raw:
                        params_with_name = dict(parameters)
                        params_with_name["mutation"] = mut_name
                        await handle_add_mutation_by_name(target_ids, params_with_name, rng, combined)

            elif action_type == "remove_mutation":
                await handle_remove_mutation_by_name(target_ids, parameters, rng, combined)

            elif action_type == "add_breed":
                await handle_add_breed(target_ids, parameters, rng, combined)

            elif action_type == "remove_breed":
                await handle_remove_breed(target_ids, parameters, rng, combined)

            elif action_type == "rename_pooch":
                await handle_rename_pooch(target_ids, parameters, rng, combined)

            elif action_type in ("modify_breeding_cooldown", "set_breeding_cooldown"):
                await handle_modify_breeding_cooldown(target_ids, parameters, rng, combined)

            # ----------------------------------------------------------------
            # Placement / ownership transfers
            # ----------------------------------------------------------------
            elif action_type == "release_stray":
                for pid in target_ids:
                    await remove_pooch_from_kennel(pid)
                    await add_pooch_to_strays(pid, server_discord_id)
                    combined.pooches_affected.append(pid)

            elif action_type == "revive_pooch":
                for pid in target_ids:
                    pooch = await revive_pooch(pid)
                    if pooch:
                        await _deliver_server_pooch(pid, server_discord_id, destination, rng)
                        combined.pooches_affected.append(pid)

            elif action_type == "enter_kennel":
                from src.game.manage_stray_events import _deliver_stray_to_kennel

                for pid in target_ids:
                    placed = await _deliver_stray_to_kennel(pid, server_discord_id, rng)
                    if placed:
                        combined.pooches_affected.append(pid)

            elif action_type == "enter_vendor_stock":
                from src.game.manage_stray_events import _deliver_stray_to_vendor

                for pid in target_ids:
                    placed = await _deliver_stray_to_vendor(pid, server_discord_id, rng)
                    if placed:
                        combined.pooches_affected.append(pid)

            # ----------------------------------------------------------------
            # Pooch creation
            # ----------------------------------------------------------------
            elif action_type == "create_pooch":
                kwargs: dict = {"rng": rng}
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
                if pooch:
                    if isinstance(mutations_param, int) and mutations_param > 0:
                        for _ in range(mutations_param):
                            await add_mutation_to_pooch(pooch.id, rng=rng)
                    await _deliver_server_pooch(pooch.id, server_discord_id, destination, rng)
                    combined.pooches_created.append(pooch.id)
                    combined.pooches_affected.append(pooch.id)
                    if save_as and isinstance(save_as, str):
                        server_context.saved_slots[save_as] = [pooch.id]

            elif action_type == "clone_pooch":
                source_id = target_ids[0] if target_ids else None
                if source_id is None:
                    logger.warning("_execute_server_actions: clone_pooch — no source resolved; skipping")
                else:
                    source = await get_pooch_by_id(source_id)
                    if source is None:
                        logger.warning("_execute_server_actions: clone_pooch — source %s not found", source_id)
                    else:
                        clone_kwargs: dict = {
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
                            await _deliver_server_pooch(clone.id, server_discord_id, destination, rng)
                            combined.pooches_created.append(clone.id)
                            combined.pooches_affected.append(clone.id)
                            # save_as: string → save clone; list of {slot, target} → save clone or source
                            save_as_raw = parameters.get("save_as")
                            if save_as_raw is not None:
                                if isinstance(save_as_raw, str):
                                    server_context.saved_slots[save_as_raw] = [clone.id]
                                elif isinstance(save_as_raw, list):
                                    for spec in save_as_raw:
                                        if not isinstance(spec, dict):
                                            continue
                                        slot = spec.get("slot")
                                        target = spec.get("target", "clone")
                                        if isinstance(slot, str) and slot:
                                            server_context.saved_slots[slot] = (
                                                [source_id] if target == "source" else [clone.id]
                                            )

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
                    logger.warning("_execute_server_actions: breed_pooches — could not resolve parents; skipping")
                else:
                    try:
                        baby_ids = await _breed_pooches(
                            first_id, second_id, rng_seed=rng.randint(0, 2**31), skip_validation=True
                        )
                        for baby_id in baby_ids:
                            await _deliver_server_pooch(baby_id, server_discord_id, destination, rng)
                            if "baby_name" in parameters:
                                await rename_pooch(baby_id, str(parameters["baby_name"]))
                            if "baby_age" in parameters:
                                from src.database import modify_pooch_age

                                await modify_pooch_age(baby_id, parameters["baby_age"])
                            if "baby_base_health" in parameters:
                                from src.database import modify_pooch_base_health

                                await modify_pooch_base_health(baby_id, parameters["baby_base_health"])
                            if "baby_breeding_cooldown" in parameters:
                                from src.database import set_pooch_breeding_cooldown

                                await set_pooch_breeding_cooldown(baby_id, parameters["baby_breeding_cooldown"])
                        combined.pooches_created.extend(baby_ids)
                        combined.pooches_affected.extend(baby_ids)
                        save_as_raw = parameters.get("save_as")
                        if save_as_raw is not None:
                            if isinstance(save_as_raw, str):
                                server_context.saved_slots[save_as_raw] = list(baby_ids)
                            elif isinstance(save_as_raw, list):
                                for spec in save_as_raw:
                                    if not isinstance(spec, dict):
                                        continue
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
                        logger.warning("_execute_server_actions: breed_pooches failed — %s", exc)

            # ----------------------------------------------------------------
            # Select (no side-effects — just saves to slot)
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
                        logger.warning("_execute_server_actions: start_stray_event — unknown '%s'", event_name)
                    else:
                        from src.database import list_strays_for_server as _list_strays
                        from src.game.manage_stray_events import (
                            _choose_stray_event_outcome,
                            _execute_stray_event_actions,
                        )
                        from src.game.models import StrayEventContext

                        strays = await _list_strays(server_discord_id)
                        stray_ctx = StrayEventContext(
                            server_discord_id=server_discord_id,
                            candidate_stray_ids=[p.id for p in strays if p.alive],
                        )
                        stray_result = await _execute_stray_event_actions(
                            server_discord_id, stray_event.actions, stray_ctx, rng
                        )
                        combined.merge(stray_result)
                        outcome = await _choose_stray_event_outcome(stray_event, stray_ctx, rng)
                        if outcome is not None:
                            outcome_result = await _execute_stray_event_actions(
                                server_discord_id, outcome.actions, stray_ctx, rng
                            )
                            combined.merge(outcome_result)

            elif action_type == "start_server_event":
                event_name = parameters.get("event")
                if isinstance(event_name, str) and event_name.strip():
                    from src.database import get_server_event_by_name

                    server_event = await get_server_event_by_name(event_name.strip())
                    if server_event is None:
                        logger.warning("_execute_server_actions: start_server_event — unknown '%s'", event_name)
                    else:
                        # Execute root-level actions of the chained server event immediately
                        chained_actions = [
                            {"action_type": a.action_type, "parameters": a.parameters or {}}
                            for a in server_event.actions
                        ]
                        chained_result = await _execute_server_actions(
                            server_discord_id, chained_actions, server_context, rng
                        )
                        combined.merge(chained_result)

            else:
                logger.warning("_execute_server_actions: unknown action_type '%s'; skipping", action_type)

        except Exception as exc:
            logger.error("_execute_server_actions: error in action '%s': %s", action_type, exc, exc_info=True)

    return combined


# ---------------------------------------------------------------------------
# Event eligibility filter (Python-side)
# ---------------------------------------------------------------------------


async def _check_server_filter(server_discord_id: int, filter_spec: dict | None) -> bool:
    """Evaluate a ServerEventFilterSpec against a server (Python-side, not DB-side)."""
    if not filter_spec:
        return True
    async with session_scope() as session:
        return await check_server_event_filter(session, server_discord_id, filter_spec)


# ---------------------------------------------------------------------------
# Trigger / query
# ---------------------------------------------------------------------------


async def trigger_daily_server_event(
    server_discord_id: int, rng: Optional[random.Random] = None
) -> TriggeredServerEvent | None:
    rng = rng if rng is not None else random.Random()

    existing = await get_active_server_event_occurrence(server_discord_id)
    if existing is not None:
        return await to_triggered_server_event(existing)

    server = await get_server_by_discord_id(server_discord_id)
    if server is None or server.event_channel_discord_id is None:
        return None

    all_events_with_weights = await list_all_server_events_with_weights()
    eligible: list[tuple] = []
    for event_obj, weight in all_events_with_weights:
        filter_spec = event_obj.filter or {}
        if await _check_server_filter(server_discord_id, filter_spec):
            eligible.append((event_obj, weight))

    if not eligible:
        return None

    server_event = weighted_choice(rng, eligible)

    if server_event is None:
        return None

    # Execute server-level trigger actions (target_type="server")
    server_context = ServerEventContext(server_discord_id=server_discord_id)
    if server_event.actions:
        server_actions = [a for a in server_event.actions if a.target_type == "server"]
        if server_actions:
            action_dicts = [{"action_type": a.action_type, "parameters": a.parameters or {}} for a in server_actions]
            await _execute_server_actions(server_discord_id, action_dicts, server_context, rng)

    occurrence = await create_server_event_occurrence(
        server_discord_id=server_discord_id,
        server_event_id=server_event.id,
        context=server_context.to_dict(),
        expires_at=datetime.now(timezone.utc) + SERVER_EVENT_DURATION,
    )
    hydrated = await get_server_event_occurrence_by_id(occurrence.id)
    if hydrated is None:
        return None
    logger.info("Triggered server event '%s' for server %s", server_event.name, server_discord_id)
    return await to_triggered_server_event(hydrated)


async def get_active_server_event(
    server_discord_id: int, viewer_owner_discord_id: int | None = None
) -> TriggeredServerEvent | None:
    occurrence = await get_active_server_event_occurrence(server_discord_id)
    if occurrence is None:
        return None
    return await to_triggered_server_event(occurrence, viewer_owner_discord_id)


async def list_active_server_events() -> list[TriggeredServerEvent]:
    occurrences = await list_active_server_event_occurrences()
    return [await to_triggered_server_event(occurrence) for occurrence in occurrences]


# ---------------------------------------------------------------------------
# Participation
# ---------------------------------------------------------------------------


async def participate_in_server_event(
    occurrence_id: int,
    server_discord_id: int,
    owner_discord_id: int,
    menu_option_id: int,
    selected_pooch_id: int | None = None,
    rng: Optional[random.Random] = None,
) -> tuple[bool, str, ServerEventParticipationSummary | None]:
    rng = rng if rng is not None else random.Random()

    occurrence = await get_server_event_occurrence_by_id(occurrence_id)
    if occurrence is None or occurrence.server_discord_id != server_discord_id:
        return False, "Server event not found.", None
    if occurrence.archived or occurrence.resolved_at is not None:
        return False, "This server event has already resolved.", None
    if datetime.now(timezone.utc) > occurrence.expires_at:
        return False, "This server event has already expired.", None

    await get_or_create_owner(server_discord_id, owner_discord_id)
    owner_server = await get_owner_server(server_discord_id, owner_discord_id)
    if owner_server is None:
        return False, "You must be registered in this server first.", None

    option = await get_server_event_menu_option_by_id(menu_option_id)
    if option is None or option.menu.server_event_id != occurrence.server_event_id:
        return False, "That option is not valid for this server event.", None

    menu = option.menu

    # Check depends_on: player must have already submitted to all prerequisite menus
    existing_participation = await get_server_event_participation(occurrence_id, owner_discord_id)
    used_menu_names: set[str] = set()
    if existing_participation is not None:
        for sub in list(existing_participation.submissions or []):
            used_menu_names.add(str(sub.get("menu_name", "")))

    for required_menu_name in list(menu.depends_on or []):
        if required_menu_name not in used_menu_names:
            return False, f"You must use the '{required_menu_name}' menu first.", None

    # Check max_uses_per_player
    max_uses = menu.max_uses_per_player  # -1 = unlimited
    if max_uses >= 0:
        uses_this_menu = (
            sum(1 for sub in list(existing_participation.submissions or []) if sub.get("menu_name") == menu.name)
            if existing_participation
            else 0
        )
        if uses_this_menu >= max_uses:
            return False, f"You have used the '{menu.label}' menu the maximum number of times.", None

    # Check option owner filter
    if option.filter:
        from src.database.utils import check_owner_event_filter

        async with session_scope() as session:
            if not await check_owner_event_filter(session, owner_discord_id, option.filter):
                return False, "You do not meet the requirements for that option.", None

    # Check requires.pooch
    if option.requires:
        pooch_req = option.requires.get("pooch")
        if pooch_req is not None:
            if selected_pooch_id is None:
                return False, "You must select a pooch for that option.", None
            pooch = await db_get_pooch_by_id(selected_pooch_id)
            if pooch is None or pooch.owner_discord_id != owner_discord_id:
                return False, "That pooch does not belong to you.", None
            pooch_filter = pooch_req.get("filter", {}) if isinstance(pooch_req, dict) else {}
            if pooch_filter:
                from src.database.utils import get_matching_pooch_ids_for_owner

                async with session_scope() as session:
                    matching_ids = await get_matching_pooch_ids_for_owner(session, owner_discord_id, pooch_filter)
                if selected_pooch_id not in matching_ids:
                    return False, "That pooch does not meet the requirements.", None

    context = await _build_owner_event_context(owner_discord_id, selected_pooch_id)

    # Execute option actions immediately
    immediate_result = await _execute_event_actions(owner_discord_id, option.actions, context, rng)

    # Build the submission record
    submission: dict = {
        "menu_name": menu.name,
        "menu_option_id": option.id,
        "option_label": option.label,
        "selected_pooch_id": selected_pooch_id,
        "context_snapshot": context.to_dict(),
        "scoring": option.scoring or {},
        "owner_discord_id": owner_discord_id,
        "immediate_result": immediate_result.to_dict(),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    if existing_participation is None:
        await create_server_event_participation(
            occurrence_id=occurrence_id,
            owner_discord_id=owner_discord_id,
            context=context.to_dict(),
            first_submission=submission,
            immediate_result=immediate_result.to_dict(),
        )
    else:
        await append_server_event_submission(existing_participation.id, submission)

    hydrated = await get_server_event_participation(occurrence_id, owner_discord_id)
    if hydrated is None:
        return False, "Failed to save your participation.", None

    summary = await to_server_event_participation_summary(hydrated)
    return True, f"You joined {occurrence.server_event.name}!", summary


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


async def resolve_server_event(
    occurrence_id: int,
    rng: Optional[random.Random] = None,
) -> ServerEventResolution | None:
    rng = rng if rng is not None else random.Random()
    occurrence = await get_server_event_occurrence_by_id(occurrence_id)
    if occurrence is None or occurrence.archived or occurrence.resolved_at is not None:
        return None

    server_discord_id = occurrence.server_discord_id
    server_context = ServerEventContext.from_dict(occurrence.context or {})
    server_event = occurrence.server_event

    ranked_participations = await _rank_participations(occurrence, rng)
    winner_owner_ids: list[int] = []
    winner_pooch_ids: list[int] = []

    # Fire default_actions if no one participated (or no scored submissions)
    if not ranked_participations:
        default_actions = list(server_event.default_actions_data or [])
        if default_actions:
            await _execute_server_actions(server_discord_id, default_actions, server_context, rng)
    else:
        for participation, score, rank in ranked_participations:
            context = OwnerEventContext.from_dict(participation.context or {})
            combined_result = (
                OwnerEventResult.from_dict(participation.resolution_result or {})
                if participation.resolution_result
                else OwnerEventResult()
            )
            matched_messages: list[str] = []

            for outcome in sorted(server_event.outcomes, key=lambda v: v.outcome_order):
                outcome_target = str(outcome.target or "ranked_players").strip().lower()

                if outcome_target == "ranked_players":
                    if not _matches_rank(outcome.min_rank, outcome.max_rank, rank):
                        continue
                elif outcome_target == "all_participants":
                    pass  # applies to every participant
                elif outcome_target == "non_participants":
                    continue  # handled separately below
                elif outcome_target == "server":
                    continue  # handled separately below

                if not _roll_outcome_chance(outcome.chance, rng):
                    continue

                outcome_result = await _execute_event_actions(
                    participation.owner_discord_id, outcome.actions, context, rng
                )
                if outcome.message:
                    outcome_result.message = outcome.message
                    matched_messages.append(outcome.message)
                combined_result.merge(outcome_result)

            if matched_messages and not combined_result.message:
                combined_result.message = matched_messages[-1]

            await finalize_server_event_participation(
                participation.id,
                resolution_result=combined_result.to_dict(),
                score=score,
                rank=rank,
            )
            if rank == 1:
                winner_owner_ids.append(participation.owner_discord_id)
                # Collect winner pooch IDs from first submission's selected_pooch_id
                for sub in list(participation.submissions or []):
                    pid = sub.get("selected_pooch_id")
                    if pid is not None and pid not in winner_pooch_ids:
                        winner_pooch_ids.append(pid)
                        break

        # Process server-scoped and non_participant outcomes
        participant_owner_ids = {p.owner_discord_id for p, _, _ in ranked_participations}
        for outcome in sorted(server_event.outcomes, key=lambda v: v.outcome_order):
            outcome_target = str(outcome.target or "ranked_players").strip().lower()
            if outcome_target not in ("server", "non_participants"):
                continue
            if not _roll_outcome_chance(outcome.chance, rng):
                continue

            if outcome_target == "server":
                action_dicts = [
                    {"action_type": a.action_type, "parameters": a.parameters or {}} for a in outcome.actions
                ]
                await _execute_server_actions(server_discord_id, action_dicts, server_context, rng)

            elif outcome_target == "non_participants":
                from sqlalchemy import select as _sa_select

                from src.database.models import OwnerServer as OwnerServerModel

                async with session_scope() as session:
                    result = await session.execute(
                        _sa_select(OwnerServerModel.owner_discord_id).where(
                            OwnerServerModel.server_discord_id == server_discord_id
                        )
                    )
                    all_server_owner_ids = list(result.scalars().all())

                for oid in all_server_owner_ids:
                    if oid not in participant_owner_ids:
                        non_ctx = await _build_owner_event_context(oid)
                        await _execute_event_actions(oid, outcome.actions, non_ctx, rng)

    summary = OwnerEventResult(
        message=(
            f"Resolved '{server_event.name}' with {len(ranked_participations)} participant"
            f"{'s' if len(ranked_participations) != 1 else ''}."
        )
    )
    summary.extra_data["winner_owner_ids"] = winner_owner_ids
    summary.extra_data["winner_pooch_ids"] = winner_pooch_ids
    summary.extra_data["participant_count"] = len(ranked_participations)

    await resolve_server_event_occurrence(occurrence_id, result_summary=summary.to_dict())

    return ServerEventResolution(
        occurrence_id=occurrence.id,
        server_discord_id=server_discord_id,
        name=server_event.name,
        participant_count=len(ranked_participations),
        winner_owner_ids=winner_owner_ids,
        winner_pooch_ids=winner_pooch_ids,
        result_summary=summary,
    )


async def run_daily_server_event_cycle(
    rng: Optional[random.Random] = None,
) -> tuple[dict[int, TriggeredServerEvent], list[ServerEventResolution]]:
    rng = rng if rng is not None else random.Random()

    resolutions: list[ServerEventResolution] = []
    active_occurrences = await list_active_server_event_occurrences()
    for occurrence in active_occurrences:
        resolution = await resolve_server_event(occurrence.id, rng)
        if resolution is not None:
            resolutions.append(resolution)

    new_events: dict[int, TriggeredServerEvent] = {}
    servers = await list_servers()
    for server in servers:
        if server.event_channel_discord_id is None:
            continue
        event = await trigger_daily_server_event(server.discord_id, rng)
        if event is not None:
            new_events[server.discord_id] = event

    return new_events, resolutions


async def set_server_event_message_id(occurrence_id: int, message_discord_id: int | None) -> None:
    await set_server_event_occurrence_message_discord_id(occurrence_id, message_discord_id)
