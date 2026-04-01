from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.database import (
    add_pooch_to_kennel,
    get_owner_by_discord_id,
)
from src.database import get_pooch_by_id as db_get_pooch_by_id
from src.database import (
    get_pooch_health,
)
from src.database import get_vendor_by_id as db_get_vendor_by_id
from src.database import (
    give_money_to_owner,
    list_kennels_for_owner,
    list_pooch_breeds,
    list_pooch_mutations,
    list_pooches_for_kennel,
    list_vendor_desired_breeds,
    list_vendor_desired_mutations,
    list_vendor_pooch_stock,
)
from src.database import list_vendors as db_list_vendors
from src.database import (
    remove_pooch_from_kennel,
    remove_pooch_from_vendor_stock,
    transfer_pooch_to_owner,
    transfer_pooch_to_vendor,
)

from .constants import (
    BASE_POOCH_DOLLAR_VALUE,
    BREED_RARITY_TO_POOCH_VALUE_MULT,
    POOCH_DOLLAR_VALUE_LOSS_BY_AGE,
    POOCH_DOLLAR_VALUE_LOSS_BY_HEALTH_BELOW_AVERAGE,
    POOCH_STAT_RANGE,
    VENDOR_DESIRED_MUTATION_MULT,
    VENDOR_PURE_BREED_MAX_MULT,
    VENDOR_PURE_BREED_THRESHOLD,
)
from .exceptions import PoochNotFound, VendorNotFound
from .manage_auctions import cancel_listing_for_pooch
from .models import to_pooch, to_vendor

if TYPE_CHECKING:
    from .models import Pooch, Vendor


async def buy_pooch(owner_discord_id: int, vendor_id: int, pooch_id: int) -> tuple[bool, str]:
    """
    Have the given owner purchase the given pooch from the given vendor.
    Fails with a specific error message if:
    - The owner doesn't exist.
    - The owner can't afford the pooch.
    - The pooch doesn't exist.
    - The owner doesn't have space in any of their kennels.
    - The pooch isn't in the vendor's stock.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner making the purchase.

    vendor_id: int
        The ID of the vendor that owns the pooch being bought.

    pooch_id: int
        The ID of the pooch being bought.

    Returns
    -------
    tuple[bool, str]
        A tuple in the form `(success?, message)`.
    """

    price = await get_pooch_buy_price(pooch_id, vendor_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return (False, "You need to visit /home first to set up your account.")
    if owner.dollars < price:
        return (False, f"You need ${price} but only have ${owner.dollars}.")

    pooch = await db_get_pooch_by_id(pooch_id)
    if pooch is None:
        return (False, "That pooch doesn't exist.")

    kennels = await list_kennels_for_owner(owner_discord_id)
    target_kennel = None
    for kennel in kennels:
        kennel_pooches = await list_pooches_for_kennel(kennel.id)
        if len(kennel_pooches) < kennel.pooch_limit:
            target_kennel = kennel
            break

    if target_kennel is None:
        return (False, "You don't have any kennel space available.")

    removed = await remove_pooch_from_vendor_stock(vendor_id, pooch_id)
    if removed is None:
        return (False, "That pooch is no longer available from this vendor.")

    await give_money_to_owner(owner_discord_id, -price)
    await cancel_listing_for_pooch(pooch_id)
    await transfer_pooch_to_owner(pooch_id, owner_discord_id)
    await add_pooch_to_kennel(target_kennel.id, pooch_id)

    return (True, f"You purchased {pooch.name} for ${price}!")


async def get_pooch_base_price(pooch_id: int) -> int:
    """
    Get pooch base price.

    Parameters
    ----------
    pooch_id: Any
        The `pooch_id` value.

    Returns
    -------
    Any
        The result of calling `get_pooch_base_price`.
    """

    pooch = await db_get_pooch_by_id(pooch_id)
    if pooch is None:
        raise PoochNotFound(pooch_id)

    # Age reduces a pooch's value
    price = BASE_POOCH_DOLLAR_VALUE - (pooch.age * POOCH_DOLLAR_VALUE_LOSS_BY_AGE)

    # Health loss reduces a pooch's value (or increases if its health is higher than average)
    pooch_health: int = await get_pooch_health(pooch.id)
    average_base_health = (POOCH_STAT_RANGE[1] - POOCH_STAT_RANGE[0]) / 2
    price = price - (POOCH_DOLLAR_VALUE_LOSS_BY_HEALTH_BELOW_AVERAGE * (average_base_health - pooch_health))

    # Mutations have advanced options that affect a pooch's value
    pooch_mutations = await list_pooch_mutations(pooch.id)
    mutation_price_add = 0
    mutation_price_mult = 1
    for mutation in pooch_mutations:
        mutation_price_add += mutation.parameters.get("dollar_value_add", 0.0)
        mutation_price_mult *= mutation.parameters.get("dollar_value_mult", 1.0)
    price = max(price + mutation_price_add, 0)
    price *= mutation_price_mult

    # Breeds multiply the pooch's value based on their rarity
    pooch_breeds = await list_pooch_breeds(pooch.id)
    breed_price_mult = 0
    for breed, weight in pooch_breeds:
        breed_price_mult += weight * BREED_RARITY_TO_POOCH_VALUE_MULT[breed.rarity]
    price *= breed_price_mult

    # Pure-breed bonus: linearly scale from 1x at VENDOR_PURE_BREED_THRESHOLD to
    # VENDOR_PURE_BREED_MAX_MULT at 100% dominant breed
    if pooch_breeds:
        dominant_weight = max(w for _, w in pooch_breeds)
        if dominant_weight > VENDOR_PURE_BREED_THRESHOLD:
            t = (dominant_weight - VENDOR_PURE_BREED_THRESHOLD) / (1.0 - VENDOR_PURE_BREED_THRESHOLD)
            pure_breed_mult = 1.0 + t * (VENDOR_PURE_BREED_MAX_MULT - 1.0)
            price *= pure_breed_mult

    return max(round(price), 0)


async def get_pooch_buy_price(pooch_id: int, vendor_id: Optional[int] = None) -> int:
    """
    Get the total price to buy the given pooch from the given vendor.
    If no vendor is provided, the returned price is the pooch's base price.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the price of.

    vendor_id: int, optional
        The ID of the vendor to check for the value they put on the pooch they're selling.

    Returns
    -------
    int
        The value of the pooch in dollars, optionally augmented by the given vendor.
    """

    price = await get_pooch_base_price(pooch_id)

    if vendor_id is not None:
        vendor = await db_get_vendor_by_id(vendor_id)
        if vendor is None:
            raise VendorNotFound(vendor_id)
        price *= vendor.price_markup

    return round(price)


async def get_pooch_sell_price(pooch_id: int, vendor_id: Optional[int] = None) -> int:
    """
    Get the total price a given vendor will pay to purchase the given pooch.
    If no vendor is provided, the returned price is the pooch's base price.

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the price of.

    vendor_id: int, optional
        The ID of the vendor to check for the value they put on the pooch they're selling.

    Returns
    -------
    int
        The value of the pooch in dollars, optionally augmented by the given vendor.
    """

    price = await get_pooch_base_price(pooch_id)

    if vendor_id is not None:

        vendor = await db_get_vendor_by_id(vendor_id)
        if vendor is None:
            raise VendorNotFound(vendor_id)

        pooch_mutation_ids = {mutation.id for mutation in (await list_pooch_mutations(pooch_id))}
        desired_mutations = await list_vendor_desired_mutations(vendor_id)
        for mutation in desired_mutations:
            if mutation.id in pooch_mutation_ids:
                price *= VENDOR_DESIRED_MUTATION_MULT

        pooch_breed_weights = {breed.id: weight for breed, weight in (await list_pooch_breeds(pooch_id))}
        desired_breeds = await list_vendor_desired_breeds(vendor_id)
        for breed in desired_breeds:
            if breed.id in pooch_breed_weights:
                price *= 1.0 + pooch_breed_weights[breed.id]

    return round(price)


async def get_vendor_by_id(vendor_id: int) -> Vendor:
    """
    Return a vendor with the given ID.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to return.

    Returns
    -------
    Vendor
        The vendor with the given ID.

    Raises
    ------
    VendorNotFound
        When a Vendor with `vendor_id` is not found.
    """

    vendor = await db_get_vendor_by_id(vendor_id)
    if vendor is None:
        raise VendorNotFound(vendor_id)
    return await to_vendor(vendor)


async def list_server_vendors(server_discord_id: int) -> list[Vendor]:
    """
    Get a list of every vendor on the given server.

    Parameters
    ----------
    server_discord_id: int
        The Discord ID of the server to get the vendors from.

    Returns
    -------
    list[Vendor]
        The list of vendors from the given server.
    """

    vendors = await db_list_vendors(server_discord_id)
    return [(await to_vendor(vendor)) for vendor in vendors]


async def list_vendor_pooches(vendor_id: int) -> list[Pooch]:
    """
    Get a list of the pooches being sold by the given vendor.

    Parameters
    ----------
    vendor_id: int
        The ID of the vendor to get the pooches from.

    Returns
    -------
    list[Pooch]
        The list of pooches being sold by the given vendor.
    """

    pooches = await list_vendor_pooch_stock(vendor_id)
    return [(await to_pooch(pooch)) for pooch in pooches]


async def sell_pooch(owner_discord_id: int, vendor_id: int, pooch_id: int) -> tuple[bool, str]:
    """
    Have the given owner sell the given pooch to the given vendor.
    Fails with a specific error message if:
    - The owner doesn't exist.
    - The pooch doesn't exist.
    - The owner doesn't own the pooch.
    - The pooch is dead.

    Parameters
    ----------
    owner_discord_id: int
        The Discord ID of the owner selling the pooch.

    vendor_id: int
        The ID of the vendor to sell the pooch to.

    pooch_id: int
        The ID of the pooch being sold.

    Returns
    -------
    tuple[bool, str]
        A tuple in the form `(success?, message)`.
    """

    price = await get_pooch_sell_price(pooch_id, vendor_id)

    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return (False, "You need to visit /home first to set up your account.")

    pooch = await db_get_pooch_by_id(pooch_id)
    if pooch is None:
        return (False, "That pooch doesn't exist.")
    if pooch.owner_discord_id != owner.discord_id:
        return (False, "You don't own that pooch.")
    if not pooch.alive:
        return (False, "That pooch is dead.")

    await give_money_to_owner(owner_discord_id, price)
    await cancel_listing_for_pooch(pooch.id)
    await transfer_pooch_to_vendor(pooch.id, vendor_id)
    await remove_pooch_from_kennel(pooch.id)

    return (True, f"You sold {pooch.name} for ${price}!")
