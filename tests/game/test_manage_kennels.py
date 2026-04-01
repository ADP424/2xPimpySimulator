"""Tests for src/game/manage_kennels.py — kennel CRUD, pricing, and upgrades."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game import (
    add_pooch_to_kennel,
    buy_kennel,
    get_kennel_buy_price,
    get_kennel_upgrade_price,
    list_kennel_pooches,
    rename_kennel,
    upgrade_kennel,
)
from src.game.exceptions import KennelNotFound, PoochNotFound
from tests.conftest import make_kennel, make_owner, make_pooch

# ---------------------------------------------------------------------------
# add_pooch_to_kennel
# ---------------------------------------------------------------------------


class TestAddPoochToKennel:
    @patch("src.game.manage_kennels.db_add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.list_kennel_pooches", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_add_pooch_success(self, mock_get_kennel, mock_get_pooch, mock_list, mock_db_add):
        mock_get_kennel.return_value = make_kennel(pooch_limit=5)
        mock_get_pooch.return_value = make_pooch(pooch_id=1)
        mock_list.return_value = [make_pooch(pooch_id=2)]  # 1 of 5 slots used

        await add_pooch_to_kennel(1, 1)
        # The function doesn't explicitly return True, it calls db_add_pooch_to_kennel
        mock_db_add.assert_awaited_once()

    @patch("src.game.manage_kennels.list_kennel_pooches", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_add_pooch_kennel_full(self, mock_get_kennel, mock_get_pooch, mock_list):
        mock_get_kennel.return_value = make_kennel(pooch_limit=2)
        mock_get_pooch.return_value = make_pooch(pooch_id=1)
        mock_list.return_value = [make_pooch(pooch_id=2), make_pooch(pooch_id=3)]  # 2/2 full

        result = await add_pooch_to_kennel(1, 1)
        assert result is False

    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_add_pooch_kennel_not_found(self, mock_get_kennel):
        mock_get_kennel.return_value = None
        with pytest.raises(KennelNotFound):
            await add_pooch_to_kennel(999, 1)

    @patch("src.game.manage_kennels.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_add_pooch_pooch_not_found(self, mock_get_kennel, mock_get_pooch):
        mock_get_kennel.return_value = make_kennel()
        mock_get_pooch.return_value = None
        with pytest.raises(PoochNotFound):
            await add_pooch_to_kennel(1, 999)


# ---------------------------------------------------------------------------
# list_kennel_pooches
# ---------------------------------------------------------------------------


class TestListKennelPooches:
    @patch("src.game.manage_kennels.to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_returns_pooch_list(self, mock_get_kennel, mock_list, mock_to_pooch):
        mock_get_kennel.return_value = make_kennel()
        pooches = [make_pooch(pooch_id=1), make_pooch(pooch_id=2)]
        mock_list.return_value = pooches
        mock_to_pooch.side_effect = lambda p: p

        result = await list_kennel_pooches(1)
        assert len(result) == 2

    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_kennel_not_found_raises(self, mock_get_kennel):
        mock_get_kennel.return_value = None
        with pytest.raises(KennelNotFound):
            await list_kennel_pooches(999)


# ---------------------------------------------------------------------------
# rename_kennel
# ---------------------------------------------------------------------------


class TestRenameKennel:
    @patch("src.game.manage_kennels.db_rename_kennel", new_callable=AsyncMock)
    async def test_rename_success(self, mock_rename):
        mock_rename.return_value = make_kennel(name="New Name")
        result = await rename_kennel(1, "New Name")
        assert result is True

    async def test_name_too_long_returns_false(self):
        # MAX_NAME_LENGTH = 100
        long_name = "A" * 101
        result = await rename_kennel(1, long_name)
        assert result is False

    @patch("src.game.manage_kennels.db_rename_kennel", new_callable=AsyncMock)
    async def test_kennel_not_found_raises(self, mock_rename):
        mock_rename.return_value = None
        with pytest.raises(KennelNotFound):
            await rename_kennel(999, "Valid")

    @patch("src.game.manage_kennels.db_rename_kennel", new_callable=AsyncMock)
    async def test_name_stripped(self, mock_rename):
        mock_rename.return_value = make_kennel(name="Trimmed")
        await rename_kennel(1, "  Trimmed  ")
        mock_rename.assert_awaited_once_with(1, "Trimmed")


# ---------------------------------------------------------------------------
# get_kennel_buy_price
# ---------------------------------------------------------------------------


class TestGetKennelBuyPrice:
    @patch("src.game.manage_kennels.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_first_kennel_base_price(self, mock_list):
        """With 0 kennels, price = max(KENNEL_BASE_PRICE, KENNEL_BASE_PRICE*0) = KENNEL_BASE_PRICE (250)."""
        mock_list.return_value = []
        from src.game.constants import KENNEL_BASE_PRICE

        price, msg = await get_kennel_buy_price(100)
        assert price == KENNEL_BASE_PRICE

    @patch("src.game.manage_kennels.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_price_scales_with_count(self, mock_list):
        """With 2 kennels, price = 250 * 2 = 500."""
        mock_list.return_value = [make_kennel(kennel_id=i) for i in range(2)]
        price, msg = await get_kennel_buy_price(100)
        assert price == 500

    @patch("src.game.manage_kennels.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_max_kennels_returns_none(self, mock_list):
        """At MAX_KENNELS (5), price is None."""
        mock_list.return_value = [make_kennel(kennel_id=i) for i in range(5)]
        price, msg = await get_kennel_buy_price(100)
        assert price is None
        assert "Maximum" in msg


# ---------------------------------------------------------------------------
# get_kennel_upgrade_price
# ---------------------------------------------------------------------------


class TestGetKennelUpgradePrice:
    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_first_upgrade_price(self, mock_get):
        """Base capacity=10, first upgrade costs KENNEL_UPGRADE_PRICES[0] = 200."""
        mock_get.return_value = make_kennel(pooch_limit=10)
        price, msg = await get_kennel_upgrade_price(1)
        assert price == 200

    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_second_upgrade_price(self, mock_get):
        """After 1 upgrade: limit=15, upgrades_done=1, price = KENNEL_UPGRADE_PRICES[1] = 400."""
        mock_get.return_value = make_kennel(pooch_limit=15)
        price, msg = await get_kennel_upgrade_price(1)
        assert price == 400

    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_max_upgrade_returns_none(self, mock_get):
        """After 3 upgrades: limit=25, upgrades_done=3 >= len(prices)=3, returns None."""
        mock_get.return_value = make_kennel(pooch_limit=25)
        price, msg = await get_kennel_upgrade_price(1)
        assert price is None
        assert "Max" in msg

    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    async def test_kennel_not_found(self, mock_get):
        mock_get.return_value = None
        price, msg = await get_kennel_upgrade_price(999)
        assert price is None
        assert "not found" in msg.lower()


# ---------------------------------------------------------------------------
# buy_kennel
# ---------------------------------------------------------------------------


class TestBuyKennel:
    @patch("src.game.manage_kennels.to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.create_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_buy_success(self, mock_get_owner, mock_list_kennels, mock_give, mock_create, mock_to_kennel):
        mock_get_owner.return_value = make_owner(dollars=500)
        mock_list_kennels.return_value = [make_kennel()]  # 1 kennel, price = 250 * 1 = 250
        mock_create.return_value = make_kennel(kennel_id=2, name="New Kennel")
        mock_to_kennel.return_value = SimpleNamespace(name="New Kennel")

        success, msg = await buy_kennel(100)
        assert success is True
        assert "New Kennel" in msg
        mock_give.assert_awaited_once_with(100, -250)

    @patch("src.game.manage_kennels.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_buy_at_max_kennels(self, mock_get_owner, mock_list_kennels):
        mock_get_owner.return_value = make_owner(dollars=9999)
        mock_list_kennels.return_value = [make_kennel(kennel_id=i) for i in range(5)]

        success, msg = await buy_kennel(100)
        assert success is False
        assert "maximum" in msg.lower()

    @patch("src.game.manage_kennels.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_buy_cannot_afford(self, mock_get_owner, mock_list_kennels):
        mock_get_owner.return_value = make_owner(dollars=10)
        mock_list_kennels.return_value = [make_kennel()]  # price = 250

        success, msg = await buy_kennel(100)
        assert success is False
        assert "$250" in msg

    @patch("src.game.manage_kennels.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_buy_no_owner(self, mock_get_owner):
        mock_get_owner.return_value = None
        success, msg = await buy_kennel(100)
        assert success is False
        assert "home" in msg.lower()


# ---------------------------------------------------------------------------
# upgrade_kennel
# ---------------------------------------------------------------------------


class TestUpgradeKennel:
    @patch("src.game.manage_kennels.modify_kennel_pooch_limit", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_upgrade_success(self, mock_get_owner, mock_get_kennel, mock_give, mock_modify):
        mock_get_owner.return_value = make_owner(discord_id=100, dollars=500)
        mock_get_kennel.return_value = make_kennel(kennel_id=1, pooch_limit=10, owner_discord_id=100)

        success, msg = await upgrade_kennel(100, 1)
        assert success is True
        assert "15" in msg  # new capacity
        mock_give.assert_awaited_once_with(100, -200)
        mock_modify.assert_awaited_once_with(1, 5)

    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_upgrade_max_tier(self, mock_get_owner, mock_get_kennel):
        mock_get_owner.return_value = make_owner(discord_id=100, dollars=9999)
        mock_get_kennel.return_value = make_kennel(kennel_id=1, pooch_limit=25, owner_discord_id=100)

        result, msg = await upgrade_kennel(100, 1)
        assert result is None
        assert "Max" in msg

    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_upgrade_cannot_afford(self, mock_get_owner, mock_get_kennel):
        mock_get_owner.return_value = make_owner(discord_id=100, dollars=10)
        mock_get_kennel.return_value = make_kennel(kennel_id=1, pooch_limit=10, owner_discord_id=100)

        success, msg = await upgrade_kennel(100, 1)
        assert success is False
        assert "$200" in msg

    @patch("src.game.manage_kennels.get_kennel_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_kennels.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_upgrade_wrong_owner(self, mock_get_owner, mock_get_kennel):
        mock_get_owner.return_value = make_owner(discord_id=100)
        mock_get_kennel.return_value = make_kennel(kennel_id=1, owner_discord_id=999)

        success, msg = await upgrade_kennel(100, 1)
        assert success is False
        assert "don't own" in msg.lower()
