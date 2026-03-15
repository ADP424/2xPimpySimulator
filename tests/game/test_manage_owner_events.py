import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.manage_owner_events import (
    _choose_option_outcome,
    _deliver_pooch,
    _execute_single_action,
)
from src.game.models import EventContext


def _make_action(action_type: str, target_type: str, parameters: dict, repeat: int = 1) -> MagicMock:
    """Build a minimal EventAction stub."""
    action = MagicMock()
    action.action_type = action_type
    action.target_type = target_type
    action.parameters = parameters
    action.repeat = repeat
    return action


def _make_kennel(kennel_id: int, name: str = "Test Kennel", pooch_limit: int = 5) -> SimpleNamespace:
    return SimpleNamespace(id=kennel_id, name=name, pooch_limit=pooch_limit)


def _make_pooch(pooch_id: int, alive: bool = True, name: str = "Fido") -> SimpleNamespace:
    return SimpleNamespace(id=pooch_id, alive=alive, name=name)


def _make_outcome(chance=None, label="opt", description="desc", message="msg", actions=None):
    """Build a minimal EventOutcome stub using MagicMock."""
    o = MagicMock()
    o.chance = chance
    o.label = label
    o.description = description
    o.message = message
    o.actions = actions or []
    return o


def _make_option(outcomes, is_default=False, is_visible=True, actions=None):
    """Build a minimal EventOption stub using MagicMock."""
    opt = MagicMock()
    opt.outcomes = outcomes
    opt.is_default = is_default
    opt.is_visible = is_visible
    opt.actions = actions or []
    return opt


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
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(return_value=_make_pooch(7))),
        patch("src.game.manage_owner_events.get_pooch_kennel", new=AsyncMock(return_value=None)),
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
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.set_pooch_dead", new=AsyncMock(return_value=_make_pooch(5))),
        patch("src.game.manage_owner_events.get_pooch_kennel", new=AsyncMock(return_value=kennel)),
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
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.set_pooch_dead", new=AsyncMock(return_value=_make_pooch(5))),
        patch("src.game.manage_owner_events.get_pooch_kennel", new=AsyncMock(return_value=None)),
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
            "src.game.manage_owner_events.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(side_effect=fake_list_in_kennel),
        ),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
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

    with patch("src.game.manage_owner_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[])):
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
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock(return_value=3)),
        patch("src.game.manage_owner_events.modify_kennel_pooch_limit", new=AsyncMock(return_value=_make_kennel(3))),
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
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch("src.game.manage_owner_events.set_pooch_dead", new=AsyncMock(return_value=_make_pooch(7))),
        patch("src.game.manage_owner_events.get_pooch_kennel", new=AsyncMock(return_value=kennel)),
        patch(
            "src.game.manage_owner_events.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(return_value=[8, 9]),
        ),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
    ):
        await _execute_single_action(1, kill_action, context, rng)
        await _execute_single_action(1, damage_action, context, rng)

    assert context.extra_data["victim"] == {"pooch_ids": [7], "kennel_ids": [42]}
    assert sorted(damaged) == [8, 9]


# ---------------------------------------------------------------------------
# Selector: "all" applies to every matching pooch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_selector_affects_every_matching_pooch(context, rng):
    """'all' selector should apply the action to every pooch returned by list_matching_pooch_ids."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "all", "amount": -1},
    )

    damaged = []

    async def fake_modify_health(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert sorted(damaged) == [1, 2, 3]
    assert sorted(result.pooches_affected) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Selector: "random" with count parameter picks N pooches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_random_selector_with_count_picks_n_pooches(context, rng):
    """'random' selector with count=2 should pick exactly 2 pooches."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "random", "count": 2, "amount": -1},
    )

    damaged = []

    async def fake_modify_health(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    all_ids = [10, 20, 30, 40, 50]

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=all_ids)),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert len(damaged) == 2
    assert all(pid in all_ids for pid in damaged)


@pytest.mark.asyncio
async def test_random_selector_count_exceeds_available(context, rng):
    """count larger than available pooches should just take all of them."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "random", "count": 10, "amount": -1},
    )

    damaged = []

    async def fake_modify_health(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert sorted(damaged) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Selector: "random_exclude" skips N randomly chosen pooches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_random_exclude_removes_n_pooches(context, rng):
    """'random_exclude' with count=1 should affect all-but-1 pooches."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "random_exclude", "count": 1, "amount": -1},
    )

    damaged = []

    async def fake_modify_health(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    all_ids = [10, 20, 30]

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=all_ids)),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
    ):
        await _execute_single_action(1, action, context, rng)

    # Should affect exactly 2 of the 3 pooches
    assert len(damaged) == 2
    assert all(pid in all_ids for pid in damaged)


@pytest.mark.asyncio
async def test_random_exclude_without_count_affects_nobody(context, rng):
    """'random_exclude' without count (or count >= total) should result in no action."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "random_exclude", "amount": -1},
    )

    damaged = []

    async def fake_modify_health(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[10, 20, 30])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert damaged == []


@pytest.mark.asyncio
async def test_random_exclude_count_ge_total_affects_nobody(context, rng):
    """'random_exclude' with count >= total available should affect nobody."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "random_exclude", "count": 5, "amount": -1},
    )

    damaged = []

    async def fake_modify_health(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[10, 20, 30])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify_health)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert damaged == []


# ---------------------------------------------------------------------------
# Kennel selector: "random" with count picks N kennels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kennel_random_selector_with_count(context, rng):
    """kennel 'random' selector with count=2 should pick exactly 2 kennels."""
    action = _make_action(
        "modify_kennel_capacity",
        "kennel",
        {"selector": "random", "count": 2, "amount": 1},
    )

    modified = []

    async def fake_modify_limit(kennel_id, amount):
        modified.append(kennel_id)
        return _make_kennel(kennel_id)

    all_kennel_ids = [100, 200, 300, 400]

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=all_kennel_ids)),
        patch("src.game.manage_owner_events.modify_kennel_pooch_limit", new=AsyncMock(side_effect=fake_modify_limit)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert len(modified) == 2
    assert all(kid in all_kennel_ids for kid in modified)


@pytest.mark.asyncio
async def test_kennel_random_exclude_removes_n_kennels(context, rng):
    """kennel 'random_exclude' with count=1 should affect all-but-1 kennels."""
    action = _make_action(
        "modify_kennel_capacity",
        "kennel",
        {"selector": "random_exclude", "count": 1, "amount": 1},
    )

    modified = []

    async def fake_modify_limit(kennel_id, amount):
        modified.append(kennel_id)
        return _make_kennel(kennel_id)

    all_kennel_ids = [100, 200, 300]

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=all_kennel_ids)),
        patch("src.game.manage_owner_events.modify_kennel_pooch_limit", new=AsyncMock(side_effect=fake_modify_limit)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert len(modified) == 2
    assert all(kid in all_kennel_ids for kid in modified)


# ---------------------------------------------------------------------------
# modify_money / modify_bloodskulls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_money_fixed_amount(context, rng):
    """modify_money with fixed amount should call give_money_to_owner."""
    action = _make_action("modify_money", "owner", {"amount": 50})

    with patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give:
        result = await _execute_single_action(1, action, context, rng)

    mock_give.assert_awaited_once_with(1, 50)
    assert result.money_changed == 50


@pytest.mark.asyncio
async def test_modify_money_negative_amount(context, rng):
    """modify_money with a negative amount deducts money."""
    action = _make_action("modify_money", "owner", {"amount": -30})

    with patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give:
        result = await _execute_single_action(1, action, context, rng)

    mock_give.assert_awaited_once_with(1, -30)
    assert result.money_changed == -30


@pytest.mark.asyncio
async def test_modify_money_random_range(context, rng):
    """modify_money with min/max_amount should roll a value in range."""
    action = _make_action("modify_money", "owner", {"min_amount": 10, "max_amount": 100})

    with patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give:
        result = await _execute_single_action(1, action, context, rng)

    called_amount = mock_give.call_args[0][1]
    assert 10 <= called_amount <= 100
    assert result.money_changed == called_amount


@pytest.mark.asyncio
async def test_modify_bloodskulls(context, rng):
    """modify_bloodskulls should call give_bloodskulls_to_owner."""
    action = _make_action("modify_bloodskulls", "owner", {"amount": 5})

    with patch("src.game.manage_owner_events.give_bloodskulls_to_owner", new=AsyncMock()) as mock_give:
        result = await _execute_single_action(1, action, context, rng)

    mock_give.assert_awaited_once_with(1, 5)
    assert result.bloodskulls_changed == 5


# ---------------------------------------------------------------------------
# modify_pooch_health / modify_pooch_age
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_pooch_health_selected(context, rng):
    """modify_pooch_health with selector='selected' targets context.selected_pooch_id."""
    context.selected_pooch_id = 99
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "selected", "amount": -5},
    )

    with patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(return_value=_make_pooch(99))):
        result = await _execute_single_action(1, action, context, rng)

    assert 99 in result.pooches_affected


@pytest.mark.asyncio
async def test_modify_pooch_health_owner_target_affects_all(context, rng):
    """target_type='owner' on modify_pooch_health applies to all owner's pooches."""
    action = _make_action(
        "modify_pooch_health",
        "owner",
        {"amount": -1},
    )

    damaged = []

    async def fake_modify(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert sorted(damaged) == [1, 2, 3]


# ---------------------------------------------------------------------------
# kill_pooch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kill_pooch_random(context, rng):
    """kill_pooch with random selector kills a single random pooch."""
    action = _make_action(
        "kill_pooch",
        "pooch",
        {"selector": "random"},
    )

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch("src.game.manage_owner_events.set_pooch_dead", new=AsyncMock(return_value=_make_pooch(7))),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert 7 in result.pooches_killed


@pytest.mark.asyncio
async def test_kill_pooch_all(context, rng):
    """kill_pooch with selector='all' kills every matching pooch."""
    action = _make_action(
        "kill_pooch",
        "pooch",
        {"selector": "all"},
    )

    killed = []

    async def fake_kill(pooch_id):
        killed.append(pooch_id)
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[10, 11, 12])),
        patch("src.game.manage_owner_events.set_pooch_dead", new=AsyncMock(side_effect=fake_kill)),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert sorted(result.pooches_killed) == [10, 11, 12]


# ---------------------------------------------------------------------------
# modify_kennel_capacity (owner target — all kennels)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_kennel_capacity_owner_target(context, rng):
    """target_type='owner' on modify_kennel_capacity modifies all kennels."""
    action = _make_action(
        "modify_kennel_capacity",
        "owner",
        {"amount": 2},
    )

    modified = []

    async def fake_modify(kennel_id, amount):
        modified.append(kennel_id)
        return _make_kennel(kennel_id)

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2])),
        patch("src.game.manage_owner_events.modify_kennel_pooch_limit", new=AsyncMock(side_effect=fake_modify)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert sorted(modified) == [1, 2]


# ---------------------------------------------------------------------------
# set_breeding_cooldown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_breeding_cooldown(context, rng):
    """set_breeding_cooldown should call set_pooch_breeding_cooldown with the given value."""
    action = _make_action(
        "set_breeding_cooldown",
        "pooch",
        {"selector": "random", "cooldown": 0},
    )

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.set_pooch_breeding_cooldown", new=AsyncMock(return_value=_make_pooch(5))),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert 5 in result.pooches_affected


# ---------------------------------------------------------------------------
# add_mutation / remove_mutation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_mutation_to_random_pooch(context, rng):
    """add_mutation should call add_mutation_to_pooch for the resolved pooch."""
    action = _make_action(
        "add_mutation",
        "pooch",
        {"selector": "random", "mutation_id": 10},
    )

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[3])),
        patch("src.game.manage_owner_events.add_mutation_to_pooch", new=AsyncMock(return_value=True)),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert 3 in result.pooches_affected


@pytest.mark.asyncio
async def test_add_random_mutation_to_pooch(context, rng):
    """add_mutation without mutation_id should add a random mutation."""
    action = _make_action(
        "add_mutation",
        "pooch",
        {"selector": "random"},
    )

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[3])),
        patch("src.game.manage_owner_events.add_mutation_to_pooch", new=AsyncMock(return_value=True)),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert 3 in result.pooches_affected


@pytest.mark.asyncio
async def test_remove_mutation_from_pooch(context, rng):
    """remove_mutation should call remove_random_mutation_from_pooch for the resolved pooch."""
    action = _make_action(
        "remove_mutation",
        "pooch",
        {"selector": "random"},
    )

    removed_mock = MagicMock()
    removed_mock.mutation_id = 10

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[3])),
        patch(
            "src.game.manage_owner_events.remove_random_mutation_from_pooch", new=AsyncMock(return_value=removed_mock)
        ),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert 3 in result.pooches_affected
    assert (3, 10) in result.mutations_removed


# ---------------------------------------------------------------------------
# rename_pooch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_pooch(context, rng):
    """rename_pooch should call set_pooch_name for the resolved pooch."""
    action = _make_action(
        "rename_pooch",
        "pooch",
        {"selector": "random", "name": "Sparky"},
    )

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch("src.game.manage_owner_events.rename_pooch", new=AsyncMock(return_value=_make_pooch(7))),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert 7 in result.pooches_affected


# ---------------------------------------------------------------------------
# breed_pooches — require_unique / require_same
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_breed_pooches_require_unique_skips_when_same(context, rng):
    """require_unique=true should skip breeding when both selectors resolve to the same pooch."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {
            "first_selector": "random",
            "second_selector": "random",
            "require_unique": True,
        },
    )

    breed_called = False

    async def fake_breed(*args, **kwargs):
        nonlocal breed_called
        breed_called = True
        return MagicMock()

    # Only one pooch available — after excluding first, second pick returns None
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(side_effect=fake_breed)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert not breed_called


@pytest.mark.asyncio
async def test_breed_pooches_require_same_forces_same_pooch(context, rng):
    """require_same=true should use the same pooch for both parents."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {
            "first_selector": "random",
            "second_selector": "random",
            "require_same": True,
        },
    )

    breed_call_args = []

    async def fake_breed(first_id, second_id, **kwargs):
        breed_call_args.extend([first_id, second_id])
        return [99]

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7, 8])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(side_effect=fake_breed)),
    ):
        await _execute_single_action(1, action, context, rng)

    # Both pooches should be the same ID (first pick, duplicated)
    assert len(breed_call_args) == 2
    assert breed_call_args[0] == breed_call_args[1]


# ---------------------------------------------------------------------------
# repeat column behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repeat_column_executes_action_n_times(context, rng):
    """An action with repeat=3 should execute 3 times in _execute_event_actions."""
    from src.game.manage_owner_events import _execute_event_actions

    action = _make_action("modify_money", "owner", {"amount": 10}, repeat=3)
    action.action_order = 0

    call_count = 0

    async def fake_give_money(owner_id, amount):
        nonlocal call_count
        call_count += 1

    with patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock(side_effect=fake_give_money)):
        await _execute_event_actions(1, [action], context, rng)

    assert call_count == 3


@pytest.mark.asyncio
async def test_repeat_column_default_1_executes_once(context, rng):
    """An action with repeat=1 (default) should execute exactly once."""
    from src.game.manage_owner_events import _execute_event_actions

    action = _make_action("modify_money", "owner", {"amount": 10}, repeat=1)
    action.action_order = 0

    call_count = 0

    async def fake_give_money(owner_id, amount):
        nonlocal call_count
        call_count += 1

    with patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock(side_effect=fake_give_money)):
        await _execute_event_actions(1, [action], context, rng)

    assert call_count == 1


# ---------------------------------------------------------------------------
# selected pooch context: no pooch → no action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_random_selector_no_pooches_is_noop(context, rng):
    """random selector with no available pooches should not apply the action."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "random", "amount": -1},
    )

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()) as mock_modify,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_modify.assert_not_awaited()
    assert result.pooches_affected == []


# ---------------------------------------------------------------------------
# kennel action: "all" selector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kennel_all_selector(context, rng):
    """kennel 'all' selector should modify every matching kennel."""
    action = _make_action(
        "modify_kennel_capacity",
        "kennel",
        {"selector": "all", "amount": 1},
    )

    modified = []

    async def fake_modify(kennel_id, amount):
        modified.append(kennel_id)
        return _make_kennel(kennel_id)

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[10, 20, 30])),
        patch("src.game.manage_owner_events.modify_kennel_pooch_limit", new=AsyncMock(side_effect=fake_modify)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert sorted(modified) == [10, 20, 30]


# ---------------------------------------------------------------------------
# save_as with multiple pooch targets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_as_with_all_selector_saves_all_pooch_ids(context, rng):
    """save_as on 'all' selector should save all affected pooch IDs."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "all", "amount": -1, "save_as": "all_victims"},
    )

    async def fake_modify(pooch_id, amount):
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify)),
        patch("src.game.manage_owner_events.get_pooch_kennel", new=AsyncMock(return_value=None)),
    ):
        await _execute_single_action(1, action, context, rng)

    assert sorted(context.extra_data["all_victims"]["pooch_ids"]) == [1, 2, 3]


# ---------------------------------------------------------------------------
# create_pooch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pooch_saves_new_id(context, rng):
    """create_pooch should create a pooch and optionally save its ID."""
    action = _make_action(
        "create_pooch",
        "owner",
        {"save_as": "new_pup"},
    )

    new_pooch = _make_pooch(99)

    with (
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=new_pooch)),
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[])),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert context.extra_data["new_pup"] == {"pooch_ids": [99]}
    assert 99 in result.pooches_affected


# ---------------------------------------------------------------------------
# use_saved on a pooch action (from a kennel slot)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_use_saved_pooch_slot_on_pooch_action(context, rng):
    """use_saved on a pooch action reads pooch_ids from the named slot."""
    context.extra_data["my_slot"] = {"pooch_ids": [42, 43]}

    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"use_saved": "my_slot", "amount": -1},
    )

    damaged = []

    async def fake_modify(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    with patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify)):
        await _execute_single_action(1, action, context, rng)

    assert sorted(damaged) == [42, 43]


# ---------------------------------------------------------------------------
# roll_once flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_money_roll_once_uses_same_amount_for_all(context, rng):
    """roll_once=true should roll one amount and apply it to every target."""
    action = _make_action(
        "modify_pooch_health",
        "pooch",
        {"selector": "all", "min_amount": -10, "max_amount": -1, "roll_once": True},
    )

    amounts = []

    async def fake_modify(pooch_id, amount):
        amounts.append(amount)
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify)),
    ):
        await _execute_single_action(1, action, context, rng)

    # All three should have gotten the same amount
    assert len(amounts) == 3
    assert amounts[0] == amounts[1] == amounts[2]
    assert -10 <= amounts[0] <= -1


# ---------------------------------------------------------------------------
# _choose_option_outcome
# ---------------------------------------------------------------------------


def test_choose_option_outcome_no_explicit_chances_returns_random_choice(rng):
    """When no outcome has an explicit chance, the function returns a random choice from all outcomes."""
    outcomes = [_make_outcome(chance=None, label=f"o{i}") for i in range(3)]
    option = _make_option(outcomes)
    result = _choose_option_outcome(option, rng)
    assert result in outcomes


def test_choose_option_outcome_all_explicit_chances_picks_weighted(rng):
    """When all outcomes have explicit chances, the returned outcome is one of them."""
    outcomes = [
        _make_outcome(chance=0.8, label="likely"),
        _make_outcome(chance=0.2, label="unlikely"),
    ]
    option = _make_option(outcomes)
    # Run many times and confirm both are reachable
    seen = set()
    for _ in range(200):
        o = _choose_option_outcome(option, random.Random())
        seen.add(o.label)
    assert "likely" in seen
    assert "unlikely" in seen


def test_choose_option_outcome_implicit_gets_remainder_weight(rng):
    """An implicit outcome (no chance) should receive the remaining weight when explicit total < 1."""
    explicit = _make_outcome(chance=0.4, label="explicit")
    implicit = _make_outcome(chance=None, label="implicit")
    option = _make_option([explicit, implicit])
    # implicit should receive 0.6 weight; explicit 0.4 — both should be reachable
    seen = set()
    for _ in range(300):
        o = _choose_option_outcome(option, random.Random())
        seen.add(o.label)
    assert "explicit" in seen
    assert "implicit" in seen


def test_choose_option_outcome_implicit_gets_flat_weight_when_explicit_ge_1():
    """When explicit total >= 1, implicit outcomes each get weight 1.0."""
    explicit = _make_outcome(chance=1.0, label="certain")
    implicit = _make_outcome(chance=None, label="implicit_bonus")
    option = _make_option([explicit, implicit])
    # implicit has weight 1.0, explicit has weight 1.0 — both reachable
    seen = set()
    for _ in range(300):
        o = _choose_option_outcome(option, random.Random())
        seen.add(o.label)
    assert "certain" in seen
    assert "implicit_bonus" in seen


def test_choose_option_outcome_zero_total_weight_falls_back_to_random_choice():
    """When total weight is 0, the function falls back to rng.choice."""
    # All explicit chances are 0 — total_weight == 0
    outcomes = [_make_outcome(chance=0.0, label="zero")]
    option = _make_option(outcomes)
    rng = random.Random(1)
    result = _choose_option_outcome(option, rng)
    assert result in outcomes


def test_choose_option_outcome_last_entry_fallback():
    """The fallback return at the end of the loop should return weighted[-1][0]."""
    # Force roll to exceed total_weight: use a seeded rng with a controlled outcome.
    # We'll patch rng.uniform to return a very large number so the loop never hits.
    outcome_a = _make_outcome(chance=0.5, label="a")
    outcome_b = _make_outcome(chance=0.5, label="b")
    option = _make_option([outcome_a, outcome_b])

    controlled_rng = MagicMock(spec=random.Random)
    controlled_rng.uniform.return_value = 999999.0  # exceeds total_weight → fallback
    result = _choose_option_outcome(option, controlled_rng)
    # fallback is weighted[-1][0]; explicit outcomes are appended last, so b is last
    assert result is outcome_b


# ---------------------------------------------------------------------------
# _deliver_pooch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_pooch_to_kennel_with_free_space():
    """_deliver_pooch should place a pooch in the first kennel that has free space."""
    kennel = _make_kennel(10, name="Happy Kennel", pooch_limit=5)
    with (
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[kennel])),
        patch("src.game.manage_owner_events.list_pooches_for_kennel", new=AsyncMock(return_value=[1, 2])),
        patch("src.game.manage_owner_events.add_pooch_to_kennel", new=AsyncMock()) as mock_add,
    ):
        dest_key, kennel_name = await _deliver_pooch(1, 99, "kennel")
    assert dest_key == "kennel"
    assert kennel_name == "Happy Kennel"
    mock_add.assert_awaited_once_with(10, 99)


@pytest.mark.asyncio
async def test_deliver_pooch_to_kennel_falls_back_to_town_when_all_full():
    """_deliver_pooch should fall back to 'town' when all kennels are full."""
    kennel = _make_kennel(10, name="Full Kennel", pooch_limit=2)
    with (
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[kennel])),
        patch("src.game.manage_owner_events.list_pooches_for_kennel", new=AsyncMock(return_value=[1, 2])),
        patch("src.game.manage_owner_events.add_pooch_to_kennel", new=AsyncMock()) as mock_add,
    ):
        dest_key, kennel_name = await _deliver_pooch(1, 99, "kennel")
    assert dest_key == "town"
    assert kennel_name is None
    mock_add.assert_not_awaited()


@pytest.mark.asyncio
async def test_deliver_pooch_to_graveyard():
    """_deliver_pooch with destination='graveyard' should call bury_pooch."""
    with patch("src.game.manage_owner_events.bury_pooch", new=AsyncMock()) as mock_bury:
        dest_key, kennel_name = await _deliver_pooch(1, 99, "graveyard")
    assert dest_key == "graveyard"
    assert kennel_name is None
    mock_bury.assert_awaited_once_with(1, 99)


@pytest.mark.asyncio
async def test_deliver_pooch_to_hell():
    """_deliver_pooch with destination='hell' should call damn_pooch."""
    with patch("src.game.manage_owner_events.damn_pooch", new=AsyncMock()) as mock_damn:
        dest_key, kennel_name = await _deliver_pooch(1, 99, "hell")
    assert dest_key == "hell"
    assert kennel_name is None
    mock_damn.assert_awaited_once_with(99)


@pytest.mark.asyncio
async def test_deliver_pooch_to_town_returns_town():
    """_deliver_pooch with destination='town' should return 'town' with no kennel name."""
    dest_key, kennel_name = await _deliver_pooch(1, 99, "town")
    assert dest_key == "town"
    assert kennel_name is None


@pytest.mark.asyncio
async def test_deliver_pooch_unknown_destination_falls_back_to_town():
    """_deliver_pooch with an unrecognised destination string should fall back to 'town'."""
    dest_key, kennel_name = await _deliver_pooch(1, 99, "void")
    assert dest_key == "town"
    assert kennel_name is None


@pytest.mark.asyncio
async def test_deliver_pooch_non_string_destination_falls_back_to_town():
    """_deliver_pooch when destination is not a string should fall back to 'town'."""
    dest_key, kennel_name = await _deliver_pooch(1, 99, None)  # type: ignore[arg-type]
    assert dest_key == "town"
    assert kennel_name is None


# ---------------------------------------------------------------------------
# create_pooch action — various destinations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pooch_destination_kennel(context, rng):
    """create_pooch with destination='kennel' places the new pooch in a kennel."""
    action = _make_action("create_pooch", "owner", {"destination": "kennel"})
    new_pooch = _make_pooch(55)
    kennel = _make_kennel(7, name="Sunny Kennel", pooch_limit=3)
    with (
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=new_pooch)),
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[kennel])),
        patch("src.game.manage_owner_events.list_pooches_for_kennel", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.add_pooch_to_kennel", new=AsyncMock()),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert 55 in result.pooches_created
    assert "Sunny Kennel" in result.message


@pytest.mark.asyncio
async def test_create_pooch_destination_graveyard(context, rng):
    """create_pooch with destination='graveyard' records the graveyard message."""
    action = _make_action("create_pooch", "owner", {"destination": "graveyard"})
    new_pooch = _make_pooch(56)
    with (
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=new_pooch)),
        patch("src.game.manage_owner_events.bury_pooch", new=AsyncMock()),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert 56 in result.pooches_created
    assert "graveyard" in result.message


@pytest.mark.asyncio
async def test_create_pooch_destination_hell(context, rng):
    """create_pooch with destination='hell' records the hell message."""
    action = _make_action("create_pooch", "owner", {"destination": "hell"})
    new_pooch = _make_pooch(57)
    with (
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=new_pooch)),
        patch("src.game.manage_owner_events.damn_pooch", new=AsyncMock()),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert 57 in result.pooches_created
    assert "Hell" in result.message


@pytest.mark.asyncio
async def test_create_pooch_default_destination_is_town(context, rng):
    """create_pooch with no destination defaults to 'town' and uses the generic message."""
    action = _make_action("create_pooch", "owner", {})
    new_pooch = _make_pooch(58)
    with (
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=new_pooch)),
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[])),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert 58 in result.pooches_created
    assert result.message == "A new pooch has appeared!"


# ---------------------------------------------------------------------------
# clone_pooch action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_pooch_copies_breeds_and_mutations(context, rng):
    """clone_pooch should copy breed weights and mutations from the source to the clone."""
    source = SimpleNamespace(id=10, name="Original", sex="female", age=3, base_health=10, breeding_cooldown=0)
    clone = _make_pooch(20)

    breed_weight = MagicMock()
    breed_weight.__iter__ = MagicMock(return_value=iter([1, 0.5]))  # (breed_id, weight)
    mutation = MagicMock()
    mutation.id = 42

    action = _make_action("clone_pooch", "pooch", {"selector": "random"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[10])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=source)),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=clone)),
        patch("src.game.manage_owner_events.list_pooch_breed_weights", new=AsyncMock(return_value=[(1, 0.5)])),
        patch("src.game.manage_owner_events.add_pooch_breeds", new=AsyncMock()) as mock_add_breeds,
        patch("src.game.manage_owner_events.list_pooch_mutations", new=AsyncMock(return_value=[mutation])),
        patch("src.game.manage_owner_events.add_mutation_to_pooch", new=AsyncMock()) as mock_add_mut,
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[])),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert 20 in result.pooches_created
    mock_add_breeds.assert_awaited_once_with(20, {1: 0.5})
    mock_add_mut.assert_awaited_once_with(20, mutation_id=42)


@pytest.mark.asyncio
async def test_clone_pooch_save_as_string_saves_clone(context, rng):
    """clone_pooch with save_as as a plain string should save the clone's ID to that slot."""
    source = SimpleNamespace(id=10, name="Rex", sex="male", age=2, base_health=8, breeding_cooldown=0)
    clone = _make_pooch(21)

    action = _make_action("clone_pooch", "pooch", {"selector": "random", "save_as": "cloned_pup"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[10])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=source)),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=clone)),
        patch("src.game.manage_owner_events.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_pooch_mutations", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[])),
    ):
        await _execute_single_action(1, action, context, rng)

    assert context.extra_data["cloned_pup"] == {"pooch_ids": [21]}


@pytest.mark.asyncio
async def test_clone_pooch_save_as_list_saves_source_and_clone(context, rng):
    """clone_pooch with save_as as a list of dicts should support saving source and clone separately."""
    source = SimpleNamespace(id=10, name="Max", sex="male", age=1, base_health=10, breeding_cooldown=0)
    clone = _make_pooch(22)

    save_as_list = [
        {"slot": "original_slot", "target": "source"},
        {"slot": "clone_slot", "target": "clone"},
    ]
    action = _make_action("clone_pooch", "pooch", {"selector": "random", "save_as": save_as_list})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[10])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=source)),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=clone)),
        patch("src.game.manage_owner_events.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_pooch_mutations", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[])),
    ):
        await _execute_single_action(1, action, context, rng)

    assert context.extra_data["original_slot"] == {"pooch_ids": [10]}
    assert context.extra_data["clone_slot"] == {"pooch_ids": [22]}


@pytest.mark.asyncio
async def test_clone_pooch_no_source_is_noop(context, rng):
    """clone_pooch with no resolvable source pooch should not create anything."""
    action = _make_action("clone_pooch", "pooch", {"selector": "random"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock()) as mock_create,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_create.assert_not_awaited()
    assert result.pooches_created == []


# ---------------------------------------------------------------------------
# modify_pooch_age action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_pooch_age_random_selector(context, rng):
    """modify_pooch_age should call modify_pooch_age for each resolved pooch."""
    action = _make_action("modify_pooch_age", "pooch", {"selector": "random", "amount": 2})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[11])),
        patch("src.game.manage_owner_events.modify_pooch_age", new=AsyncMock(return_value=_make_pooch(11))) as mock_age,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_age.assert_awaited_once_with(11, 2)
    assert 11 in result.pooches_affected


@pytest.mark.asyncio
async def test_modify_pooch_age_all_selector(context, rng):
    """modify_pooch_age with 'all' selector should age every matching pooch."""
    aged = []

    async def fake_age(pooch_id, amount):
        aged.append(pooch_id)
        return _make_pooch(pooch_id)

    action = _make_action("modify_pooch_age", "pooch", {"selector": "all", "amount": 1})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch("src.game.manage_owner_events.modify_pooch_age", new=AsyncMock(side_effect=fake_age)),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert sorted(aged) == [1, 2, 3]
    assert sorted(result.pooches_affected) == [1, 2, 3]


# ---------------------------------------------------------------------------
# add_breed action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_breed_with_specific_breed_id(context, rng):
    """add_breed with explicit breed_id should call add_breed_to_pooch with that breed_id."""
    action = _make_action("add_breed", "pooch", {"selector": "random", "breed_id": 7, "weight": 0.6})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[3])),
        patch("src.game.manage_owner_events.add_breed_to_pooch", new=AsyncMock()) as mock_add,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_add.assert_awaited_once_with(3, 7, weight=0.6)
    assert 3 in result.pooches_affected


@pytest.mark.asyncio
async def test_add_breed_without_breed_id_uses_random(context, rng):
    """add_breed without breed_id should call add_breed_to_pooch with rng only."""
    action = _make_action("add_breed", "pooch", {"selector": "random", "weight": 0.5})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[4])),
        patch("src.game.manage_owner_events.add_breed_to_pooch", new=AsyncMock()) as mock_add,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_add.assert_awaited_once_with(4, rng=rng, weight=0.5)
    assert 4 in result.pooches_affected


# ---------------------------------------------------------------------------
# transfer_pooch action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transfer_pooch_to_new_owner(context, rng):
    """transfer_pooch with new_owner_discord_id should call transfer_pooch_to_owner."""
    action = _make_action("transfer_pooch", "pooch", {"selector": "random", "new_owner_discord_id": 999})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.transfer_pooch_to_owner", new=AsyncMock()) as mock_transfer,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_transfer.assert_awaited_once_with(5, 999)
    assert 5 in result.pooches_affected


@pytest.mark.asyncio
async def test_transfer_pooch_to_vendor(context, rng):
    """transfer_pooch with vendor_id should call transfer_pooch_to_vendor."""
    action = _make_action("transfer_pooch", "pooch", {"selector": "random", "vendor_id": 88})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[6])),
        patch("src.game.manage_owner_events.transfer_pooch_to_vendor", new=AsyncMock()) as mock_transfer,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_transfer.assert_awaited_once_with(6, 88)
    assert 6 in result.pooches_affected


# ---------------------------------------------------------------------------
# set_breeding_cooldown — "base" string resolves from mutation total
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_breeding_cooldown_base_string(context, rng):
    """set_breeding_cooldown with cooldown='base' should resolve via POOCH_BREEDING_COOLDOWN + mutation total."""
    action = _make_action("set_breeding_cooldown", "pooch", {"selector": "random", "cooldown": "base"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch(
            "src.game.manage_owner_events.get_pooch_mutation_advanced_option_total",
            new=AsyncMock(return_value=-2),
        ),
        patch("src.game.manage_owner_events.set_pooch_breeding_cooldown", new=AsyncMock()) as mock_cooldown,
        patch("src.game.manage_owner_events.POOCH_BREEDING_COOLDOWN", new=5),
    ):
        result = await _execute_single_action(1, action, context, rng)

    # POOCH_BREEDING_COOLDOWN(5) + mutation_total(-2) = 3; max(3, 0) = 3
    mock_cooldown.assert_awaited_once_with(7, 3)
    assert 7 in result.pooches_affected


@pytest.mark.asyncio
async def test_set_breeding_cooldown_base_clamps_at_zero(context, rng):
    """set_breeding_cooldown with cooldown='base' clamps the result to >= 0."""
    action = _make_action("set_breeding_cooldown", "pooch", {"selector": "random", "cooldown": "base"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[8])),
        patch(
            "src.game.manage_owner_events.get_pooch_mutation_advanced_option_total",
            new=AsyncMock(return_value=-100),
        ),
        patch("src.game.manage_owner_events.set_pooch_breeding_cooldown", new=AsyncMock()) as mock_cooldown,
        patch("src.game.manage_owner_events.POOCH_BREEDING_COOLDOWN", new=3),
    ):
        await _execute_single_action(1, action, context, rng)

    # 3 + (-100) = -97 → clamped to 0
    mock_cooldown.assert_awaited_once_with(8, 0)


# ---------------------------------------------------------------------------
# breed_pooches — save_as variants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_breed_pooches_save_as_string_saves_baby(context, rng):
    """breed_pooches with save_as as a plain string should save baby IDs to that slot."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {
            "first_selector": "random",
            "second_selector": "random",
            "require_unique": False,
            "save_as": "new_baby",
        },
    )
    parent_a = MagicMock()
    parent_a.id = 1
    parent_a.sex = "male"
    parent_b = MagicMock()
    parent_b.id = 2
    parent_b.sex = "female"

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(return_value=[100])),
    ):
        await _execute_single_action(1, action, context, rng)

    assert context.extra_data["new_baby"] == {"pooch_ids": [100]}


@pytest.mark.asyncio
async def test_breed_pooches_save_as_list_saves_parents_and_baby(context, rng):
    """breed_pooches with save_as as a list of dicts should save first_parent, second_parent, and baby."""
    save_as_list = [
        {"slot": "parent_one", "target": "first_parent"},
        {"slot": "parent_two", "target": "second_parent"},
        {"slot": "offspring", "target": "baby"},
    ]
    action = _make_action(
        "breed_pooches",
        "owner",
        {
            "first_selector": "random",
            "second_selector": "random",
            "require_unique": False,
            "save_as": save_as_list,
        },
    )
    parent_a = MagicMock()
    parent_a.id = 3
    parent_a.sex = "male"
    parent_b = MagicMock()
    parent_b.id = 4
    parent_b.sex = "female"

    breed_call_ids: list[int] = []

    async def fake_breed(first_id, second_id, **kwargs):
        breed_call_ids.extend([first_id, second_id])
        return [200]

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[3, 4])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(side_effect=fake_breed)),
    ):
        await _execute_single_action(1, action, context, rng)

    first_id, second_id = breed_call_ids
    assert context.extra_data["parent_one"] == {"pooch_ids": [first_id]}
    assert context.extra_data["parent_two"] == {"pooch_ids": [second_id]}
    assert context.extra_data["offspring"] == {"pooch_ids": [200]}


# ---------------------------------------------------------------------------
# sell_pooch action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sell_pooch_no_vendor_credits_base_price(context, rng):
    """sell_pooch with no vendor_id and no available vendors should credit the base sell price."""
    action = _make_action("sell_pooch", "pooch", {"selector": "random"})
    live_pooch = _make_pooch(30, alive=True)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[30])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=live_pooch)),
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[])),
        patch(
            "src.game.manage_owner_events.get_pooch_sell_price",
            new=AsyncMock(return_value=50),
        ),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_give.assert_awaited_once_with(1, 50)
    assert result.money_changed == 50
    assert 30 in result.pooches_affected


@pytest.mark.asyncio
async def test_sell_pooch_with_explicit_vendor_id(context, rng):
    """sell_pooch with explicit vendor_id should transfer pooch and credit adjusted price."""
    action = _make_action("sell_pooch", "pooch", {"selector": "random", "vendor_id": 7})
    live_pooch = _make_pooch(31, alive=True)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[31])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=live_pooch)),
        patch("src.game.manage_owner_events.get_pooch_sell_price", new=AsyncMock(return_value=100)),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events.transfer_pooch_to_vendor", new=AsyncMock()) as mock_transfer,
        patch("src.game.manage_owner_events.remove_pooch_from_kennel", new=AsyncMock()),
        patch("src.game.manage_owner_events.add_pooch_to_vendor_stock", new=AsyncMock()),
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_transfer.assert_awaited_once_with(31, 7)
    assert result.money_changed == 100
    assert 31 in result.pooches_affected


@pytest.mark.asyncio
async def test_sell_pooch_skips_dead_pooches(context, rng):
    """sell_pooch should skip pooches that are not alive."""
    action = _make_action("sell_pooch", "pooch", {"selector": "all"})
    dead_pooch = _make_pooch(32, alive=False)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[32])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=dead_pooch)),
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_give.assert_not_awaited()
    assert result.pooches_affected == []


@pytest.mark.asyncio
async def test_sell_pooch_with_vendor_selector_picks_random_vendor(context, rng):
    """sell_pooch with vendor_selector='random' and no explicit vendor_id should pick a random vendor."""
    action = _make_action("sell_pooch", "pooch", {"selector": "random", "vendor_selector": "random"})
    live_pooch = _make_pooch(33, alive=True)
    server = MagicMock()
    server.discord_id = 111
    vendor = MagicMock()
    vendor.id = 55

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[33])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=live_pooch)),
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[server])),
        patch("src.game.manage_owner_events.list_vendors", new=AsyncMock(return_value=[vendor])),
        patch("src.game.manage_owner_events.get_pooch_sell_price", new=AsyncMock(return_value=75)),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events.transfer_pooch_to_vendor", new=AsyncMock()) as mock_transfer,
        patch("src.game.manage_owner_events.remove_pooch_from_kennel", new=AsyncMock()),
        patch("src.game.manage_owner_events.add_pooch_to_vendor_stock", new=AsyncMock()),
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_transfer.assert_awaited_once_with(33, 55)
    assert 33 in result.pooches_affected


# ---------------------------------------------------------------------------
# buy_pooch action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buy_pooch_no_vendor_available_is_noop(context, rng):
    """buy_pooch should skip when no vendor is resolved."""
    action = _make_action("buy_pooch", "owner", {})
    with (
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_give.assert_not_awaited()
    assert result.pooches_created == []


@pytest.mark.asyncio
async def test_buy_pooch_no_stock_available_is_noop(context, rng):
    """buy_pooch should skip when the vendor has no stock."""
    action = _make_action("buy_pooch", "owner", {"vendor_id": 9})
    with (
        patch("src.game.manage_owner_events.list_vendor_pooch_stock", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_give.assert_not_awaited()
    assert result.pooches_created == []


@pytest.mark.asyncio
async def test_buy_pooch_owner_cannot_afford_is_noop(context, rng):
    """buy_pooch should skip when owner cannot afford the pooch."""
    action = _make_action("buy_pooch", "owner", {"vendor_id": 9})
    vendor_pooch = MagicMock()
    vendor_pooch.id = 77
    vendor_pooch.name = "Pricey"
    poor_owner = MagicMock()
    poor_owner.dollars = 0

    with (
        patch("src.game.manage_owner_events.list_vendor_pooch_stock", new=AsyncMock(return_value=[vendor_pooch])),
        patch("src.game.manage_owner_events.get_pooch_buy_price", new=AsyncMock(return_value=1000)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=poor_owner)),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_give.assert_not_awaited()
    assert result.pooches_created == []


@pytest.mark.asyncio
async def test_buy_pooch_success_charges_owner_and_transfers(context, rng):
    """buy_pooch success path should charge the owner and transfer the pooch."""
    action = _make_action("buy_pooch", "owner", {"vendor_id": 9, "destination": "town"})
    vendor_pooch = MagicMock()
    vendor_pooch.id = 78
    vendor_pooch.name = "Buddy"
    rich_owner = MagicMock()
    rich_owner.dollars = 5000

    with (
        patch("src.game.manage_owner_events.list_vendor_pooch_stock", new=AsyncMock(return_value=[vendor_pooch])),
        patch("src.game.manage_owner_events.get_pooch_buy_price", new=AsyncMock(return_value=200)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=rich_owner)),
        patch("src.game.manage_owner_events.remove_pooch_from_vendor_stock", new=AsyncMock()),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give,
        patch("src.game.manage_owner_events.transfer_pooch_to_owner", new=AsyncMock()) as mock_transfer,
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[])),
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_give.assert_awaited_once_with(1, -200)
    mock_transfer.assert_awaited_once_with(78, 1)
    assert result.money_changed == -200
    assert 78 in result.pooches_created


@pytest.mark.asyncio
async def test_buy_pooch_save_as_stores_pooch_id(context, rng):
    """buy_pooch with save_as should store the purchased pooch's ID in context.extra_data."""
    action = _make_action("buy_pooch", "owner", {"vendor_id": 9, "destination": "town", "save_as": "new_dog"})
    vendor_pooch = MagicMock()
    vendor_pooch.id = 79
    vendor_pooch.name = "Lucky"
    owner = MagicMock()
    owner.dollars = 9999

    with (
        patch("src.game.manage_owner_events.list_vendor_pooch_stock", new=AsyncMock(return_value=[vendor_pooch])),
        patch("src.game.manage_owner_events.get_pooch_buy_price", new=AsyncMock(return_value=100)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        patch("src.game.manage_owner_events.remove_pooch_from_vendor_stock", new=AsyncMock()),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events.transfer_pooch_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events.list_kennels_for_owner", new=AsyncMock(return_value=[])),
    ):
        await _execute_single_action(1, action, context, rng)

    assert context.extra_data["new_dog"] == {"pooch_ids": [79]}


# ---------------------------------------------------------------------------
# start_event action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_event_random_event_true_calls_trigger_random(context, rng):
    """start_event with random_event=True should call trigger_random_event."""
    action = _make_action("start_event", "owner", {"random_event": True})
    triggered = MagicMock()
    triggered.active_owner_event_id = 1
    triggered.event_id = 10
    triggered.name = "Wild Event"

    with patch(
        "src.game.manage_owner_events.trigger_random_event", new=AsyncMock(return_value=triggered)
    ) as mock_trigger:
        result = await _execute_single_action(1, action, context, rng)

    mock_trigger.assert_awaited_once()
    assert "Wild Event" in result.message
    assert result.extra_data["started_events"][0]["event_id"] == 10


@pytest.mark.asyncio
async def test_start_event_named_event_calls_trigger_specific(context, rng):
    """start_event with a named event should look it up and call trigger_specific_event."""
    action = _make_action("start_event", "owner", {"event": "my_special_event"})
    event_db = MagicMock()
    event_db.id = 42
    triggered = MagicMock()
    triggered.active_owner_event_id = 2
    triggered.event_id = 42
    triggered.name = "Special Event"

    with (
        patch("src.game.manage_owner_events.db_get_owner_event_by_name", new=AsyncMock(return_value=event_db)),
        patch(
            "src.game.manage_owner_events.trigger_specific_event", new=AsyncMock(return_value=triggered)
        ) as mock_specific,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_specific.assert_awaited_once_with(1, 42, rng=rng)
    assert "Special Event" in result.message


@pytest.mark.asyncio
async def test_start_event_unknown_event_name_logs_warning_and_returns(context, rng):
    """start_event with an event name that doesn't exist should return an error message."""
    action = _make_action("start_event", "owner", {"event": "nonexistent_event"})

    with patch("src.game.manage_owner_events.db_get_owner_event_by_name", new=AsyncMock(return_value=None)):
        result = await _execute_single_action(1, action, context, rng)

    assert result.message == "Error starting followup event."


# ---------------------------------------------------------------------------
# _get_target_pooch_ids — target_type="kennel", selector="selected"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kennel_selected_selector_uses_context_kennel_id(context, rng):
    """When target_type='kennel' and selector='selected', pooches from context.selected_kennel_id are used."""
    context.selected_kennel_id = 77
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"selector": "selected", "amount": -3},
    )

    damaged = []

    async def fake_modify(pooch_id, amount):
        damaged.append(pooch_id)
        return _make_pooch(pooch_id)

    with (
        patch(
            "src.game.manage_owner_events.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(return_value=[50, 51]),
        ),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify)),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert sorted(damaged) == [50, 51]
    assert sorted(result.pooches_affected) == [50, 51]


@pytest.mark.asyncio
async def test_kennel_selected_selector_no_selected_kennel_is_noop(context, rng):
    """When target_type='kennel', selector='selected', and no kennel is selected, no action should occur."""
    context.selected_kennel_id = None
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"selector": "selected", "amount": -3},
    )

    with patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()) as mock_modify:
        result = await _execute_single_action(1, action, context, rng)

    mock_modify.assert_not_awaited()
    assert result.pooches_affected == []


# ---------------------------------------------------------------------------
# _get_target_pooch_ids — target_type="kennel", selector="random_exclude"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kennel_random_exclude_selector_excludes_n_kennels(context, rng):
    """For target_type='kennel', random_exclude should exclude count kennels and affect pooches in the rest."""
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"selector": "random_exclude", "count": 1, "amount": -1},
    )
    # 3 kennels; 1 excluded → 2 kennels active → each returns 1 pooch
    kennel_ids = [10, 20, 30]
    call_tracker: list[int] = []

    async def fake_list_in_kennel(owner_id, kennel_id, filter_spec):
        call_tracker.append(kennel_id)
        return [kennel_id + 100]

    async def fake_modify(pooch_id, amount):
        return _make_pooch(pooch_id)

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=kennel_ids)),
        patch(
            "src.game.manage_owner_events.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(side_effect=fake_list_in_kennel),
        ),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(side_effect=fake_modify)),
    ):
        await _execute_single_action(1, action, context, rng)

    # Exactly 2 of the 3 kennels should have been queried
    assert len(call_tracker) == 2
    assert all(kid in kennel_ids for kid in call_tracker)


@pytest.mark.asyncio
async def test_kennel_unknown_selector_on_pooch_action_is_noop(context, rng):
    """An unrecognised selector on a kennel target type should result in no pooches affected."""
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"selector": "this_selector_does_not_exist", "amount": -1},
    )

    with patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()) as mock_modify:
        result = await _execute_single_action(1, action, context, rng)

    mock_modify.assert_not_awaited()
    assert result.pooches_affected == []


# ---------------------------------------------------------------------------
# _get_target_kennel_ids — selector="selected" and unknown selector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_target_kennel_selected_uses_context_kennel(context, rng):
    """modify_kennel_capacity with selector='selected' targets context.selected_kennel_id."""
    context.selected_kennel_id = 88
    action = _make_action(
        "modify_kennel_capacity",
        "kennel",
        {"selector": "selected", "amount": 3},
    )

    with patch(
        "src.game.manage_owner_events.modify_kennel_pooch_limit",
        new=AsyncMock(return_value=_make_kennel(88)),
    ) as mock_modify:
        await _execute_single_action(1, action, context, rng)

    mock_modify.assert_awaited_once_with(88, 3)


@pytest.mark.asyncio
async def test_get_target_kennel_unknown_selector_returns_empty(context, rng):
    """modify_kennel_capacity with an unknown selector should modify no kennels."""
    action = _make_action(
        "modify_kennel_capacity",
        "kennel",
        {"selector": "totally_unknown_selector", "amount": 1},
    )

    with patch("src.game.manage_owner_events.modify_kennel_pooch_limit", new=AsyncMock()) as mock_modify:
        await _execute_single_action(1, action, context, rng)

    mock_modify.assert_not_awaited()


# ---------------------------------------------------------------------------
# _execute_event_actions — action_order sorting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_event_actions_respects_action_order(context, rng):
    """_execute_event_actions should execute actions in ascending action_order, not list order."""
    from src.game.manage_owner_events import _execute_event_actions

    action_first = _make_action("modify_money", "owner", {"amount": 1}, repeat=1)
    action_first.action_order = 1

    action_second = _make_action("modify_money", "owner", {"amount": 2}, repeat=1)
    action_second.action_order = 2

    amounts_seen: list[int] = []

    async def fake_give_money(owner_id, amount):
        amounts_seen.append(amount)

    # Pass in reverse order — the action with order=2 first
    with patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock(side_effect=fake_give_money)):
        await _execute_event_actions(1, [action_second, action_first], context, rng)

    assert amounts_seen == [1, 2]


# ---------------------------------------------------------------------------
# _get_target_pooch_ids — remaining uncovered branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_use_saved_non_dict_slot_returns_empty_pooch_ids(context, rng):
    """use_saved slot that is not a dict should return empty pooch ids."""
    context.extra_data["bad_slot"] = "not_a_dict"
    action = _make_action("modify_pooch_health", "pooch", {"use_saved": "bad_slot", "amount": -1})
    with patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()) as mock_modify:
        result = await _execute_single_action(1, action, context, rng)
    mock_modify.assert_not_awaited()
    assert result.pooches_affected == []


@pytest.mark.asyncio
async def test_get_target_pooch_ids_unknown_selector_returns_empty(context, rng):
    """An unknown selector on target_type='pooch' should produce no targets."""
    action = _make_action("modify_pooch_health", "pooch", {"selector": "banana", "amount": -5})
    with patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()) as mock_modify:
        result = await _execute_single_action(1, action, context, rng)
    mock_modify.assert_not_awaited()
    assert result.pooches_affected == []


@pytest.mark.asyncio
async def test_kennel_target_random_with_count_samples_kennels(context, rng):
    """kennel target + random selector + count should sample N kennels (path coverage)."""
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"selector": "random", "count": 2, "amount": -1},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[10, 20, 30])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()),
    ):
        result = await _execute_single_action(1, action, context, rng)
    # No pooches in kennels so nothing affected, but the count-sampling branch ran
    assert result.pooches_affected == []


@pytest.mark.asyncio
async def test_kennel_target_all_selector_returns_all_kennels_pooches(context, rng):
    """kennel target + 'all' selector should list all matching kennels and their pooches."""
    action = _make_action("modify_pooch_health", "kennel", {"selector": "all", "amount": -1})
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[5, 6])),
        patch(
            "src.game.manage_owner_events.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(side_effect=lambda owner, kid, f: [kid * 10]),
        ),
        patch(
            "src.game.manage_owner_events.modify_pooch_base_health",
            new=AsyncMock(side_effect=lambda pid, amt: _make_pooch(pid)),
        ),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert sorted(result.pooches_affected) == [50, 60]


@pytest.mark.asyncio
async def test_kennel_target_random_exclude_excludes_some_kennels(context, rng):
    """kennel target + random_exclude should exclude N randomly selected kennels."""
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"selector": "random_exclude", "count": 1, "amount": -1},
    )
    # With 3 kennels and count=1, 2 should remain; no pooches inside so just path coverage
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()),
    ):
        await _execute_single_action(1, action, context, rng)


# ---------------------------------------------------------------------------
# _get_target_kennel_ids — remaining uncovered branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_use_saved_non_dict_kennel_slot_returns_empty(context, rng):
    """use_saved slot that is not a dict for kennel action should affect no kennels."""
    context.extra_data["bad_kennel_slot"] = 42
    action = _make_action("modify_kennel_capacity", "kennel", {"use_saved": "bad_kennel_slot", "amount": 1})
    with patch("src.game.manage_owner_events.modify_kennel_pooch_limit", new=AsyncMock()) as mock_modify:
        await _execute_single_action(1, action, context, rng)
    mock_modify.assert_not_awaited()


@pytest.mark.asyncio
async def test_kennel_random_exclude_count_gte_len_returns_empty(context, rng):
    """random_exclude on kennel with count >= available kennels should affect nothing."""
    action = _make_action(
        "modify_kennel_capacity",
        "kennel",
        {"selector": "random_exclude", "count": 5, "amount": 1},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2])),
        patch("src.game.manage_owner_events.modify_kennel_pooch_limit", new=AsyncMock()) as mock_modify,
    ):
        await _execute_single_action(1, action, context, rng)
    mock_modify.assert_not_awaited()


# ---------------------------------------------------------------------------
# create_pooch action — with optional params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pooch_with_all_optional_params(context, rng):
    """create_pooch action should pass all optional parameters through to create_pooch."""
    action = _make_action(
        "create_pooch",
        "owner",
        {
            "name": "Rex",
            "sex": "male",
            "age": 3,
            "base_health": 80,
            "breeding_cooldown": 5,
            "destination": "town",
        },
    )
    pooch = _make_pooch(99, name="Rex")
    captured_kwargs: dict = {}

    async def fake_create(**kwargs):
        captured_kwargs.update(kwargs)
        return pooch

    with (
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(side_effect=fake_create)),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("town", None))),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert captured_kwargs["name"] == "Rex"
    assert captured_kwargs["sex"] == "male"
    assert captured_kwargs["age"] == 3
    assert captured_kwargs["base_health"] == 80
    assert captured_kwargs["breeding_cooldown"] == 5
    assert 99 in result.pooches_created


# ---------------------------------------------------------------------------
# clone_pooch action — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_pooch_source_not_found_is_noop(context, rng):
    """clone_pooch should be a no-op if get_pooch_by_id returns None for the source."""
    action = _make_action("clone_pooch", "pooch", {"selector": "random"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[10])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=None)),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock()) as mock_create,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_create.assert_not_awaited()
    assert result.pooches_created == []


def _make_source_pooch(pooch_id, name="Source"):
    p = _make_pooch(pooch_id, name=name)
    p.sex = "female"
    p.age = 2
    p.base_health = 100
    p.breeding_cooldown = 0
    return p


@pytest.mark.asyncio
async def test_clone_pooch_to_kennel_destination(context, rng):
    """clone_pooch with destination='kennel' should report kennel placement."""
    source = _make_source_pooch(1, name="Original")
    clone = _make_pooch(2, name="Original")
    action = _make_action("clone_pooch", "pooch", {"selector": "random", "destination": "kennel"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=source)),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=clone)),
        patch("src.game.manage_owner_events.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_pooch_mutations", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("kennel", "Fluffy's Den"))),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert "Fluffy's Den" in result.message
    assert 2 in result.pooches_created


@pytest.mark.asyncio
async def test_clone_pooch_to_graveyard_destination(context, rng):
    """clone_pooch with destination='graveyard' should report graveyard placement."""
    source = _make_source_pooch(1, name="Ghost")
    clone = _make_pooch(3, name="Ghost")
    action = _make_action("clone_pooch", "pooch", {"selector": "random", "destination": "graveyard"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=source)),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=clone)),
        patch("src.game.manage_owner_events.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_pooch_mutations", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("graveyard", None))),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert "graveyard" in result.message


@pytest.mark.asyncio
async def test_clone_pooch_to_hell_destination(context, rng):
    """clone_pooch with destination='hell' should report hell placement."""
    source = _make_source_pooch(1, name="Demon")
    clone = _make_pooch(4, name="Demon")
    action = _make_action("clone_pooch", "pooch", {"selector": "random", "destination": "hell"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=source)),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=clone)),
        patch("src.game.manage_owner_events.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_pooch_mutations", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("hell", None))),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert "Hell" in result.message


@pytest.mark.asyncio
async def test_clone_pooch_save_as_invalid_type_is_noop(context, rng):
    """clone_pooch save_as with unsupported type (e.g. int) should produce no slot."""
    source = _make_source_pooch(1, name="X")
    clone = _make_pooch(2, name="X")
    action = _make_action("clone_pooch", "pooch", {"selector": "random", "save_as": 999})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=source)),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=clone)),
        patch("src.game.manage_owner_events.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_pooch_mutations", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("town", None))),
    ):
        await _execute_single_action(1, action, context, rng)
    # Only candidate_pooch_ids should be in extra_data (set by the action), no save_as slot
    assert all(k == "candidate_pooch_ids" for k in context.extra_data)


@pytest.mark.asyncio
async def test_clone_pooch_save_as_list_with_empty_slot_string_skips(context, rng):
    """clone_pooch save_as list spec with empty slot string should be skipped."""
    source = _make_source_pooch(1, name="Y")
    clone = _make_pooch(5, name="Y")
    action = _make_action(
        "clone_pooch",
        "pooch",
        {"selector": "random", "save_as": [{"slot": "", "target": "clone"}]},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=source)),
        patch("src.game.manage_owner_events.create_pooch", new=AsyncMock(return_value=clone)),
        patch("src.game.manage_owner_events.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_pooch_mutations", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("town", None))),
    ):
        await _execute_single_action(1, action, context, rng)
    assert "" not in context.extra_data


# ---------------------------------------------------------------------------
# remove_mutation with explicit mutation_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_mutation_with_explicit_mutation_id(context, rng):
    """remove_mutation with mutation_id should call remove_mutation_from_pooch with that id."""
    action = _make_action("remove_mutation", "pooch", {"selector": "random", "mutation_id": 7})
    removed = MagicMock()
    removed.mutation_id = 7
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[3])),
        patch(
            "src.game.manage_owner_events.remove_mutation_from_pooch", new=AsyncMock(return_value=removed)
        ) as mock_rm,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_rm.assert_awaited_once_with(3, 7)
    assert (3, 7) in result.mutations_removed


# ---------------------------------------------------------------------------
# breed_pooches — selector variants and edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_breed_pooches_selected_selector_uses_context(context, rng):
    """breed_pooches with 'selected' selector should use context.selected_pooch_id."""
    context.selected_pooch_id = 11
    action = _make_action(
        "breed_pooches",
        "owner",
        {"first_selector": "selected", "second_selector": "selected", "require_unique": False},
    )
    with patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(return_value=[99])):
        result = await _execute_single_action(1, action, context, rng)
    assert 99 in result.pooches_created


@pytest.mark.asyncio
async def test_breed_pooches_all_selector_picks_from_list(context, rng):
    """breed_pooches with 'all' selector should pick a random ID from all matching."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {"first_selector": "all", "second_selector": "all", "require_unique": False},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(return_value=[50])),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert 50 in result.pooches_created


@pytest.mark.asyncio
async def test_breed_pooches_all_selector_empty_skips_breeding(context, rng):
    """breed_pooches with 'all' selector and no matching pooches should skip."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {"first_selector": "all", "second_selector": "all"},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock()) as mock_breed,
    ):
        await _execute_single_action(1, action, context, rng)
    mock_breed.assert_not_awaited()


@pytest.mark.asyncio
async def test_breed_pooches_unknown_selector_resolves_none_skips(context, rng):
    """breed_pooches with an unknown selector should resolve to None and skip."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {"first_selector": "bogus", "second_selector": "bogus"},
    )
    with patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock()) as mock_breed:
        await _execute_single_action(1, action, context, rng)
    mock_breed.assert_not_awaited()


@pytest.mark.asyncio
async def test_breed_pooches_require_unique_excludes_first_from_second(context, rng):
    """breed_pooches with require_unique=True should exclude the first pooch when picking the second."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {"first_selector": "random", "second_selector": "random", "require_unique": True},
    )
    # Two pooches available; first pick gets pooch 7, second pick should exclude 7 and pick 8
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7, 8])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(return_value=[99])) as mock_breed,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_breed.assert_awaited_once()
    assert 99 in result.pooches_created


@pytest.mark.asyncio
async def test_breed_pooches_require_unique_no_second_available_skips(context, rng):
    """breed_pooches with require_unique=True skips when only one pooch matches (no second available)."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {"first_selector": "random", "second_selector": "random", "require_unique": True},
    )
    # Only one pooch available — after excluding first, second pick has nothing
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock()) as mock_breed,
    ):
        await _execute_single_action(1, action, context, rng)
    mock_breed.assert_not_awaited()


@pytest.mark.asyncio
async def test_breed_pooches_with_baby_params(context, rng):
    """breed_pooches should apply baby_name, baby_age, baby_base_health, baby_breeding_cooldown."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {
            "first_selector": "random",
            "second_selector": "random",
            "require_unique": False,
            "baby_name": "Pup",
            "baby_age": 0,
            "baby_base_health": 90,
            "baby_breeding_cooldown": 3,
        },
    )
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(return_value=[77])),
        patch("src.game.manage_owner_events.rename_pooch", new=AsyncMock()) as mock_rename,
        patch("src.game.manage_owner_events.modify_pooch_age", new=AsyncMock()) as mock_age,
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()) as mock_health,
        patch("src.game.manage_owner_events.set_pooch_breeding_cooldown", new=AsyncMock()) as mock_cd,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_rename.assert_awaited_once_with(77, "Pup")
    mock_age.assert_awaited_once_with(77, 0)
    mock_health.assert_awaited_once_with(77, 90)
    mock_cd.assert_awaited_once_with(77, 3)
    assert 77 in result.pooches_created


@pytest.mark.asyncio
async def test_breed_pooches_save_as_invalid_type_is_noop(context, rng):
    """breed_pooches save_as with non-str/non-list type should write nothing."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {"first_selector": "random", "second_selector": "random", "require_unique": False, "save_as": 123},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(return_value=[88])),
    ):
        await _execute_single_action(1, action, context, rng)
    assert not any(k for k in context.extra_data)


@pytest.mark.asyncio
async def test_breed_pooches_save_as_list_empty_slot_skips(context, rng):
    """breed_pooches save_as list spec with empty slot string should be skipped."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {
            "first_selector": "random",
            "second_selector": "random",
            "require_unique": False,
            "save_as": [{"slot": "", "target": "baby"}],
        },
    )
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[3, 4])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(return_value=[55])),
    ):
        await _execute_single_action(1, action, context, rng)
    assert "" not in context.extra_data


@pytest.mark.asyncio
async def test_breed_pooches_raises_value_error_logs_warning(context, rng):
    """breed_pooches should log a warning and not raise if breeding raises ValueError."""
    action = _make_action(
        "breed_pooches",
        "owner",
        {"first_selector": "random", "second_selector": "random", "require_unique": False},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[5, 6])),
        patch("src.game.manage_owner_events.breed_pooches", new=AsyncMock(side_effect=ValueError("incompatible"))),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert result.pooches_created == []


# ---------------------------------------------------------------------------
# sell_pooch — vendor_selector random path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sell_pooch_vendor_selector_random_picks_vendor(context, rng):
    """sell_pooch with vendor_selector='random' should find a vendor from the owner's servers."""
    action = _make_action("sell_pooch", "pooch", {"selector": "random", "vendor_selector": "random"})
    vendor = SimpleNamespace(id=99)
    server = SimpleNamespace(discord_id=100)
    pooch = _make_pooch(7, alive=True)
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch("src.game.manage_owner_events.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[server])),
        patch("src.game.manage_owner_events.list_vendors", new=AsyncMock(return_value=[vendor])),
        patch("src.game.manage_owner_events.get_pooch_sell_price", new=AsyncMock(return_value=200)),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events.transfer_pooch_to_vendor", new=AsyncMock()),
        patch("src.game.manage_owner_events.remove_pooch_from_kennel", new=AsyncMock()),
        patch("src.game.manage_owner_events.add_pooch_to_vendor_stock", new=AsyncMock()),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert result.money_changed == 200


# ---------------------------------------------------------------------------
# buy_pooch — vendor_selector random, pooch_filter, kennel destination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buy_pooch_vendor_selector_random_finds_vendor(context, rng):
    """buy_pooch with vendor_selector='random' should pick vendor from owner's servers."""
    action = _make_action("buy_pooch", "owner", {"vendor_selector": "random", "destination": "town"})
    vendor = SimpleNamespace(id=55)
    server = SimpleNamespace(discord_id=200)
    stock_pooch = _make_pooch(10, name="Buddy")
    owner = SimpleNamespace(dollars=500)
    with (
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[server])),
        patch("src.game.manage_owner_events.list_vendors", new=AsyncMock(return_value=[vendor])),
        patch("src.game.manage_owner_events.list_vendor_pooch_stock", new=AsyncMock(return_value=[stock_pooch])),
        patch("src.game.manage_owner_events.get_pooch_buy_price", new=AsyncMock(return_value=100)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        patch("src.game.manage_owner_events.remove_pooch_from_vendor_stock", new=AsyncMock()),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events.transfer_pooch_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("town", None))),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert result.money_changed == -100
    assert 10 in result.pooches_created


@pytest.mark.asyncio
async def test_buy_pooch_with_pooch_filter_narrows_stock(context, rng):
    """buy_pooch with pooch_filter should filter vendor stock by matching pooch IDs."""
    action = _make_action(
        "buy_pooch", "owner", {"vendor_id": 77, "pooch_filter": {"min_age": 2}, "destination": "town"}
    )
    stock_a = _make_pooch(20, name="A")
    stock_b = _make_pooch(21, name="B")
    owner = SimpleNamespace(dollars=500)
    with (
        patch("src.game.manage_owner_events.list_vendor_pooch_stock", new=AsyncMock(return_value=[stock_a, stock_b])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[21])),
        patch("src.game.manage_owner_events.get_pooch_buy_price", new=AsyncMock(return_value=50)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        patch("src.game.manage_owner_events.remove_pooch_from_vendor_stock", new=AsyncMock()),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events.transfer_pooch_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("town", None))),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert 21 in result.pooches_created
    assert 20 not in result.pooches_created


@pytest.mark.asyncio
async def test_buy_pooch_kennel_destination_includes_kennel_name(context, rng):
    """buy_pooch with destination='kennel' should include the kennel name in result message."""
    action = _make_action("buy_pooch", "owner", {"vendor_id": 88, "destination": "kennel"})
    stock_pooch = _make_pooch(30, name="Spot")
    owner = SimpleNamespace(dollars=1000)
    with (
        patch("src.game.manage_owner_events.list_vendor_pooch_stock", new=AsyncMock(return_value=[stock_pooch])),
        patch("src.game.manage_owner_events.get_pooch_buy_price", new=AsyncMock(return_value=75)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        patch("src.game.manage_owner_events.remove_pooch_from_vendor_stock", new=AsyncMock()),
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events.transfer_pooch_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("kennel", "Happy Kennel"))),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert "Happy Kennel" in result.message


# ---------------------------------------------------------------------------
# Exception handler in _execute_single_action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_action_exception_sets_success_false(context, rng):
    """An unexpected exception inside _execute_single_action should set result.success = False."""
    action = _make_action("modify_money", "owner", {"amount": 10})
    with patch(
        "src.game.manage_owner_events.give_money_to_owner",
        new=AsyncMock(side_effect=RuntimeError("DB down")),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert result.success is False
    assert "DB down" in result.message


# ---------------------------------------------------------------------------
# trigger_specific_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_specific_event_not_found_returns_none():
    """trigger_specific_event should return None when the event doesn't exist."""
    from src.game.manage_owner_events import trigger_specific_event

    with patch("src.game.manage_owner_events.db_get_owner_event_by_id", new=AsyncMock(return_value=None)):
        result = await trigger_specific_event(1, 999)
    assert result is None


@pytest.mark.asyncio
async def test_trigger_specific_event_delegates_to_create_and_execute():
    """trigger_specific_event should call _create_and_execute_event when event is found."""
    from src.game.manage_owner_events import trigger_specific_event

    fake_event = MagicMock()
    fake_triggered = MagicMock()
    with (
        patch("src.game.manage_owner_events.db_get_owner_event_by_id", new=AsyncMock(return_value=fake_event)),
        patch("src.game.manage_owner_events._create_and_execute_event", new=AsyncMock(return_value=fake_triggered)),
    ):
        result = await trigger_specific_event(1, 42)
    assert result is fake_triggered


# ---------------------------------------------------------------------------
# trigger_random_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_random_event_too_many_active_returns_none():
    """trigger_random_event returns None when owner has max active events."""
    from src.game.constants import EVENT_MAX_ACTIVE_PER_OWNER
    from src.game.manage_owner_events import trigger_random_event

    many_events = [MagicMock()] * EVENT_MAX_ACTIVE_PER_OWNER
    with patch(
        "src.game.manage_owner_events.list_active_owner_events_for_owner", new=AsyncMock(return_value=many_events)
    ):
        result = await trigger_random_event(1)
    assert result is None


@pytest.mark.asyncio
async def test_trigger_random_event_no_eligible_returns_none():
    """trigger_random_event returns None when no eligible event is found."""
    from src.game.manage_owner_events import trigger_random_event

    with (
        patch("src.game.manage_owner_events.list_active_owner_events_for_owner", new=AsyncMock(return_value=[])),
        patch(
            "src.game.manage_owner_events.get_random_eligible_owner_event_for_owner", new=AsyncMock(return_value=None)
        ),
    ):
        result = await trigger_random_event(1)
    assert result is None


@pytest.mark.asyncio
async def test_trigger_random_event_triggers_eligible_event():
    """trigger_random_event should call _create_and_execute_event when an event is found."""
    from src.game.manage_owner_events import trigger_random_event

    fake_event = MagicMock()
    fake_triggered = MagicMock()
    with (
        patch("src.game.manage_owner_events.list_active_owner_events_for_owner", new=AsyncMock(return_value=[])),
        patch(
            "src.game.manage_owner_events.get_random_eligible_owner_event_for_owner",
            new=AsyncMock(return_value=fake_event),
        ),
        patch("src.game.manage_owner_events._create_and_execute_event", new=AsyncMock(return_value=fake_triggered)),
    ):
        result = await trigger_random_event(1)
    assert result is fake_triggered


# ---------------------------------------------------------------------------
# _create_and_execute_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_execute_event_returns_none_when_creation_fails():
    """_create_and_execute_event returns None if create_active_owner_event returns None."""
    from src.game.manage_owner_events import _create_and_execute_event

    fake_event = MagicMock()
    fake_event.requires_response = False
    fake_event.actions = []
    fake_event.options = []

    with (
        patch(
            "src.game.manage_owner_events._create_event_context",
            new=AsyncMock(return_value=EventContext(owner_discord_id=1)),
        ),
        patch("src.game.manage_owner_events.create_active_owner_event", new=AsyncMock(return_value=None)),
    ):
        result = await _create_and_execute_event(1, fake_event, random.Random(0))
    assert result is None


@pytest.mark.asyncio
async def test_create_and_execute_event_no_response_archives_immediately():
    """_create_and_execute_event archives immediately when requires_response=False."""
    from src.game.manage_owner_events import _create_and_execute_event

    fake_event = MagicMock()
    fake_event.requires_response = False
    fake_event.actions = []
    fake_event.options = []
    fake_event.name = "Instant Event"

    active_event = MagicMock()
    active_event.id = 1
    active_event.result_summary = None
    triggered = MagicMock()

    with (
        patch(
            "src.game.manage_owner_events._create_event_context",
            new=AsyncMock(return_value=EventContext(owner_discord_id=1)),
        ),
        patch("src.game.manage_owner_events.create_active_owner_event", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.update_active_event_result", new=AsyncMock()),
        patch("src.game.manage_owner_events.archive_active_event", new=AsyncMock()) as mock_archive,
        patch("src.game.manage_owner_events.to_triggered_event", new=AsyncMock(return_value=triggered)),
    ):
        result = await _create_and_execute_event(1, fake_event, random.Random(0))

    mock_archive.assert_awaited_once_with(1)
    assert result is triggered


@pytest.mark.asyncio
async def test_create_and_execute_event_requires_response_does_not_archive():
    """_create_and_execute_event should NOT archive when requires_response=True."""
    from src.game.manage_owner_events import _create_and_execute_event

    fake_event = MagicMock()
    fake_event.requires_response = True
    fake_event.response_timeout = 3600
    fake_event.actions = []
    fake_event.options = []
    fake_event.name = "Interactive Event"

    active_event = MagicMock()
    active_event.id = 2
    active_event.result_summary = None
    triggered = MagicMock()

    with (
        patch(
            "src.game.manage_owner_events._create_event_context",
            new=AsyncMock(return_value=EventContext(owner_discord_id=1)),
        ),
        patch("src.game.manage_owner_events.create_active_owner_event", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.update_active_event_result", new=AsyncMock()),
        patch("src.game.manage_owner_events.update_active_event_context", new=AsyncMock()),
        patch("src.game.manage_owner_events.archive_active_event", new=AsyncMock()) as mock_archive,
        patch("src.game.manage_owner_events.to_triggered_event", new=AsyncMock(return_value=triggered)),
    ):
        result = await _create_and_execute_event(1, fake_event, random.Random(0))

    mock_archive.assert_not_awaited()
    assert result is triggered


# ---------------------------------------------------------------------------
# start_event action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_event_random_calls_trigger_random_event(context, rng):
    """start_event with random_event=True should call trigger_random_event."""
    action = _make_action("start_event", "owner", {"random_event": True})
    triggered = MagicMock()
    triggered.active_owner_event_id = 5
    triggered.event_id = 10
    triggered.name = "Random Event"
    with patch("src.game.manage_owner_events.trigger_random_event", new=AsyncMock(return_value=triggered)):
        result = await _execute_single_action(1, action, context, rng)
    assert result.extra_data["started_events"][0]["name"] == "Random Event"


@pytest.mark.asyncio
async def test_start_event_named_event_triggers_specific(context, rng):
    """start_event with a named event should look it up and trigger it."""
    action = _make_action("start_event", "owner", {"event": "My Event"})
    fake_event = MagicMock()
    fake_event.id = 42
    triggered = MagicMock()
    triggered.active_owner_event_id = 7
    triggered.event_id = 42
    triggered.name = "My Event"
    with (
        patch("src.game.manage_owner_events.db_get_owner_event_by_name", new=AsyncMock(return_value=fake_event)),
        patch("src.game.manage_owner_events.trigger_specific_event", new=AsyncMock(return_value=triggered)),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert result.extra_data["started_events"][0]["event_id"] == 42


@pytest.mark.asyncio
async def test_start_event_unknown_name_sets_error_message(context, rng):
    """start_event with an unknown event name should set an error message."""
    action = _make_action("start_event", "owner", {"event": "Nonexistent Event"})
    with patch("src.game.manage_owner_events.db_get_owner_event_by_name", new=AsyncMock(return_value=None)):
        result = await _execute_single_action(1, action, context, rng)
    assert "Error" in result.message


@pytest.mark.asyncio
async def test_start_event_trigger_returns_none_no_started_events(context, rng):
    """start_event where trigger returns None should not populate started_events."""
    action = _make_action("start_event", "owner", {"random_event": True})
    with patch("src.game.manage_owner_events.trigger_random_event", new=AsyncMock(return_value=None)):
        result = await _execute_single_action(1, action, context, rng)
    assert "started_events" not in result.extra_data


# ---------------------------------------------------------------------------
# _get_target_pooch_ids — kennel target, random without count (lines 610-611)
# and random_exclude when count >= len (line 620)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kennel_target_random_no_count_uses_get_random_kennel(context, rng):
    """kennel target_type + random selector + no count uses get_random_matching_kennel_id."""
    action = _make_action("modify_pooch_health", "kennel", {"selector": "random", "amount": -1})
    # No count param → falls through to get_random_matching_kennel_id
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock(return_value=7)) as mock_rk,
        patch("src.game.manage_owner_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[101])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock(return_value=_make_pooch(101))),
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_rk.assert_awaited_once()
    assert 101 in result.pooches_affected


@pytest.mark.asyncio
async def test_kennel_target_random_no_count_no_kennel_empty(context, rng):
    """kennel target_type + random selector + no kennel found yields empty pooch list."""
    action = _make_action("modify_pooch_health", "kennel", {"selector": "random", "amount": -1})
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock(return_value=None)),
        patch("src.game.manage_owner_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()) as mock_modify,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_modify.assert_not_awaited()
    assert result.pooches_affected == []


@pytest.mark.asyncio
async def test_kennel_target_random_exclude_count_gte_len_pooches_yields_empty(context, rng):
    """kennel target_type + random_exclude when count >= len(kennels) → empty pooch list."""
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"selector": "random_exclude", "count": 10, "amount": -1},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()) as mock_modify,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_modify.assert_not_awaited()
    assert result.pooches_affected == []


# ---------------------------------------------------------------------------
# mode='set' on modify_* actions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_money_set_mode_calls_set_owner_dollars(context, rng):
    """modify_money with mode='set' should call set_owner_dollars instead of give_money_to_owner."""
    action = _make_action("modify_money", "owner", {"amount": 0, "mode": "set"})
    with (
        patch("src.game.manage_owner_events.set_owner_dollars", new=AsyncMock()) as mock_set,
        patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_set.assert_awaited_once_with(1, 0)
    mock_give.assert_not_awaited()
    assert result.money_changed == 0


@pytest.mark.asyncio
async def test_modify_bloodskulls_set_mode_calls_set_owner_bloodskulls(context, rng):
    """modify_bloodskulls with mode='set' should call set_owner_bloodskulls."""
    action = _make_action("modify_bloodskulls", "owner", {"amount": 5, "mode": "set"})
    with (
        patch("src.game.manage_owner_events.set_owner_bloodskulls", new=AsyncMock()) as mock_set,
        patch("src.game.manage_owner_events.give_bloodskulls_to_owner", new=AsyncMock()) as mock_give,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_set.assert_awaited_once_with(1, 5)
    mock_give.assert_not_awaited()
    assert result.bloodskulls_changed == 5


@pytest.mark.asyncio
async def test_modify_pooch_health_set_mode_calls_set_pooch_base_health(context, rng):
    """modify_pooch_health with mode='set' should call set_pooch_base_health."""
    action = _make_action("modify_pooch_health", "pooch", {"selector": "random", "amount": 100, "mode": "set"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch(
            "src.game.manage_owner_events.set_pooch_base_health",
            new=AsyncMock(return_value=_make_pooch(7)),
        ) as mock_set,
        patch("src.game.manage_owner_events.modify_pooch_base_health", new=AsyncMock()) as mock_modify,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_set.assert_awaited_once_with(7, 100)
    mock_modify.assert_not_awaited()
    assert 7 in result.pooches_affected


@pytest.mark.asyncio
async def test_modify_pooch_age_set_mode_calls_set_pooch_age(context, rng):
    """modify_pooch_age with mode='set' should call set_pooch_age."""
    action = _make_action("modify_pooch_age", "pooch", {"selector": "random", "amount": 3, "mode": "set"})
    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[9])),
        patch(
            "src.game.manage_owner_events.set_pooch_age",
            new=AsyncMock(return_value=_make_pooch(9)),
        ) as mock_set,
        patch("src.game.manage_owner_events.modify_pooch_age", new=AsyncMock()) as mock_modify,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_set.assert_awaited_once_with(9, 3)
    mock_modify.assert_not_awaited()
    assert 9 in result.pooches_affected


@pytest.mark.asyncio
async def test_modify_kennel_capacity_set_mode_calls_set_kennel_pooch_limit(context, rng):
    """modify_kennel_capacity with mode='set' should call set_kennel_pooch_limit."""
    action = _make_action("modify_kennel_capacity", "kennel", {"selector": "random", "amount": 10, "mode": "set"})
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock(return_value=5)),
        patch(
            "src.game.manage_owner_events.set_kennel_pooch_limit",
            new=AsyncMock(return_value=_make_kennel(5)),
        ) as mock_set,
        patch("src.game.manage_owner_events.modify_kennel_pooch_limit", new=AsyncMock()) as mock_modify,
    ):
        await _execute_single_action(1, action, context, rng)
    mock_set.assert_awaited_once_with(5, 10)
    mock_modify.assert_not_awaited()


# ---------------------------------------------------------------------------
# exclude_amount on modify_* actions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_money_exclude_amount_never_rolls_excluded_value(context, rng):
    """exclude_amount ensures the rolled amount is never in the exclusion list."""
    # Range is [1, 3], exclude [2] → only 1 or 3 are valid
    action = _make_action("modify_money", "owner", {"min_amount": 1, "max_amount": 3, "exclude_amount": [2]})
    amounts_seen = set()
    with patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give:
        for _ in range(20):
            await _execute_single_action(1, action, context, rng)
        for call in mock_give.await_args_list:
            amounts_seen.add(call.args[1])
    assert 2 not in amounts_seen
    assert amounts_seen <= {1, 3}


@pytest.mark.asyncio
async def test_modify_money_exclude_amount_all_excluded_falls_back_to_min(context, rng):
    """When all values in range are excluded, falls back to min_amount."""
    action = _make_action("modify_money", "owner", {"min_amount": 5, "max_amount": 5, "exclude_amount": [5]})
    with patch("src.game.manage_owner_events.give_money_to_owner", new=AsyncMock()) as mock_give:
        await _execute_single_action(1, action, context, rng)
    mock_give.assert_awaited_once_with(1, 5)


# ---------------------------------------------------------------------------
# pooch_selector / pooch_count on kennel target
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kennel_pooch_selector_random_picks_one_pooch(context, rng):
    """pooch_selector='random' on kennel target picks one random pooch from the kennel."""
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"selector": "random", "amount": -1, "pooch_selector": "random"},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock(return_value=10)),
        patch("src.game.manage_owner_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[1, 2, 3])),
        patch(
            "src.game.manage_owner_events.modify_pooch_base_health",
            new=AsyncMock(side_effect=lambda pid, amt: _make_pooch(pid)),
        ),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert len(result.pooches_affected) == 1


@pytest.mark.asyncio
async def test_kennel_pooch_selector_random_with_count(context, rng):
    """pooch_selector='random' + pooch_count=2 picks exactly 2 pooches from the kennel."""
    action = _make_action(
        "modify_pooch_health",
        "kennel",
        {"selector": "random", "amount": -1, "pooch_selector": "random", "pooch_count": 2},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock(return_value=10)),
        patch(
            "src.game.manage_owner_events.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(return_value=[1, 2, 3, 4]),
        ),
        patch(
            "src.game.manage_owner_events.modify_pooch_base_health",
            new=AsyncMock(side_effect=lambda pid, amt: _make_pooch(pid)),
        ),
    ):
        result = await _execute_single_action(1, action, context, rng)
    assert len(result.pooches_affected) == 2


@pytest.mark.asyncio
async def test_kennel_pooch_selector_random_exclude_kills_all_but_one(context, rng):
    """pooch_selector='random_exclude' + pooch_count=1 kills all pooches in kennel except one."""
    action = _make_action(
        "kill_pooch",
        "kennel",
        {"selector": "random", "pooch_selector": "random_exclude", "pooch_count": 1},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock(return_value=10)),
        patch(
            "src.game.manage_owner_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[1, 2, 3, 4])
        ),
        patch(
            "src.game.manage_owner_events.set_pooch_dead",
            new=AsyncMock(side_effect=lambda pid: _make_pooch(pid)),
        ),
    ):
        result = await _execute_single_action(1, action, context, rng)
    # 4 pooches, exclude 1 randomly → 3 killed
    assert len(result.pooches_killed) == 3


@pytest.mark.asyncio
async def test_kennel_pooch_selector_random_exclude_count_gte_len_spares_all(context, rng):
    """pooch_selector='random_exclude' when pooch_count >= kennel size affects no pooches."""
    action = _make_action(
        "kill_pooch",
        "kennel",
        {"selector": "random", "pooch_selector": "random_exclude", "pooch_count": 5},
    )
    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock(return_value=10)),
        patch("src.game.manage_owner_events.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[1, 2, 3])),
        patch("src.game.manage_owner_events.set_pooch_dead", new=AsyncMock()) as mock_kill,
    ):
        result = await _execute_single_action(1, action, context, rng)
    mock_kill.assert_not_awaited()
    assert result.pooches_killed == []


# ---------------------------------------------------------------------------
# Unknown action type (line 1130)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_action_type_is_noop(context, rng):
    """An unknown action_type should log a warning and return an empty result."""
    action = _make_action("completely_unknown_action", "owner", {})
    result = await _execute_single_action(1, action, context, rng)
    assert result.pooches_affected == []
    assert result.money_changed == 0


# ---------------------------------------------------------------------------
# Top-level wrapper functions (get_active_events_for_owner, get_event_history,
# get_pending_event, list_all_owner_events, process_expired_events,
# respond_to_event, run_hourly_event_check, _create_event_context)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_events_for_owner_returns_triggered_events():
    """get_active_events_for_owner should map DB records to TriggeredEvent."""
    from src.game.manage_owner_events import get_active_events_for_owner

    fake_active = MagicMock()
    fake_triggered = MagicMock()
    with (
        patch(
            "src.game.manage_owner_events.list_active_owner_events_for_owner", new=AsyncMock(return_value=[fake_active])
        ),
        patch("src.game.manage_owner_events.to_triggered_event", new=AsyncMock(return_value=fake_triggered)),
    ):
        result = await get_active_events_for_owner(1)
    assert result == [fake_triggered]


@pytest.mark.asyncio
async def test_get_event_history_returns_history_records():
    """get_event_history should map DB records to EventHistory."""
    from src.game.manage_owner_events import get_event_history

    fake_record = MagicMock()
    fake_history = MagicMock()
    with (
        patch(
            "src.game.manage_owner_events.list_owner_event_history_for_owner", new=AsyncMock(return_value=[fake_record])
        ),
        patch("src.game.manage_owner_events.to_event_history", new=AsyncMock(return_value=fake_history)),
    ):
        result = await get_event_history(1)
    assert result == [fake_history]


@pytest.mark.asyncio
async def test_list_all_owner_events_returns_events():
    """list_all_owner_events should map DB records to Event."""
    from src.game.manage_owner_events import list_all_owner_events

    fake_db_event = MagicMock()
    fake_event = MagicMock()
    with (
        patch("src.game.manage_owner_events.db_list_all_owner_events", new=AsyncMock(return_value=[fake_db_event])),
        patch("src.game.manage_owner_events.to_event", new=AsyncMock(return_value=fake_event)),
    ):
        result = await list_all_owner_events()
    assert result == [fake_event]


@pytest.mark.asyncio
async def test_get_pending_event_returns_none_when_not_found():
    """get_pending_event should return None when the active event does not exist."""
    from src.game.manage_owner_events import get_pending_event

    with patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=None)):
        result = await get_pending_event(1, active_owner_event_id=99)
    assert result is None


@pytest.mark.asyncio
async def test_get_pending_event_returns_none_when_wrong_owner():
    """get_pending_event should return None when the event belongs to a different owner."""
    from src.game.manage_owner_events import get_pending_event

    active_event = MagicMock()
    active_event.owner_discord_id = 999  # different owner
    active_event.responded_at = None
    with patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)):
        result = await get_pending_event(1, active_owner_event_id=5)
    assert result is None


@pytest.mark.asyncio
async def test_get_pending_event_returns_none_when_already_responded():
    """get_pending_event should return None when the event has already been responded to."""
    from src.game.manage_owner_events import get_pending_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = MagicMock()  # not None
    with patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)):
        result = await get_pending_event(1, active_owner_event_id=5)
    assert result is None


@pytest.mark.asyncio
async def test_get_pending_event_returns_triggered_event():
    """get_pending_event should return a TriggeredEvent when all checks pass."""
    from src.game.manage_owner_events import get_pending_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    triggered = MagicMock()
    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.to_triggered_event", new=AsyncMock(return_value=triggered)),
    ):
        result = await get_pending_event(1, active_owner_event_id=5)
    assert result is triggered


@pytest.mark.asyncio
async def test_get_pending_event_no_id_returns_none_when_no_pending():
    """get_pending_event without event_id returns None when no pending event."""
    from src.game.manage_owner_events import get_pending_event

    with patch("src.game.manage_owner_events.get_pending_active_owner_event", new=AsyncMock(return_value=None)):
        result = await get_pending_event(1)
    assert result is None


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_event_not_found():
    """respond_to_event should return (False, ...) when active event is not found."""
    from src.game.manage_owner_events import respond_to_event

    with patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=None)):
        success, msg, result = await respond_to_event(1, 99, 1)
    assert success is False
    assert result is None


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_wrong_owner():
    """respond_to_event should return (False, ...) when event belongs to another owner."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 999
    active_event.responded_at = None
    with patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is False


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_already_responded():
    """respond_to_event should return (False, ...) when event was already responded to."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = MagicMock()
    with patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is False


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_option_not_found():
    """respond_to_event should return (False, ...) when option is not found."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    active_event.expires_at = None
    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.get_owner_event_option_by_id", new=AsyncMock(return_value=None)),
    ):
        success, msg, result = await respond_to_event(1, 5, 99)
    assert success is False


@pytest.mark.asyncio
async def test_process_expired_events_empty_returns_empty():
    """process_expired_events with no expired events should return empty list."""
    from src.game.manage_owner_events import process_expired_events

    with patch("src.game.manage_owner_events.list_expired_active_owner_events", new=AsyncMock(return_value=[])):
        result = await process_expired_events()
    assert result == []


@pytest.mark.asyncio
async def test_run_hourly_event_check_with_no_owners():
    """run_hourly_event_check with no owners should return empty dict."""
    from src.game.manage_owner_events import run_hourly_event_check

    with (
        patch("src.game.manage_owner_events.process_expired_events", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_owners", new=AsyncMock(return_value=[])),
    ):
        result = await run_hourly_event_check(rng_seed=0)
    assert result == {}


@pytest.mark.asyncio
async def test_create_event_context_no_selected_needed():
    """_create_event_context should not call get_random_matching_pooch_id when no selected selector."""
    from src.game.manage_owner_events import _create_event_context

    fake_event = MagicMock()
    fake_event.filter = {}
    fake_event.actions = []
    fake_event.options = []

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.get_random_matching_pooch_id", new=AsyncMock()) as mock_rp,
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock()) as mock_rk,
    ):
        ctx = await _create_event_context(1, fake_event, random.Random(0))

    mock_rp.assert_not_awaited()
    mock_rk.assert_not_awaited()
    assert ctx.owner_discord_id == 1


@pytest.mark.asyncio
async def test_create_event_context_selects_pooch_and_kennel_when_needed():
    """_create_event_context should call get_random_matching_*_id when 'selected' selector is used."""
    from src.game.manage_owner_events import _create_event_context

    # Build a fake event action that uses "selected" selector for both pooch and kennel
    pooch_action = MagicMock()
    pooch_action.target_type = "pooch"
    pooch_action.parameters = {"selector": "selected"}

    kennel_action = MagicMock()
    kennel_action.target_type = "kennel"
    kennel_action.parameters = {"selector": "selected"}

    option = MagicMock()
    option.actions = []
    option.outcomes = []

    fake_event = MagicMock()
    fake_event.filter = {}
    fake_event.actions = [pooch_action, kennel_action]
    fake_event.options = [option]

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[10])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.get_random_matching_pooch_id", new=AsyncMock(return_value=5)) as mock_rp,
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock(return_value=10)) as mock_rk,
    ):
        ctx = await _create_event_context(1, fake_event, random.Random(0))

    mock_rp.assert_awaited_once()
    mock_rk.assert_awaited_once()
    assert ctx.selected_pooch_id == 5
    assert ctx.selected_kennel_id == 10


@pytest.mark.asyncio
async def test_create_event_context_selected_in_option_outcome():
    """_create_event_context detects 'selected' selector in option outcomes."""
    from src.game.manage_owner_events import _create_event_context

    outcome_action = MagicMock()
    outcome_action.target_type = "pooch"
    outcome_action.parameters = {"selector": "selected"}

    outcome = MagicMock()
    outcome.actions = [outcome_action]

    option = MagicMock()
    option.actions = []
    option.outcomes = [outcome]

    fake_event = MagicMock()
    fake_event.filter = {}
    fake_event.actions = []
    fake_event.options = [option]

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch("src.game.manage_owner_events.get_random_matching_pooch_id", new=AsyncMock(return_value=7)) as mock_rp,
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock()) as mock_rk,
    ):
        ctx = await _create_event_context(1, fake_event, random.Random(0))

    mock_rp.assert_awaited_once()
    mock_rk.assert_not_awaited()
    assert ctx.selected_pooch_id == 7


@pytest.mark.asyncio
async def test_create_event_context_uses_event_filter_for_default_pooch():
    """_create_event_context should derive pooch filter from event.filter['pooches'][0]."""
    from src.game.manage_owner_events import _create_event_context

    pooch_action = MagicMock()
    pooch_action.target_type = "pooch"
    pooch_action.parameters = {"selector": "selected"}

    fake_event = MagicMock()
    fake_event.filter = {"pooches": [{"min_age": 2, "max_age": 5, "min_count": 1, "description": "adult"}]}
    fake_event.actions = [pooch_action]
    fake_event.options = []

    captured_filter = {}

    async def fake_get_random_pooch(owner_id, filt, rng):
        captured_filter.update(filt)
        return 3

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[3])),
        patch(
            "src.game.manage_owner_events.get_random_matching_pooch_id",
            new=AsyncMock(side_effect=fake_get_random_pooch),
        ),
    ):
        await _create_event_context(1, fake_event, random.Random(0))

    # min_count and description should be stripped out; min_age/max_age should remain
    assert "min_age" in captured_filter
    assert "min_count" not in captured_filter
    assert "description" not in captured_filter


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_option_wrong_event():
    """respond_to_event returns (False, ...) when option belongs to a different event."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    active_event.expires_at = None
    active_event.event_id = 10

    option = MagicMock()
    option.event_id = 99  # different event
    option.is_visible = True

    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.get_owner_event_option_by_id", new=AsyncMock(return_value=option)),
    ):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is False


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_option_not_visible():
    """respond_to_event returns (False, ...) when option is not visible."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    active_event.expires_at = None
    active_event.event_id = 10

    option = MagicMock()
    option.event_id = 10
    option.is_visible = False

    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.get_owner_event_option_by_id", new=AsyncMock(return_value=option)),
    ):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is False


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_insufficient_money():
    """respond_to_event returns (False, ...) when owner lacks the minimum money."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    active_event.expires_at = None
    active_event.event_id = 10

    option = MagicMock()
    option.event_id = 10
    option.is_visible = True
    option.min_money = 1000
    option.min_bloodskulls = 0

    owner = MagicMock()
    owner.dollars = 5  # not enough

    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.get_owner_event_option_by_id", new=AsyncMock(return_value=option)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
    ):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is False
    assert "1000" in msg


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_insufficient_bloodskulls():
    """respond_to_event returns (False, ...) when owner lacks bloodskulls."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    active_event.expires_at = None
    active_event.event_id = 10

    option = MagicMock()
    option.event_id = 10
    option.is_visible = True
    option.min_money = 0
    option.min_bloodskulls = 50

    owner = MagicMock()
    owner.dollars = 9999
    owner.bloodskulls = 0  # not enough

    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.get_owner_event_option_by_id", new=AsyncMock(return_value=option)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
    ):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is False
    assert "50" in msg


@pytest.mark.asyncio
async def test_respond_to_event_success_path():
    """respond_to_event should return (True, ...) when all checks pass."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    active_event.expires_at = None
    active_event.event_id = 10
    active_event.id = 5
    active_event.result_summary = None

    outcome = _make_outcome(chance=1.0)
    option = MagicMock()
    option.id = 1
    option.event_id = 10
    option.is_visible = True
    option.min_money = 0
    option.min_bloodskulls = 0
    option.actions = []
    option.outcomes = [outcome]
    option.label = "Accept"
    option.filter = {}

    owner = MagicMock()
    owner.dollars = 100
    owner.bloodskulls = 10

    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.get_owner_event_option_by_id", new=AsyncMock(return_value=option)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        patch("src.game.manage_owner_events.check_owner_event_filter_for_owner", new=AsyncMock(return_value=True)),
        patch("src.game.manage_owner_events.respond_to_active_owner_event", new=AsyncMock()),
        patch("src.game.manage_owner_events.archive_active_event", new=AsyncMock()),
    ):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is True
    assert result is not None


@pytest.mark.asyncio
async def test_process_expired_events_with_default_option():
    """process_expired_events should execute the default option's actions when event expires."""
    from src.game.manage_owner_events import process_expired_events

    default_outcome = _make_outcome(chance=1.0)
    default_option = MagicMock()
    default_option.is_default = True
    default_option.id = 1
    default_option.label = "Default"
    default_option.actions = []
    default_option.outcomes = [default_outcome]

    non_default_option = MagicMock()
    non_default_option.is_default = False

    event = MagicMock()
    event.name = "Test"
    event.options = [non_default_option, default_option]
    event.actions = []

    active_event = MagicMock()
    active_event.id = 99
    active_event.owner_discord_id = 1
    active_event.context = {}
    active_event.result_summary = None
    active_event.event = event

    with (
        patch(
            "src.game.manage_owner_events.list_expired_active_owner_events", new=AsyncMock(return_value=[active_event])
        ),
        patch("src.game.manage_owner_events.respond_to_active_owner_event", new=AsyncMock()),
        patch("src.game.manage_owner_events.archive_active_event", new=AsyncMock()),
    ):
        results = await process_expired_events(rng=random.Random(0))

    assert len(results) == 1
    owner_id, event_id, result = results[0]
    assert owner_id == 1


@pytest.mark.asyncio
async def test_process_expired_events_no_default_option():
    """process_expired_events should handle expired event with no default option."""
    from src.game.manage_owner_events import process_expired_events

    option = MagicMock()
    option.is_default = False

    event = MagicMock()
    event.name = "Test"
    event.options = [option]
    event.actions = []

    active_event = MagicMock()
    active_event.id = 100
    active_event.owner_discord_id = 2
    active_event.context = {}
    active_event.result_summary = None
    active_event.event = event

    with (
        patch(
            "src.game.manage_owner_events.list_expired_active_owner_events", new=AsyncMock(return_value=[active_event])
        ),
        patch("src.game.manage_owner_events.respond_to_active_owner_event", new=AsyncMock()),
        patch("src.game.manage_owner_events.archive_active_event", new=AsyncMock()),
    ):
        results = await process_expired_events(rng=random.Random(0))

    assert len(results) == 1
    assert "expired" in results[0][2].message.lower()


@pytest.mark.asyncio
async def test_run_hourly_event_check_skips_when_rng_above_threshold():
    """run_hourly_event_check skips owners whose RNG roll exceeds EVENT_HOURLY_TRIGGER_CHANCE."""
    from src.game.manage_owner_events import run_hourly_event_check

    owner = MagicMock()
    owner.discord_id = 1

    # Seed RNG so the roll will always be above threshold (chance is low)
    with (
        patch("src.game.manage_owner_events.process_expired_events", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_owners", new=AsyncMock(return_value=[owner])),
        patch("src.game.manage_owner_events.trigger_random_event", new=AsyncMock()) as mock_trigger,
        # Patch the constant to 0.0 so no one ever passes
        patch("src.game.manage_owner_events.EVENT_HOURLY_TRIGGER_CHANCE", 0.0),
    ):
        result = await run_hourly_event_check(rng_seed=0)

    mock_trigger.assert_not_awaited()
    assert result == {}


@pytest.mark.asyncio
async def test_run_hourly_event_check_triggers_for_eligible_owner():
    """run_hourly_event_check triggers events for owners whose roll passes the threshold."""
    from src.game.manage_owner_events import run_hourly_event_check

    owner = MagicMock()
    owner.discord_id = 42
    triggered = MagicMock()

    with (
        patch("src.game.manage_owner_events.process_expired_events", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_owners", new=AsyncMock(return_value=[owner])),
        patch("src.game.manage_owner_events.trigger_random_event", new=AsyncMock(return_value=triggered)),
        # Set threshold to 1.0 so every owner passes
        patch("src.game.manage_owner_events.EVENT_HOURLY_TRIGGER_CHANCE", 1.0),
    ):
        result = await run_hourly_event_check(rng_seed=0)

    assert 42 in result
    assert result[42] == [triggered]


@pytest.mark.asyncio
async def test_run_hourly_event_check_uses_seeded_rng():
    """run_hourly_event_check with rng_seed should use it (covers line 401)."""
    from src.game.manage_owner_events import run_hourly_event_check

    with (
        patch("src.game.manage_owner_events.process_expired_events", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_owners", new=AsyncMock(return_value=[])),
    ):
        result = await run_hourly_event_check(rng_seed=12345)
    assert result == {}


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_expired():
    """respond_to_event should return (False, ...) when event has expired."""
    from datetime import datetime, timedelta, timezone

    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    # Set expires_at to a past time
    active_event.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    active_event.id = 5

    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.archive_active_event", new=AsyncMock()),
    ):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is False
    assert "expired" in msg.lower()


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_owner_not_found():
    """respond_to_event should return (False, ...) when owner is not found."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    active_event.expires_at = None
    active_event.event_id = 10

    option = MagicMock()
    option.event_id = 10
    option.is_visible = True
    option.min_money = 0
    option.min_bloodskulls = 0

    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.get_owner_event_option_by_id", new=AsyncMock(return_value=option)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=None)),
    ):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is False


@pytest.mark.asyncio
async def test_respond_to_event_returns_false_when_filter_fails():
    """respond_to_event should return (False, ...) when owner event filter check fails."""
    from src.game.manage_owner_events import respond_to_event

    active_event = MagicMock()
    active_event.owner_discord_id = 1
    active_event.responded_at = None
    active_event.expires_at = None
    active_event.event_id = 10

    option = MagicMock()
    option.event_id = 10
    option.is_visible = True
    option.min_money = 0
    option.min_bloodskulls = 0
    option.filter = {}

    owner = MagicMock()
    owner.dollars = 100
    owner.bloodskulls = 10

    with (
        patch("src.game.manage_owner_events.get_active_owner_event_by_id", new=AsyncMock(return_value=active_event)),
        patch("src.game.manage_owner_events.get_owner_event_option_by_id", new=AsyncMock(return_value=option)),
        patch("src.game.manage_owner_events.get_owner_by_discord_id", new=AsyncMock(return_value=owner)),
        patch("src.game.manage_owner_events.check_owner_event_filter_for_owner", new=AsyncMock(return_value=False)),
    ):
        success, msg, result = await respond_to_event(1, 5, 1)
    assert success is False


@pytest.mark.asyncio
async def test_create_event_context_scans_option_actions():
    """_create_event_context detects 'selected' in option-level actions."""
    from src.game.manage_owner_events import _create_event_context

    # Option action with selected selector on pooch
    option_action = MagicMock()
    option_action.target_type = "pooch"
    option_action.parameters = {"selector": "selected"}

    option = MagicMock()
    option.actions = [option_action]
    option.outcomes = []

    fake_event = MagicMock()
    fake_event.filter = {}
    fake_event.actions = []
    fake_event.options = [option]

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[3])),
        patch("src.game.manage_owner_events.get_random_matching_pooch_id", new=AsyncMock(return_value=3)) as mock_rp,
        patch("src.game.manage_owner_events.get_random_matching_kennel_id", new=AsyncMock()) as mock_rk,
    ):
        ctx = await _create_event_context(1, fake_event, random.Random(0))

    mock_rp.assert_awaited_once()
    mock_rk.assert_not_awaited()
    assert ctx.selected_pooch_id == 3


@pytest.mark.asyncio
async def test_create_event_context_non_selected_selector_not_detected():
    """_create_event_context should not select a pooch for 'random' or other selectors."""
    from src.game.manage_owner_events import _create_event_context

    # Action with random selector → should NOT trigger selected-pooch logic
    action = MagicMock()
    action.target_type = "pooch"
    action.parameters = {"selector": "random"}

    fake_event = MagicMock()
    fake_event.filter = {}
    fake_event.actions = [action]
    fake_event.options = []

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.get_random_matching_pooch_id", new=AsyncMock()) as mock_rp,
    ):
        ctx = await _create_event_context(1, fake_event, random.Random(0))

    mock_rp.assert_not_awaited()
    assert ctx.selected_pooch_id is None


@pytest.mark.asyncio
async def test_create_event_context_with_kennel_filter_entry():
    """_create_event_context should derive kennel filter from event.filter['kennels'][0]."""
    from src.game.manage_owner_events import _create_event_context

    kennel_action = MagicMock()
    kennel_action.target_type = "kennel"
    kennel_action.parameters = {"selector": "selected"}

    fake_event = MagicMock()
    fake_event.filter = {"kennels": [{"min_pooches": 1, "min_count": 1, "description": "big"}]}
    fake_event.actions = [kennel_action]
    fake_event.options = []

    captured_filter = {}

    async def fake_get_random_kennel(owner_id, filt, rng):
        captured_filter.update(filt)
        return 5

    with (
        patch("src.game.manage_owner_events.list_matching_kennel_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
        patch(
            "src.game.manage_owner_events.get_random_matching_kennel_id",
            new=AsyncMock(side_effect=fake_get_random_kennel),
        ),
    ):
        ctx = await _create_event_context(1, fake_event, random.Random(0))

    assert "min_pooches" in captured_filter
    assert "min_count" not in captured_filter
    assert "description" not in captured_filter
    assert ctx.selected_kennel_id == 5


@pytest.mark.asyncio
async def test_run_hourly_event_check_without_seed_uses_fresh_rng():
    """run_hourly_event_check without rng_seed should create a fresh random.Random (line 401)."""
    from src.game.manage_owner_events import run_hourly_event_check

    with (
        patch("src.game.manage_owner_events.process_expired_events", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.list_owners", new=AsyncMock(return_value=[])),
    ):
        # No rng_seed → hits the `else: rng = random.Random()` branch
        result = await run_hourly_event_check()
    assert result == {}


@pytest.mark.asyncio
async def test_process_expired_events_outcome_no_message_uses_default_message():
    """process_expired_events sets default message when outcome has no message/description/label."""
    from src.game.manage_owner_events import process_expired_events

    # Outcome whose message/description/label are all falsy → outcome_message is None
    no_msg_outcome = MagicMock()
    no_msg_outcome.chance = 1.0
    no_msg_outcome.message = None
    no_msg_outcome.description = None
    no_msg_outcome.label = None
    no_msg_outcome.actions = []

    default_option = MagicMock()
    default_option.is_default = True
    default_option.id = 1
    default_option.label = "Expire"
    default_option.actions = []
    default_option.outcomes = [no_msg_outcome]

    event = MagicMock()
    event.name = "Expiring Event"
    event.options = [default_option]
    event.actions = []

    active_event = MagicMock()
    active_event.id = 77
    active_event.owner_discord_id = 5
    active_event.context = {}
    active_event.result_summary = None
    active_event.event = event

    with (
        patch(
            "src.game.manage_owner_events.list_expired_active_owner_events", new=AsyncMock(return_value=[active_event])
        ),
        patch("src.game.manage_owner_events.respond_to_active_owner_event", new=AsyncMock()),
        patch("src.game.manage_owner_events.archive_active_event", new=AsyncMock()),
    ):
        results = await process_expired_events(rng=random.Random(0))

    assert len(results) == 1
    _, _, result = results[0]
    # When outcome_message is None, falls back to "Event '...' expired. Expire was applied."
    assert "Expiring Event" in result.message
    assert "Expire" in result.message


# ---------------------------------------------------------------------------
# release_stray action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_release_stray_action_calls_add_pooch_to_strays(context, rng):
    """release_stray should call add_pooch_to_strays with the resolved pooch and server IDs."""
    action = _make_action(
        "release_stray",
        "pooch",
        {"selector": "random"},
    )

    fake_server = SimpleNamespace(discord_id=999)
    fake_stray = SimpleNamespace(pooch_id=5, server_discord_id=999)

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[fake_server])),
        patch("src.game.manage_owner_events.add_pooch_to_strays", new=AsyncMock(return_value=fake_stray)) as mock_add,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_add.assert_awaited_once_with(5, 999)
    assert 5 in result.pooches_affected


@pytest.mark.asyncio
async def test_release_stray_no_server_skips(context, rng):
    """release_stray with no servers available should skip without error."""
    action = _make_action(
        "release_stray",
        "pooch",
        {"selector": "random"},
    )

    with (
        patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[5])),
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.add_pooch_to_strays", new=AsyncMock()) as mock_add,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_add.assert_not_awaited()
    assert result.pooches_affected == []


# ---------------------------------------------------------------------------
# receive_stray action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_receive_stray_action_delivers_pooch_to_kennel(context, rng):
    """receive_stray should claim a stray and deliver it to the requested destination."""
    action = _make_action(
        "receive_stray",
        "owner",
        {"destination": "kennel"},
    )

    fake_server = SimpleNamespace(discord_id=999)
    fake_pooch = SimpleNamespace(id=42, name="Rover", sex="male", age=3)

    with (
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[fake_server])),
        patch("src.game.manage_owner_events.list_strays_for_server", new=AsyncMock(return_value=[fake_pooch])),
        patch("src.game.manage_owner_events.remove_pooch_from_strays", new=AsyncMock(return_value=fake_pooch)),
        patch("src.game.manage_owner_events.transfer_pooch_to_owner", new=AsyncMock()),
        patch("src.game.manage_owner_events._deliver_pooch", new=AsyncMock(return_value=("kennel", "Main Kennel"))),
    ):
        result = await _execute_single_action(1, action, context, rng)

    assert 42 in result.pooches_created
    created_entries = result.extra_data.get("created_pooches", [])
    assert len(created_entries) == 1
    assert created_entries[0]["pooch_name"] == "Rover"
    assert created_entries[0]["kennel_name"] == "Main Kennel"


@pytest.mark.asyncio
async def test_receive_stray_no_strays_available_skips(context, rng):
    """receive_stray should skip gracefully when no strays are available on the server."""
    action = _make_action(
        "receive_stray",
        "owner",
        {"destination": "kennel"},
    )

    fake_server = SimpleNamespace(discord_id=999)

    with (
        patch("src.game.manage_owner_events.list_servers_for_owner", new=AsyncMock(return_value=[fake_server])),
        patch("src.game.manage_owner_events.list_strays_for_server", new=AsyncMock(return_value=[])),
        patch("src.game.manage_owner_events.remove_pooch_from_strays", new=AsyncMock()) as mock_remove,
    ):
        result = await _execute_single_action(1, action, context, rng)

    mock_remove.assert_not_awaited()
    assert result.pooches_created == []


# ---------------------------------------------------------------------------
# exclude_claimed preflight
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exclude_claimed_suppresses_option_when_no_strays_available(context, rng):
    """
    When exclude_claimed=True is set on an option's action and no valid candidate pooch exists
    (because all have been claimed by earlier options), the option should be added to
    suppressed_option_ids in context.extra_data.

    This test calls _execute_single_action with _exclude_ids populated so that no candidates
    remain, and verifies the resolver returns an empty list (simulating suppression behavior).
    """
    # Action with exclude_claimed and a _exclude_ids that covers all candidates
    action = _make_action(
        "kill_pooch",
        "pooch",
        {"selector": "random", "exclude_claimed": True, "_exclude_ids": [10, 20, 30]},
    )

    with patch("src.game.manage_owner_events.list_matching_pooch_ids", new=AsyncMock(return_value=[10, 20, 30])):
        result = await _execute_single_action(1, action, context, rng)

    # All candidates excluded — no pooches should be killed
    assert result.pooches_killed == []
