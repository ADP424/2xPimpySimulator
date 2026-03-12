import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.manage_events import _execute_single_action
from src.game.models import EventContext


def _make_action(action_type: str, target_type: str, parameters: dict) -> MagicMock:
    """Build a minimal EventAction stub."""
    action = MagicMock()
    action.action_type = action_type
    action.target_type = target_type
    action.parameters = parameters
    return action


def _make_kennel(kennel_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=kennel_id)


def _make_pooch(pooch_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=pooch_id)


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


@pytest.fixture
def context() -> EventContext:
    return EventContext(owner_discord_id=1)


# ---------------------------------------------------------------------------
# save_as on a pooch action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_as_writes_pooch_ids_to_slot(context, rng):
    """save_as should store resolved pooch IDs in context.extra_data."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "random", "amount": -1, "save_as": "my_slot"},
    )

    with (
        patch("src.game.manage_events.get_random_matching_pooch_id", new=AsyncMock(return_value=7)),
        patch("src.game.manage_events.modify_pooch_base_health", new=AsyncMock(return_value=_make_pooch(7))),
        patch("src.game.manage_events.get_pooch_kennel", new=AsyncMock(return_value=None)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert context.extra_data["my_slot"] == {"pooch_ids": [7]}


@pytest.mark.asyncio
async def test_save_as_with_save_kennel_stores_kennel_ids(context, rng):
    """save_as + save_kennel should also store the kennel the pooch belongs to."""
    action = _make_action(
        "kill_pooch",
        "pooch",
        {"selector": "random", "save_as": "fire_victim", "save_kennel": True},
    )
    kennel = _make_kennel(99)

    with (
        patch("src.game.manage_events.get_random_matching_pooch_id", new=AsyncMock(return_value=5)),
        patch("src.game.manage_events.set_pooch_dead", new=AsyncMock(return_value=_make_pooch(5))),
        patch("src.game.manage_events.get_pooch_kennel", new=AsyncMock(return_value=kennel)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert context.extra_data["fire_victim"] == {"pooch_ids": [5], "kennel_ids": [99]}


@pytest.mark.asyncio
async def test_save_kennel_homeless_pooch_stores_empty_kennel_ids(context, rng):
    """When the resolved pooch has no kennel, kennel_ids should be []."""
    action = _make_action(
        "kill_pooch",
        "pooch",
        {"selector": "random", "save_as": "fire_victim", "save_kennel": True},
    )

    with (
        patch("src.game.manage_events.get_random_matching_pooch_id", new=AsyncMock(return_value=5)),
        patch("src.game.manage_events.set_pooch_dead", new=AsyncMock(return_value=_make_pooch(5))),
        patch("src.game.manage_events.get_pooch_kennel", new=AsyncMock(return_value=None)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert context.extra_data["fire_victim"] == {"pooch_ids": [5], "kennel_ids": []}


# ---------------------------------------------------------------------------
# use_saved on a kennel action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_use_saved_reads_kennel_ids_from_slot(context, rng):
    """use_saved on a kennel action should pull kennel_ids from the named slot."""
    context.extra_data["fire_victim"] = {"pooch_ids": [5], "kennel_ids": [99]}

    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"use_saved": "fire_victim", "amount": -2},
    )

    affected_pooches = []

    async def fake_list_in_kennel(owner_id, kennel_id, filter_spec):
        return [10, 11]  # simulated pooches in kennel 99

    async def fake_modify_health(pooch_id, amount):
        affected_pooches.append(pooch_id)
        return _make_pooch(pooch_id)

    with (
        patch(
            "src.game.manage_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(side_effect=fake_list_in_kennel)
        ),
        patch("src.game.manage_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert sorted(affected_pooches) == [10, 11]
    assert sorted(result.pooches_affected) == [10, 11]


@pytest.mark.asyncio
async def test_use_saved_missing_slot_is_noop(context, rng):
    """use_saved pointing to a non-existent slot should result in no pooches affected."""
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"use_saved": "nonexistent_slot", "amount": -2},
    )

    with patch("src.game.manage_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[])):
        result = await _execute_single_action(1, action, context, rng)

    assert result.pooches_affected == []


# ---------------------------------------------------------------------------
# save_as on a kennel action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_as_on_kennel_action_writes_kennel_ids(context, rng):
    """save_as on a kennel action should store kennel_ids in the slot."""
    action = _make_action(
        "modify_kennel_capacity",
        "kennel",
        {"selector": "random", "amount": 1, "save_as": "chosen_kennel"},
    )

    with (
        patch("src.game.manage_events.get_random_matching_kennel_id", new=AsyncMock(return_value=3)),
        patch("src.game.manage_events.modify_kennel_pooch_limit", new=AsyncMock(return_value=_make_kennel(3))),
    ):
        await _execute_single_action(1, action, context, rng)

    assert context.extra_data["chosen_kennel"] == {"kennel_ids": [3]}


# ---------------------------------------------------------------------------
# End-to-end: two-action chain (kill pooch → damage kennel)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kill_then_damage_kennel_chain(context, rng):
    """
    Full chain: kill_pooch with save_as+save_kennel, then modify_pooch_health
    with use_saved targeting the saved kennel.
    """
    kennel = _make_kennel(42)
    kill_action = _make_action(
        "kill_pooch",
        "pooch",
        {"selector": "random", "filter": {"location": "kennel"}, "save_as": "victim", "save_kennel": True},
    )
    damage_action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"use_saved": "victim", "amount": -2},
    )

    damaged = []

    async def fake_modify_health(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_events.get_random_matching_pooch_id", new=AsyncMock(return_value=7)),
        patch("src.game.manage_events.set_pooch_dead", new=AsyncMock(return_value=_make_pooch(7))),
        patch("src.game.manage_events.get_pooch_kennel", new=AsyncMock(return_value=kennel)),
        patch(
            "src.game.manage_events.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(return_value=[8, 9]),
        ),
        patch("src.game.manage_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
    ):
        await _execute_single_action(1, kill_action, context, rng)
        await _execute_single_action(1, damage_action, context, rng)

    assert context.extra_data["victim"] == {"pooch_ids": [7], "kennel_ids": [42]}
    assert sorted(damaged) == [8, 9]
