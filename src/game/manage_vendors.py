from database import (
    list_vendors as db_list_vendors,
    list_vendor_pooch_stock,
    get_owner_by_discord_id,
    get_pooch_by_id as db_get_pooch_by_id,
    remove_pooch_from_vendor_stock,
    transfer_pooch_to_owner,
    give_money_to_owner,
    add_pooch_to_kennel,
    list_kennels_for_owner,
    list_pooches_for_kennel,
)

from .model import Vendor, to_vendor, Pooch, to_pooch


def get_price(pooch_id: int) -> int:
    # TODO: real pricing logic
    return 50


async def list_server_vendors(server_id: int) -> list[Vendor]:
    vendors = await db_list_vendors(server_id)
    return [to_vendor(v) for v in vendors]


async def list_vendor_pooches(server_id: int, vendor_id: int) -> list[Pooch]:
    pooches = await list_vendor_pooch_stock(vendor_id)
    return [to_pooch(p) for p in pooches]


async def buy_pooch(
    *,
    server_id: int,
    owner_discord_id: int,
    vendor_id: int,
    pooch_id: int,
) -> tuple[bool, str]:
    price = get_price(pooch_id)

    # Verify the owner exists and has enough money
    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return (False, "You need to visit /home first to set up your account.")
    if owner.dollars < price:
        return (False, f"You need ${price} but only have ${owner.dollars}.")

    # Verify the pooch is still in stock
    pooch = await db_get_pooch_by_id(pooch_id)
    if pooch is None:
        return (False, "That pooch doesn't exist.")

    # Find a kennel with space
    kennels = await list_kennels_for_owner(owner_discord_id)
    target_kennel = None
    for kennel in kennels:
        kennel_pooches = await list_pooches_for_kennel(int(kennel.id))
        if len(kennel_pooches) < kennel.pooch_limit:
            target_kennel = kennel
            break

    if target_kennel is None:
        return (False, "You don't have any kennel space available.")

    # Remove from vendor stock
    removed = await remove_pooch_from_vendor_stock(vendor_id, pooch_id)
    if removed is None:
        return (False, "That pooch is no longer available from this vendor.")

    # Deduct money
    await give_money_to_owner(owner_discord_id, -price)

    # Transfer ownership from vendor to player
    await transfer_pooch_to_owner(pooch_id, owner_discord_id)

    # Add to the owner's kennel
    await add_pooch_to_kennel(int(target_kennel.id), pooch_id)

    return (True, f"You purchased {pooch.name} for ${price}!")
