"""
Public API for server events — participation, query, and message ID management.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional

from src.database import (
    append_server_event_submission,
    check_owner_event_filter_for_owner,
    create_server_event_participation,
    get_active_server_event_occurrence,
    get_owner_server,
    get_server_event_menu_option_by_id,
    get_server_event_occurrence_by_id,
    get_server_event_participation,
    list_active_server_event_occurrences,
    list_matching_pooch_ids,
    set_server_event_occurrence_message_discord_id,
)
from src.game.events.owner_events import (
    execute_event_actions as _execute_owner_event_actions,
)
from src.game.manage_owners import get_or_create_owner
from src.game.models.events import (
    ServerEventParticipationSummary,
    TriggeredServerEvent,
    to_server_event_participation_summary,
    to_triggered_server_event,
)
from src.logger import get_logger

from .arena import handle_arena_action
from .coordinator import build_owner_event_context

logger = get_logger("game/events/server_events/public")


async def get_active_server_event(
    server_discord_id: int, viewer_owner_discord_id: int | None = None
) -> TriggeredServerEvent | None:
    """
    Get active server event.

    Parameters
    ----------
    server_discord_id: Any
        The `server_discord_id` value.

    viewer_owner_discord_id: Any
        The `viewer_owner_discord_id` value.

    Returns
    -------
    Any
        The result of calling `get_active_server_event`.
    """

    occurrence = await get_active_server_event_occurrence(server_discord_id)
    if occurrence is None:
        return None
    return await to_triggered_server_event(occurrence, viewer_owner_discord_id)


async def list_active_server_events() -> list[TriggeredServerEvent]:
    """
    List active server events.

    Returns
    -------
    Any
        The result of calling `list_active_server_events`.
    """

    occurrences = await list_active_server_event_occurrences()
    return [await to_triggered_server_event(occurrence) for occurrence in occurrences]


async def participate_in_server_event(
    occurrence_id: int,
    server_discord_id: int,
    owner_discord_id: int,
    menu_option_id: int,
    selected_pooch_id: int | None = None,
    extra_params: dict | None = None,
    rng: Optional[random.Random] = None,
) -> tuple[bool, str, ServerEventParticipationSummary | None]:
    """
    Participate in server event.

    Parameters
    ----------
    occurrence_id: Any
        The `occurrence_id` value.

    server_discord_id: Any
        The `server_discord_id` value.

    owner_discord_id: Any
        The `owner_discord_id` value.

    menu_option_id: Any
        The `menu_option_id` value.

    selected_pooch_id: Any
        The `selected_pooch_id` value.

    extra_params: Any
        The `extra_params` value.

    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `participate_in_server_event`.
    """

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

    existing_participation = await get_server_event_participation(occurrence_id, owner_discord_id)
    used_menu_names: set[str] = set()
    if existing_participation is not None:
        for sub in list(existing_participation.submissions or []):
            used_menu_names.add(str(sub.get("menu_name", "")))

    for required_menu_name in list(menu.depends_on or []):
        if required_menu_name not in used_menu_names:
            return False, f"You must use the '{required_menu_name}' menu first.", None

    max_uses = menu.max_uses_per_player
    if max_uses >= 0:
        uses_this_menu = (
            sum(1 for sub in list(existing_participation.submissions or []) if sub.get("menu_name") == menu.name)
            if existing_participation
            else 0
        )
        if uses_this_menu >= max_uses:
            return False, f"You have used the '{menu.label}' menu the maximum number of times.", None

    if option.filter:
        if not await check_owner_event_filter_for_owner(owner_discord_id, option.filter):
            return False, "You do not meet the requirements for that option.", None

    if option.requires:
        pooch_req = option.requires.get("pooch")
        if pooch_req is not None:
            if selected_pooch_id is None:
                return False, "You must select a pooch for that option.", None
            from src.database import get_pooch_by_id as db_get_pooch_by_id

            pooch = await db_get_pooch_by_id(selected_pooch_id)
            if pooch is None or pooch.owner_discord_id != owner_discord_id:
                return False, "That pooch does not belong to you.", None
            pooch_filter = pooch_req.get("filter", {}) if isinstance(pooch_req, dict) else {}
            if pooch_filter:
                matching_ids = await list_matching_pooch_ids(owner_discord_id, pooch_filter)
                if selected_pooch_id not in matching_ids:
                    return False, "That pooch does not meet the requirements.", None

    context = await build_owner_event_context(owner_discord_id, selected_pooch_id)
    immediate_result = await _execute_owner_event_actions(owner_discord_id, option.actions, context, rng)

    arena_result: dict = {}
    arena_action = str((option.parameters or {}).get("arena_action", "")).strip().lower()
    if arena_action:
        success, arena_msg, arena_result = await handle_arena_action(
            occurrence=occurrence,
            owner_discord_id=owner_discord_id,
            selected_pooch_id=selected_pooch_id,
            arena_action=arena_action,
            option_parameters=option.parameters or {},
            extra_params=extra_params or {},
            rng=rng,
        )
        if not success:
            return False, arena_msg, None
        immediate_result.message = arena_msg or immediate_result.message

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
    if arena_result:
        submission["arena_result"] = arena_result

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


async def set_server_event_message_id(occurrence_id: int, message_discord_id: int | None) -> None:
    """
    Set server event message id.

    Parameters
    ----------
    occurrence_id: Any
        The `occurrence_id` value.

    message_discord_id: Any
        The `message_discord_id` value.
    """

    await set_server_event_occurrence_message_discord_id(occurrence_id, message_discord_id)
