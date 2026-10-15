from __future__ import annotations

import random
from typing import TYPE_CHECKING

from src.database import add_injury_to_pooch, get_injury_by_name, list_servers_for_pooch
from src.logger import get_logger

from ..models import OtherEvent, to_pooch, to_server
from .pronouns import substitute_placeholders

if TYPE_CHECKING:
    from src.database.models import Pooch

logger = get_logger("game/on_death_effects")


async def apply_on_death_injure(
    *,
    trigger: dict,
    source_pooch: "Pooch",
    target_pooches: list["Pooch"],
    other_events_by_server: dict[int, list[OtherEvent]],
    rng: random.Random,
) -> None:
    """
    Apply the ``injure`` on-death effect.

    ``trigger`` is the raw mutation ``on_death_triggers`` entry. Its
    ``on_death_options`` list holds injury names to pick from. Unknown
    injury names are ignored (resource loader also validates them).
    """
    options: list[str] = list(trigger.get("on_death_options") or [])
    if not options:
        logger.warning("on_death: injure without on_death_options — nothing to apply")
        return
    for target in target_pooches:
        injury_name = options[0] if len(options) == 1 else rng.choice(options)
        injury = await get_injury_by_name(injury_name)
        if injury is None:
            logger.warning("on_death injure: unknown injury '%s'", injury_name)
            continue
        await add_injury_to_pooch(target.id, injury.id)
        impact_msg = substitute_placeholders(
            trigger.get(
                "impact_message",
                f"{target.name} was hurt by the fallout from {source_pooch.name}'s death.",
            ),
            {"pooch": source_pooch, "victim": target},
        )
        for server in await list_servers_for_pooch(target.id):
            other_events_by_server.setdefault(server.discord_id, []).append(
                OtherEvent(
                    server=(await to_server(server)),
                    pooch=(await to_pooch(target)),
                    message=impact_msg,
                )
            )
