"""Tests for src/game/manage_owners.py — owner management, begging, park visits."""

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_kennel, make_owner, make_pooch


@pytest.fixture(autouse=True)
def mock_owners_db_calls():
    """Auto-patch get_current_season so tests never hit the real DB."""
    with patch("src.game.manage_owners.get_current_season", new=AsyncMock(return_value="spring")):
        yield


from src.game.exceptions import OwnerNotFound
from src.game import (
    add_money,
    beg_for_money,
    cast_out_pooch,
    get_or_create_owner,
    list_owner_kennels,
    spend_bone_at_park,
    update_owner_names,
    visit_park,
)

# ---------------------------------------------------------------------------
# Helper — patch the to_owner/to_kennel converters to pass-through
# ---------------------------------------------------------------------------


def _passthrough_to_owner(owner):
    return SimpleNamespace(**{k: getattr(owner, k) for k in vars(owner) if not k.startswith("_")})


def _passthrough_to_kennel(kennel):
    return SimpleNamespace(**{k: getattr(kennel, k) for k in vars(kennel) if not k.startswith("_")})


# ---------------------------------------------------------------------------
# add_money
# ---------------------------------------------------------------------------


class TestAddMoney:
    @patch("src.game.manage_owners.to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.give_money_to_owner", new_callable=AsyncMock)
    async def test_add_money_existing_owner(self, mock_give, mock_to_owner):
        owner = make_owner(discord_id=100, dollars=100)
        mock_give.return_value = owner
        mock_to_owner.return_value = _passthrough_to_owner(owner)

        result = await add_money(200, 100, 50)
        mock_give.assert_awaited_once_with(100, 50)
        assert result.discord_id == 100

    @patch("src.game.manage_owners.to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.give_money_to_owner", new_callable=AsyncMock)
    async def test_add_money_creates_owner_if_needed(self, mock_give, mock_get_create, mock_to_owner):
        owner = make_owner(discord_id=100)
        # First call returns None (owner doesn't exist), second returns owner
        mock_give.side_effect = [None, owner]
        mock_to_owner.return_value = _passthrough_to_owner(owner)

        result = await add_money(200, 100, 50)
        mock_get_create.assert_awaited_once()
        assert result.discord_id == 100

    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.give_money_to_owner", new_callable=AsyncMock)
    async def test_add_money_raises_if_still_none(self, mock_give, mock_get_create):
        mock_give.return_value = None
        with pytest.raises(OwnerNotFound):
            await add_money(200, 100, 50)


# ---------------------------------------------------------------------------
# beg_for_money
# ---------------------------------------------------------------------------


class TestBegForMoney:
    @patch("src.game.manage_owners.set_owner_begged_today", new_callable=AsyncMock)
    @patch("src.game.manage_owners.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_successful_beg(self, mock_get_create, mock_get_owner, mock_give, mock_set_begged):
        owner = make_owner(discord_id=100, dollars=10, begged_today=False)
        mock_get_owner.return_value = owner

        rng = random.Random(42)
        amount, msg = await beg_for_money(200, 100, rng=rng)

        assert amount > 0
        assert msg is None
        mock_give.assert_awaited_once()
        mock_set_begged.assert_awaited_once()

    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_beg_already_begged_today(self, mock_get_create, mock_get_owner):
        owner = make_owner(discord_id=100, dollars=10, begged_today=True)
        mock_get_owner.return_value = owner

        amount, msg = await beg_for_money(200, 100)
        assert amount == 0
        assert "already begged" in msg

    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_beg_too_rich(self, mock_get_create, mock_get_owner):
        owner = make_owner(discord_id=100, dollars=999, begged_today=False)
        mock_get_owner.return_value = owner

        amount, msg = await beg_for_money(200, 100)
        assert amount == 0
        assert "too much money" in msg

    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_beg_owner_not_found_raises(self, mock_get_create, mock_get_owner):
        mock_get_owner.return_value = None

        with pytest.raises(OwnerNotFound):
            await beg_for_money(200, 100)

    @patch("src.game.manage_owners.set_owner_begged_today", new_callable=AsyncMock)
    @patch("src.game.manage_owners.give_money_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_beg_amount_within_range(self, mock_get_create, mock_get_owner, mock_give, mock_set_begged):
        owner = make_owner(discord_id=100, dollars=10, begged_today=False)
        mock_get_owner.return_value = owner

        amount, _ = await beg_for_money(200, 100, rng=random.Random(42))
        assert 5 <= amount <= 25  # BEG_DOLLARS_RANGE


# ---------------------------------------------------------------------------
# get_or_create_owner
# ---------------------------------------------------------------------------


class TestGetOrCreateOwner:
    @patch("src.game.manage_owners.to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_server", new_callable=AsyncMock)
    async def test_existing_owner_returned(self, mock_server, mock_get_owner, mock_to_owner):
        owner = make_owner(discord_id=100)
        mock_get_owner.return_value = owner
        mock_to_owner.return_value = _passthrough_to_owner(owner)

        # Patch get_owner_server to return something (not None) so no server join happens
        with patch("src.game.manage_owners.get_owner_server", new_callable=AsyncMock) as mock_os:
            mock_os.return_value = SimpleNamespace()
            result = await get_or_create_owner(200, 100)

        assert result.discord_id == 100

    @patch("src.game.manage_owners.to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_owners.create_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.manage_owners.create_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_owners.add_owner_to_server", new_callable=AsyncMock)
    @patch("src.game.manage_owners.create_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_server", new_callable=AsyncMock)
    async def test_new_owner_gets_kennel_and_two_pooches(
        self,
        mock_server,
        mock_get_owner,
        mock_create_owner,
        mock_add_to_server,
        mock_create_kennel,
        mock_breed_ids,
        mock_create_pooch,
        mock_add_to_kennel,
        mock_to_owner,
    ):
        mock_get_owner.return_value = None
        new_owner = make_owner(discord_id=100)
        mock_create_owner.return_value = new_owner

        kennel = make_kennel(kennel_id=1)
        mock_create_kennel.return_value = kennel
        mock_breed_ids.return_value = [1]
        mock_create_pooch.side_effect = [
            make_pooch(pooch_id=10, sex="female"),
            make_pooch(pooch_id=11, sex="male"),
        ]
        mock_to_owner.return_value = _passthrough_to_owner(new_owner)

        result = await get_or_create_owner(200, 100)

        mock_create_kennel.assert_awaited_once_with(100)
        assert mock_create_pooch.call_count == 2
        assert mock_add_to_kennel.call_count == 2
        assert result.discord_id == 100


# ---------------------------------------------------------------------------
# visit_park
# ---------------------------------------------------------------------------


class TestVisitPark:
    @patch("src.game.manage_owners.add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.transfer_pooch_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.cancel_listing_for_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_owners.remove_pooch_from_strays", new_callable=AsyncMock)
    @patch("src.game.manage_owners.count_owners_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_owners.set_owner_visited_park_today", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_visit_park_catches_stray(
        self,
        mock_get_create,
        mock_get_owner,
        mock_set_visited,
        mock_strays,
        mock_count_owners,
        mock_remove_stray,
        mock_cancel_listing,
        mock_transfer,
        mock_kennels,
        mock_kennel_pooches,
        mock_add_to_kennel,
    ):
        owner = make_owner(discord_id=100, visited_park_today=False)
        mock_get_owner.return_value = owner
        stray = make_pooch(pooch_id=50, name="Lucky")
        mock_strays.return_value = [stray] * 10  # Many strays for high catch chance
        mock_count_owners.return_value = 1

        kennel = make_kennel(kennel_id=1, pooch_limit=10)
        mock_kennels.return_value = [kennel]
        mock_kennel_pooches.return_value = []  # Empty kennel

        # Use a seeded rng that gives a low roll (high catch chance with many strays)
        caught, msg = await visit_park(200, 100, rng=random.Random(42))

        # With 10 strays / 1 owner / divisor 5 = min(2.0, 1.0) = 1.0 chance
        assert caught is True
        assert "trotted up to you" in msg

    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_visit_park_already_visited(self, mock_get_create, mock_get_owner):
        owner = make_owner(discord_id=100, visited_park_today=True)
        mock_get_owner.return_value = owner

        caught, msg = await visit_park(200, 100)
        assert caught is False
        assert "already" in msg

    @patch("src.game.manage_owners.count_owners_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_owners.set_owner_visited_park_today", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_visit_park_no_strays(
        self, mock_get_create, mock_get_owner, mock_set_visited, mock_strays, mock_count
    ):
        owner = make_owner(discord_id=100, visited_park_today=False)
        mock_get_owner.return_value = owner
        mock_strays.return_value = []

        caught, msg = await visit_park(200, 100)
        assert caught is False
        assert "no stray" in msg.lower()


# ---------------------------------------------------------------------------
# spend_bone_at_park
# ---------------------------------------------------------------------------


class TestSpendBoneAtPark:
    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_no_bones_returns_failure(self, mock_get_create, mock_get_owner):
        owner = make_owner(discord_id=100, bones=0)
        mock_get_owner.return_value = owner

        caught, msg = await spend_bone_at_park(200, 100)
        assert caught is False
        assert "bones" in msg.lower()

    @patch("src.game.manage_owners.add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.transfer_pooch_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.cancel_listing_for_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_owners.remove_pooch_from_strays", new_callable=AsyncMock)
    @patch("src.game.manage_owners.count_owners_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_strays_for_server", new_callable=AsyncMock)
    @patch("src.game.manage_owners.give_bones_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_owners.get_or_create_owner", new_callable=AsyncMock)
    async def test_spend_bone_success(
        self,
        mock_get_create,
        mock_get_owner,
        mock_give_bones,
        mock_strays,
        mock_count,
        mock_remove_stray,
        mock_cancel,
        mock_transfer,
        mock_kennels,
        mock_kennel_pooches,
        mock_add_to_kennel,
    ):
        owner = make_owner(discord_id=100, bones=1)
        mock_get_owner.return_value = owner
        stray = make_pooch(pooch_id=60, name="Boney")
        mock_strays.return_value = [stray] * 10
        mock_count.return_value = 1

        kennel = make_kennel(kennel_id=1, pooch_limit=10)
        mock_kennels.return_value = [kennel]
        mock_kennel_pooches.return_value = []

        caught, msg = await spend_bone_at_park(200, 100, rng=random.Random(42))

        mock_give_bones.assert_awaited_once_with(100, -1)
        assert caught is True


# ---------------------------------------------------------------------------
# cast_out_pooch
# ---------------------------------------------------------------------------


class TestCastOutPooch:
    @patch("src.game.manage_owners.add_pooch_to_strays", new_callable=AsyncMock)
    @patch("src.game.manage_owners.cancel_listing_for_pooch", new_callable=AsyncMock)
    async def test_cast_out_adds_to_strays(self, mock_cancel, mock_add_stray):
        await cast_out_pooch(1, 200)
        mock_add_stray.assert_awaited_once_with(1, 200)


# ---------------------------------------------------------------------------
# list_owner_kennels
# ---------------------------------------------------------------------------


class TestListOwnerKennels:
    @patch("src.game.manage_owners.to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_kennels_for_owner", new_callable=AsyncMock)
    async def test_returns_converted_kennels(self, mock_list, mock_to_kennel):
        kennels = [make_kennel(kennel_id=1), make_kennel(kennel_id=2)]
        mock_list.return_value = kennels
        mock_to_kennel.side_effect = lambda k: _passthrough_to_kennel(k)

        result = await list_owner_kennels(100)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# update_owner_names
# ---------------------------------------------------------------------------


class TestUpdateOwnerNames:
    @patch("src.game.manage_owners.update_owner_discord_name", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_owners", new_callable=AsyncMock)
    async def test_updates_changed_names(self, mock_list, mock_update):
        owner = make_owner(discord_id=100, discord_name="OldName")
        mock_list.return_value = [owner]

        count = await update_owner_names({100: "NewName"})
        assert count == 1
        mock_update.assert_awaited_once_with(100, "NewName")

    @patch("src.game.manage_owners.update_owner_discord_name", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_owners", new_callable=AsyncMock)
    async def test_skips_unchanged_names(self, mock_list, mock_update):
        owner = make_owner(discord_id=100, discord_name="SameName")
        mock_list.return_value = [owner]

        count = await update_owner_names({100: "SameName"})
        assert count == 0
        mock_update.assert_not_awaited()

    @patch("src.game.manage_owners.update_owner_discord_name", new_callable=AsyncMock)
    @patch("src.game.manage_owners.list_owners", new_callable=AsyncMock)
    async def test_skips_unknown_owners(self, mock_list, mock_update):
        mock_list.return_value = []

        count = await update_owner_names({999: "Whatever"})
        assert count == 0
