import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.events.shared import (
    handle_add_breed,
    handle_add_mutation,
    handle_damn_pooch,
    handle_kill_pooch,
    handle_modify_age,
    handle_modify_breeding_cooldown,
    handle_modify_health,
    handle_modify_stat,
    handle_remove_breed,
    handle_remove_mutation,
    handle_rename_pooch,
    handle_select_pooch,
)

_MODULE = "src.game.events.shared.pooch_actions"


@pytest.fixture
def rng() -> random.Random:
    """
    Rng.

    Returns
    -------
    Any
        The result of calling `rng`.
    """

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
    @patch("src.game.events.shared.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    async def test_modify_mode(self, mock_modify, rng):
        mock_modify.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_health([1], {"amount": 5}, rng, result)
        mock_modify.assert_awaited_once_with(1, 5)
        assert result.pooches_affected == [1]
        assert result.extra_data["health_changes"][1] == 5

    @patch("src.game.events.shared.pooch_actions.set_pooch_base_health", new_callable=AsyncMock)
    async def test_set_mode(self, mock_set, rng):
        mock_set.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_health([1], {"amount": 20, "mode": "set"}, rng, result)
        mock_set.assert_awaited_once_with(1, 20)
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    async def test_no_pooch_returned(self, mock_modify, rng):
        mock_modify.return_value = None
        result = _make_result()
        await handle_modify_health([1], {"amount": 5}, rng, result)
        assert result.pooches_affected == []

    @patch("src.game.events.shared.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    async def test_multiple_pooches(self, mock_modify, rng):
        mock_modify.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_health([1, 2, 3], {"amount": 2}, rng, result)
        assert mock_modify.await_count == 3
        assert len(result.pooches_affected) == 3

    @patch("src.game.events.shared.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
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
    @patch("src.game.events.shared.pooch_actions.modify_pooch_age", new_callable=AsyncMock)
    async def test_modify_mode(self, mock_modify, rng):
        mock_modify.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_age([1], {"amount": 3}, rng, result)
        mock_modify.assert_awaited_once_with(1, 3)
        assert result.pooches_affected == [1]
        assert result.extra_data["age_changes"][1] == 3

    @patch("src.game.events.shared.pooch_actions.set_pooch_age", new_callable=AsyncMock)
    async def test_set_mode(self, mock_set, rng):
        mock_set.return_value = SimpleNamespace(id=1)
        result = _make_result()
        await handle_modify_age([1], {"amount": 5, "mode": "set"}, rng, result)
        mock_set.assert_awaited_once_with(1, 5)

    @patch("src.game.events.shared.pooch_actions.modify_pooch_age", new_callable=AsyncMock)
    async def test_no_pooch_returned(self, mock_modify, rng):
        mock_modify.return_value = None
        result = _make_result()
        await handle_modify_age([1], {"amount": 1}, rng, result)
        assert result.pooches_affected == []


# ===========================================================================
# handle_kill_pooch
# ===========================================================================


class TestHandleKillPooch:
    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_single_kill(self, mock_kill, rng):
        mock_kill.return_value = SimpleNamespace(id=1, owner_discord_id=None, name="Doggo")
        result = _make_result()
        await handle_kill_pooch([1], {}, rng, result)
        mock_kill.assert_awaited_once_with(1)
        assert result.pooches_killed == [1]
        assert result.message == "A pooch has died!"

    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_multiple_kills(self, mock_kill, rng):
        mock_kill.return_value = SimpleNamespace(id=1, owner_discord_id=None, name="Doggo")
        result = _make_result()
        await handle_kill_pooch([1, 2, 3], {}, rng, result)
        assert len(result.pooches_killed) == 3
        assert result.message == "3 pooches have died!"

    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
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
    @patch("src.game.events.shared.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_with_name(self, mock_get, mock_add, rng):
        mock_get.return_value = SimpleNamespace(id=5)
        result = _make_result()
        await handle_add_mutation([1], {"mutation": "Cataracts"}, rng, result)
        mock_get.assert_awaited_once_with("Cataracts")
        mock_add.assert_awaited_once_with(1, 5)
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_name_not_found(self, mock_get, mock_add, rng):
        mock_get.return_value = None
        result = _make_result()
        await handle_add_mutation([1], {"mutation": "NonExistent"}, rng, result)
        mock_add.assert_not_awaited()
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    async def test_random(self, mock_add, rng):
        result = _make_result()
        await handle_add_mutation([1], {"min_rarity": "common", "max_rarity": "rare"}, rng, result)
        mock_add.assert_awaited_once()
        kwargs = mock_add.call_args
        assert kwargs[1]["min_rarity"] == "common"
        assert kwargs[1]["max_rarity"] == "rare"


# ===========================================================================
# handle_remove_mutation
# ===========================================================================


class TestHandleRemoveMutation:
    @patch("src.game.events.shared.pooch_actions.remove_mutation_from_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_with_name(self, mock_get, mock_remove, rng):
        mock_get.return_value = SimpleNamespace(id=5)
        mock_remove.return_value = SimpleNamespace(mutation_id=5)
        result = _make_result()
        await handle_remove_mutation([1], {"mutation": "Cataracts"}, rng, result)
        mock_get.assert_awaited_once_with("Cataracts")
        mock_remove.assert_awaited_once_with(1, 5)
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.remove_random_mutation_from_pooch", new_callable=AsyncMock)
    async def test_random_removal(self, mock_remove, rng):
        mock_remove.return_value = SimpleNamespace(mutation_id=20)
        result = _make_result()
        await handle_remove_mutation([1], {}, rng, result)
        mock_remove.assert_awaited_once()
        assert result.mutations_removed == [(1, 20)]

    @patch("src.game.events.shared.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_name_not_found(self, mock_get, rng):
        mock_get.return_value = None
        result = _make_result()
        await handle_remove_mutation([1], {"mutation": "Nope"}, rng, result)
        assert result.pooches_affected == []


# ===========================================================================
# handle_add_breed
# ===========================================================================


class TestHandleAddBreed:
    @patch("src.game.events.shared.pooch_actions.add_breed_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_breed_by_name", new_callable=AsyncMock)
    async def test_with_name(self, mock_get, mock_add, rng):
        mock_get.return_value = SimpleNamespace(id=3)
        result = _make_result()
        await handle_add_breed([1], {"breed": "Greyhound", "weight": 0.8}, rng, result)
        mock_get.assert_awaited_once_with("Greyhound")
        mock_add.assert_awaited_once_with(1, 3, weight=0.8)
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.add_breed_to_pooch", new_callable=AsyncMock)
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
    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.remove_breed_from_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_breed_by_name", new_callable=AsyncMock)
    async def test_with_name(self, mock_get_breed, mock_remove, mock_get_pooch, rng):
        mock_get_breed.return_value = SimpleNamespace(id=3)
        mock_remove.return_value = True
        mock_get_pooch.return_value = SimpleNamespace(name="Doggo")
        result = _make_result()
        await handle_remove_breed([1], {"breed": "Greyhound"}, rng, result)
        mock_get_breed.assert_awaited_once_with("Greyhound")
        mock_remove.assert_awaited_once_with(1, 3)
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.remove_random_breed_from_pooch", new_callable=AsyncMock)
    async def test_random_removal(self, mock_remove, mock_get_pooch, rng):
        mock_remove.return_value = True
        mock_get_pooch.return_value = SimpleNamespace(name="Doggo")
        result = _make_result()
        await handle_remove_breed([1], {}, rng, result)
        mock_remove.assert_awaited_once()
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.remove_random_breed_from_pooch", new_callable=AsyncMock)
    async def test_removal_returns_falsy(self, mock_remove, rng):
        mock_remove.return_value = None
        result = _make_result()
        await handle_remove_breed([1], {}, rng, result)
        assert result.pooches_affected == []


# ===========================================================================
# handle_rename_pooch
# ===========================================================================


class TestHandleRenamePooch:
    @patch("src.game.events.shared.pooch_actions.rename_pooch", new_callable=AsyncMock)
    async def test_rename(self, mock_rename, rng):
        result = _make_result()
        await handle_rename_pooch([1, 2], {"name": "Buddy"}, rng, result)
        assert mock_rename.await_count == 2
        mock_rename.assert_any_await(1, "Buddy")
        mock_rename.assert_any_await(2, "Buddy")
        assert result.pooches_affected == [1, 2]

    @patch("src.game.events.shared.pooch_actions.rename_pooch", new_callable=AsyncMock)
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
        mock_modify = AsyncMock(return_value=SimpleNamespace(id=1, name="Doggo"))
        mock_set = AsyncMock()
        with (
            patch.dict("src.game.events.shared.pooch_actions._MODIFY_FNS", {"strength": mock_modify}),
            patch.dict("src.game.events.shared.pooch_actions._SET_FNS", {"strength": mock_set}),
        ):
            result = _make_result()
            await handle_modify_stat("modify_strength", [1], {"amount": 5}, rng, result)
            mock_modify.assert_awaited_once_with(1, 5)
            assert result.pooches_affected == [1]

    async def test_set_cuteness(self, rng):
        mock_modify = AsyncMock()
        mock_set = AsyncMock(return_value=SimpleNamespace(id=1, name="Doggo"))
        with (
            patch.dict("src.game.events.shared.pooch_actions._MODIFY_FNS", {"cuteness": mock_modify}),
            patch.dict("src.game.events.shared.pooch_actions._SET_FNS", {"cuteness": mock_set}),
        ):
            result = _make_result()
            await handle_modify_stat("modify_cuteness", [1], {"amount": 10, "mode": "set"}, rng, result)
            mock_set.assert_awaited_once_with(1, 10)

    async def test_no_pooch_returned(self, rng):
        mock_modify = AsyncMock(return_value=None)
        mock_set = AsyncMock()
        with (
            patch.dict("src.game.events.shared.pooch_actions._MODIFY_FNS", {"intelligence": mock_modify}),
            patch.dict("src.game.events.shared.pooch_actions._SET_FNS", {"intelligence": mock_set}),
        ):
            result = _make_result()
            await handle_modify_stat("modify_intelligence", [1], {"amount": 3}, rng, result)
            assert result.pooches_affected == []


# ===========================================================================
# handle_damn_pooch
# ===========================================================================


class TestHandleDamnPooch:
    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.damn_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_damn_pooch(self, mock_kill, mock_damn, mock_get_pooch, rng):
        mock_kill.return_value = SimpleNamespace(id=1)
        mock_damn.return_value = SimpleNamespace(id=1, pooch_id=1)
        mock_get_pooch.return_value = SimpleNamespace(name="Doggo")
        context = SimpleNamespace(affected_pooch_ids=[1, 2], extra_data={})
        result = _make_result()
        await handle_damn_pooch([1], {}, rng, result, context, "affected_pooch_ids")
        mock_kill.assert_awaited_once_with(1)
        mock_damn.assert_awaited_once_with(1)
        assert result.pooches_killed == [1]
        assert 1 not in context.affected_pooch_ids

    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.damn_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_damn_pooch_with_save_as(self, mock_kill, mock_damn, mock_get_pooch, rng):
        mock_kill.return_value = SimpleNamespace(id=1)
        mock_damn.return_value = SimpleNamespace(id=1, pooch_id=1)
        mock_get_pooch.return_value = SimpleNamespace(name="Doggo")
        context = SimpleNamespace(affected_pooch_ids=[1], extra_data={})
        result = _make_result()
        await handle_damn_pooch([1], {"save_as": "damned"}, rng, result, context, "affected_pooch_ids")
        assert context.extra_data["damned"] == {"pooch_ids": [1]}

    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.damn_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    async def test_damn_returns_none(self, mock_kill, mock_damn, mock_get_pooch, rng):
        mock_kill.return_value = SimpleNamespace(id=1)
        mock_damn.return_value = None
        mock_get_pooch.return_value = SimpleNamespace(name="Doggo")
        context = SimpleNamespace(affected_pooch_ids=[1], extra_data={})
        result = _make_result()
        await handle_damn_pooch([1], {}, rng, result, context, "affected_pooch_ids")
        assert result.pooches_killed == []


# ===========================================================================
# handle_modify_breeding_cooldown
# ===========================================================================


class TestHandleModifyBreedingCooldown:
    @patch("src.game.events.shared.pooch_actions.set_pooch_breeding_cooldown", new_callable=AsyncMock)
    async def test_explicit_cooldown_value(self, mock_set, rng):
        result = _make_result()
        await handle_modify_breeding_cooldown([1], {"amount": 10, "mode": "set"}, rng, result)
        mock_set.assert_awaited_once_with(1, 10)
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.reset_pooch_breeding_cooldown", new_callable=AsyncMock)
    async def test_cooldown_base(self, mock_reset, rng):
        result = _make_result()
        await handle_modify_breeding_cooldown([1], {"reset": True}, rng, result)
        mock_reset.assert_awaited_once_with(1)
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.modify_pooch_breeding_cooldown", new_callable=AsyncMock)
    async def test_amount_modify_mode(self, mock_modify, rng):
        result = _make_result()
        await handle_modify_breeding_cooldown([1], {"amount": -2}, rng, result)
        mock_modify.assert_awaited_once_with(1, -2)
        assert result.pooches_affected == [1]

    @patch("src.game.events.shared.pooch_actions.set_pooch_breeding_cooldown", new_callable=AsyncMock)
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


# ===========================================================================
# handle_add_mutation — list of mutations ("mutations" key)
# ===========================================================================


class TestHandleAddMutationList:
    @patch("src.game.events.shared.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_mutations_list(self, mock_get, mock_add, rng):
        """When 'mutations' key is a list, each mutation in the list is added."""
        mock_get.side_effect = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        result = _make_result()
        await handle_add_mutation([10], {"mutations": ["Alpha", "Beta"]}, rng, result)
        assert mock_get.await_count == 2
        assert mock_add.await_count == 2
        assert result.pooches_affected == [10]

    @patch("src.game.events.shared.pooch_actions.add_mutation_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_mutation_by_name", new_callable=AsyncMock)
    async def test_mutations_list_unknown_skipped(self, mock_get, mock_add, rng):
        """If a mutation name in the list is not found, it is silently skipped."""
        mock_get.return_value = None
        result = _make_result()
        await handle_add_mutation([10], {"mutations": ["Unknown"]}, rng, result)
        mock_add.assert_not_awaited()


# ===========================================================================
# handle_injure_pooch
# ===========================================================================


from src.game.events.shared import handle_injure_pooch


class TestHandleInjurePooch:
    @patch("src.game.events.shared.pooch_actions.add_injury_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_injury_by_name", new_callable=AsyncMock)
    async def test_named_injury(self, mock_get_injury, mock_get_pooch, mock_add, rng):
        mock_get_injury.return_value = SimpleNamespace(id=7, name="Broken Leg")
        mock_add.return_value = True
        mock_get_pooch.return_value = SimpleNamespace(name="Buddy")
        result = _make_result()

        await handle_injure_pooch([1], {"injury": "Broken Leg"}, rng, result)

        mock_get_injury.assert_awaited_once_with("Broken Leg")
        mock_add.assert_awaited_once_with(1, 7)
        assert 1 in result.pooches_affected

    @patch("src.game.events.shared.pooch_actions.get_injury_by_name", new_callable=AsyncMock)
    async def test_named_injury_not_found_does_nothing(self, mock_get_injury, rng):
        mock_get_injury.return_value = None
        result = _make_result()

        await handle_injure_pooch([1], {"injury": "Ghost Injury"}, rng, result)

        assert result.pooches_affected == []

    @patch("src.game.events.shared.pooch_actions.add_injury_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_random_injury", new_callable=AsyncMock)
    async def test_random_injury_per_pooch(self, mock_random_inj, mock_get_pooch, mock_add, rng):
        mock_random_inj.return_value = SimpleNamespace(id=3, name="Minor Scratch")
        mock_add.return_value = True
        mock_get_pooch.return_value = SimpleNamespace(name="Buddy")
        result = _make_result()

        await handle_injure_pooch([1, 2], {}, rng, result)

        # Random injury rolled independently per pooch
        assert mock_random_inj.await_count == 2
        assert len(result.pooches_affected) == 2

    @patch("src.game.events.shared.pooch_actions.add_injury_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_random_injury", new_callable=AsyncMock)
    async def test_roll_once_reuses_injury(self, mock_random_inj, mock_get_pooch, mock_add, rng):
        mock_random_inj.return_value = SimpleNamespace(id=5, name="Bite")
        mock_add.return_value = True
        mock_get_pooch.return_value = SimpleNamespace(name="Buddy")
        result = _make_result()

        await handle_injure_pooch([1, 2, 3], {"roll_once": True}, rng, result)

        # Should only roll once, then apply to all
        assert mock_random_inj.await_count == 1
        assert mock_add.await_count == 3

    @patch("src.game.events.shared.pooch_actions.get_random_injury", new_callable=AsyncMock)
    async def test_roll_once_no_injury_found(self, mock_random_inj, rng):
        mock_random_inj.return_value = None
        result = _make_result()

        await handle_injure_pooch([1], {"roll_once": True}, rng, result)

        assert result.pooches_affected == []

    @patch("src.game.events.shared.pooch_actions.get_random_injury", new_callable=AsyncMock)
    async def test_random_injury_not_found_skips(self, mock_random_inj, rng):
        mock_random_inj.return_value = None
        result = _make_result()

        await handle_injure_pooch([1], {}, rng, result)

        assert result.pooches_affected == []


# ===========================================================================
# _compute_damage and _strength_loss_for_round (pure functions)
# ===========================================================================


from src.game.events.shared.pooch_actions import (
    _compute_damage,
    _strength_loss_for_round,
)


class TestComputeDamage:
    def test_returns_at_least_one(self):
        rng = random.Random(0)
        dmg = _compute_damage(
            attacker_strength=1,
            attacker_size=1,
            attacker_dexterity=1,
            attacker_aggressiveness=1,
            defender_strength=1000,
            defender_dexterity=1000,
            defender_constitution=1000,
            defender_size=1000,
            rng=rng,
        )
        assert dmg >= 1

    def test_high_attacker_high_damage(self):
        rng = random.Random(42)
        dmg = _compute_damage(
            attacker_strength=50,
            attacker_size=20,
            attacker_dexterity=50,
            attacker_aggressiveness=50,
            defender_strength=1,
            defender_dexterity=1,
            defender_constitution=1,
            defender_size=1,
            rng=rng,
        )
        assert dmg > 5

    def test_deterministic(self):
        kwargs = dict(
            attacker_strength=10,
            attacker_size=10,
            attacker_dexterity=10,
            attacker_aggressiveness=10,
            defender_strength=10,
            defender_dexterity=10,
            defender_constitution=10,
            defender_size=10,
        )
        assert _compute_damage(**kwargs, rng=random.Random(7)) == _compute_damage(**kwargs, rng=random.Random(7))


class TestStrengthLossForRound:
    def test_returns_at_least_one(self):
        assert _strength_loss_for_round(constitution=100) >= 1

    def test_low_constitution_higher_loss(self):
        loss_low = _strength_loss_for_round(constitution=1)
        loss_high = _strength_loss_for_round(constitution=20)
        assert loss_low >= loss_high

    def test_zero_constitution(self):
        # 2 / (1 + 0) = 2 → rounds to 2
        assert _strength_loss_for_round(constitution=0) == 2


# ===========================================================================
# handle_fight_pooches
# ===========================================================================


from src.game.events.shared import handle_fight_pooches


class TestHandleFightPooches:
    @pytest.fixture(autouse=True)
    def _effective_stats_are_the_pooch_fields(self):
        """Fighters use effective stats; here those are just the (patched) pooch's own fields."""
        from src.game.events.shared import pooch_actions
        from src.game.manage_stats import ALL_STATS

        async def stats(pooch_id):
            pooch = await pooch_actions.get_pooch_by_id(pooch_id)
            return {stat: getattr(pooch, stat, 10) for stat in ALL_STATS}

        with patch("src.game.events.shared.pooch_actions.get_effective_stats", new=stats):
            yield

    def _make_pooch_ns(self, **overrides):
        defaults = dict(
            id=1,
            name="Pooch",
            alive=True,
            strength=10,
            size=10,
            dexterity=10,
            constitution=10,
            aggressiveness=10,
            base_health=20,
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    @patch("src.game.events.shared.pooch_actions.add_injury_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_injury_by_name", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    async def test_attacker_or_defender_none_returns_draw(
        self, mock_get, mock_dead, mock_health, mock_inj_name, mock_add_inj, rng
    ):
        mock_get.return_value = None
        result = await handle_fight_pooches(1, 2, rng=rng)
        assert result["draw"] is True
        assert result["rounds_fought"] == 0
        assert "error" in result

    @patch("src.game.events.shared.pooch_actions.add_injury_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_injury_by_name", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    async def test_dead_pooch_returns_draw(self, mock_get, mock_dead, mock_health, mock_inj_name, mock_add_inj, rng):
        dead_pooch = self._make_pooch_ns(id=1, alive=False)
        living_pooch = self._make_pooch_ns(id=2)
        mock_get.side_effect = [dead_pooch, living_pooch]
        result = await handle_fight_pooches(1, 2, rng=rng)
        assert result["draw"] is True
        assert result["rounds_fought"] == 0

    @patch("src.game.events.shared.pooch_actions.add_injury_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_injury_by_name", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    async def test_fight_returns_expected_keys(
        self, mock_get, mock_dead, mock_health, mock_inj_name, mock_add_inj, rng
    ):
        attacker = self._make_pooch_ns(id=1, base_health=100)
        defender = self._make_pooch_ns(id=2, base_health=100)
        mock_get.side_effect = lambda pid: {1: attacker, 2: defender}[pid]
        mock_inj_name.return_value = None

        result = await handle_fight_pooches(1, 2, rounds=1, rng=rng)

        for key in (
            "attacker_id",
            "defender_id",
            "attacker_damage",
            "defender_damage",
            "attacker_died",
            "defender_died",
            "winner_id",
            "draw",
            "rounds_fought",
        ):
            assert key in result

    @patch("src.game.events.shared.pooch_actions.add_injury_to_pooch", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_injury_by_name", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.modify_pooch_base_health", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.set_pooch_dead", new_callable=AsyncMock)
    @patch("src.game.events.shared.pooch_actions.get_pooch_by_id", new_callable=AsyncMock)
    async def test_fight_attacker_wins_when_deals_more_damage(
        self, mock_get, mock_dead, mock_health, mock_inj_name, mock_add_inj, rng
    ):
        # Give attacker huge stats, defender very low stats — attacker should deal more damage
        attacker = self._make_pooch_ns(id=1, strength=100, dexterity=100, aggressiveness=100, size=20, base_health=1000)
        defender = self._make_pooch_ns(id=2, strength=1, dexterity=1, aggressiveness=1, size=1, base_health=1000)
        mock_get.side_effect = lambda pid: {1: attacker, 2: defender}[pid]
        mock_inj_name.return_value = None

        result = await handle_fight_pooches(1, 2, rounds=1, rng=rng)

        # With massively superior attacker, should deal more damage
        assert result["defender_damage"] > result["attacker_damage"]
