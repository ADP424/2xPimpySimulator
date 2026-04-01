"""
Unit tests for src/game/events/owner_events/coordinator.py
"""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.events.owner_events import (
    create_and_execute_event,
    execute_event_actions,
    execute_single_action,
)
from src.game.models.events.owner_events.owner_event_context import OwnerEventContext
from src.game.models.events.owner_events.owner_event_result import OwnerEventResult

MOD = "src.game.events.owner_events.coordinator"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(
    action_type: str, target_type: str = "pooch", parameters: dict | None = None, repeat: int = 1
) -> MagicMock:
    action = MagicMock()
    action.action_type = action_type
    action.target_type = target_type
    action.parameters = parameters if parameters is not None else {}
    action.repeat = repeat
    action.action_order = 0
    return action


def _make_pooch(pooch_id: int, name: str = "Fido", alive: bool = True, **kwargs) -> SimpleNamespace:
    defaults = dict(
        id=pooch_id,
        name=name,
        alive=alive,
        sex="M",
        age=1,
        base_health=10,
        size=10,
        strength=5,
        cuteness=5,
        fluffiness=5,
        intelligence=5,
        dexterity=5,
        fertility=5,
        aggressiveness=5,
        constitution=5,
        breeding_cooldown=0,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_kennel(kennel_id: int, name: str = "My Kennel", pooch_limit: int = 5) -> SimpleNamespace:
    return SimpleNamespace(id=kennel_id, name=name, pooch_limit=pooch_limit)


def _make_server(discord_id: int = 9000) -> SimpleNamespace:
    return SimpleNamespace(discord_id=discord_id)


def _make_vendor(vendor_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=vendor_id)


def _make_option(
    option_id: int = 1,
    actions: list | None = None,
    outcomes: list | None = None,
    is_default: bool = False,
    is_visible: bool = True,
    option_order: int = 0,
) -> MagicMock:
    opt = MagicMock()
    opt.id = option_id
    opt.actions = actions if actions is not None else []
    opt.outcomes = outcomes if outcomes is not None else []
    opt.is_default = is_default
    opt.is_visible = is_visible
    opt.option_order = option_order
    return opt


def _make_outcome(actions: list | None = None) -> MagicMock:
    outcome = MagicMock()
    outcome.actions = actions if actions is not None else []
    outcome.chance = 1.0
    outcome.stat_weights = None
    return outcome


def _make_event_db(
    event_id: int = 10,
    name: str = "Test Event",
    requires_response: bool = False,
    response_timeout: int = 86400,
    actions: list | None = None,
    options: list | None = None,
    event_filter: dict | None = None,
) -> MagicMock:
    ev = MagicMock()
    ev.id = event_id
    ev.name = name
    ev.category = "test"
    ev.description = "desc"
    ev.flavor_text = "flavor"
    ev.severity = "minor"
    ev.requires_response = requires_response
    ev.response_timeout = response_timeout
    ev.actions = actions if actions is not None else []
    ev.options = options if options is not None else []
    ev.filter = event_filter if event_filter is not None else {}
    return ev


def _make_active_event(event_id: int = 10, active_id: int = 99) -> MagicMock:
    ae = MagicMock()
    ae.id = active_id
    ae.event_id = event_id
    ae.result_summary = None
    ae.context = {}
    ae.expires_at = None
    return ae


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


@pytest.fixture
def context() -> OwnerEventContext:
    """
    Context.

    Returns
    -------
    Any
        The result of calling `context`.
    """

    return OwnerEventContext(owner_discord_id=1)


@pytest.fixture(autouse=True)
def mock_cancel_listing():
    """
    Mock cancel listing.

    Returns
    -------
    Any
        The result of calling `mock_cancel_listing`.
    """

    with patch(f"{MOD}.cancel_listing_for_pooch", new=AsyncMock()):
        yield


@pytest.fixture(autouse=True)
def mock_get_current_season():
    """
    Mock get current season.

    Returns
    -------
    Any
        The result of calling `mock_get_current_season`.
    """

    with patch(f"{MOD}.get_current_season", new=AsyncMock(return_value="spring")):
        yield


# ---------------------------------------------------------------------------
# execute_single_action: modify_money
# ---------------------------------------------------------------------------


class TestModifyMoney:
    @pytest.mark.asyncio
    async def test_modify_money_add(self, context, rng):
        action = _make_action("modify_money", "owner", {"amount": 100})
        with patch(f"{MOD}.give_money_to_owner", new=AsyncMock()) as mock_give:
            result = await execute_single_action(1, action, context, rng)
        mock_give.assert_awaited_once_with(1, 100)
        assert result.money_changed == 100
        assert "+100" in result.message

    @pytest.mark.asyncio
    async def test_modify_money_set_mode(self, context, rng):
        action = _make_action("modify_money", "owner", {"amount": 50, "mode": "set"})
        with patch(f"{MOD}.set_owner_dollars", new=AsyncMock()) as mock_set:
            result = await execute_single_action(1, action, context, rng)
        mock_set.assert_awaited_once_with(1, 50)
        assert result.money_changed == 50

    @pytest.mark.asyncio
    async def test_modify_money_random_range(self, context, rng):
        action = _make_action("modify_money", "owner", {"min_amount": 10, "max_amount": 20})
        with patch(f"{MOD}.give_money_to_owner", new=AsyncMock()):
            result = await execute_single_action(1, action, context, rng)
        assert 10 <= result.money_changed <= 20


# ---------------------------------------------------------------------------
# execute_single_action: modify_bloodskulls
# ---------------------------------------------------------------------------


class TestModifyBloodskulls:
    @pytest.mark.asyncio
    async def test_modify_bloodskulls_add(self, context, rng):
        action = _make_action("modify_bloodskulls", "owner", {"amount": 5})
        with patch(f"{MOD}.give_bloodskulls_to_owner", new=AsyncMock()) as mock_give:
            result = await execute_single_action(1, action, context, rng)
        mock_give.assert_awaited_once_with(1, 5)
        assert result.bloodskulls_changed == 5

    @pytest.mark.asyncio
    async def test_modify_bloodskulls_set_mode(self, context, rng):
        action = _make_action("modify_bloodskulls", "owner", {"amount": 3, "mode": "set"})
        with patch(f"{MOD}.set_owner_bloodskulls", new=AsyncMock()) as mock_set:
            await execute_single_action(1, action, context, rng)
        mock_set.assert_awaited_once_with(1, 3)


# ---------------------------------------------------------------------------
# execute_single_action: create_pooch
# ---------------------------------------------------------------------------


class TestCreatePooch:
    @pytest.mark.asyncio
    async def test_create_pooch_basic_delivers(self, context, rng):
        new_pooch = _make_pooch(42)
        action = _make_action("create_pooch", "pooch", {"destination": "kennel"})
        with (
            patch(f"{MOD}.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch(f"{MOD}.deliver_pooch", new=AsyncMock(return_value=("kennel", "My Kennel"))),
        ):
            result = await execute_single_action(1, action, context, rng)
        assert 42 in result.pooches_created
        assert context.selected_pooch_id == 42

    @pytest.mark.asyncio
    async def test_create_pooch_kennel_target_type(self, context, rng):
        """When target_type='kennel' the pooch goes into that specific kennel if there's space."""
        new_pooch = _make_pooch(50)
        kennel = _make_kennel(7, "Kennel7", pooch_limit=5)
        action = _make_action("create_pooch", "kennel", {})
        with (
            patch(f"{MOD}.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch(f"{MOD}.get_target_kennel_ids", new=AsyncMock(return_value=[7])),
            patch(f"{MOD}.get_kennel_by_id", new=AsyncMock(return_value=kennel)),
            patch(f"{MOD}.list_pooches_for_kennel", new=AsyncMock(return_value=[])),
            patch(f"{MOD}.add_pooch_to_kennel", new=AsyncMock()),
        ):
            result = await execute_single_action(1, action, context, rng)
        assert 50 in result.pooches_created
        assert "Kennel7" in result.message

    @pytest.mark.asyncio
    async def test_create_pooch_full_kennel_falls_back(self, context, rng):
        new_pooch = _make_pooch(51)
        kennel = _make_kennel(8, "Full Kennel", pooch_limit=1)
        pooches_in = [_make_pooch(100)]
        action = _make_action("create_pooch", "kennel", {})
        with (
            patch(f"{MOD}.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch(f"{MOD}.get_target_kennel_ids", new=AsyncMock(return_value=[8])),
            patch(f"{MOD}.get_kennel_by_id", new=AsyncMock(return_value=kennel)),
            patch(f"{MOD}.list_pooches_for_kennel", new=AsyncMock(return_value=pooches_in)),
        ):
            result = await execute_single_action(1, action, context, rng)
        assert "no space" in result.message.lower()

    @pytest.mark.asyncio
    async def test_create_pooch_save_as(self, context, rng):
        new_pooch = _make_pooch(60)
        action = _make_action("create_pooch", "pooch", {"save_as": "my_slot"})
        with (
            patch(f"{MOD}.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch(f"{MOD}.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))),
        ):
            await execute_single_action(1, action, context, rng)
        assert context.extra_data["my_slot"] == {"pooch_ids": [60]}


# ---------------------------------------------------------------------------
# execute_single_action: clone_pooch
# ---------------------------------------------------------------------------


class TestClonePooch:
    @pytest.mark.asyncio
    async def test_clone_pooch_success(self, context, rng):
        source = _make_pooch(10)
        clone = _make_pooch(11, name="Fido Clone")
        action = _make_action("clone_pooch", "pooch", {})
        with (
            patch(f"{MOD}.get_target_pooch_ids", new=AsyncMock(return_value=[10])),
            patch(f"{MOD}.create_pooch", new=AsyncMock(return_value=clone)),
            patch(f"{MOD}.copy_pooch_genetics", new=AsyncMock()),
            patch(f"{MOD}.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=source)),
        ):
            result = await execute_single_action(1, action, context, rng)
        assert 11 in result.pooches_created
        assert context.selected_pooch_id == 11

    @pytest.mark.asyncio
    async def test_clone_pooch_no_source_pooch(self, context, rng):
        action = _make_action("clone_pooch", "pooch", {})
        with patch(f"{MOD}.get_target_pooch_ids", new=AsyncMock(return_value=[])):
            result = await execute_single_action(1, action, context, rng)
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_clone_pooch_copies_breeds_and_mutations(self, context, rng):
        source = _make_pooch(30)
        clone = _make_pooch(31, name="CloneC")
        action = _make_action("clone_pooch", "pooch", {})
        with (
            patch(f"{MOD}.get_target_pooch_ids", new=AsyncMock(return_value=[30])),
            patch(f"{MOD}.create_pooch", new=AsyncMock(return_value=clone)),
            patch(f"{MOD}.copy_pooch_genetics", new=AsyncMock()) as mock_genetics,
            patch(f"{MOD}.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=source)),
        ):
            await execute_single_action(1, action, context, rng)
        mock_genetics.assert_awaited_once_with(30, 31)

    @pytest.mark.asyncio
    async def test_clone_pooch_save_as_list(self, context, rng):
        source = _make_pooch(10)
        clone = _make_pooch(21, name="CloneB")
        save_as = [{"slot": "src_slot", "target": "source"}, {"slot": "clone_slot", "target": "clone"}]
        action = _make_action("clone_pooch", "pooch", {"save_as": save_as})
        with (
            patch(f"{MOD}.get_target_pooch_ids", new=AsyncMock(return_value=[10])),
            patch(f"{MOD}.create_pooch", new=AsyncMock(return_value=clone)),
            patch(f"{MOD}.copy_pooch_genetics", new=AsyncMock()),
            patch(f"{MOD}.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=source)),
        ):
            await execute_single_action(1, action, context, rng)
        assert context.extra_data["src_slot"] == {"pooch_ids": [10]}
        assert context.extra_data["clone_slot"] == {"pooch_ids": [21]}


# ---------------------------------------------------------------------------
# execute_single_action: modify_kennel_capacity
# ---------------------------------------------------------------------------


class TestModifyKennelCapacity:
    @pytest.mark.asyncio
    async def test_modify_kennel_capacity_adjust(self, context, rng):
        kennel = _make_kennel(3, "Kennel3")
        action = _make_action("modify_kennel_capacity", "kennel", {"amount": 2})
        with (
            patch(f"{MOD}.get_target_kennel_ids", new=AsyncMock(return_value=[3])),
            patch(f"{MOD}.modify_kennel_pooch_limit", new=AsyncMock(return_value=kennel)) as mock_mod,
        ):
            await execute_single_action(1, action, context, rng)
        mock_mod.assert_awaited_once_with(3, 2)
        assert 3 in context.affected_kennel_ids

    @pytest.mark.asyncio
    async def test_modify_kennel_capacity_set_mode(self, context, rng):
        kennel = _make_kennel(4, "Kennel4")
        action = _make_action("modify_kennel_capacity", "kennel", {"amount": 10, "mode": "set"})
        with (
            patch(f"{MOD}.get_target_kennel_ids", new=AsyncMock(return_value=[4])),
            patch(f"{MOD}.set_kennel_pooch_limit", new=AsyncMock(return_value=kennel)) as mock_set,
        ):
            await execute_single_action(1, action, context, rng)
        mock_set.assert_awaited_once_with(4, 10)


# ---------------------------------------------------------------------------
# execute_single_action: kill_pooch
# ---------------------------------------------------------------------------


class TestKillPooch:
    @pytest.mark.asyncio
    async def test_kill_pooch(self, context, rng):
        action = _make_action("kill_pooch", "pooch", {"selector": "random"})
        with (
            patch(f"{MOD}.get_target_pooch_ids", new=AsyncMock(return_value=[9])),
            patch(f"{MOD}.handle_kill_pooch", new=AsyncMock()) as mock_kill,
        ):
            await execute_single_action(1, action, context, rng)
        mock_kill.assert_awaited_once()


# ---------------------------------------------------------------------------
# execute_single_action: modify_base_health
# ---------------------------------------------------------------------------


class TestModifyHealth:
    @pytest.mark.asyncio
    async def test_modify_base_health(self, context, rng):
        action = _make_action("modify_base_health", "pooch", {"selector": "random", "amount": -5})
        with (
            patch(f"{MOD}.get_target_pooch_ids", new=AsyncMock(return_value=[7])),
            patch(f"{MOD}.handle_modify_health", new=AsyncMock()) as mock_health,
        ):
            await execute_single_action(1, action, context, rng)
        mock_health.assert_awaited_once()


# ---------------------------------------------------------------------------
# execute_single_action: modify_pooch_age
# ---------------------------------------------------------------------------


class TestModifyAge:
    @pytest.mark.asyncio
    async def test_modify_age(self, context, rng):
        action = _make_action("modify_pooch_age", "pooch", {"selector": "random", "amount": 1})
        with (
            patch(f"{MOD}.get_target_pooch_ids", new=AsyncMock(return_value=[5])),
            patch(f"{MOD}.handle_modify_age", new=AsyncMock()) as mock_age,
        ):
            await execute_single_action(1, action, context, rng)
        mock_age.assert_awaited_once()


# ---------------------------------------------------------------------------
# execute_event_actions
# ---------------------------------------------------------------------------


class TestExecuteEventActions:
    @pytest.mark.asyncio
    async def test_empty_actions_returns_empty_result(self, context, rng):
        result = await execute_event_actions(1, [], context, rng)
        assert isinstance(result, OwnerEventResult)
        assert result.pooches_created == []
        assert result.money_changed == 0

    @pytest.mark.asyncio
    async def test_single_action_executed(self, context, rng):
        action = _make_action("modify_money", "owner", {"amount": 50})
        with patch(f"{MOD}.give_money_to_owner", new=AsyncMock()):
            result = await execute_event_actions(1, [action], context, rng)
        assert result.money_changed == 50

    @pytest.mark.asyncio
    async def test_action_repeat_executes_multiple_times(self, context, rng):
        action = _make_action("modify_money", "owner", {"amount": 10}, repeat=3)
        with patch(f"{MOD}.give_money_to_owner", new=AsyncMock()) as mock_give:
            await execute_event_actions(1, [action], context, rng)
        assert mock_give.await_count == 3


# ---------------------------------------------------------------------------
# create_and_execute_event
# ---------------------------------------------------------------------------


class TestCreateAndExecuteEvent:
    @pytest.mark.asyncio
    async def test_no_response_required_executes_immediately(self, rng):
        event = _make_event_db(requires_response=False, actions=[])
        active_event = _make_active_event()
        mock_triggered = MagicMock()
        with (
            patch(f"{MOD}.create_event_context", new=AsyncMock(return_value=OwnerEventContext(owner_discord_id=1))),
            patch(f"{MOD}.create_active_owner_event", new=AsyncMock(return_value=active_event)),
            patch(f"{MOD}.get_current_season", new=AsyncMock(return_value="spring")),
            patch(f"{MOD}.execute_event_actions", new=AsyncMock(return_value=OwnerEventResult())),
            patch(f"{MOD}.update_active_event_result", new=AsyncMock()),
            patch(f"{MOD}.archive_active_event", new=AsyncMock()),
            patch(f"{MOD}.to_triggered_owner_event", new=AsyncMock(return_value=mock_triggered)),
        ):
            triggered = await create_and_execute_event(1, event, rng)
        assert triggered is mock_triggered

    @pytest.mark.asyncio
    async def test_response_required_saves_pending(self, rng):
        action = _make_action("modify_money", "owner", {"amount": 10})
        option = _make_option(actions=[action])
        event = _make_event_db(requires_response=True, options=[option])
        active_event = _make_active_event()
        mock_triggered = MagicMock()
        with (
            patch(f"{MOD}.create_event_context", new=AsyncMock(return_value=OwnerEventContext(owner_discord_id=1))),
            patch(f"{MOD}.create_active_owner_event", new=AsyncMock(return_value=active_event)),
            patch(f"{MOD}.execute_event_actions", new=AsyncMock(return_value=OwnerEventResult())),
            patch(f"{MOD}.update_active_event_result", new=AsyncMock()),
            patch(f"{MOD}.update_active_event_context", new=AsyncMock()),
            patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
            patch(f"{MOD}.to_triggered_owner_event", new=AsyncMock(return_value=mock_triggered)),
        ):
            triggered = await create_and_execute_event(1, event, rng)
        assert triggered is mock_triggered
