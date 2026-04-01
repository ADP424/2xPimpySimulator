from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from src.database import (
    add_pooch_to_kennel,
    cancel_auction_bounty_listing,
    close_auction_sale_listing,
    create_auction_bid,
    create_auction_bounty_listing,
    create_auction_sale_listing,
    fulfill_auction_bounty_listing,
    get_active_auction_sale_listing_for_pooch,
    get_auction_bounty_listing_by_id,
    get_auction_sale_listing_by_id,
    get_highest_bid_for_listing,
    get_owner_by_discord_id,
    get_pooch_by_id,
    give_money_to_owner,
    list_active_bounty_listings_for_owner,
    list_active_bounty_listings_for_server,
    list_active_sale_listings_for_owner,
    list_active_sale_listings_for_server,
    list_bids_for_listing,
    list_expired_sale_listings,
    list_kennels_for_owner,
    list_pooches_for_kennel,
    remove_pooch_from_kennel,
    transfer_pooch_to_owner,
)
from src.game.models import (
    AuctionBountyListing,
    AuctionSaleListing,
    BountyMatchResult,
    to_auction_bounty_listing,
    to_auction_sale_listing,
    to_pooch,
)

_RARITY_ORDER = [
    "common",
    "uncommon",
    "novel",
    "rare",
    "unprecedented",
    "remarkable",
    "extraordinary",
    "unique",
]

_VALID_STATS = {
    "strength",
    "cuteness",
    "fluffiness",
    "intelligence",
    "dexterity",
    "fertility",
    "aggressiveness",
    "constitution",
    "size",
}

_VALID_CRITERION_TYPES = {"breed", "mutation", "sex", "min_stat", "min_rarity"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _find_kennel_space(owner_discord_id: int) -> Optional[int]:
    """Return the ID of the first kennel with free space, or None."""
    kennels = await list_kennels_for_owner(owner_discord_id)
    for kennel in kennels:
        pooches = await list_pooches_for_kennel(kennel.id)
        if len(pooches) < kennel.pooch_limit:
            return kennel.id
    return None


def _validate_criterion(criterion: dict) -> Optional[str]:
    """Return an error string if the criterion is invalid, else None."""
    ctype = criterion.get("type")
    if ctype not in _VALID_CRITERION_TYPES:
        return f"Unknown criterion type: {ctype!r}"
    if not isinstance(criterion.get("dollar_value"), int) or criterion["dollar_value"] <= 0:
        return f"Criterion {ctype!r} must have a positive integer dollar_value"
    if ctype == "breed":
        if not isinstance(criterion.get("breed_id"), int):
            return "breed criterion requires integer breed_id"
        min_w = criterion.get("min_weight", 0)
        if not isinstance(min_w, (int, float)) or not (0 < min_w <= 1):
            return "breed criterion min_weight must be a float in (0, 1]"
    elif ctype == "mutation":
        if not isinstance(criterion.get("mutation_id"), int):
            return "mutation criterion requires integer mutation_id"
    elif ctype == "sex":
        value = criterion.get("value")
        if value not in ("male", "female", "either"):
            return "sex criterion value must be 'male', 'female', or 'either'"
        if value == "either" and criterion.get("preferred_sex") not in ("male", "female"):
            return "sex criterion with value='either' requires preferred_sex of 'male' or 'female'"
    elif ctype == "min_stat":
        if criterion.get("stat") not in _VALID_STATS:
            return f"min_stat criterion stat must be one of {sorted(_VALID_STATS)}"
        if not isinstance(criterion.get("threshold"), int) or criterion["threshold"] < 0:
            return "min_stat criterion requires non-negative integer threshold"
    elif ctype == "min_rarity":
        if criterion.get("value") not in _RARITY_ORDER:
            return f"min_rarity criterion value must be one of {_RARITY_ORDER}"
    return None


async def _resolve_auction_listing(listing_id: int) -> tuple[bool, str]:
    """
    Finalise an auction. Transfers the pooch to the winner and pays the seller,
    or closes with no sale if there are no bids or the winner has no kennel space.
    """
    listing = await get_auction_sale_listing_by_id(listing_id)
    if listing is None:
        return False, "Listing not found."
    if not listing.is_active:
        return False, "Listing is already closed."

    highest_bid_row = await get_highest_bid_for_listing(listing_id)

    if highest_bid_row is None:
        await close_auction_sale_listing(listing_id, None, None)
        return True, "Auction closed with no bids."

    winner_id = highest_bid_row.bidder_discord_id
    amount = highest_bid_row.amount

    kennel_id = await _find_kennel_space(winner_id)
    if kennel_id is None:
        # Refund the winner; close with no sale
        await give_money_to_owner(winner_id, amount)
        await close_auction_sale_listing(listing_id, None, None)
        return True, "Auction closed; winner had no kennel space, bid refunded."

    await transfer_pooch_to_owner(listing.pooch_id, winner_id)
    await add_pooch_to_kennel(kennel_id, listing.pooch_id)
    await give_money_to_owner(listing.seller_discord_id, amount)
    await close_auction_sale_listing(listing_id, winner_id, amount)
    return True, f"Auction resolved. Pooch sold for ${amount}."


# ---------------------------------------------------------------------------
# Shared helper — cancel listing when ownership changes externally
# ---------------------------------------------------------------------------


async def cancel_listing_for_pooch(pooch_id: int) -> None:
    """
    If there is an active sale listing for this pooch, close it with no winner
    and refund all bidders. Call this before any transfer_pooch_to_owner that
    isn't the auction's own resolution.
    """
    listing = await get_active_auction_sale_listing_for_pooch(pooch_id)
    if listing is None:
        return
    bids = await list_bids_for_listing(listing.id)
    refunded: set[int] = set()
    for bid in bids:  # ordered amount DESC; first occurrence per bidder = their highest
        if bid.bidder_discord_id not in refunded:
            await give_money_to_owner(bid.bidder_discord_id, bid.amount)
            refunded.add(bid.bidder_discord_id)
    await close_auction_sale_listing(listing.id, None, None)


# ---------------------------------------------------------------------------
# Sale listings — public API
# ---------------------------------------------------------------------------


async def create_sale_listing(
    owner_discord_id: int,
    pooch_id: int,
    server_discord_id: int,
    minimum_bid: int,
    duration_hours: Optional[int] = None,
) -> tuple[bool, str]:
    """List a pooch for auction. Pooch stays in the owner's kennel."""
    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found."

    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        return False, "Pooch not found."
    if pooch.owner_discord_id != owner_discord_id:
        return False, "You don't own that pooch."
    if not pooch.alive:
        return False, "You can't auction a dead pooch."

    if minimum_bid < 0:
        return False, "Minimum bid cannot be negative."

    existing = await get_active_auction_sale_listing_for_pooch(pooch_id)
    if existing is not None:
        return False, f"{pooch.name} is already listed on the auction house."

    expires_at = None
    if duration_hours is not None:
        if duration_hours <= 0:
            return False, "Duration must be at least 1 hour."
        expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

    await create_auction_sale_listing(
        pooch_id=pooch_id,
        seller_discord_id=owner_discord_id,
        server_discord_id=server_discord_id,
        minimum_bid=minimum_bid,
        expires_at=expires_at,
    )
    duration_str = f" (expires in {duration_hours}h)" if duration_hours else " (no expiry)"
    return True, f"{pooch.name} has been listed with a minimum bid of ${minimum_bid}{duration_str}."


async def place_bid(
    bidder_discord_id: int,
    listing_id: int,
    amount: int,
) -> tuple[bool, str]:
    """Place or raise a bid on an active listing."""
    listing = await get_auction_sale_listing_by_id(listing_id)
    if listing is None:
        return False, "Listing not found."
    if not listing.is_active:
        return False, "This listing is no longer active."
    if listing.expires_at is not None and listing.expires_at <= datetime.now(timezone.utc):
        return False, "This auction has expired."
    if listing.seller_discord_id == bidder_discord_id:
        return False, "You can't bid on your own listing."

    if amount <= 0:
        return False, "Bid amount must be positive."

    bidder = await get_owner_by_discord_id(bidder_discord_id)
    if bidder is None:
        return False, "Bidder not found."

    # Determine the minimum acceptable bid
    highest_bid_row = await get_highest_bid_for_listing(listing_id)
    current_high = highest_bid_row.amount if highest_bid_row is not None else None
    if current_high is None:
        if amount < listing.minimum_bid:
            return False, f"Opening bid must be at least ${listing.minimum_bid}."
    else:
        if amount <= current_high:
            return False, f"Bid must exceed the current highest bid of ${current_high}."

    if bidder.dollars < amount:
        return False, f"You don't have enough money. You have ${bidder.dollars}, bid is ${amount}."

    # Refund previous highest bidder if it's a different person
    if highest_bid_row is not None and highest_bid_row.bidder_discord_id != bidder_discord_id:
        await give_money_to_owner(highest_bid_row.bidder_discord_id, highest_bid_row.amount)

    await give_money_to_owner(bidder_discord_id, -amount)
    await create_auction_bid(listing_id=listing_id, bidder_discord_id=bidder_discord_id, amount=amount)
    return True, f"Bid of ${amount} placed successfully."


async def close_sale_listing(owner_discord_id: int, listing_id: int) -> tuple[bool, str]:
    """Owner manually closes their auction early."""
    listing = await get_auction_sale_listing_by_id(listing_id)
    if listing is None:
        return False, "Listing not found."
    if not listing.is_active:
        return False, "This listing is already closed."
    if listing.seller_discord_id != owner_discord_id:
        return False, "You don't own this listing."
    return await _resolve_auction_listing(listing_id)


async def process_expired_sale_listings() -> list[tuple[int, bool, str]]:
    """Called from change_day.py. Resolves all listings past their expiry time."""
    expired = await list_expired_sale_listings()
    results = []
    for listing in expired:
        success, message = await _resolve_auction_listing(listing.id)
        results.append((listing.id, success, message))
    return results


async def get_sale_listing(listing_id: int) -> Optional[AuctionSaleListing]:
    """Return a game-layer AuctionSaleListing, or None."""
    orm = await get_auction_sale_listing_by_id(listing_id)
    if orm is None:
        return None
    highest_bid_row = await get_highest_bid_for_listing(listing_id)
    bids = await list_bids_for_listing(listing_id)
    return await to_auction_sale_listing(
        orm,
        highest_bid=highest_bid_row.amount if highest_bid_row else None,
        highest_bidder_discord_id=highest_bid_row.bidder_discord_id if highest_bid_row else None,
        bid_count=len(bids),
    )


async def list_server_sale_listings(server_discord_id: int) -> list[AuctionSaleListing]:
    """Return all active sale listings on a server."""
    listings = []
    for orm in await list_active_sale_listings_for_server(server_discord_id):
        highest_bid_row = await get_highest_bid_for_listing(orm.id)
        bids = await list_bids_for_listing(orm.id)
        listings.append(
            await to_auction_sale_listing(
                orm,
                highest_bid=highest_bid_row.amount if highest_bid_row else None,
                highest_bidder_discord_id=highest_bid_row.bidder_discord_id if highest_bid_row else None,
                bid_count=len(bids),
            )
        )
    return listings


async def list_owner_sale_listings(owner_discord_id: int) -> list[AuctionSaleListing]:
    """Return all active listings by this seller."""
    listings = []
    for orm in await list_active_sale_listings_for_owner(owner_discord_id):
        highest_bid_row = await get_highest_bid_for_listing(orm.id)
        bids = await list_bids_for_listing(orm.id)
        listings.append(
            await to_auction_sale_listing(
                orm,
                highest_bid=highest_bid_row.amount if highest_bid_row else None,
                highest_bidder_discord_id=highest_bid_row.bidder_discord_id if highest_bid_row else None,
                bid_count=len(bids),
            )
        )
    return listings


# ---------------------------------------------------------------------------
# Bounty listings — public API
# ---------------------------------------------------------------------------


async def create_bounty_listing(
    owner_discord_id: int,
    server_discord_id: int,
    title: str,
    escrow_amount: int,
    criteria: list,
) -> tuple[bool, str]:
    """Create a Want-to-Buy bounty. Deducts escrow_amount from owner immediately."""
    owner = await get_owner_by_discord_id(owner_discord_id)
    if owner is None:
        return False, "Owner not found."
    if escrow_amount <= 0:
        return False, "Escrow amount must be positive."
    if owner.dollars < escrow_amount:
        return False, f"You need ${escrow_amount} but only have ${owner.dollars}."
    if not criteria:
        return False, "You must specify at least one criterion."
    for criterion in criteria:
        error = _validate_criterion(criterion)
        if error:
            return False, f"Invalid criterion: {error}"

    await give_money_to_owner(owner_discord_id, -escrow_amount)
    await create_auction_bounty_listing(
        buyer_discord_id=owner_discord_id,
        server_discord_id=server_discord_id,
        title=title or "Wanted",
        escrow_amount=escrow_amount,
        criteria=criteria,
    )
    return True, f"Bounty listing '{title or 'Wanted'}' created with ${escrow_amount} in escrow."


async def evaluate_bounty_match(bounty_listing_id: int, pooch_id: int) -> BountyMatchResult:
    """
    Check a pooch against each criterion of the bounty and compute the payout.
    Pure logic — no DB writes.
    """
    listing_orm = await get_auction_bounty_listing_by_id(bounty_listing_id)
    if listing_orm is None:
        return BountyMatchResult(listing_id=bounty_listing_id, matched_criteria=[], payout=0)

    pooch_orm = await get_pooch_by_id(pooch_id)
    if pooch_orm is None:
        return BountyMatchResult(listing_id=bounty_listing_id, matched_criteria=[], payout=0)

    pooch = await to_pooch(pooch_orm)

    matched_criteria = []
    total_payout = 0

    for criterion in listing_orm.criteria or []:
        ctype = criterion.get("type")
        dollar_value = criterion.get("dollar_value", 0)
        entry = dict(criterion)
        entry["matched"] = False
        earned = 0

        if ctype == "breed":
            breed_id = criterion["breed_id"]
            min_weight = criterion.get("min_weight", 0)
            for bi in pooch.breeds:
                if bi.breed.id == breed_id and bi.relative_weight >= min_weight:
                    entry["matched"] = True
                    earned = dollar_value
                    break

        elif ctype == "mutation":
            mutation_id = criterion["mutation_id"]
            if any(m.mutation.id == mutation_id for m in pooch.mutations):
                entry["matched"] = True
                earned = dollar_value

        elif ctype == "sex":
            value = criterion["value"]
            if value in ("male", "female"):
                if pooch.sex == value:
                    entry["matched"] = True
                    earned = dollar_value
            else:  # "either"
                # Always matches; bonus if preferred sex matches
                entry["matched"] = True
                preferred = criterion.get("preferred_sex")
                if pooch.sex == preferred:
                    earned = dollar_value
                else:
                    earned = 0  # matches but no bonus

        elif ctype == "min_stat":
            stat = criterion["stat"]
            threshold = criterion["threshold"]
            actual = getattr(pooch, stat, None)
            if actual is not None and actual >= threshold:
                entry["matched"] = True
                earned = dollar_value

        elif ctype == "min_rarity":
            required_value = criterion["value"]
            required_rank = _RARITY_ORDER.index(required_value) if required_value in _RARITY_ORDER else 0
            # Use the highest-weight breed's rarity
            if pooch.breeds:
                top_breed = max(pooch.breeds, key=lambda bi: bi.relative_weight)
                breed_rarity = top_breed.breed.rarity
                breed_rank = _RARITY_ORDER.index(breed_rarity) if breed_rarity in _RARITY_ORDER else 0
                if breed_rank >= required_rank:
                    entry["matched"] = True
                    earned = dollar_value

        total_payout += earned
        matched_criteria.append(entry)

    payout = min(total_payout, listing_orm.escrow_amount)
    return BountyMatchResult(
        listing_id=bounty_listing_id,
        matched_criteria=matched_criteria,
        payout=payout,
    )


async def fulfill_bounty(
    seller_discord_id: int,
    listing_id: int,
    pooch_id: int,
) -> tuple[bool, str]:
    """Sell a pooch to a bounty listing."""
    listing_orm = await get_auction_bounty_listing_by_id(listing_id)
    if listing_orm is None:
        return False, "Bounty listing not found."
    if not listing_orm.is_active:
        return False, "This bounty is no longer active."
    if listing_orm.buyer_discord_id == seller_discord_id:
        return False, "You can't fulfill your own bounty."

    pooch = await get_pooch_by_id(pooch_id)
    if pooch is None:
        return False, "Pooch not found."
    if pooch.owner_discord_id != seller_discord_id:
        return False, "You don't own that pooch."
    if not pooch.alive:
        return False, "You can't sell a dead pooch."

    match = await evaluate_bounty_match(listing_id, pooch_id)
    if match.payout <= 0:
        return False, "This pooch doesn't match any criteria on this bounty."

    payout = match.payout
    refund = listing_orm.escrow_amount - payout

    await remove_pooch_from_kennel(pooch_id)
    await transfer_pooch_to_owner(pooch_id, listing_orm.buyer_discord_id)
    await give_money_to_owner(seller_discord_id, payout)
    if refund > 0:
        await give_money_to_owner(listing_orm.buyer_discord_id, refund)
    await fulfill_auction_bounty_listing(listing_id, seller_discord_id, pooch_id)

    return True, (
        f"Sold {pooch.name} for ${payout}."
        + (f" ${refund} returned to the buyer." if refund > 0 else "")
        + " The buyer needs to place the pooch in a kennel."
    )


async def cancel_bounty_listing(owner_discord_id: int, listing_id: int) -> tuple[bool, str]:
    """Cancel a bounty and refund escrow to the owner."""
    listing_orm = await get_auction_bounty_listing_by_id(listing_id)
    if listing_orm is None:
        return False, "Bounty listing not found."
    if not listing_orm.is_active:
        return False, "This bounty is already closed."
    if listing_orm.buyer_discord_id != owner_discord_id:
        return False, "You don't own this bounty listing."

    await give_money_to_owner(owner_discord_id, listing_orm.escrow_amount)
    await cancel_auction_bounty_listing(listing_id)
    return True, f"Bounty cancelled. ${listing_orm.escrow_amount} returned to your account."


async def list_server_bounty_listings(server_discord_id: int) -> list[AuctionBountyListing]:
    """Return all active bounty listings on a server."""
    return [to_auction_bounty_listing(orm) for orm in await list_active_bounty_listings_for_server(server_discord_id)]


async def list_owner_bounty_listings(owner_discord_id: int) -> list[AuctionBountyListing]:
    """Return active bounties posted by this owner."""
    return [to_auction_bounty_listing(orm) for orm in await list_active_bounty_listings_for_owner(owner_discord_id)]
