"""Tests for src/game/manage_items.py and src/game/access.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.game.access import owns_kennel, owns_pooch
from src.game.manage_items import (
    buy_item,
    feed_kennel,
    get_item_price,
    list_vendor_items,
)

ITEMS = "src.game.manage_items"


def _item(name="Soap", category="cleaning", **parameters):
    return SimpleNamespace(name=name, category=category, parameters=parameters)


class TestBuyItem:
    async def test_charges_and_gives_items(self):
        with (
            patch(f"{ITEMS}.get_item_by_name", new=AsyncMock(return_value=_item(price=15))),
            patch(f"{ITEMS}.get_owner_by_discord_id", new=AsyncMock(return_value=SimpleNamespace(dollars=100))),
            patch(f"{ITEMS}.give_money_to_owner", new=AsyncMock()) as give_money,
            patch(f"{ITEMS}.give_owner_item", new=AsyncMock()) as give_item,
        ):
            ok, message = await buy_item(1, "Soap", 2)
        assert ok is True
        assert message == "Purchased **2x Soap** for **$30**."
        give_money.assert_awaited_once_with(1, -30)
        give_item.assert_awaited_once_with(1, "Soap", 2)

    async def test_too_poor_is_not_charged(self):
        with (
            patch(f"{ITEMS}.get_item_by_name", new=AsyncMock(return_value=_item(price=15))),
            patch(f"{ITEMS}.get_owner_by_discord_id", new=AsyncMock(return_value=SimpleNamespace(dollars=10))),
            patch(f"{ITEMS}.give_money_to_owner", new=AsyncMock()) as give_money,
        ):
            ok, message = await buy_item(1, "Soap")
        assert ok is False
        assert "Not enough money" in message
        give_money.assert_not_awaited()

    async def test_unknown_or_unsold_item(self):
        with patch(f"{ITEMS}.get_item_by_name", new=AsyncMock(return_value=_item(category="relic"))):
            assert (await buy_item(1, "Skull"))[0] is False
        with patch(f"{ITEMS}.get_item_by_name", new=AsyncMock(return_value=None)):
            assert (await buy_item(1, "Nope"))[0] is False

    async def test_rejects_zero_count(self):
        assert await buy_item(1, "Soap", 0) == (False, "You must buy at least one.")


class TestFeedKennel:
    def _patches(self, kennel_owner=1, item=None, consumed=True):
        return (
            patch(
                f"{ITEMS}.get_kennel_by_id", new=AsyncMock(return_value=SimpleNamespace(owner_discord_id=kennel_owner))
            ),
            patch(
                f"{ITEMS}.get_item_by_name", new=AsyncMock(return_value=item or _item("Kibble", "food", food_units=4))
            ),
            patch(f"{ITEMS}.consume_owner_item", new=AsyncMock(return_value=consumed)),
            patch(f"{ITEMS}.modify_kennel_food_stock", new=AsyncMock(return_value=20)),
        )

    async def test_adds_food_units(self):
        kennel, item, consume, stock = self._patches()
        with kennel, item, consume as consume_mock, stock as stock_mock:
            ok, message, new_stock = await feed_kennel(1, 5, "Kibble", 3)
        assert (ok, new_stock) == (True, 20)
        assert "+12 food units" in message
        consume_mock.assert_awaited_once_with(1, "Kibble", 3)
        stock_mock.assert_awaited_once_with(5, 12)

    async def test_someone_elses_kennel_uses_nothing(self):
        kennel, item, consume, stock = self._patches(kennel_owner=2)
        with kennel, item, consume as consume_mock, stock:
            assert await feed_kennel(1, 5, "Kibble") == (False, "That's not your kennel.", None)
        consume_mock.assert_not_awaited()

    async def test_non_food_is_rejected(self):
        kennel, item, consume, stock = self._patches(item=_item("Soap", "cleaning"))
        with kennel, item, consume as consume_mock, stock:
            assert await feed_kennel(1, 5, "Soap") == (False, "That item is not food.", None)
        consume_mock.assert_not_awaited()

    async def test_not_owned(self):
        kennel, item, consume, stock = self._patches(consumed=False)
        with kennel, item, consume, stock as stock_mock:
            ok, message, _ = await feed_kennel(1, 5, "Kibble", 2)
        assert ok is False
        assert message == "You don't own 2x Kibble."
        stock_mock.assert_not_awaited()


async def test_list_vendor_items_is_cleaning_then_food():
    by_category = {"cleaning": [_item("Soap")], "food": [_item("Kibble", "food")]}
    with patch(f"{ITEMS}.list_items_by_category", new=AsyncMock(side_effect=lambda c: by_category[c])):
        assert [i.name for i in await list_vendor_items()] == ["Soap", "Kibble"]


def test_item_price_defaults_to_ten():
    assert get_item_price(_item()) == 10
    assert get_item_price(SimpleNamespace(parameters=None)) == 10


class TestAccess:
    async def test_owns_pooch(self):
        with patch("src.game.access.get_pooch_by_id", new=AsyncMock(return_value=SimpleNamespace(owner_discord_id=1))):
            assert await owns_pooch(1, 9) is True
            assert await owns_pooch(2, 9) is False
        with patch("src.game.access.get_pooch_by_id", new=AsyncMock(return_value=None)):
            assert await owns_pooch(1, 9) is None

    async def test_owns_kennel(self):
        with patch("src.game.access.get_kennel_by_id", new=AsyncMock(return_value=SimpleNamespace(owner_discord_id=1))):
            assert await owns_kennel(1, 9) is True
            assert await owns_kennel(2, 9) is False
        with patch("src.game.access.get_kennel_by_id", new=AsyncMock(return_value=None)):
            assert await owns_kennel(1, 9) is None


class TestFoodStatBonus:
    def _patches(self, pooches, stat_fn):
        steak = _item("Steak", "food", food_units=60, strength_add=1)
        return (
            patch(f"{ITEMS}.get_kennel_by_id", new=AsyncMock(return_value=SimpleNamespace(owner_discord_id=1))),
            patch(f"{ITEMS}.get_item_by_name", new=AsyncMock(return_value=steak)),
            patch(f"{ITEMS}.consume_owner_item", new=AsyncMock(return_value=True)),
            patch(f"{ITEMS}.modify_kennel_food_stock", new=AsyncMock(return_value=60)),
            patch(f"{ITEMS}.list_pooches_for_kennel", new=AsyncMock(return_value=pooches)),
            patch(f"{ITEMS}.modify_pooch_stat", new=stat_fn),
        )

    async def test_lucky_rolls_grant_bonus_once_per_pooch(self):
        rex = SimpleNamespace(id=1, name="Rex", alive=True)
        ghost = SimpleNamespace(id=2, name="Ghost", alive=False)
        stat = AsyncMock()
        rng = SimpleNamespace(random=lambda: 0.0)  # every roll succeeds
        a, b, c, d, e, f = self._patches([rex, ghost], stat)
        with a, b, c, d, e, f:
            ok, message, _ = await feed_kennel(1, 5, "Steak", count=3, rng=rng)
        assert ok is True
        stat.assert_awaited_once_with(1, "strength", 1)
        assert message.endswith("Rex thrived on the Steak!")

    async def test_unlucky_rolls_grant_nothing(self):
        stat = AsyncMock()
        rng = SimpleNamespace(random=lambda: 0.99)
        a, b, c, d, e, f = self._patches([SimpleNamespace(id=1, name="Rex", alive=True)], stat)
        with a, b, c, d, e, f:
            _, message, _ = await feed_kennel(1, 5, "Steak", rng=rng)
        stat.assert_not_awaited()
        assert "thrived" not in message
