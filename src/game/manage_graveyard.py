from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

from src.database import (
    get_breed_by_id,
    list_graveyard_pooches_for_owner,
    list_graveyard_pooches_for_owners,
    list_hell_pooches,
    list_kennels_for_owner,
    list_owner_discord_ids_for_server,
    list_pooch_breed_weights,
    list_pooches_for_kennel,
    list_strays_for_server,
)

from .models import to_pooch

if TYPE_CHECKING:
    from .models import Pooch


async def list_graveyard_pooches(owner_discord_id: int) -> list[tuple[Pooch, datetime]]:
    """
    List every deceased pooch buried by the given owner, most recently buried first.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner to fetch the buried pooches for.

    Returns
    -------
    list[tuple[Pooch, datetime]]
        A list of (game Pooch, buried_at datetime) tuples.
    """

    rows = await list_graveyard_pooches_for_owner(owner_discord_id)
    return [(await to_pooch(pooch), buried_at) for pooch, buried_at in rows]


async def _summarize_breed_population(pooches: list, *, get_breed_name) -> list[dict]:
    if not pooches:
        return []
    weighted: dict[str, float] = defaultdict(float)
    dominant: dict[str, int] = defaultdict(int)
    n = len(pooches)
    for pooch in pooches:
        weights = await list_pooch_breed_weights(pooch.id)
        if not weights:
            continue
        total = sum(w for _, w in weights) or 1
        for breed_id, w in weights:
            name = await get_breed_name(breed_id)
            if name is None:
                continue
            weighted[name] += float(w) / float(total)
        dominant_id = max(weights, key=lambda pair: pair[1])[0]
        dominant_name = await get_breed_name(dominant_id)
        if dominant_name is not None:
            dominant[dominant_name] += 1

    rows = []
    for name, total in weighted.items():
        rows.append(
            {
                "breed": name,
                "weighted_total": round(total / n, 4),
                "dominant_count": dominant.get(name, 0),
            }
        )
    rows.sort(key=lambda r: (-r["weighted_total"], r["breed"]))
    return rows


async def breed_population_survey(server_id: int) -> dict[str, list[dict]]:
    """
    Build a breed-population survey for the given server.

    Returns a dict with four populations:

    - ``owned``: living pooches in kennels owned by server members
    - ``strays``: living strays on the server
    - ``graveyard``: dead pooches buried by server members
    - ``hell``: pooches damned to Hell that were owned by server members

    Each population is a list of ``{breed, weighted_total, dominant_count}``
    rows sorted descending by weighted_total.
    """
    breed_name_cache: dict[int, str | None] = {}

    async def _get_breed_name(breed_id: int) -> str | None:
        if breed_id not in breed_name_cache:
            breed = await get_breed_by_id(breed_id)
            breed_name_cache[breed_id] = breed.name if breed is not None else None
        return breed_name_cache[breed_id]

    owner_ids = await list_owner_discord_ids_for_server(server_id)

    owned_pooches: list = []
    for owner_id in owner_ids:
        for kennel in await list_kennels_for_owner(owner_id):
            for p in await list_pooches_for_kennel(kennel.id):
                if p.alive:
                    owned_pooches.append(p)

    strays = [p for p in (await list_strays_for_server(server_id)) if p.alive]
    graveyard = await list_graveyard_pooches_for_owners(owner_ids)
    hell = [p for p in (await list_hell_pooches()) if p.owner_discord_id in set(owner_ids)]

    return {
        "owned": await _summarize_breed_population(owned_pooches, get_breed_name=_get_breed_name),
        "strays": await _summarize_breed_population(strays, get_breed_name=_get_breed_name),
        "graveyard": await _summarize_breed_population(graveyard, get_breed_name=_get_breed_name),
        "hell": await _summarize_breed_population(hell, get_breed_name=_get_breed_name),
    }
