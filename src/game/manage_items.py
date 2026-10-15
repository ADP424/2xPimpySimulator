from __future__ import annotations

import random
from typing import Any, Optional

from src.database import (
    consume_owner_item,
    get_item_by_name,
    get_kennel_by_id,
    get_owner_by_discord_id,
    get_owner_items,
    give_money_to_owner,
    give_owner_item,
    list_all_items,
    list_items_by_category,
    list_pooches_for_kennel,
    modify_kennel_food_stock,
)

from .constants import FOOD_STAT_BONUS_CHANCE
from .events.shared import modify_pooch_stat

DEFAULT_ITEM_PRICE = 10
VENDOR_ITEM_CATEGORIES = ("cleaning", "food")


def get_item_price(item: Any) -> int:
    """Return the dollar price of one of an item."""
    return int((item.parameters or {}).get("price", DEFAULT_ITEM_PRICE))


def get_item_food_units(item: Any) -> int:
    """Return how many food units one of an item adds to a kennel's food stock."""
    return int((item.parameters or {}).get("food_units", 0))


def get_food_stat_bonuses(item: Any) -> dict[str, int]:
    """Return a food's permanent stat bonuses (its ``<stat>_add`` parameters) by stat name."""
    return {key[: -len("_add")]: int(value) for key, value in (item.parameters or {}).items() if key.endswith("_add")}


async def list_items(category: Optional[str] = None) -> list:
    """
    List the static item catalog.

    Parameters
    ----------
    category: str, optional
        Only list items in this category (e.g. "cleaning", "food").

    Returns
    -------
    list
        The catalog items.
    """

    if category is None:
        return await list_all_items()
    return await list_items_by_category(category)


async def list_vendor_items() -> list:
    """List every item vendors sell (cleaning products, then food)."""
    items: list = []
    for category in VENDOR_ITEM_CATEGORIES:
        items.extend(await list_items_by_category(category))
    return items


async def get_owner_inventory(owner_discord_id: int) -> dict[str, int]:
    """Return the owner's item counts by item name (only items they have at least one of)."""
    return await get_owner_items(owner_discord_id)


async def buy_item(owner_discord_id: int, item_name: str, count: int = 1) -> tuple[bool, str]:
    """
    Buy ``count`` of an item from a vendor at its fixed price.

    Returns
    -------
    tuple[bool, str]
        (success, message)
    """

    if count < 1:
        return False, "You must buy at least one."
    item = await get_item_by_name(item_name)
    if item is None or item.category not in VENDOR_ITEM_CATEGORIES:
        return False, f"Unknown item: {item_name}."
    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found."

    total_cost = get_item_price(item) * count
    if owner.dollars < total_cost:
        return False, f"Not enough money. Cost: **${total_cost}**."

    await give_money_to_owner(owner_discord_id, -total_cost)
    await give_owner_item(owner_discord_id, item.name, count)
    return True, f"Purchased **{count}x {item.name}** for **${total_cost}**."


async def feed_kennel(
    owner_discord_id: int,
    kennel_id: int,
    item_name: str,
    count: int = 1,
    rng: Optional[random.Random] = None,
) -> tuple[bool, str, Optional[int]]:
    """
    Use up ``count`` of a food item from the owner's inventory to add to one of their kennels' food stock.

    Foods with stat bonuses (``<stat>_add``) give each living pooch in the kennel a FOOD_STAT_BONUS_CHANCE chance
    per item fed to gain that bonus permanently (at most once per pooch per feeding).

    Returns
    -------
    tuple[bool, str, int | None]
        (success, message, new_food_stock). The stock is None on failure.
    """

    if count < 1:
        return False, "You must use at least one.", None
    kennel = await get_kennel_by_id(kennel_id)
    if kennel is None:
        return False, "Kennel not found.", None
    if kennel.owner_discord_id != owner_discord_id:
        return False, "That's not your kennel.", None

    item = await get_item_by_name(item_name)
    if item is None or item.category != "food":
        return False, "That item is not food.", None
    units = get_item_food_units(item)
    if units <= 0:
        return False, f"{item.name} has no food value.", None

    if not await consume_owner_item(owner_discord_id, item.name, count):
        return False, f"You don't own {count}x {item.name}.", None

    added = units * count
    new_stock = await modify_kennel_food_stock(kennel_id, added)
    message = f"Deposited **{count}x {item.name}** (+{added} food units). Stock now: **{new_stock}** units."

    bonuses = get_food_stat_bonuses(item)
    if bonuses:
        rng = rng or random.Random()
        lucky = []
        for pooch in await list_pooches_for_kennel(kennel_id):
            if pooch.alive and any(rng.random() < FOOD_STAT_BONUS_CHANCE for _ in range(count)):
                for stat, amount in bonuses.items():
                    await modify_pooch_stat(pooch.id, stat, amount)
                lucky.append(pooch.name)
        if lucky:
            message += f" {', '.join(lucky)} thrived on the {item.name}!"
    return True, message, new_stock
