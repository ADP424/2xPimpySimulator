"""Tests for src/game/manage_hell.py — sacrifice, conjure, bloodskull values."""

from unittest.mock import AsyncMock, patch

import pytest

from src.game import (
    conjure_pooch,
    get_conjure_pooch_price,
    get_pooch_bloodskull_value,
    get_summon_pooch_price,
    sacrifice_pooch,
)
from src.game.exceptions import PoochNotFound
from tests.conftest import (
    make_breed,
    make_kennel,
    make_mutation,
    make_owner,
    make_pooch,
)


@pytest.fixture(autouse=True)
def mock_hell_db_calls():
    """Auto-patch get_current_season so tests never hit the real DB."""
    with patch("src.game.manage_hell.get_current_season", new=AsyncMock(return_value="spring")):
        yield


# ---------------------------------------------------------------------------
# get_conjure_pooch_price / get_summon_pooch_price
# ---------------------------------------------------------------------------


class TestGetConjurePoochPrice:
    def test_one_roll(self):
        # BASE_POOCH_SUMMON_PRICE (10) + BLOODSKULL_PRICE_PER_POOCH_SUMMON_ROLL (2) * 1 = 12
        assert get_conjure_pooch_price(1) == 12

    def test_five_rolls(self):
        assert get_conjure_pooch_price(5) == 10 + 2 * 5

    def test_minimum_one_roll(self):
        """Passing 0 rolls is clamped to max(0, 1) = 1."""
        assert get_conjure_pooch_price(0) == 10 + 2 * 1

    def test_negative_rolls_clamped(self):
        assert get_conjure_pooch_price(-5) == 10 + 2 * 1

    def test_alias(self):
        """get_summon_pooch_price is an alias for get_conjure_pooch_price."""
        assert get_summon_pooch_price(3) == get_conjure_pooch_price(3)


# ---------------------------------------------------------------------------
# get_pooch_bloodskull_value
# ---------------------------------------------------------------------------


class TestGetPoochBloodskullValue:
    @patch("src.game.manage_hell.list_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_by_id", new_callable=AsyncMock)
    async def test_base_value_healthy_pooch(self, mock_get, mock_health, mock_muts, mock_breeds):
        """Base value = 8, healthy pooch with average health and uncommon breed."""
        mock_get.return_value = make_pooch(pooch_id=1)
        mock_health.return_value = 10
        mock_muts.return_value = []
        breed = make_breed(breed_id=1, rarity="uncommon")  # mult = 1.0
        mock_breeds.return_value = [(breed, 1)]

        value = await get_pooch_bloodskull_value(1)
        assert isinstance(value, int)
        assert value > 0

    @patch("src.game.manage_hell.get_pooch_by_id", new_callable=AsyncMock)
    async def test_pooch_not_found_raises(self, mock_get):
        mock_get.return_value = None
        with pytest.raises(PoochNotFound):
            await get_pooch_bloodskull_value(999)

    @patch("src.game.manage_hell.list_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_by_id", new_callable=AsyncMock)
    async def test_mutation_bloodskull_add(self, mock_get, mock_health, mock_muts, mock_breeds):
        """Mutations with bloodskull_value_add increase value."""
        mock_get.return_value = make_pooch(pooch_id=1)
        mock_health.return_value = 10
        breed = make_breed(breed_id=1, rarity="uncommon")
        mock_breeds.return_value = [(breed, 1)]

        mut = make_mutation(mutation_id=1, parameters={"bloodskull_value_add": 10.0})
        mock_muts.return_value = [mut]
        value_with = await get_pooch_bloodskull_value(1)

        mock_muts.return_value = []
        value_without = await get_pooch_bloodskull_value(1)

        assert value_with > value_without

    @patch("src.game.manage_hell.list_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_by_id", new_callable=AsyncMock)
    async def test_rare_breed_increases_value(self, mock_get, mock_health, mock_muts, mock_breeds):
        """Rare breeds multiply the bloodskull value more than common ones."""
        mock_get.return_value = make_pooch(pooch_id=1)
        mock_health.return_value = 10
        mock_muts.return_value = []

        common_breed = make_breed(breed_id=1, rarity="common")  # 0.5
        mock_breeds.return_value = [(common_breed, 1)]
        common_value = await get_pooch_bloodskull_value(1)

        rare_breed = make_breed(breed_id=2, rarity="extraordinary")  # 4.0
        mock_breeds.return_value = [(rare_breed, 1)]
        rare_value = await get_pooch_bloodskull_value(1)

        assert rare_value > common_value

    @patch("src.game.manage_hell.list_pooch_breeds", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_pooch_mutations", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_health", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_by_id", new_callable=AsyncMock)
    async def test_value_never_negative(self, mock_get, mock_health, mock_muts, mock_breeds):
        """Even with very low health and penalties, value should be >= 0."""
        mock_get.return_value = make_pooch(pooch_id=1)
        mock_health.return_value = -100
        mock_muts.return_value = [make_mutation(mutation_id=1, parameters={"bloodskull_value_add": -1000.0})]
        mock_breeds.return_value = [(make_breed(rarity="common"), 1)]

        value = await get_pooch_bloodskull_value(1)
        assert value >= 0


# ---------------------------------------------------------------------------
# sacrifice_pooch
# ---------------------------------------------------------------------------


class TestSacrificePooch:
    @patch("src.game.manage_hell.damn_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.remove_pooch_from_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_hell.set_pooch_dead", new_callable=AsyncMock)
    @patch("src.game.manage_hell.give_bones_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_hell.give_bloodskulls_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_bloodskull_value", new_callable=AsyncMock)
    async def test_sacrifice_success(
        self,
        mock_value,
        mock_owner,
        mock_pooch,
        mock_bloodskulls,
        mock_bones,
        mock_kill,
        mock_remove,
        mock_damn,
    ):
        mock_value.return_value = 15
        mock_owner.return_value = make_owner(discord_id=100)
        mock_pooch.return_value = make_pooch(pooch_id=1, name="Fido", owner_discord_id=100, alive=True)

        success, msg = await sacrifice_pooch(100, 1)

        assert success is True
        assert "15 bloodskulls" in msg
        mock_bloodskulls.assert_awaited_once_with(100, 15)
        mock_bones.assert_awaited_once_with(100, 1)
        mock_kill.assert_awaited_once_with(1)
        mock_damn.assert_awaited_once_with(1)

    @patch("src.game.manage_hell.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_bloodskull_value", new_callable=AsyncMock)
    async def test_sacrifice_not_owned(self, mock_value, mock_owner, mock_pooch):
        mock_value.return_value = 10
        mock_owner.return_value = make_owner(discord_id=100)
        mock_pooch.return_value = make_pooch(pooch_id=1, owner_discord_id=999)

        success, msg = await sacrifice_pooch(100, 1)
        assert success is False

    @patch("src.game.manage_hell.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_bloodskull_value", new_callable=AsyncMock)
    async def test_sacrifice_dead_pooch(self, mock_value, mock_owner, mock_pooch):
        mock_value.return_value = 10
        mock_owner.return_value = make_owner(discord_id=100)
        mock_pooch.return_value = make_pooch(pooch_id=1, owner_discord_id=100, alive=False)

        success, msg = await sacrifice_pooch(100, 1)
        assert success is False
        assert "dead" in msg.lower()

    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_bloodskull_value", new_callable=AsyncMock)
    async def test_sacrifice_no_owner(self, mock_value, mock_owner):
        mock_value.return_value = 10
        mock_owner.return_value = None

        success, msg = await sacrifice_pooch(100, 1)
        assert success is False


# ---------------------------------------------------------------------------
# conjure_pooch
# ---------------------------------------------------------------------------


class TestConjurePooch:
    @patch("src.game.manage_hell.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_mutation_by_name", new_callable=AsyncMock)
    @patch("src.game.manage_hell.add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_hell.give_bloodskulls_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_bloodskull_value", new_callable=AsyncMock)
    @patch("src.game.manage_hell.delete_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.create_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_conjure_single_roll_success(
        self,
        mock_owner,
        mock_kennels,
        mock_kennel_pooches,
        mock_breed_ids,
        mock_create,
        mock_delete,
        mock_value,
        mock_bloodskulls,
        mock_add_kennel,
        mock_mark,
        mock_add_mut,
    ):
        mock_owner.return_value = make_owner(discord_id=100, bloodskulls=50)
        mock_kennels.return_value = [make_kennel(kennel_id=1, pooch_limit=10)]
        mock_kennel_pooches.return_value = []
        mock_breed_ids.return_value = [1]
        conjured = make_pooch(pooch_id=99, name="Hellhound")
        mock_create.return_value = conjured
        mock_value.return_value = 20
        mark = make_mutation(mutation_id=666, name="Mark of the Beast")
        mock_mark.return_value = mark

        success, msg = await conjure_pooch(100, num_rolls=1, rng_seed=42)

        assert success is True
        assert "Hellhound" in msg
        mock_bloodskulls.assert_awaited_once_with(100, -12)  # price = 10 + 2*1 = 12
        mock_add_mut.assert_awaited_once_with(99, mutation_id=666)

    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_conjure_zero_rolls_returns_error(self, mock_owner):
        success, msg = await conjure_pooch(100, num_rolls=0)
        assert success is False
        assert "at least 1" in msg

    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_conjure_cannot_afford(self, mock_owner):
        mock_owner.return_value = make_owner(discord_id=100, bloodskulls=0)

        success, msg = await conjure_pooch(100, num_rolls=1, rng_seed=42)
        assert success is False
        assert "bloodskulls" in msg

    @patch("src.game.manage_hell.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_conjure_no_kennel_space(self, mock_owner, mock_kennels, mock_kennel_pooches):
        mock_owner.return_value = make_owner(discord_id=100, bloodskulls=100)
        mock_kennels.return_value = [make_kennel(kennel_id=1, pooch_limit=1)]
        mock_kennel_pooches.return_value = [make_pooch()]  # full

        success, msg = await conjure_pooch(100, num_rolls=1, rng_seed=42)
        assert success is False
        assert "space" in msg.lower()

    @patch("src.game.manage_hell.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_mutation_by_name", new_callable=AsyncMock)
    @patch("src.game.manage_hell.add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_hell.give_bloodskulls_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_bloodskull_value", new_callable=AsyncMock)
    @patch("src.game.manage_hell.delete_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.create_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_conjure_multi_roll_keeps_best(
        self,
        mock_owner,
        mock_kennels,
        mock_kennel_pooches,
        mock_breed_ids,
        mock_create,
        mock_delete,
        mock_value,
        mock_bloodskulls,
        mock_add_kennel,
        mock_mark,
        mock_add_mut,
    ):
        """With multiple rolls, the highest-value pooch is kept, others deleted."""
        mock_owner.return_value = make_owner(discord_id=100, bloodskulls=100)
        mock_kennels.return_value = [make_kennel(kennel_id=1, pooch_limit=10)]
        mock_kennel_pooches.return_value = []
        mock_breed_ids.return_value = [1]

        pooch_a = make_pooch(pooch_id=10, name="Weak")
        pooch_b = make_pooch(pooch_id=11, name="Strong")
        mock_create.side_effect = [pooch_a, pooch_b]

        # First pooch is worth 5, second is worth 20
        mock_value.side_effect = lambda pid: 5 if pid == 10 else 20

        mock_mark.return_value = make_mutation(mutation_id=666)

        success, msg = await conjure_pooch(100, num_rolls=2, rng_seed=42)

        assert success is True
        # The weak pooch (id=10) should have been deleted
        mock_delete.assert_awaited_once_with(10)

    @patch("src.game.manage_hell.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_mutation_by_name", new_callable=AsyncMock)
    @patch("src.game.manage_hell.add_pooch_to_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_hell.give_bloodskulls_to_owner", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_pooch_bloodskull_value", new_callable=AsyncMock)
    @patch("src.game.manage_hell.delete_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.create_pooch", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_random_breed_ids", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_pooches_for_kennel", new_callable=AsyncMock)
    @patch("src.game.manage_hell.list_kennels_for_owner", new_callable=AsyncMock)
    @patch("src.game.manage_hell.get_owner_by_discord_id", new_callable=AsyncMock)
    async def test_conjure_no_mark_of_beast_gracefully(
        self,
        mock_owner,
        mock_kennels,
        mock_kennel_pooches,
        mock_breed_ids,
        mock_create,
        mock_delete,
        mock_value,
        mock_bloodskulls,
        mock_add_kennel,
        mock_mark,
        mock_add_mut,
    ):
        """If Mark of the Beast mutation doesn't exist, conjure still succeeds."""
        mock_owner.return_value = make_owner(discord_id=100, bloodskulls=50)
        mock_kennels.return_value = [make_kennel(kennel_id=1, pooch_limit=10)]
        mock_kennel_pooches.return_value = []
        mock_breed_ids.return_value = [1]
        mock_create.return_value = make_pooch(pooch_id=99, name="NoBrand")
        mock_value.return_value = 10
        mock_mark.return_value = None  # Mutation doesn't exist

        success, msg = await conjure_pooch(100, num_rolls=1, rng_seed=42)

        assert success is True
        mock_add_mut.assert_not_awaited()
