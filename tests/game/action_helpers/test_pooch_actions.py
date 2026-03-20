import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.action_helpers.pooch_actions import (
    handle_add_breed,
    handle_add_mutation,
    handle_add_mutation_by_name,
    handle_damn_pooch,
    handle_kill_pooch,
    handle_modify_age,
    handle_modify_breeding_cooldown,
    handle_modify_health,
    handle_modify_stat,
    handle_remove_breed,
    handle_remove_mutation,
    handle_remove_mutation_by_name,
    handle_rename_pooch,
    handle_select_pooch,
)


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


def _make_result():
    """Create a minimal result-like object with the attributes used by handlers."""
    return SimpleNamespace(
        pooches_affected=[],
        pooches_killed=[],
        pooches_created=[],
        mutations_added=[],
        mutations_removed=[],
        message="",
        extra_data={},
    )


# ===========================================================================
# handle_modify_health
# ===========================================================================


class TestHandleModifyHealth:
    @patch("src.game.action_helpers.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    async def test_modify_mode(self, mock_modify, rng):
        mock_modify.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_health([1], {"amount": 5}, rng, result)
        mock_modify.assert_awaited_once_with(1, 5)
        assert result.pooches_affected == [1]
        assert result.extra_data["health_changes"][1] == 5

    @patch("src.game.action_helpers.pooch_actions.set_pooch_base_health", new_callable=AsyncMock)
    async def test_set_mode(self, mock_set, rng):
        mock_set.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_health([1], {"amount": 20, "mode": "set"}, rng, result)
        mock_set.assert_awaited_once_with(1, 20)
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    async def test_no_pooch_returned(self, mock_modify, rng):
        mock_modify.return_value = None
        result = _make_result()
        await handle_modify_health([1], {"amount": 5}, rng, result)
        assert result.pooches_affected == []

    @patch("src.game.action_helpers.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    async def test_multiple_pooches(self, mock_modify, rng):
        mock_modify.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_health([1, 2, 3], {"amount": 2}, rng, result)
        assert mock_modify.await_count == 3
        assert len(result.pooches_affected) == 3

    @patch("src.game.action_helpers.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    async def test_roll_once(self, mock_modify, rng):
        mock_modify.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_health([1, 2], {"min_amount": 1, "max_amount": 100, "roll_once": True}, rng, result)
        # Both calls should use the same pre-rolled amount
        call1_amount = mock_modify.call_args_list[0][0][1]
        call2_amount = mock_modify.call_args_list[1][0][1]
        assert call1_amount == call2_amount


# ===========================================================================
# handle_modify_age
# ===========================================================================


class TestHandleModifyAge:
    @patch("src.game.action_helpers.pooch_actions.modify_pooch_age", new_callable=AsyncMock)
    async def test_modify_mode(self, mock_modify, rng):
        mock_modify.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_age([1], {"amount": 3}, rng, result)
        mock_modify.assert_awaited_once_with(1, 3)
        assert result.pooches_affected == [1]
        assert result.extra_data["age_changes"][1] == 3

    @patch("src.game.action_helpers.pooch_actions.set_pooch_age", new_callable=AsyncMock)
    async def test_set_mode(self, mock_set, rng):
        mock_set.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_age([1], {"amount": 5, "mode": "set"}, rng, result)
        mock_set.assert_awaited_once_with(1, 5)

    @patch("src.game.action_helpers.pooch_actions.modify_pooch_age", new_callable=AsyncMock)
    async def test_no_pooch_returned(self, mock_modify, rng):
        mock_modify.return_value = None
        result = _make_result()
        await handle_modify_age([1], {"amount": 1}, rng, result)
        assert result.pooches_affected == []


# ===========================================================================
# handle_kill_pooch
# ===========================================================================


class TestHandleKillPooch:
    @patch("src.game.action_helpers.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_single_kill(self, mock_kill, rng):
        mock_kill.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_kill_pooch([1], {}, rng, result)
        mock_kill.assert_awaited_once_with(1)
        assert result.pooches_killed == [1]
        assert result.message == "A pooch has died!"

    @patch("src.game.action_helpers.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_multiple_kills(self, mock_kill, rng):
        mock_kill.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_kill_pooch([1, 2, 3], {}, rng, result)
        assert len(result.pooches_killed) == 3
        assert result.message == "3 pooches have died!"

    @patch("src.game.action_helpers.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_kill_returns_none(self, mock_kill, rng):
        mock_kill.return_value = None
        result = _make_result()
        await handle_kill_pooch([1], {}, rng, result)
        assert result.pooches_killed == []
        assert result.message == ""


# ===========================================================================
# handle_add_mutation
# ===========================================================================


class TestHandleAddMutation:
    @patch("src.game.action_helpers.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    async def test_with_mutation_id(self, mock_add, rng):
        result = _make_result()
        await handle_add_mutation([1], {"mutation_id": 10}, rng, result)
        mock_add.assert_awaited_once_with(1, 10)
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    async def test_without_mutation_id_random(self, mock_add, rng):
        result = _make_result()
        await handle_add_mutation([1], {"min_rarity": "common", "max_rarity": "rare"}, rng, result)
        mock_add.assert_awaited_once()
        kwargs = mock_add.call_args
        assert kwargs[1]["min_rarity"] == "common"
        assert kwargs[1]["max_rarity"] == "rare"


# ===========================================================================
# handle_add_mutation_by_name
# ===========================================================================


class TestHandleAddMutationByName:
    @patch("src.game.action_helpers.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.action_helpers.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_with_name(self, mock_get, mock_add, rng):
        mock_get.return_value = SimpleNamespace(id=5)
        result = _make_result()
        await handle_add_mutation_by_name([1], {"mutation": "Cataracts"}, rng, result)
        mock_get.assert_awaited_once_with("Cataracts")
        mock_add.assert_awaited_once_with(1, 5)
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.action_helpers.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_name_not_found(self, mock_get, mock_add, rng):
        mock_get.return_value = None
        result = _make_result()
        await handle_add_mutation_by_name([1], {"mutation": "NonExistent"}, rng, result)
        mock_add.assert_not_awaited()
        # Pooch is still marked as affected
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    async def test_with_mutation_id(self, mock_add, rng):
        result = _make_result()
        await handle_add_mutation_by_name([1], {"mutation_id": 7}, rng, result)
        mock_add.assert_awaited_once_with(1, 7)


# ===========================================================================
# handle_remove_mutation
# ===========================================================================


class TestHandleRemoveMutation:
    @patch("src.game.action_helpers.pooch_actions.remove_mutation_from_pooch", new_callable=AsyncMock)
    async def test_with_mutation_id(self, mock_remove, rng):
        mock_remove.return_value = SimpleNamespace(mutation_id=10)
        result = _make_result()
        await handle_remove_mutation([1], {"mutation_id": 10}, rng, result)
        mock_remove.assert_awaited_once_with(1, 10)
        assert result.mutations_removed == [(1, 10)]
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.remove_random_mutation_from_pooch", new_callable=AsyncMock)
    async def test_random_removal(self, mock_remove, rng):
        mock_remove.return_value = SimpleNamespace(mutation_id=20)
        result = _make_result()
        await handle_remove_mutation([1], {}, rng, result)
        mock_remove.assert_awaited_once()
        assert result.mutations_removed == [(1, 20)]

    @patch("src.game.action_helpers.pooch_actions.remove_mutation_from_pooch", new_callable=AsyncMock)
    async def test_removal_returns_none(self, mock_remove, rng):
        mock_remove.return_value = None
        result = _make_result()
        await handle_remove_mutation([1], {"mutation_id": 10}, rng, result)
        assert result.mutations_removed == []
        assert result.pooches_affected == []


# ===========================================================================
# handle_remove_mutation_by_name
# ===========================================================================


class TestHandleRemoveMutationByName:
    @patch("src.game.action_helpers.pooch_actions.remove_mutation_from_pooch", new_callable=AsyncMock)
    @patch("src.game.action_helpers.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_with_name(self, mock_get, mock_remove, rng):
        mock_get.return_value = SimpleNamespace(id=5)
        mock_remove.return_value = SimpleNamespace(mutation_id=5)
        result = _make_result()
        await handle_remove_mutation_by_name([1], {"mutation": "Cataracts"}, rng, result)
        mock_get.assert_awaited_once_with("Cataracts")
        mock_remove.assert_awaited_once_with(1, 5)
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_name_not_found(self, mock_get, rng):
        mock_get.return_value = None
        result = _make_result()
        await handle_remove_mutation_by_name([1], {"mutation": "Nope"}, rng, result)
        assert result.pooches_affected == []


# ===========================================================================
# handle_add_breed
# ===========================================================================


class TestHandleAddBreed:
    @patch("src.game.action_helpers.pooch_actions.add_breed_to_pooch", new_callable=AsyncMock)
    async def test_with_breed_id(self, mock_add, rng):
        result = _make_result()
        await handle_add_breed([1], {"breed_id": 3, "weight": 0.8}, rng, result)
        mock_add.assert_awaited_once_with(1, 3, weight=0.8)
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.add_breed_to_pooch", new_callable=AsyncMock)
    async def test_default_weight(self, mock_add, rng):
        result = _make_result()
        await handle_add_breed([1], {"breed_id": 3}, rng, result)
        mock_add.assert_awaited_once_with(1, 3, weight=0.5)

    @patch("src.game.action_helpers.pooch_actions.add_breed_to_pooch", new_callable=AsyncMock)
    async def test_random_breed(self, mock_add, rng):
        result = _make_result()
        await handle_add_breed([1], {"min_rarity": "common"}, rng, result)
        mock_add.assert_awaited_once()
        kwargs = mock_add.call_args[1]
        assert kwargs["min_rarity"] == "common"


# ===========================================================================
# handle_remove_breed
# ===========================================================================


class TestHandleRemoveBreed:
    @patch("src.game.action_helpers.pooch_actions.remove_breed_from_pooch", new_callable=AsyncMock)
    async def test_with_breed_id(self, mock_remove, rng):
        mock_remove.return_value = True
        result = _make_result()
        await handle_remove_breed([1], {"breed_id": 3}, rng, result)
        mock_remove.assert_awaited_once_with(1, 3)
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.remove_random_breed_from_pooch", new_callable=AsyncMock)
    async def test_random_removal(self, mock_remove, rng):
        mock_remove.return_value = True
        result = _make_result()
        await handle_remove_breed([1], {}, rng, result)
        mock_remove.assert_awaited_once()
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.remove_breed_from_pooch", new_callable=AsyncMock)
    async def test_removal_returns_falsy(self, mock_remove, rng):
        mock_remove.return_value = None
        result = _make_result()
        await handle_remove_breed([1], {"breed_id": 3}, rng, result)
        assert result.pooches_affected == []


# ===========================================================================
# handle_rename_pooch
# ===========================================================================


class TestHandleRenamePooch:
    @patch("src.game.action_helpers.pooch_actions.rename_pooch", new_callable=AsyncMock)
    async def test_rename(self, mock_rename, rng):
        result = _make_result()
        await handle_rename_pooch([1, 2], {"name": "Buddy"}, rng, result)
        assert mock_rename.await_count == 2
        mock_rename.assert_any_await(1, "Buddy")
        mock_rename.assert_any_await(2, "Buddy")
        assert result.pooches_affected == [1, 2]

    @patch("src.game.action_helpers.pooch_actions.rename_pooch", new_callable=AsyncMock)
    async def test_no_name_param(self, mock_rename, rng):
        result = _make_result()
        await handle_rename_pooch([1], {}, rng, result)
        mock_rename.assert_not_awaited()
        assert result.pooches_affected == []


# ===========================================================================
# handle_modify_stat
# ===========================================================================


class TestHandleModifyStat:
    async def test_modify_strength(self, rng):
        mock_modify = AsyncMock(return_value=SimpleNamespace(id=1))
        mock_set = AsyncMock()
        with (
            patch.dict("src.game.action_helpers.pooch_actions._MODIFY_FNS", {"strength": mock_modify}),
            patch.dict("src.game.action_helpers.pooch_actions._SET_FNS", {"strength": mock_set}),
        ):
            result = _make_result()
            await handle_modify_stat("modify_strength", [1], {"amount": 5}, rng, result)
            mock_modify.assert_awaited_once_with(1, 5)
            assert result.pooches_affected == [1]

    async def test_set_cuteness(self, rng):
        mock_modify = AsyncMock()
        mock_set = AsyncMock(return_value=SimpleNamespace(id=1))
        with (
            patch.dict("src.game.action_helpers.pooch_actions._MODIFY_FNS", {"cuteness": mock_modify}),
            patch.dict("src.game.action_helpers.pooch_actions._SET_FNS", {"cuteness": mock_set}),
        ):
            result = _make_result()
            await handle_modify_stat("modify_cuteness", [1], {"amount": 10, "mode": "set"}, rng, result)
            mock_set.assert_awaited_once_with(1, 10)

    async def test_no_pooch_returned(self, rng):
        mock_modify = AsyncMock(return_value=None)
        mock_set = AsyncMock()
        with (
            patch.dict("src.game.action_helpers.pooch_actions._MODIFY_FNS", {"intelligence": mock_modify}),
            patch.dict("src.game.action_helpers.pooch_actions._SET_FNS", {"intelligence": mock_set}),
        ):
            result = _make_result()
            await handle_modify_stat("modify_intelligence", [1], {"amount": 3}, rng, result)
            assert result.pooches_affected == []


# ===========================================================================
# handle_damn_pooch
# ===========================================================================


class TestHandleDamnPooch:
    @patch("src.game.action_helpers.pooch_actions.damn_pooch", new_callable=AsyncMock)
    @patch("src.game.action_helpers.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_damn_pooch(self, mock_kill, mock_damn, rng):
        mock_kill.return_value = SimpleNamespace(id=1)
        mock_damn.return_value = SimpleNamespace(id=1, pooch_id=1)
        context = SimpleNamespace(affected_pooch_ids=[1, 2], extra_data={})
        result = _make_result()
        await handle_damn_pooch([1], {}, rng, result, context, "affected_pooch_ids")
        mock_kill.assert_awaited_once_with(1)
        mock_damn.assert_awaited_once_with(1)
        assert result.pooches_killed == [1]
        assert 1 not in context.affected_pooch_ids

    @patch("src.game.action_helpers.pooch_actions.damn_pooch", new_callable=AsyncMock)
    @patch("src.game.action_helpers.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_damn_pooch_with_save_as(self, mock_kill, mock_damn, rng):
        mock_kill.return_value = SimpleNamespace(id=1)
        mock_damn.return_value = SimpleNamespace(id=1, pooch_id=1)
        context = SimpleNamespace(affected_pooch_ids=[1], extra_data={})
        result = _make_result()
        await handle_damn_pooch([1], {"save_as": "damned"}, rng, result, context, "affected_pooch_ids")
        assert context.extra_data["damned"] == {"pooch_ids": [1]}

    @patch("src.game.action_helpers.pooch_actions.damn_pooch", new_callable=AsyncMock)
    @patch("src.game.action_helpers.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_damn_returns_none(self, mock_kill, mock_damn, rng):
        mock_kill.return_value = SimpleNamespace(id=1)
        mock_damn.return_value = None
        context = SimpleNamespace(affected_pooch_ids=[1], extra_data={})
        result = _make_result()
        await handle_damn_pooch([1], {}, rng, result, context, "affected_pooch_ids")
        assert result.pooches_killed == []


# ===========================================================================
# handle_modify_breeding_cooldown
# ===========================================================================


class TestHandleModifyBreedingCooldown:
    @patch("src.game.action_helpers.pooch_actions.set_pooch_breeding_cooldown", new_callable=AsyncMock)
    async def test_explicit_cooldown_value(self, mock_set, rng):
        result = _make_result()
        await handle_modify_breeding_cooldown([1], {"cooldown": 10}, rng, result)
        mock_set.assert_awaited_once_with(1, 10)
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    @patch("src.game.action_helpers.pooch_actions._get_breeding_cooldown_default", return_value=5)
    async def test_cooldown_base(self, mock_default, mock_reset, rng):
        result = _make_result()
        await handle_modify_breeding_cooldown([1], {"cooldown": "base"}, rng, result)
        mock_reset.assert_awaited_once_with(1, base_cooldown=5)
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.modify_pooch_breeding_cooldown", new_callable=AsyncMock)
    async def test_amount_modify_mode(self, mock_modify, rng):
        result = _make_result()
        await handle_modify_breeding_cooldown([1], {"amount": -2}, rng, result)
        mock_modify.assert_awaited_once_with(1, -2)
        assert result.pooches_affected == [1]

    @patch("src.game.action_helpers.pooch_actions.set_pooch_breeding_cooldown", new_callable=AsyncMock)
    async def test_amount_set_mode(self, mock_set, rng):
        result = _make_result()
        await handle_modify_breeding_cooldown([1], {"amount": 3, "mode": "set"}, rng, result)
        mock_set.assert_awaited_once_with(1, 3)


# ===========================================================================
# handle_select_pooch
# ===========================================================================


class TestHandleSelectPooch:
    async def test_select_pooch_is_noop(self, rng):
        """handle_select_pooch does nothing (resolution is handled externally)."""
        result = _make_result()
        await handle_select_pooch([1], {}, rng, result)
        assert result.pooches_affected == []
        assert result.pooches_killed == []
