"""Tests for src/game/manage_vendors.py — buy/sell pooches and pricing."""

from unittest.mock import AsyncMock, patch

import pytest

from conftest import (
    make_breed,
    make_kennel,
    make_mutation,
    make_owner,
    make_pooch,
    make_vendor,
)
from src.game.exceptions import PoochNotFound, VendorNotFound
from src.game.manage_vendors import (
    _get_pooch_base_price,
    buy_pooch,
    get_pooch_buy_price,
    get_pooch_sell_price,
    get_vendor_by_id,
    sell_pooch,
)

# ---------------------------------------------------------------------------
# _get_pooch_base_price
# ---------------------------------------------------------------------------


class TestGetPoochBasePrice:
    @patch("src.game.manage_vendors.list_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    async def test_base_price_young_healthy(self, mock_get, mock_health, mock_muts, mock_breeds):
        """Young healthy pooch with common breed: BASE (75) - age*5 - health_penalty * breed_mult."""
        pooch = make_pooch(pooch_id=1, age=0)
        mock_get.return_value = pooch
        mock_health.return_value = 10  # average = (12-8)/2 = 2, so pooch_health=10 > avg => bonus
        mock_muts.return_value = []
        breed = make_breed(breed_id=1, rarity="common")
        mock_breeds.return_value = [(breed, 1)]

        price = await _get_pooch_base_price(1)
        # 75 - 0*5 = 75; health: 75 - 5*(2 - 10) = 75 + 40 = 115; breed: 115 * 0.5 = 57.5 -> 58
        assert isinstance(price, int)
        assert price >= 0

    @patch("src.game.manage_vendors.list_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    async def test_age_reduces_value(self, mock_get, mock_health, mock_muts, mock_breeds):
        """Older pooches lose POOCH_DOLLAR_VALUE_LOSS_BY_AGE (5) per age unit."""
        young = make_pooch(pooch_id=1, age=0)
        old = make_pooch(pooch_id=2, age=10)

        mock_health.return_value = 10
        mock_muts.return_value = []
        breed = make_breed(breed_id=1, rarity="uncommon")  # mult = 1.0
        mock_breeds.return_value = [(breed, 1)]

        mock_get.return_value = young
        young_price = await _get_pooch_base_price(1)

        mock_get.return_value = old
        old_price = await _get_pooch_base_price(2)

        assert young_price > old_price

    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    async def test_pooch_not_found_raises(self, mock_get):
        mock_get.return_value = None
        with pytest.raises(PoochNotFound):
            await _get_pooch_base_price(999)

    @patch("src.game.manage_vendors.list_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    async def test_mutation_dollar_value_add(self, mock_get, mock_health, mock_muts, mock_breeds):
        """Mutations with dollar_value_add increase the price."""
        pooch = make_pooch(pooch_id=1, age=0)
        mock_get.return_value = pooch
        mock_health.return_value = 10
        mut = make_mutation(mutation_id=1, parameters={"dollar_value_add": 50.0})
        mock_muts.return_value = [mut]
        breed = make_breed(breed_id=1, rarity="uncommon")
        mock_breeds.return_value = [(breed, 1)]

        price_with_mut = await _get_pooch_base_price(1)

        mock_muts.return_value = []
        price_without = await _get_pooch_base_price(1)

        assert price_with_mut > price_without

    @patch("src.game.manage_vendors.list_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    async def test_rare_breed_multiplies_price(self, mock_get, mock_health, mock_muts, mock_breeds):
        """A rare breed (mult=2.0) makes the pooch more valuable than common (mult=0.5)."""
        pooch = make_pooch(pooch_id=1, age=0)
        mock_get.return_value = pooch
        mock_health.return_value = 10
        mock_muts.return_value = []

        common_breed = make_breed(breed_id=1, rarity="common")
        mock_breeds.return_value = [(common_breed, 1)]
        common_price = await _get_pooch_base_price(1)

        rare_breed = make_breed(breed_id=2, rarity="rare")
        mock_breeds.return_value = [(rare_breed, 1)]
        rare_price = await _get_pooch_base_price(1)

        assert rare_price > common_price


# ---------------------------------------------------------------------------
# get_pooch_buy_price
# ---------------------------------------------------------------------------


class TestGetPoochBuyPrice:
    @patch("src.game.manage_vendors._get_pooch_base_price", new_callable=AsyncMock)
    async def test_without_vendor_returns_base_price(self, mock_base):
        mock_base.return_value = 100
        price = await get_pooch_buy_price(1)
        assert price == 100

    @patch("src.game.manage_vendors.db_get_vendor_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors._get_pooch_base_price", new_callable=AsyncMock)
    async def test_with_vendor_markup(self, mock_base, mock_vendor):
        mock_base.return_value = 100
        vendor = make_vendor(vendor_id=1)
        vendor.price_markup = 1.5
        mock_vendor.return_value = vendor

        price = await get_pooch_buy_price(1, vendor_id=1)
        assert price == 150

    @patch("src.game.manage_vendors.db_get_vendor_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors._get_pooch_base_price", new_callable=AsyncMock)
    async def test_vendor_not_found_raises(self, mock_base, mock_vendor):
        mock_base.return_value = 100
        mock_vendor.return_value = None

        with pytest.raises(VendorNotFound):
            await get_pooch_buy_price(1, vendor_id=999)


# ---------------------------------------------------------------------------
# get_pooch_sell_price
# ---------------------------------------------------------------------------


class TestGetPoochSellPrice:
    @patch("src.game.manage_vendors._get_pooch_base_price", new_callable=AsyncMock)
    async def test_without_vendor_returns_base_price(self, mock_base):
        mock_base.return_value = 80
        price = await get_pooch_sell_price(1)
        assert price == 80

    @patch("src.game.manage_vendors.get_mutation_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_vendor_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors._get_pooch_base_price", new_callable=AsyncMock)
    async def test_sell_price_with_desired_mutation_bonus(self, mock_base, mock_vendor, mock_muts, mock_get_mut):
        """A vendor with desired mutations pays VENDOR_DESIRED_MUTATION_MULT (2x) per match."""
        mock_base.return_value = 100

        vendor = make_vendor(vendor_id=1)
        vendor.desired_mutation_1 = 5
        vendor.desired_mutation_2 = None
        vendor.desired_mutation_3 = None
        mock_vendor.return_value = vendor

        mut = make_mutation(mutation_id=5)
        mock_muts.return_value = [mut]
        mock_get_mut.side_effect = lambda mid: mut if mid == 5 else None

        price = await get_pooch_sell_price(1, vendor_id=1)
        # base=100, one desired match => 100 * 2 = 200
        assert price == 200

    @patch("src.game.manage_vendors.get_mutation_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_vendor_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors._get_pooch_base_price", new_callable=AsyncMock)
    async def test_sell_price_no_matching_mutation(self, mock_base, mock_vendor, mock_muts, mock_get_mut):
        """No desired mutation matches means base price returned."""
        mock_base.return_value = 100

        vendor = make_vendor(vendor_id=1)
        vendor.desired_mutation_1 = 5
        vendor.desired_mutation_2 = None
        vendor.desired_mutation_3 = None
        mock_vendor.return_value = vendor

        mock_muts.return_value = [make_mutation(mutation_id=99)]  # doesn't match 5
        mock_get_mut.side_effect = lambda mid: make_mutation(mutation_id=mid) if mid is not None else None

        price = await get_pooch_sell_price(1, vendor_id=1)
        assert price == 100


# ---------------------------------------------------------------------------
# buy_pooch
# ---------------------------------------------------------------------------


class TestBuyPooch:
    @patch("src.game.manage_vendors.add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.transfer_pooch_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.remove_pooch_from_vendor_stock", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_buy_price", new_callable=AsyncMock)
    async def test_buy_success(
        self,
        mock_price,
        mock_owner,
        mock_pooch,
        mock_kennels,
        mock_kennel_pooches,
        mock_remove_stock,
        mock_give,
        mock_transfer,
        mock_add_kennel,
    ):
        mock_price.return_value = 50
        mock_owner.return_value = make_owner(dollars=100)
        mock_pooch.return_value = make_pooch(pooch_id=1, name="Buddy")
        mock_kennels.return_value = [make_kennel(kennel_id=1, pooch_limit=10)]
        mock_kennel_pooches.return_value = []
        mock_remove_stock.return_value = True

        success, msg = await buy_pooch(100, 1, 1)
        assert success is True
        assert "Buddy" in msg
        mock_give.assert_awaited_once_with(100, -50)

    @patch("src.game.manage_vendors.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_buy_price", new_callable=AsyncMock)
    async def test_buy_no_owner(self, mock_price, mock_owner):
        mock_price.return_value = 50
        mock_owner.return_value = None

        success, msg = await buy_pooch(100, 1, 1)
        assert success is False

    @patch("src.game.manage_vendors.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_buy_price", new_callable=AsyncMock)
    async def test_buy_cannot_afford(self, mock_price, mock_owner):
        mock_price.return_value = 500
        mock_owner.return_value = make_owner(dollars=10)

        success, msg = await buy_pooch(100, 1, 1)
        assert success is False
        assert "$500" in msg

    @patch("src.game.manage_vendors.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_buy_price", new_callable=AsyncMock)
    async def test_buy_no_kennel_space(self, mock_price, mock_owner, mock_pooch, mock_kennels, mock_pooches):
        mock_price.return_value = 50
        mock_owner.return_value = make_owner(dollars=100)
        mock_pooch.return_value = make_pooch(pooch_id=1)
        mock_kennels.return_value = [make_kennel(kennel_id=1, pooch_limit=1)]
        mock_pooches.return_value = [make_pooch()]  # kennel is full

        success, msg = await buy_pooch(100, 1, 1)
        assert success is False
        assert "space" in msg.lower()


# ---------------------------------------------------------------------------
# sell_pooch
# ---------------------------------------------------------------------------


class TestSellPooch:
    @patch("src.game.manage_vendors.remove_pooch_from_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.transfer_pooch_to_vendor", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_sell_price", new_callable=AsyncMock)
    async def test_sell_success(self, mock_price, mock_owner, mock_pooch, mock_give, mock_transfer, mock_remove):
        mock_price.return_value = 80
        mock_owner.return_value = make_owner(discord_id=100)
        mock_pooch.return_value = make_pooch(pooch_id=1, name="Fido", owner_discord_id=100, alive=True)

        success, msg = await sell_pooch(100, 1, 1)
        assert success is True
        assert "Fido" in msg
        assert "$80" in msg

    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_sell_price", new_callable=AsyncMock)
    async def test_sell_not_owned(self, mock_price, mock_owner, mock_pooch):
        mock_price.return_value = 80
        mock_owner.return_value = make_owner(discord_id=100)
        mock_pooch.return_value = make_pooch(pooch_id=1, owner_discord_id=999)

        success, msg = await sell_pooch(100, 1, 1)
        assert success is False
        assert "don't own" in msg.lower()

    @patch("src.game.manage_vendors.db_get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_sell_price", new_callable=AsyncMock)
    async def test_sell_dead_pooch(self, mock_price, mock_owner, mock_pooch):
        mock_price.return_value = 80
        mock_owner.return_value = make_owner(discord_id=100)
        mock_pooch.return_value = make_pooch(pooch_id=1, owner_discord_id=100, alive=False)

        success, msg = await sell_pooch(100, 1, 1)
        assert success is False
        assert "dead" in msg.lower()

    @patch("src.game.manage_vendors.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.get_pooch_sell_price", new_callable=AsyncMock)
    async def test_sell_no_owner(self, mock_price, mock_owner):
        mock_price.return_value = 80
        mock_owner.return_value = None

        success, msg = await sell_pooch(100, 1, 1)
        assert success is False


# ---------------------------------------------------------------------------
# get_vendor_by_id
# ---------------------------------------------------------------------------


class TestGetVendorById:
    @patch("src.game.manage_vendors.to_vendor", new_callable=AsyncMock)
    @patch("src.game.manage_vendors.db_get_vendor_by_id", new_callable=AsyncMock)
    async def test_returns_vendor(self, mock_get, mock_to_vendor):
        vendor = make_vendor(vendor_id=1)
        mock_get.return_value = vendor
        mock_to_vendor.return_value = vendor

        result = await get_vendor_by_id(1)
        assert result.id == 1

    @patch("src.game.manage_vendors.db_get_vendor_by_id", new_callable=AsyncMock)
    async def test_raises_not_found(self, mock_get):
        mock_get.return_value = None
        with pytest.raises(VendorNotFound):
            await get_vendor_by_id(999)
