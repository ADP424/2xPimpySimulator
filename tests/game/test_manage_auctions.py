"""Tests for src/game/manage_auctions.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.game.manage_auctions import (
    _find_kennel_space,
    _validate_criterion,
    cancel_bounty_listing,
    cancel_listing_for_pooch,
    close_sale_listing,
    create_bounty_listing,
    create_sale_listing,
    evaluate_bounty_match,
    fulfill_bounty,
    get_sale_listing,
    list_owner_bounty_listings,
    list_owner_sale_listings,
    list_server_bounty_listings,
    list_server_sale_listings,
    place_bid,
    process_expired_sale_listings,
)

_MOD = "src.game.manage_auctions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_listing(
    listing_id=1,
    pooch_id=10,
    seller_discord_id=42,
    server_discord_id=5,
    minimum_bid=100,
    is_active=True,
    expires_at=None,
):
    return SimpleNamespace(
        id=listing_id,
        pooch_id=pooch_id,
        seller_discord_id=seller_discord_id,
        server_discord_id=server_discord_id,
        minimum_bid=minimum_bid,
        is_active=is_active,
        expires_at=expires_at,
        created_at=None,
        winning_bidder_discord_id=None,
        winning_bid_amount=None,
    )


def _make_bounty(
    listing_id=1,
    buyer_discord_id=77,
    server_discord_id=5,
    title="Wanted",
    escrow_amount=500,
    criteria=None,
    is_active=True,
):
    return SimpleNamespace(
        id=listing_id,
        buyer_discord_id=buyer_discord_id,
        server_discord_id=server_discord_id,
        title=title,
        escrow_amount=escrow_amount,
        criteria=criteria or [],
        is_active=is_active,
        created_at=None,
    )


def _make_bid(bid_id=1, listing_id=1, bidder_discord_id=99, amount=200):
    return SimpleNamespace(
        id=bid_id,
        listing_id=listing_id,
        bidder_discord_id=bidder_discord_id,
        amount=amount,
    )


def _make_kennel(kennel_id=1, pooch_limit=5):
    return SimpleNamespace(id=kennel_id, pooch_limit=pooch_limit)


# ===========================================================================
# _find_kennel_space
# ===========================================================================


class TestFindKennelSpace:
    @patch(f"{_MOD}.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_returns_kennel_id_with_space(self, mock_list_kennels, mock_list_pooches):
        mock_list_kennels.return_value = [_make_kennel(kennel_id=1, pooch_limit=5)]
        mock_list_pooches.return_value = [SimpleNamespace(id=10)]  # 1 of 5 used

        result = await _find_kennel_space(42)

        assert result == 1

    @patch(f"{_MOD}.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_returns_none_when_all_full(self, mock_list_kennels, mock_list_pooches):
        mock_list_kennels.return_value = [_make_kennel(kennel_id=1, pooch_limit=1)]
        mock_list_pooches.return_value = [SimpleNamespace(id=10)]  # 1/1 full

        result = await _find_kennel_space(42)

        assert result is None

    @patch(f"{_MOD}.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_returns_none_when_no_kennels(self, mock_list_kennels):
        mock_list_kennels.return_value = []

        result = await _find_kennel_space(42)

        assert result is None

    @patch(f"{_MOD}.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_returns_first_kennel_with_space(self, mock_list_kennels, mock_list_pooches):
        kennels = [_make_kennel(kennel_id=1, pooch_limit=1), _make_kennel(kennel_id=2, pooch_limit=5)]
        mock_list_kennels.return_value = kennels
        # First kennel is full, second has space
        mock_list_pooches.side_effect = [
            [SimpleNamespace(id=10)],  # kennel 1: full
            [],  # kennel 2: empty
        ]

        result = await _find_kennel_space(42)

        assert result == 2


# ===========================================================================
# _validate_criterion
# ===========================================================================


class TestValidateCriterion:
    def test_valid_sex_male(self):
        assert _validate_criterion({"type": "sex", "value": "male", "dollar_value": 10}) is None

    def test_valid_sex_female(self):
        assert _validate_criterion({"type": "sex", "value": "female", "dollar_value": 10}) is None

    def test_valid_sex_either_with_preferred(self):
        assert (
            _validate_criterion({"type": "sex", "value": "either", "preferred_sex": "male", "dollar_value": 5}) is None
        )

    def test_sex_either_missing_preferred(self):
        err = _validate_criterion({"type": "sex", "value": "either", "dollar_value": 5})
        assert err is not None
        assert "preferred_sex" in err

    def test_sex_invalid_value(self):
        err = _validate_criterion({"type": "sex", "value": "nonbinary", "dollar_value": 5})
        assert err is not None

    def test_valid_breed(self):
        assert _validate_criterion({"type": "breed", "breed_id": 1, "min_weight": 0.5, "dollar_value": 20}) is None

    def test_breed_missing_breed_id(self):
        err = _validate_criterion({"type": "breed", "min_weight": 0.5, "dollar_value": 20})
        assert err is not None
        assert "breed_id" in err

    def test_breed_invalid_min_weight_zero(self):
        err = _validate_criterion({"type": "breed", "breed_id": 1, "min_weight": 0, "dollar_value": 20})
        assert err is not None

    def test_breed_invalid_min_weight_over_one(self):
        err = _validate_criterion({"type": "breed", "breed_id": 1, "min_weight": 1.5, "dollar_value": 20})
        assert err is not None

    def test_valid_mutation(self):
        assert _validate_criterion({"type": "mutation", "mutation_id": 3, "dollar_value": 15}) is None

    def test_mutation_missing_mutation_id(self):
        err = _validate_criterion({"type": "mutation", "dollar_value": 15})
        assert err is not None

    def test_valid_min_stat(self):
        assert (
            _validate_criterion({"type": "min_stat", "stat": "strength", "threshold": 15, "dollar_value": 30}) is None
        )

    def test_min_stat_invalid_stat(self):
        err = _validate_criterion({"type": "min_stat", "stat": "magic", "threshold": 10, "dollar_value": 10})
        assert err is not None

    def test_min_stat_negative_threshold(self):
        err = _validate_criterion({"type": "min_stat", "stat": "strength", "threshold": -1, "dollar_value": 10})
        assert err is not None

    def test_valid_min_rarity(self):
        assert _validate_criterion({"type": "min_rarity", "value": "rare", "dollar_value": 50}) is None

    def test_min_rarity_invalid_value(self):
        err = _validate_criterion({"type": "min_rarity", "value": "godlike", "dollar_value": 50})
        assert err is not None

    def test_unknown_type(self):
        err = _validate_criterion({"type": "zodiac", "dollar_value": 10})
        assert err is not None

    def test_non_positive_dollar_value(self):
        err = _validate_criterion({"type": "sex", "value": "male", "dollar_value": 0})
        assert err is not None

    def test_non_integer_dollar_value(self):
        err = _validate_criterion({"type": "sex", "value": "male", "dollar_value": "ten"})
        assert err is not None


# ===========================================================================
# create_sale_listing
# ===========================================================================


class TestCreateSaleListing:
    @patch(f"{_MOD}.create_auction_sale_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_active_auction_sale_listing_for_pooch", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_success_no_expiry(self, mock_owner, mock_pooch, mock_active, mock_create):
        mock_owner.return_value = SimpleNamespace(discord_id=42)
        mock_pooch.return_value = SimpleNamespace(id=10, name="Buddy", owner_discord_id=42, alive=True)
        mock_active.return_value = None
        mock_create.return_value = _make_listing()

        ok, msg = await create_sale_listing(42, 10, 5, 100)

        assert ok is True
        assert "Buddy" in msg
        assert "no expiry" in msg
        mock_create.assert_awaited_once()

    @patch(f"{_MOD}.create_auction_sale_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_active_auction_sale_listing_for_pooch", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_success_with_duration(self, mock_owner, mock_pooch, mock_active, mock_create):
        mock_owner.return_value = SimpleNamespace(discord_id=42)
        mock_pooch.return_value = SimpleNamespace(id=10, name="Rex", owner_discord_id=42, alive=True)
        mock_active.return_value = None
        mock_create.return_value = _make_listing()

        ok, msg = await create_sale_listing(42, 10, 5, 50, duration_hours=24)

        assert ok is True
        assert "24h" in msg

    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_owner_not_found(self, mock_owner):
        mock_owner.return_value = None

        ok, msg = await create_sale_listing(999, 10, 5, 100)

        assert ok is False
        assert "Owner not found" in msg

    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_pooch_not_found(self, mock_owner, mock_pooch):
        mock_owner.return_value = SimpleNamespace(discord_id=42)
        mock_pooch.return_value = None

        ok, msg = await create_sale_listing(42, 999, 5, 100)

        assert ok is False
        assert "Pooch not found" in msg

    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_pooch_not_owned(self, mock_owner, mock_pooch):
        mock_owner.return_value = SimpleNamespace(discord_id=42)
        mock_pooch.return_value = SimpleNamespace(id=10, name="Buddy", owner_discord_id=99, alive=True)

        ok, msg = await create_sale_listing(42, 10, 5, 100)

        assert ok is False
        assert "don't own" in msg

    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_dead_pooch(self, mock_owner, mock_pooch):
        mock_owner.return_value = SimpleNamespace(discord_id=42)
        mock_pooch.return_value = SimpleNamespace(id=10, name="Ghost", owner_discord_id=42, alive=False)

        ok, msg = await create_sale_listing(42, 10, 5, 100)

        assert ok is False
        assert "dead" in msg

    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_negative_minimum_bid(self, mock_owner, mock_pooch):
        mock_owner.return_value = SimpleNamespace(discord_id=42)
        mock_pooch.return_value = SimpleNamespace(id=10, name="Buddy", owner_discord_id=42, alive=True)

        ok, msg = await create_sale_listing(42, 10, 5, -1)

        assert ok is False
        assert "negative" in msg

    @patch(f"{_MOD}.get_active_auction_sale_listing_for_pooch", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_already_listed(self, mock_owner, mock_pooch, mock_active):
        mock_owner.return_value = SimpleNamespace(discord_id=42)
        mock_pooch.return_value = SimpleNamespace(id=10, name="Buddy", owner_discord_id=42, alive=True)
        mock_active.return_value = _make_listing()

        ok, msg = await create_sale_listing(42, 10, 5, 100)

        assert ok is False
        assert "already listed" in msg

    @patch(f"{_MOD}.get_active_auction_sale_listing_for_pooch", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_zero_duration_rejected(self, mock_owner, mock_pooch, mock_active):
        mock_owner.return_value = SimpleNamespace(discord_id=42)
        mock_pooch.return_value = SimpleNamespace(id=10, name="Buddy", owner_discord_id=42, alive=True)
        mock_active.return_value = None

        ok, msg = await create_sale_listing(42, 10, 5, 100, duration_hours=0)

        assert ok is False
        assert "Duration" in msg


# ===========================================================================
# place_bid
# ===========================================================================


class TestPlaceBid:
    @patch(f"{_MOD}.create_auction_bid", new_callable=AsyncMock)
    @patch(f"{_MOD}.give_money_to_owner", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_highest_bid_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_opening_bid_success(self, mock_get_listing, mock_get_owner, mock_highest, mock_give, mock_create):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42, minimum_bid=50)
        mock_get_owner.return_value = SimpleNamespace(discord_id=99, dollars=500)
        mock_highest.return_value = None  # No bids yet

        ok, msg = await place_bid(99, 1, 50)

        assert ok is True
        assert "placed successfully" in msg
        mock_create.assert_awaited_once()

    @patch(f"{_MOD}.create_auction_bid", new_callable=AsyncMock)
    @patch(f"{_MOD}.give_money_to_owner", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_highest_bid_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_outbid_refunds_previous_bidder(
        self, mock_get_listing, mock_get_owner, mock_highest, mock_give, mock_create
    ):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42, minimum_bid=50)
        mock_get_owner.return_value = SimpleNamespace(discord_id=88, dollars=1000)
        mock_highest.return_value = _make_bid(bidder_discord_id=77, amount=100)

        ok, msg = await place_bid(88, 1, 200)

        assert ok is True
        # give_money_to_owner called twice: refund prev bidder and deduct from new bidder
        assert mock_give.await_count == 2

    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_listing_not_found(self, mock_get_listing):
        mock_get_listing.return_value = None

        ok, msg = await place_bid(99, 999, 100)

        assert ok is False
        assert "Listing not found" in msg

    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_inactive_listing(self, mock_get_listing):
        mock_get_listing.return_value = _make_listing(is_active=False)

        ok, msg = await place_bid(99, 1, 100)

        assert ok is False
        assert "no longer active" in msg

    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_cannot_bid_on_own_listing(self, mock_get_listing):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42)

        ok, msg = await place_bid(42, 1, 100)

        assert ok is False
        assert "own listing" in msg

    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_zero_bid_rejected(self, mock_get_listing):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42)

        ok, msg = await place_bid(99, 1, 0)

        assert ok is False
        assert "positive" in msg

    @patch(f"{_MOD}.get_highest_bid_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_bid_below_minimum(self, mock_get_listing, mock_get_owner, mock_highest):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42, minimum_bid=100)
        mock_get_owner.return_value = SimpleNamespace(discord_id=99, dollars=500)
        mock_highest.return_value = None  # No prior bids

        ok, msg = await place_bid(99, 1, 50)

        assert ok is False
        assert "Opening bid" in msg

    @patch(f"{_MOD}.get_highest_bid_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_bid_not_exceeding_current_high(self, mock_get_listing, mock_get_owner, mock_highest):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42, minimum_bid=50)
        mock_get_owner.return_value = SimpleNamespace(discord_id=99, dollars=500)
        mock_highest.return_value = _make_bid(bidder_discord_id=77, amount=200)

        ok, msg = await place_bid(99, 1, 200)  # tie, not exceeding

        assert ok is False
        assert "highest bid" in msg

    @patch(f"{_MOD}.get_highest_bid_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_insufficient_funds(self, mock_get_listing, mock_get_owner, mock_highest):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42, minimum_bid=50)
        mock_get_owner.return_value = SimpleNamespace(discord_id=99, dollars=10)
        mock_highest.return_value = None

        ok, msg = await place_bid(99, 1, 100)

        assert ok is False
        assert "enough money" in msg

    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_expired_listing_rejected(self, mock_get_listing):
        from datetime import datetime, timezone

        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        mock_get_listing.return_value = _make_listing(seller_discord_id=42, expires_at=past)

        ok, msg = await place_bid(99, 1, 100)

        assert ok is False
        assert "expired" in msg


# ===========================================================================
# close_sale_listing
# ===========================================================================


class TestCloseSaleListing:
    @patch(f"{_MOD}._resolve_auction_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_owner_can_close(self, mock_get_listing, mock_resolve):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42)
        mock_resolve.return_value = (True, "Auction resolved.")

        ok, msg = await close_sale_listing(42, 1)

        assert ok is True
        mock_resolve.assert_awaited_once_with(1)

    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_listing_not_found(self, mock_get_listing):
        mock_get_listing.return_value = None

        ok, msg = await close_sale_listing(42, 999)

        assert ok is False
        assert "not found" in msg

    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_already_closed(self, mock_get_listing):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42, is_active=False)

        ok, msg = await close_sale_listing(42, 1)

        assert ok is False
        assert "already closed" in msg

    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_non_owner_cannot_close(self, mock_get_listing):
        mock_get_listing.return_value = _make_listing(seller_discord_id=42)

        ok, msg = await close_sale_listing(99, 1)

        assert ok is False
        assert "don't own" in msg


# ===========================================================================
# process_expired_sale_listings
# ===========================================================================


class TestProcessExpiredSaleListings:
    @patch(f"{_MOD}._resolve_auction_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_expired_sale_listings", new_callable=AsyncMock)
    async def test_processes_all_expired(self, mock_list, mock_resolve):
        mock_list.return_value = [_make_listing(listing_id=1), _make_listing(listing_id=2)]
        mock_resolve.return_value = (True, "done")

        results = await process_expired_sale_listings()

        assert len(results) == 2
        assert all(r[1] is True for r in results)

    @patch(f"{_MOD}.list_expired_sale_listings", new_callable=AsyncMock)
    async def test_returns_empty_when_nothing_expired(self, mock_list):
        mock_list.return_value = []

        results = await process_expired_sale_listings()

        assert results == []


# ===========================================================================
# get_sale_listing
# ===========================================================================


class TestGetSaleListing:
    @patch(f"{_MOD}.to_auction_sale_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_bids_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_highest_bid_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_returns_sale_listing(self, mock_get, mock_highest, mock_bids, mock_to):
        mock_get.return_value = _make_listing()
        mock_highest.return_value = _make_bid(amount=300)
        mock_bids.return_value = [_make_bid(), _make_bid(bid_id=2)]
        mock_to.return_value = SimpleNamespace(id=1)

        result = await get_sale_listing(1)

        assert result is not None
        mock_to.assert_awaited_once()
        _, kwargs = mock_to.call_args
        assert kwargs["highest_bid"] == 300
        assert kwargs["bid_count"] == 2

    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_returns_none_when_missing(self, mock_get):
        mock_get.return_value = None

        result = await get_sale_listing(999)

        assert result is None

    @patch(f"{_MOD}.to_auction_sale_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_bids_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_highest_bid_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_sale_listing_by_id", new_callable=AsyncMock)
    async def test_no_bids_passes_none(self, mock_get, mock_highest, mock_bids, mock_to):
        mock_get.return_value = _make_listing()
        mock_highest.return_value = None
        mock_bids.return_value = []
        mock_to.return_value = SimpleNamespace(id=1)

        await get_sale_listing(1)

        _, kwargs = mock_to.call_args
        assert kwargs["highest_bid"] is None
        assert kwargs["highest_bidder_discord_id"] is None
        assert kwargs["bid_count"] == 0


# ===========================================================================
# list_server_sale_listings / list_owner_sale_listings
# ===========================================================================


class TestListSaleListings:
    @patch(f"{_MOD}.to_auction_sale_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_bids_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_highest_bid_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_active_sale_listings_for_server", new_callable=AsyncMock)
    async def test_list_server_returns_formatted(self, mock_list, mock_highest, mock_bids, mock_to):
        mock_list.return_value = [_make_listing(listing_id=1), _make_listing(listing_id=2)]
        mock_highest.return_value = None
        mock_bids.return_value = []
        mock_to.return_value = SimpleNamespace(id=1)

        result = await list_server_sale_listings(5)

        assert len(result) == 2

    @patch(f"{_MOD}.list_active_sale_listings_for_server", new_callable=AsyncMock)
    async def test_list_server_empty(self, mock_list):
        mock_list.return_value = []

        result = await list_server_sale_listings(5)

        assert result == []

    @patch(f"{_MOD}.to_auction_sale_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_bids_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_highest_bid_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_active_sale_listings_for_owner", new_callable=AsyncMock)
    async def test_list_owner_returns_formatted(self, mock_list, mock_highest, mock_bids, mock_to):
        mock_list.return_value = [_make_listing(listing_id=3)]
        mock_highest.return_value = None
        mock_bids.return_value = []
        mock_to.return_value = SimpleNamespace(id=3)

        result = await list_owner_sale_listings(42)

        assert len(result) == 1


# ===========================================================================
# cancel_listing_for_pooch
# ===========================================================================


class TestCancelListingForPooch:
    @patch(f"{_MOD}.close_auction_sale_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.give_money_to_owner", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_bids_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_active_auction_sale_listing_for_pooch", new_callable=AsyncMock)
    async def test_cancels_and_refunds_bidders(self, mock_get_active, mock_bids, mock_give, mock_close):
        mock_get_active.return_value = _make_listing(listing_id=1)
        # Two bids from different bidders (DESC order, each bidder once)
        mock_bids.return_value = [
            _make_bid(bid_id=1, bidder_discord_id=10, amount=200),
            _make_bid(bid_id=2, bidder_discord_id=20, amount=100),
        ]

        await cancel_listing_for_pooch(10)

        # Both bidders refunded once
        assert mock_give.await_count == 2
        mock_close.assert_awaited_once_with(1, None, None)

    @patch(f"{_MOD}.close_auction_sale_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.give_money_to_owner", new_callable=AsyncMock)
    @patch(f"{_MOD}.list_bids_for_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_active_auction_sale_listing_for_pooch", new_callable=AsyncMock)
    async def test_each_bidder_refunded_only_once(self, mock_get_active, mock_bids, mock_give, mock_close):
        """Bids ordered DESC — only the first (highest) bid per bidder should be refunded."""
        mock_get_active.return_value = _make_listing(listing_id=1)
        # Same bidder has multiple bids (shouldn't happen, but defensive test)
        mock_bids.return_value = [
            _make_bid(bid_id=1, bidder_discord_id=10, amount=300),
            _make_bid(bid_id=2, bidder_discord_id=10, amount=100),
        ]

        await cancel_listing_for_pooch(10)

        assert mock_give.await_count == 1  # Only the highest bid refunded

    @patch(f"{_MOD}.get_active_auction_sale_listing_for_pooch", new_callable=AsyncMock)
    async def test_no_active_listing_does_nothing(self, mock_get_active):
        mock_get_active.return_value = None

        # Should return without error
        await cancel_listing_for_pooch(10)


# ===========================================================================
# create_bounty_listing
# ===========================================================================


class TestCreateBountyListing:
    @patch(f"{_MOD}.create_auction_bounty_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.give_money_to_owner", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_success(self, mock_owner, mock_give, mock_create):
        mock_owner.return_value = SimpleNamespace(discord_id=77, dollars=1000)
        criteria = [{"type": "sex", "value": "female", "dollar_value": 50}]
        mock_create.return_value = _make_bounty()

        ok, msg = await create_bounty_listing(77, 5, "Wanted: Female", 500, criteria)

        assert ok is True
        assert "Wanted: Female" in msg
        mock_give.assert_awaited_once_with(77, -500)
        mock_create.assert_awaited_once()

    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_owner_not_found(self, mock_owner):
        mock_owner.return_value = None

        ok, msg = await create_bounty_listing(999, 5, "Wanted", 100, [])

        assert ok is False
        assert "Owner not found" in msg

    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_zero_escrow_rejected(self, mock_owner):
        mock_owner.return_value = SimpleNamespace(discord_id=77, dollars=1000)

        ok, msg = await create_bounty_listing(77, 5, "Wanted", 0, [])

        assert ok is False
        assert "positive" in msg

    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_insufficient_funds(self, mock_owner):
        mock_owner.return_value = SimpleNamespace(discord_id=77, dollars=50)

        criteria = [{"type": "sex", "value": "female", "dollar_value": 50}]
        ok, msg = await create_bounty_listing(77, 5, "Wanted", 100, criteria)

        assert ok is False
        assert "only have" in msg

    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_empty_criteria_rejected(self, mock_owner):
        mock_owner.return_value = SimpleNamespace(discord_id=77, dollars=1000)

        ok, msg = await create_bounty_listing(77, 5, "Wanted", 100, [])

        assert ok is False
        assert "criterion" in msg

    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_invalid_criterion_rejected(self, mock_owner):
        mock_owner.return_value = SimpleNamespace(discord_id=77, dollars=1000)
        bad_criteria = [{"type": "zodiac", "dollar_value": 50}]

        ok, msg = await create_bounty_listing(77, 5, "Wanted", 100, bad_criteria)

        assert ok is False
        assert "Invalid criterion" in msg

    @patch(f"{_MOD}.create_auction_bounty_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.give_money_to_owner", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_empty_title_defaults_to_wanted(self, mock_owner, mock_give, mock_create):
        mock_owner.return_value = SimpleNamespace(discord_id=77, dollars=1000)
        criteria = [{"type": "sex", "value": "male", "dollar_value": 10}]
        mock_create.return_value = _make_bounty()

        ok, msg = await create_bounty_listing(77, 5, "", 100, criteria)

        assert ok is True
        assert "Wanted" in msg
        _, kwargs = mock_create.call_args
        assert kwargs["title"] == "Wanted"


# ===========================================================================
# evaluate_bounty_match
# ===========================================================================


class TestEvaluateBountyMatch:
    async def test_listing_not_found_returns_zero_payout(self):
        with patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await evaluate_bounty_match(999, 10)

        assert result.payout == 0
        assert result.matched_criteria == []

    async def test_pooch_not_found_returns_zero_payout(self):
        with (
            patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock) as mock_listing,
            patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock) as mock_pooch,
        ):
            mock_listing.return_value = _make_bounty(criteria=[{"type": "sex", "value": "male", "dollar_value": 10}])
            mock_pooch.return_value = None

            result = await evaluate_bounty_match(1, 999)

        assert result.payout == 0

    async def test_sex_criterion_match(self):
        criteria = [{"type": "sex", "value": "male", "dollar_value": 50}]
        fake_pooch = SimpleNamespace(sex="male", breeds=[], mutations=[], strength=10, size=10)
        with (
            patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock) as mock_listing,
            patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock) as mock_pooch,
            patch(f"{_MOD}.to_pooch", new_callable=AsyncMock) as mock_to_pooch,
        ):
            mock_listing.return_value = _make_bounty(criteria=criteria, escrow_amount=200)
            mock_pooch.return_value = SimpleNamespace(id=10)
            mock_to_pooch.return_value = fake_pooch

            result = await evaluate_bounty_match(1, 10)

        assert result.payout == 50
        assert result.matched_criteria[0]["matched"] is True

    async def test_sex_criterion_no_match(self):
        criteria = [{"type": "sex", "value": "female", "dollar_value": 50}]
        fake_pooch = SimpleNamespace(sex="male", breeds=[], mutations=[])
        with (
            patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock) as mock_listing,
            patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock) as mock_pooch,
            patch(f"{_MOD}.to_pooch", new_callable=AsyncMock) as mock_to_pooch,
        ):
            mock_listing.return_value = _make_bounty(criteria=criteria, escrow_amount=200)
            mock_pooch.return_value = SimpleNamespace(id=10)
            mock_to_pooch.return_value = fake_pooch

            result = await evaluate_bounty_match(1, 10)

        assert result.payout == 0
        assert result.matched_criteria[0]["matched"] is False

    async def test_min_stat_criterion_match(self):
        criteria = [{"type": "min_stat", "stat": "strength", "threshold": 10, "dollar_value": 30}]
        fake_pooch = SimpleNamespace(sex="male", breeds=[], mutations=[], strength=15)
        with (
            patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock) as mock_listing,
            patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock) as mock_pooch,
            patch(f"{_MOD}.to_pooch", new_callable=AsyncMock) as mock_to_pooch,
        ):
            mock_listing.return_value = _make_bounty(criteria=criteria, escrow_amount=200)
            mock_pooch.return_value = SimpleNamespace(id=10)
            mock_to_pooch.return_value = fake_pooch

            result = await evaluate_bounty_match(1, 10)

        assert result.payout == 30
        assert result.matched_criteria[0]["matched"] is True

    async def test_payout_capped_at_escrow(self):
        """Payout cannot exceed the escrow amount."""
        criteria = [
            {"type": "sex", "value": "male", "dollar_value": 500},
            {"type": "min_stat", "stat": "strength", "threshold": 5, "dollar_value": 500},
        ]
        fake_pooch = SimpleNamespace(sex="male", breeds=[], mutations=[], strength=10)
        with (
            patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock) as mock_listing,
            patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock) as mock_pooch,
            patch(f"{_MOD}.to_pooch", new_callable=AsyncMock) as mock_to_pooch,
        ):
            mock_listing.return_value = _make_bounty(criteria=criteria, escrow_amount=100)
            mock_pooch.return_value = SimpleNamespace(id=10)
            mock_to_pooch.return_value = fake_pooch

            result = await evaluate_bounty_match(1, 10)

        assert result.payout == 100  # capped at escrow

    async def test_sex_either_matches_but_no_bonus_for_non_preferred(self):
        criteria = [{"type": "sex", "value": "either", "preferred_sex": "female", "dollar_value": 40}]
        fake_pooch = SimpleNamespace(sex="male", breeds=[], mutations=[])
        with (
            patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock) as mock_listing,
            patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock) as mock_pooch,
            patch(f"{_MOD}.to_pooch", new_callable=AsyncMock) as mock_to_pooch,
        ):
            mock_listing.return_value = _make_bounty(criteria=criteria, escrow_amount=200)
            mock_pooch.return_value = SimpleNamespace(id=10)
            mock_to_pooch.return_value = fake_pooch

            result = await evaluate_bounty_match(1, 10)

        # "either" always matches but earns $0 when sex != preferred
        assert result.matched_criteria[0]["matched"] is True
        assert result.payout == 0

    async def test_mutation_criterion_match(self):
        criteria = [{"type": "mutation", "mutation_id": 3, "dollar_value": 20}]
        fake_mutation_info = SimpleNamespace(mutation=SimpleNamespace(id=3))
        fake_pooch = SimpleNamespace(sex="male", breeds=[], mutations=[fake_mutation_info])
        with (
            patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock) as mock_listing,
            patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock) as mock_pooch,
            patch(f"{_MOD}.to_pooch", new_callable=AsyncMock) as mock_to_pooch,
        ):
            mock_listing.return_value = _make_bounty(criteria=criteria, escrow_amount=200)
            mock_pooch.return_value = SimpleNamespace(id=10)
            mock_to_pooch.return_value = fake_pooch

            result = await evaluate_bounty_match(1, 10)

        assert result.payout == 20
        assert result.matched_criteria[0]["matched"] is True


# ===========================================================================
# fulfill_bounty
# ===========================================================================


class TestFulfillBounty:
    @patch(f"{_MOD}.fulfill_auction_bounty_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.give_money_to_owner", new_callable=AsyncMock)
    @patch(f"{_MOD}.transfer_pooch_to_owner", new_callable=AsyncMock)
    @patch(f"{_MOD}.remove_pooch_from_kennel", new_callable=AsyncMock)
    @patch(f"{_MOD}.evaluate_bounty_match", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_success_with_partial_payout(
        self, mock_get_bounty, mock_get_pooch, mock_eval, mock_remove, mock_transfer, mock_give, mock_fulfill
    ):
        mock_get_bounty.return_value = _make_bounty(listing_id=1, buyer_discord_id=77, escrow_amount=500)
        mock_get_pooch.return_value = SimpleNamespace(id=10, name="Rex", owner_discord_id=55, alive=True)
        from src.game.models.auction import BountyMatchResult

        mock_eval.return_value = BountyMatchResult(listing_id=1, matched_criteria=[], payout=300)

        ok, msg = await fulfill_bounty(55, 1, 10)

        assert ok is True
        assert "Rex" in msg
        assert "$300" in msg
        assert "$200" in msg  # refund to buyer (500 - 300)
        mock_give.assert_any_await(55, 300)
        mock_give.assert_any_await(77, 200)
        mock_fulfill.assert_awaited_once()

    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_bounty_not_found(self, mock_get_bounty):
        mock_get_bounty.return_value = None

        ok, msg = await fulfill_bounty(55, 999, 10)

        assert ok is False
        assert "not found" in msg

    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_inactive_bounty(self, mock_get_bounty):
        mock_get_bounty.return_value = _make_bounty(is_active=False)

        ok, msg = await fulfill_bounty(55, 1, 10)

        assert ok is False
        assert "no longer active" in msg

    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_cannot_fulfill_own_bounty(self, mock_get_bounty):
        mock_get_bounty.return_value = _make_bounty(buyer_discord_id=55)

        ok, msg = await fulfill_bounty(55, 1, 10)

        assert ok is False
        assert "own bounty" in msg

    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_pooch_not_found(self, mock_get_bounty, mock_get_pooch):
        mock_get_bounty.return_value = _make_bounty(buyer_discord_id=77)
        mock_get_pooch.return_value = None

        ok, msg = await fulfill_bounty(55, 1, 999)

        assert ok is False
        assert "Pooch not found" in msg

    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_pooch_not_owned(self, mock_get_bounty, mock_get_pooch):
        mock_get_bounty.return_value = _make_bounty(buyer_discord_id=77)
        mock_get_pooch.return_value = SimpleNamespace(id=10, name="Rex", owner_discord_id=99, alive=True)

        ok, msg = await fulfill_bounty(55, 1, 10)

        assert ok is False
        assert "don't own" in msg

    @patch(f"{_MOD}.evaluate_bounty_match", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_pooch_by_id", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_no_criteria_match(self, mock_get_bounty, mock_get_pooch, mock_eval):
        mock_get_bounty.return_value = _make_bounty(buyer_discord_id=77)
        mock_get_pooch.return_value = SimpleNamespace(id=10, name="Rex", owner_discord_id=55, alive=True)
        from src.game.models.auction import BountyMatchResult

        mock_eval.return_value = BountyMatchResult(listing_id=1, matched_criteria=[], payout=0)

        ok, msg = await fulfill_bounty(55, 1, 10)

        assert ok is False
        assert "doesn't match" in msg


# ===========================================================================
# cancel_bounty_listing
# ===========================================================================


class TestCancelBountyListing:
    @patch(f"{_MOD}.cancel_auction_bounty_listing", new_callable=AsyncMock)
    @patch(f"{_MOD}.give_money_to_owner", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_success(self, mock_get_bounty, mock_give, mock_cancel):
        mock_get_bounty.return_value = _make_bounty(listing_id=1, buyer_discord_id=77, escrow_amount=500)

        ok, msg = await cancel_bounty_listing(77, 1)

        assert ok is True
        assert "$500" in msg
        mock_give.assert_awaited_once_with(77, 500)
        mock_cancel.assert_awaited_once_with(1)

    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_bounty_not_found(self, mock_get_bounty):
        mock_get_bounty.return_value = None

        ok, msg = await cancel_bounty_listing(77, 999)

        assert ok is False
        assert "not found" in msg

    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_already_closed(self, mock_get_bounty):
        mock_get_bounty.return_value = _make_bounty(buyer_discord_id=77, is_active=False)

        ok, msg = await cancel_bounty_listing(77, 1)

        assert ok is False
        assert "already closed" in msg

    @patch(f"{_MOD}.get_auction_bounty_listing_by_id", new_callable=AsyncMock)
    async def test_non_owner_cannot_cancel(self, mock_get_bounty):
        mock_get_bounty.return_value = _make_bounty(buyer_discord_id=77)

        ok, msg = await cancel_bounty_listing(99, 1)

        assert ok is False
        assert "don't own" in msg


# ===========================================================================
# list_server_bounty_listings / list_owner_bounty_listings
# ===========================================================================


class TestListBountyListings:
    @patch(f"{_MOD}.to_auction_bounty_listing")
    @patch(f"{_MOD}.list_active_bounty_listings_for_server", new_callable=AsyncMock)
    async def test_list_server_bounties(self, mock_list, mock_to):
        fake_orm = [_make_bounty(listing_id=1), _make_bounty(listing_id=2)]
        mock_list.return_value = fake_orm
        mock_to.side_effect = lambda orm: orm  # pass-through

        result = await list_server_bounty_listings(5)

        assert len(result) == 2

    @patch(f"{_MOD}.list_active_bounty_listings_for_server", new_callable=AsyncMock)
    async def test_list_server_bounties_empty(self, mock_list):
        mock_list.return_value = []

        result = await list_server_bounty_listings(5)

        assert result == []

    @patch(f"{_MOD}.to_auction_bounty_listing")
    @patch(f"{_MOD}.list_active_bounty_listings_for_owner", new_callable=AsyncMock)
    async def test_list_owner_bounties(self, mock_list, mock_to):
        fake_orm = [_make_bounty(listing_id=10)]
        mock_list.return_value = fake_orm
        mock_to.side_effect = lambda orm: orm

        result = await list_owner_bounty_listings(77)

        assert len(result) == 1
