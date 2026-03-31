import logging
import random
from typing import TYPE_CHECKING, Optional

from src.database import (
    add_pooch_to_kennel,
    add_pooch_to_strays,
    add_pooch_to_vendor_stock,
    bury_pooch,
    damn_pooch,
    get_random_matching_kennel_id,
    get_random_matching_pooch_id,
    list_kennels_for_owner,
    list_matching_kennel_ids,
    list_matching_pooch_ids,
    list_pooches_for_kennel,
    list_servers_for_owner,
    list_vendors,
    transfer_pooch_to_vendor,
)

if TYPE_CHECKING:
    from src.database.models import Event as EventDB
    from src.database.models import EventAction

    from ..models import OwnerEventContext

logger = logging.getLogger(__name__)


async def create_event_context(owner_discord_id: int, event: EventDB, rng: random.Random) -> OwnerEventContext:
    """
    Create context for an event based on its requirements.

    This pre-selects contextual targets for actions that use the `selected` selector.
    Random targets are resolved when the action executes so they can respect action filters.
    """

    from ..models import OwnerEventContext

    context = OwnerEventContext(owner_discord_id=owner_discord_id)

    candidate_kennel_ids = await list_matching_kennel_ids(owner_discord_id, {})
    candidate_pooch_ids = await list_matching_pooch_ids(owner_discord_id, {})
    context.extra_data["candidate_kennel_ids"] = candidate_kennel_ids
    context.extra_data["candidate_pooch_ids"] = candidate_pooch_ids

    def _uses_selected_selector(action: "EventAction") -> tuple[bool, bool]:
        selector = action.parameters.get("selector")
        if not isinstance(selector, str) or selector.strip().lower() != "selected":
            return False, False
        return action.target_type == "pooch", action.target_type == "kennel"

    needs_selected_pooch = False
    needs_selected_kennel = False

    for action in event.actions:
        p, k = _uses_selected_selector(action)
        needs_selected_pooch = needs_selected_pooch or p
        needs_selected_kennel = needs_selected_kennel or k

    for option in event.options:
        for action in option.actions:
            p, k = _uses_selected_selector(action)
            needs_selected_pooch = needs_selected_pooch or p
            needs_selected_kennel = needs_selected_kennel or k
        for outcome in option.outcomes:
            for action in outcome.actions:
                p, k = _uses_selected_selector(action)
                needs_selected_pooch = needs_selected_pooch or p
                needs_selected_kennel = needs_selected_kennel or k

    default_pooch_filter = None
    if event.filter.get("pooches"):
        first_filter = event.filter["pooches"][0]
        if isinstance(first_filter, dict):
            default_pooch_filter = {
                key: value
                for key, value in first_filter.items()
                if key not in {"min_count", "max_count", "description"}
            }

    default_kennel_filter = None
    if event.filter.get("kennels"):
        first_filter = event.filter["kennels"][0]
        if isinstance(first_filter, dict):
            default_kennel_filter = {
                key: value
                for key, value in first_filter.items()
                if key not in {"min_count", "max_count", "description"}
            }

    if needs_selected_pooch:
        context.selected_pooch_id = await get_random_matching_pooch_id(
            owner_discord_id,
            default_pooch_filter or {},
            rng,
        )

    if needs_selected_kennel:
        context.selected_kennel_id = await get_random_matching_kennel_id(
            owner_discord_id,
            default_kennel_filter or {},
            rng,
        )

    return context


async def deliver_pooch(owner_discord_id: int, pooch_id: int, destination: str) -> tuple[str, Optional[str]]:
    """
    Deliver a pooch to a destination. Returns (destination_key, kennel_name_or_None).

    Destinations: "kennel" | "graveyard" | "hell" | "town" | "vendor"
    For "kennel", places in the first kennel with free space. If no kennel has space, falls back to "town".
    For "town", releases the pooch as a stray on a random server the owner belongs to.
    For "vendor", transfers to a random vendor across all owner's servers.
    """

    destination = destination.strip().lower() if isinstance(destination, str) else "town"

    if destination == "kennel":
        kennels = await list_kennels_for_owner(owner_discord_id)
        for kennel in kennels:
            pooches_in_kennel = await list_pooches_for_kennel(kennel.id)
            if len(pooches_in_kennel) < kennel.pooch_limit:
                await add_pooch_to_kennel(kennel.id, pooch_id)
                return "kennel", kennel.name
        # No kennel with free space — fall through to town
        destination = "town"

    if destination == "town":
        servers = await list_servers_for_owner(owner_discord_id)
        if servers:
            server = random.choice(servers)
            await add_pooch_to_strays(pooch_id, server.discord_id)
        return "town", None

    elif destination == "vendor":
        servers = await list_servers_for_owner(owner_discord_id)
        all_vendors = []
        for server in servers:
            all_vendors.extend(await list_vendors(server.discord_id))
        if all_vendors:
            vendor = random.choice(all_vendors)
            await transfer_pooch_to_vendor(pooch_id, vendor.id)
            await add_pooch_to_vendor_stock(vendor.id, pooch_id)
        else:
            # No vendor available — fall through to town
            servers_list = await list_servers_for_owner(owner_discord_id)
            if servers_list:
                server = random.choice(servers_list)
                await add_pooch_to_strays(pooch_id, server.discord_id)
        return "vendor", None

    elif destination == "graveyard":
        await bury_pooch(owner_discord_id, pooch_id)
        return "graveyard", None

    elif destination == "hell":
        await damn_pooch(pooch_id)
        return "hell", None

    else:  # unknown
        return "town", None
