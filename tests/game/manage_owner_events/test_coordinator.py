"""
Comprehensive unit tests for src.game.manage_owner_events.coordinator
"""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.manage_owner_events.coordinator import (
    _execute_single_action,
    create_and_execute_event,
    execute_event_actions,
)
from src.game.models.events.owner_events.owner_event_context import OwnerEventContext
from src.game.models.events.owner_events.owner_event_result import OwnerEventResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(
    action_type: str, target_type: str = "pooch", parameters: dict | None = None, repeat: int = 1
) -> MagicMock:
    """Build a minimal EventAction stub."""
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


def _make_stray(pooch_id: int, name: str = "Stray", sex: str = "F", age: int = 2) -> SimpleNamespace:
    return SimpleNamespace(id=pooch_id, name=name, sex=sex, age=age)


def _make_active_event(event_id: int = 10, active_id: int = 99) -> MagicMock:
    ae = MagicMock()
    ae.id = active_id
    ae.event_id = event_id
    ae.result_summary = None
    ae.context = {}
    ae.expires_at = None
    return ae


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


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


@pytest.fixture
def context() -> OwnerEventContext:
    return OwnerEventContext(owner_discord_id=1)


@pytest.fixture(autouse=True)
def mock_cancel_listing():
    """Auto-patch cancel_listing_for_pooch so tests never hit the real DB."""
    with patch("src.game.manage_owner_events.coordinator.cancel_listing_for_pooch", new=AsyncMock()):
        yield


@pytest.fixture(autouse=True)
def mock_get_current_season():
    """Auto-patch get_current_season so tests never hit the real DB."""
    with patch("src.game.manage_owner_events.coordinator.get_current_season", new=AsyncMock(return_value="spring")):
        yield


# ---------------------------------------------------------------------------
# _execute_single_action: modify_money
# ---------------------------------------------------------------------------


class TestModifyMoney:
    @pytest.mark.asyncio
    async def test_modify_money_add(self, context, rng):
        action = _make_action("modify_money", "owner", {"amount": 100})
        with patch("src.game.manage_owner_events.coordinator.give_money_to_owner", new=AsyncMock()) as mock_give:
            result = await _execute_single_action(1, action, context, rng)
        mock_give.assert_awaited_once_with(1, 100)
        assert result.money_changed == 100
        assert "+100" in result.message

    @pytest.mark.asyncio
    async def test_modify_money_set_mode(self, context, rng):
        action = _make_action("modify_money", "owner", {"amount": 50, "mode": "set"})
        with patch("src.game.manage_owner_events.coordinator.set_owner_dollars", new=AsyncMock()) as mock_set:
            result = await _execute_single_action(1, action, context, rng)
        mock_set.assert_awaited_once_with(1, 50)
        assert result.money_changed == 50

    @pytest.mark.asyncio
    async def test_modify_money_random_range(self, context, rng):
        action = _make_action("modify_money", "owner", {"min_amount": 10, "max_amount": 20})
        with patch("src.game.manage_owner_events.coordinator.give_money_to_owner", new=AsyncMock()):
            result = await _execute_single_action(1, action, context, rng)
        assert 10 <= result.money_changed <= 20


# ---------------------------------------------------------------------------
# _execute_single_action: modify_bloodskulls
# ---------------------------------------------------------------------------


class TestModifyBloodskulls:
    @pytest.mark.asyncio
    async def test_modify_bloodskulls_add(self, context, rng):
        action = _make_action("modify_bloodskulls", "owner", {"amount": 5})
        with patch("src.game.manage_owner_events.coordinator.give_bloodskulls_to_owner", new=AsyncMock()) as mock_give:
            result = await _execute_single_action(1, action, context, rng)
        mock_give.assert_awaited_once_with(1, 5)
        assert result.bloodskulls_changed == 5

    @pytest.mark.asyncio
    async def test_modify_bloodskulls_set_mode(self, context, rng):
        action = _make_action("modify_bloodskulls", "owner", {"amount": 3, "mode": "set"})
        with patch("src.game.manage_owner_events.coordinator.set_owner_bloodskulls", new=AsyncMock()) as mock_set:
            await _execute_single_action(1, action, context, rng)
        mock_set.assert_awaited_once_with(1, 3)


# ---------------------------------------------------------------------------
# _execute_single_action: create_pooch
# ---------------------------------------------------------------------------


class TestCreatePooch:
    @pytest.mark.asyncio
    async def test_create_pooch_basic_kennel_destination(self, context, rng):
        new_pooch = _make_pooch(42)
        action = _make_action("create_pooch", "pooch", {"destination": "kennel"})
        with (
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch",
                new=AsyncMock(return_value=("kennel", "My Kennel")),
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 42 in result.pooches_created
        assert context.selected_pooch_id == 42
        assert "My Kennel" in result.message

    @pytest.mark.asyncio
    async def test_create_pooch_graveyard_destination(self, context, rng):
        new_pooch = _make_pooch(43)
        action = _make_action("create_pooch", "pooch", {"destination": "graveyard"})
        with (
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch",
                new=AsyncMock(return_value=("graveyard", None)),
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert "graveyard" in result.message.lower()

    @pytest.mark.asyncio
    async def test_create_pooch_hell_destination(self, context, rng):
        new_pooch = _make_pooch(44)
        action = _make_action("create_pooch", "pooch", {"destination": "hell"})
        with (
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch("src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("hell", None))),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert "Hell" in result.message

    @pytest.mark.asyncio
    async def test_create_pooch_kennel_target_type(self, context, rng):
        """When target_type='kennel' the pooch goes into that specific kennel if there's space."""
        new_pooch = _make_pooch(50)
        kennel = _make_kennel(7, "Kennel7", pooch_limit=5)
        action = _make_action("create_pooch", "kennel", {})
        with (
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch(
                "src.game.manage_owner_events.coordinator.get_target_kennel_ids",
                new=AsyncMock(return_value=[7]),
            ),
            patch("src.game.manage_owner_events.coordinator.get_kennel_by_id", new=AsyncMock(return_value=kennel)),
            patch("src.game.manage_owner_events.coordinator.list_pooches_for_kennel", new=AsyncMock(return_value=[])),
            patch("src.game.manage_owner_events.coordinator.add_pooch_to_kennel", new=AsyncMock()),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 50 in result.pooches_created
        assert "Kennel7" in result.message

    @pytest.mark.asyncio
    async def test_create_pooch_with_random_breeds_count(self, context, rng):
        new_pooch = _make_pooch(55)
        action = _make_action("create_pooch", "pooch", {"breeds": 2})
        with (
            patch("src.game.manage_owner_events.coordinator.get_random_breed_ids", new=AsyncMock(return_value=[1, 2])),
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch("src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("town", None))),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 55 in result.pooches_created

    @pytest.mark.asyncio
    async def test_create_pooch_with_mutation_count(self, context, rng):
        new_pooch = _make_pooch(56)
        action = _make_action("create_pooch", "pooch", {"mutations": 2})
        with (
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch("src.game.manage_owner_events.coordinator.add_mutation_to_pooch", new=AsyncMock()) as mock_add_mut,
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
        ):
            await _execute_single_action(1, action, context, rng)
        assert mock_add_mut.await_count == 2

    @pytest.mark.asyncio
    async def test_create_pooch_save_as(self, context, rng):
        new_pooch = _make_pooch(60)
        action = _make_action("create_pooch", "pooch", {"save_as": "my_slot"})
        with (
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
        ):
            await _execute_single_action(1, action, context, rng)
        assert context.extra_data["my_slot"] == {"pooch_ids": [60]}

    @pytest.mark.asyncio
    async def test_create_pooch_full_kennel_falls_back(self, context, rng):
        """If target_type='kennel' but kennel is full, message says no space."""
        new_pooch = _make_pooch(51)
        kennel = _make_kennel(8, "Full Kennel", pooch_limit=1)
        pooches_in = [_make_pooch(100)]
        action = _make_action("create_pooch", "kennel", {})
        with (
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=new_pooch)),
            patch("src.game.manage_owner_events.coordinator.get_target_kennel_ids", new=AsyncMock(return_value=[8])),
            patch("src.game.manage_owner_events.coordinator.get_kennel_by_id", new=AsyncMock(return_value=kennel)),
            patch(
                "src.game.manage_owner_events.coordinator.list_pooches_for_kennel",
                new=AsyncMock(return_value=pooches_in),
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert "no space" in result.message.lower()


# ---------------------------------------------------------------------------
# _execute_single_action: clone_pooch
# ---------------------------------------------------------------------------


class TestClonePooch:
    @pytest.mark.asyncio
    async def test_clone_pooch_success(self, context, rng):
        source = _make_pooch(10)
        clone = _make_pooch(11, name="Fido Clone")
        action = _make_action("clone_pooch", "pooch", {})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[10])),
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=clone)),
            patch("src.game.manage_owner_events.coordinator.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
            patch("src.game.manage_owner_events.coordinator.list_pooch_mutations", new=AsyncMock(return_value=[])),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=source)),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 11 in result.pooches_created
        assert context.selected_pooch_id == 11

    @pytest.mark.asyncio
    async def test_clone_pooch_no_source_pooch(self, context, rng):
        """If no pooch IDs resolved, skip without error."""
        action = _make_action("clone_pooch", "pooch", {})
        with patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[])):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_clone_pooch_save_as_string(self, context, rng):
        source = _make_pooch(10)
        clone = _make_pooch(20, name="CloneA")
        action = _make_action("clone_pooch", "pooch", {"save_as": "clone_slot"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[10])),
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=clone)),
            patch("src.game.manage_owner_events.coordinator.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
            patch("src.game.manage_owner_events.coordinator.list_pooch_mutations", new=AsyncMock(return_value=[])),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=source)),
        ):
            await _execute_single_action(1, action, context, rng)
        assert context.extra_data["clone_slot"] == {"pooch_ids": [20]}

    @pytest.mark.asyncio
    async def test_clone_pooch_save_as_list_source_and_clone(self, context, rng):
        source = _make_pooch(10)
        clone = _make_pooch(21, name="CloneB")
        save_as = [{"slot": "src_slot", "target": "source"}, {"slot": "clone_slot", "target": "clone"}]
        action = _make_action("clone_pooch", "pooch", {"save_as": save_as})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[10])),
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=clone)),
            patch("src.game.manage_owner_events.coordinator.list_pooch_breed_weights", new=AsyncMock(return_value=[])),
            patch("src.game.manage_owner_events.coordinator.list_pooch_mutations", new=AsyncMock(return_value=[])),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=source)),
        ):
            await _execute_single_action(1, action, context, rng)
        assert context.extra_data["src_slot"] == {"pooch_ids": [10]}
        assert context.extra_data["clone_slot"] == {"pooch_ids": [21]}

    @pytest.mark.asyncio
    async def test_clone_pooch_copies_breeds_and_mutations(self, context, rng):
        source = _make_pooch(30)
        clone = _make_pooch(31, name="CloneC")
        breed_weights = [(1, 0.8), (2, 0.2)]
        mut1 = SimpleNamespace(id=5)
        mut2 = SimpleNamespace(id=6)
        action = _make_action("clone_pooch", "pooch", {})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[30])),
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=clone)),
            patch(
                "src.game.manage_owner_events.coordinator.list_pooch_breed_weights",
                new=AsyncMock(return_value=breed_weights),
            ),
            patch("src.game.manage_owner_events.coordinator.add_pooch_breeds", new=AsyncMock()) as mock_breeds,
            patch(
                "src.game.manage_owner_events.coordinator.list_pooch_mutations",
                new=AsyncMock(return_value=[mut1, mut2]),
            ),
            patch("src.game.manage_owner_events.coordinator.add_mutation_to_pooch", new=AsyncMock()) as mock_muts,
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=source)),
        ):
            await _execute_single_action(1, action, context, rng)
        mock_breeds.assert_awaited_once()
        assert mock_muts.await_count == 2


# ---------------------------------------------------------------------------
# _execute_single_action: modify_kennel_capacity
# ---------------------------------------------------------------------------


class TestModifyKennelCapacity:
    @pytest.mark.asyncio
    async def test_modify_kennel_capacity_adjust(self, context, rng):
        kennel = _make_kennel(3, "Kennel3")
        action = _make_action("modify_kennel_capacity", "kennel", {"amount": 2})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_kennel_ids", new=AsyncMock(return_value=[3])),
            patch(
                "src.game.manage_owner_events.coordinator.modify_kennel_pooch_limit", new=AsyncMock(return_value=kennel)
            ) as mock_mod,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_mod.assert_awaited_once_with(3, 2)
        assert 3 in context.affected_kennel_ids

    @pytest.mark.asyncio
    async def test_modify_kennel_capacity_set_mode(self, context, rng):
        kennel = _make_kennel(4, "Kennel4")
        action = _make_action("modify_kennel_capacity", "kennel", {"amount": 10, "mode": "set"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_kennel_ids", new=AsyncMock(return_value=[4])),
            patch(
                "src.game.manage_owner_events.coordinator.set_kennel_pooch_limit", new=AsyncMock(return_value=kennel)
            ) as mock_set,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_set.assert_awaited_once_with(4, 10)

    @pytest.mark.asyncio
    async def test_modify_kennel_capacity_multiple_kennels(self, context, rng):
        kennel_a = _make_kennel(10, "KA")
        kennel_b = _make_kennel(11, "KB")
        action = _make_action("modify_kennel_capacity", "kennel", {"amount": 1})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.get_target_kennel_ids", new=AsyncMock(return_value=[10, 11])
            ),
            patch(
                "src.game.manage_owner_events.coordinator.modify_kennel_pooch_limit",
                new=AsyncMock(side_effect=[kennel_a, kennel_b]),
            ) as mock_mod,
        ):
            await _execute_single_action(1, action, context, rng)
        assert mock_mod.await_count == 2
        assert 10 in context.affected_kennel_ids
        assert 11 in context.affected_kennel_ids


# ---------------------------------------------------------------------------
# _execute_single_action: modify_base_health
# ---------------------------------------------------------------------------


class TestModifyHealth:
    @pytest.mark.asyncio
    async def test_modify_base_health(self, context, rng):
        action = _make_action("modify_base_health", "pooch", {"selector": "random", "amount": -5})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[7])),
            patch("src.game.manage_owner_events.coordinator.handle_modify_health", new=AsyncMock()) as mock_health,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_health.assert_awaited_once()


# ---------------------------------------------------------------------------
# _execute_single_action: modify_pooch_age
# ---------------------------------------------------------------------------


class TestModifyAge:
    @pytest.mark.asyncio
    async def test_modify_age(self, context, rng):
        action = _make_action("modify_pooch_age", "pooch", {"selector": "random", "amount": 1})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[5])),
            patch("src.game.manage_owner_events.coordinator.handle_modify_age", new=AsyncMock()) as mock_age,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_age.assert_awaited_once()


# ---------------------------------------------------------------------------
# _execute_single_action: kill_pooch
# ---------------------------------------------------------------------------


class TestKillPooch:
    @pytest.mark.asyncio
    async def test_kill_pooch(self, context, rng):
        action = _make_action("kill_pooch", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[9])),
            patch("src.game.manage_owner_events.coordinator.handle_kill_pooch", new=AsyncMock()) as mock_kill,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_kill.assert_awaited_once()


# ---------------------------------------------------------------------------
# _execute_single_action: release_stray
# ---------------------------------------------------------------------------


class TestReleaseStray:
    @pytest.mark.asyncio
    async def test_release_stray(self, context, rng):
        server = _make_server()
        action = _make_action("release_stray", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[12])),
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch(
                "src.game.manage_owner_events.coordinator.add_pooch_to_strays", new=AsyncMock(return_value=True)
            ) as mock_add,
        ):
            result = await _execute_single_action(1, action, context, rng)
        mock_add.assert_awaited_once()
        assert 12 in result.pooches_affected

    @pytest.mark.asyncio
    async def test_release_stray_no_servers(self, context, rng):
        """If owner has no servers, skip without error."""
        action = _make_action("release_stray", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[13])),
            patch("src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[])),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_affected == []


# ---------------------------------------------------------------------------
# _execute_single_action: receive_stray
# ---------------------------------------------------------------------------


class TestReceiveStray:
    @pytest.mark.asyncio
    async def test_receive_stray_basic(self, context, rng):
        server = _make_server()
        stray = _make_stray(77)
        action = _make_action("receive_stray", "pooch", {})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch(
                "src.game.manage_owner_events.coordinator.list_strays_for_server", new=AsyncMock(return_value=[stray])
            ),
            patch("src.game.manage_owner_events.coordinator.remove_pooch_from_strays", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.transfer_pooch_to_owner", new=AsyncMock()),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 77 in result.pooches_created

    @pytest.mark.asyncio
    async def test_receive_stray_no_servers(self, context, rng):
        action = _make_action("receive_stray", "pooch", {})
        with patch("src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[])):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_receive_stray_no_strays(self, context, rng):
        server = _make_server()
        action = _make_action("receive_stray", "pooch", {})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch("src.game.manage_owner_events.coordinator.list_strays_for_server", new=AsyncMock(return_value=[])),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_receive_stray_use_saved(self, context, rng):
        server = _make_server()
        stray = _make_stray(80)
        context.extra_data["my_strays"] = {"pooch_ids": [80]}
        action = _make_action("receive_stray", "pooch", {"use_saved": "my_strays"})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch(
                "src.game.manage_owner_events.coordinator.list_strays_for_server", new=AsyncMock(return_value=[stray])
            ),
            patch("src.game.manage_owner_events.coordinator.remove_pooch_from_strays", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.cancel_listing_for_pooch", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.transfer_pooch_to_owner", new=AsyncMock()),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 80 in result.pooches_created

    @pytest.mark.asyncio
    async def test_receive_stray_kennel_target(self, context, rng):
        server = _make_server()
        stray = _make_stray(85)
        kennel = _make_kennel(20, "K20", pooch_limit=5)
        action = _make_action("receive_stray", "kennel", {})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch(
                "src.game.manage_owner_events.coordinator.list_strays_for_server", new=AsyncMock(return_value=[stray])
            ),
            patch("src.game.manage_owner_events.coordinator.remove_pooch_from_strays", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.transfer_pooch_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.get_target_kennel_ids", new=AsyncMock(return_value=[20])),
            patch("src.game.manage_owner_events.coordinator.get_kennel_by_id", new=AsyncMock(return_value=kennel)),
            patch("src.game.manage_owner_events.coordinator.list_pooches_for_kennel", new=AsyncMock(return_value=[])),
            patch("src.game.manage_owner_events.coordinator.add_pooch_to_kennel", new=AsyncMock()),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 85 in result.pooches_created


# ---------------------------------------------------------------------------
# _execute_single_action: add_mutation / remove_mutation / add_breed / remove_breed
# ---------------------------------------------------------------------------


class TestMutationAndBreed:
    @pytest.mark.asyncio
    async def test_add_mutation(self, context, rng):
        action = _make_action("add_mutation", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[1])),
            patch("src.game.manage_owner_events.coordinator.handle_add_mutation", new=AsyncMock()) as mock_add,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_add.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_mutation(self, context, rng):
        action = _make_action("remove_mutation", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[1])),
            patch("src.game.manage_owner_events.coordinator.handle_remove_mutation", new=AsyncMock()) as mock_rem,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_rem.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_breed(self, context, rng):
        action = _make_action("add_breed", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[2])),
            patch("src.game.manage_owner_events.coordinator.handle_add_breed", new=AsyncMock()) as mock_breed,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_breed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_breed(self, context, rng):
        action = _make_action("remove_breed", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[3])),
            patch("src.game.manage_owner_events.coordinator.handle_remove_breed", new=AsyncMock()) as mock_rem,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_rem.assert_awaited_once()


# ---------------------------------------------------------------------------
# _execute_single_action: transfer_pooch
# ---------------------------------------------------------------------------


class TestTransferPooch:
    @pytest.mark.asyncio
    async def test_transfer_to_owner(self, context, rng):
        action = _make_action("transfer_pooch", "pooch", {"new_owner_discord_id": 999})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[5])),
            patch("src.game.manage_owner_events.coordinator.transfer_pooch_to_owner", new=AsyncMock()) as mock_to_owner,
        ):
            result = await _execute_single_action(1, action, context, rng)
        mock_to_owner.assert_awaited_once_with(5, 999)
        assert 5 in result.pooches_affected

    @pytest.mark.asyncio
    async def test_transfer_to_vendor(self, context, rng):
        action = _make_action("transfer_pooch", "pooch", {"vendor_id": 7})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[6])),
            patch(
                "src.game.manage_owner_events.coordinator.transfer_pooch_to_vendor", new=AsyncMock()
            ) as mock_to_vendor,
        ):
            result = await _execute_single_action(1, action, context, rng)
        mock_to_vendor.assert_awaited_once_with(6, 7)
        assert 6 in result.pooches_affected


# ---------------------------------------------------------------------------
# _execute_single_action: modify_breeding_cooldown
# ---------------------------------------------------------------------------


class TestBreedingCooldown:
    @pytest.mark.asyncio
    async def test_modify_breeding_cooldown(self, context, rng):
        action = _make_action("modify_breeding_cooldown", "pooch", {"amount": -1})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[4])),
            patch(
                "src.game.manage_owner_events.coordinator.handle_modify_breeding_cooldown", new=AsyncMock()
            ) as mock_cd,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_cd.assert_awaited_once()


# ---------------------------------------------------------------------------
# _execute_single_action: rename_pooch
# ---------------------------------------------------------------------------


class TestRenamePooch:
    @pytest.mark.asyncio
    async def test_rename_pooch(self, context, rng):
        action = _make_action("rename_pooch", "pooch", {"name": "Rex"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[7])),
            patch("src.game.manage_owner_events.coordinator.handle_rename_pooch", new=AsyncMock()) as mock_rename,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_rename.assert_awaited_once()


# ---------------------------------------------------------------------------
# _execute_single_action: breed_pooches
# ---------------------------------------------------------------------------


class TestBreedPooches:
    @pytest.mark.asyncio
    async def test_breed_pooches_basic(self, context, rng):
        action = _make_action("breed_pooches", "pooch", {})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])
            ),
            patch("src.game.manage_owner_events.coordinator.breed_pooches", new=AsyncMock(return_value=[100])),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 100 in result.pooches_created
        assert "puppy" in result.message.lower()

    @pytest.mark.asyncio
    async def test_breed_pooches_multiple_babies(self, context, rng):
        action = _make_action("breed_pooches", "pooch", {})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])
            ),
            patch("src.game.manage_owner_events.coordinator.breed_pooches", new=AsyncMock(return_value=[101, 102])),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.message == "2 puppies were born!"
        assert 101 in result.pooches_created
        assert 102 in result.pooches_created

    @pytest.mark.asyncio
    async def test_breed_pooches_no_pooches_available(self, context, rng):
        action = _make_action("breed_pooches", "pooch", {})
        with patch("src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[])):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_breed_pooches_kennel_target_no_kennel(self, context, rng):
        action = _make_action("breed_pooches", "kennel", {})
        with (patch("src.game.manage_owner_events.coordinator.get_target_kennel_ids", new=AsyncMock(return_value=[])),):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_breed_pooches_save_as_baby(self, context, rng):
        action = _make_action("breed_pooches", "pooch", {"save_as": "baby_slot"})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])
            ),
            patch("src.game.manage_owner_events.coordinator.breed_pooches", new=AsyncMock(return_value=[200])),
        ):
            await _execute_single_action(1, action, context, rng)
        assert context.extra_data["baby_slot"] == {"pooch_ids": [200]}

    @pytest.mark.asyncio
    async def test_breed_pooches_save_as_list(self, context, rng):
        save_as = [
            {"slot": "dad_slot", "target": "first_parent"},
            {"slot": "mom_slot", "target": "second_parent"},
            {"slot": "baby_slot", "target": "baby"},
        ]
        action = _make_action("breed_pooches", "pooch", {"save_as": save_as, "require_unique": True})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])
            ),
            patch("src.game.manage_owner_events.coordinator.breed_pooches", new=AsyncMock(return_value=[201])),
        ):
            await _execute_single_action(1, action, context, rng)
        assert "dad_slot" in context.extra_data
        assert "mom_slot" in context.extra_data
        assert context.extra_data["baby_slot"] == {"pooch_ids": [201]}

    @pytest.mark.asyncio
    async def test_breed_pooches_require_same(self, context, rng):
        """require_same=True means both parent IDs are the same."""
        action = _make_action("breed_pooches", "pooch", {"require_same": True})
        with (
            patch("src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[10])),
            patch(
                "src.game.manage_owner_events.coordinator.breed_pooches", new=AsyncMock(return_value=[300])
            ) as mock_breed,
        ):
            await _execute_single_action(1, action, context, rng)
        # Both parent IDs should be identical
        call_args = mock_breed.call_args
        assert call_args[0][0] == call_args[0][1]

    @pytest.mark.asyncio
    async def test_breed_pooches_value_error(self, context, rng):
        """If breed_pooches raises ValueError, it's caught gracefully."""
        action = _make_action("breed_pooches", "pooch", {})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])
            ),
            patch(
                "src.game.manage_owner_events.coordinator.breed_pooches", new=AsyncMock(side_effect=ValueError("bad"))
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_breed_pooches_selected_selector(self, context, rng):
        context.selected_pooch_id = 5
        action = _make_action(
            "breed_pooches", "pooch", {"first_pooch_selector": "selected", "second_pooch_selector": "random"}
        )
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[6, 7])
            ),
            patch(
                "src.game.manage_owner_events.coordinator.breed_pooches", new=AsyncMock(return_value=[400])
            ) as mock_breed,
        ):
            await _execute_single_action(1, action, context, rng)
        call_args = mock_breed.call_args
        # First parent should be the selected pooch
        assert call_args[0][0] == 5

    @pytest.mark.asyncio
    async def test_breed_pooches_with_baby_params(self, context, rng):
        """baby_name, baby_age, baby_base_health, baby_breeding_cooldown should be applied."""
        action = _make_action(
            "breed_pooches",
            "pooch",
            {
                "baby_name": "Spot",
                "baby_age": 0,
                "baby_base_health": 8,
                "baby_breeding_cooldown": 30,
            },
        )
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])
            ),
            patch("src.game.manage_owner_events.coordinator.breed_pooches", new=AsyncMock(return_value=[500])),
            patch("src.game.manage_owner_events.coordinator.rename_pooch", new=AsyncMock()) as mock_rename,
            patch("src.game.manage_owner_events.coordinator.modify_pooch_age", new=AsyncMock()) as mock_age,
            patch("src.game.manage_owner_events.coordinator.modify_pooch_base_health", new=AsyncMock()) as mock_health,
            patch("src.game.manage_owner_events.coordinator.set_pooch_breeding_cooldown", new=AsyncMock()) as mock_cd,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_rename.assert_awaited_once_with(500, "Spot")
        mock_age.assert_awaited_once_with(500, 0)
        mock_health.assert_awaited_once_with(500, 8)
        mock_cd.assert_awaited_once_with(500, 30)


# ---------------------------------------------------------------------------
# _execute_single_action: sell_pooch
# ---------------------------------------------------------------------------


class TestSellPooch:
    @pytest.mark.asyncio
    async def test_sell_pooch_to_random_vendor(self, context, rng):
        pooch = _make_pooch(15, alive=True)
        server = _make_server()
        vendor = _make_vendor(1)
        action = _make_action("sell_pooch", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[15])),
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch("src.game.manage_owner_events.coordinator.list_vendors", new=AsyncMock(return_value=[vendor])),
            patch("src.game.manage_owner_events.coordinator.get_pooch_sell_price", new=AsyncMock(return_value=100)),
            patch("src.game.manage_owner_events.coordinator.give_money_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.transfer_pooch_to_vendor", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.remove_pooch_from_kennel", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.add_pooch_to_vendor_stock", new=AsyncMock()),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.money_changed == 100
        assert 15 in result.pooches_affected

    @pytest.mark.asyncio
    async def test_sell_pooch_dead_skipped(self, context, rng):
        dead_pooch = _make_pooch(16, alive=False)
        action = _make_action("sell_pooch", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[16])),
            patch("src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[])),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=dead_pooch)),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.money_changed == 0
        assert result.pooches_affected == []

    @pytest.mark.asyncio
    async def test_sell_pooch_no_vendor(self, context, rng):
        pooch = _make_pooch(17, alive=True)
        action = _make_action("sell_pooch", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[17])),
            patch("src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[])),
            patch("src.game.manage_owner_events.coordinator.get_pooch_sell_price", new=AsyncMock(return_value=50)),
            patch("src.game.manage_owner_events.coordinator.give_money_to_owner", new=AsyncMock()),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
        ):
            result = await _execute_single_action(1, action, context, rng)
        # Should still pay money even without a vendor
        assert result.money_changed == 50


# ---------------------------------------------------------------------------
# _execute_single_action: buy_pooch
# ---------------------------------------------------------------------------


class TestBuyPooch:
    @pytest.mark.asyncio
    async def test_buy_pooch_success(self, context, rng):
        server = _make_server()
        vendor = _make_vendor(2)
        pooch_db = _make_pooch(90, name="ForSale")
        owner = SimpleNamespace(dollars=500)
        action = _make_action("buy_pooch", "pooch", {})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch("src.game.manage_owner_events.coordinator.list_vendors", new=AsyncMock(return_value=[vendor])),
            patch(
                "src.game.manage_owner_events.coordinator.list_vendor_pooch_stock",
                new=AsyncMock(return_value=[pooch_db]),
            ),
            patch("src.game.manage_owner_events.coordinator.get_pooch_buy_price", new=AsyncMock(return_value=200)),
            patch(
                "src.game.manage_owner_events.coordinator.get_owner_by_discord_id", new=AsyncMock(return_value=owner)
            ),
            patch("src.game.manage_owner_events.coordinator.remove_pooch_from_vendor_stock", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.give_money_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.transfer_pooch_to_owner", new=AsyncMock()),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.money_changed == -200
        assert 90 in result.pooches_created

    @pytest.mark.asyncio
    async def test_buy_pooch_insufficient_funds(self, context, rng):
        server = _make_server()
        vendor = _make_vendor(3)
        pooch_db = _make_pooch(91, name="Pricey")
        owner = SimpleNamespace(dollars=10)
        action = _make_action("buy_pooch", "pooch", {})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch("src.game.manage_owner_events.coordinator.list_vendors", new=AsyncMock(return_value=[vendor])),
            patch(
                "src.game.manage_owner_events.coordinator.list_vendor_pooch_stock",
                new=AsyncMock(return_value=[pooch_db]),
            ),
            patch("src.game.manage_owner_events.coordinator.get_pooch_buy_price", new=AsyncMock(return_value=999)),
            patch(
                "src.game.manage_owner_events.coordinator.get_owner_by_discord_id", new=AsyncMock(return_value=owner)
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.money_changed == 0
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_buy_pooch_no_vendor(self, context, rng):
        action = _make_action("buy_pooch", "pooch", {})
        with (
            patch("src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[])),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_buy_pooch_empty_stock(self, context, rng):
        server = _make_server()
        vendor = _make_vendor(4)
        action = _make_action("buy_pooch", "pooch", {})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch("src.game.manage_owner_events.coordinator.list_vendors", new=AsyncMock(return_value=[vendor])),
            patch("src.game.manage_owner_events.coordinator.list_vendor_pooch_stock", new=AsyncMock(return_value=[])),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_created == []

    @pytest.mark.asyncio
    async def test_buy_pooch_save_as(self, context, rng):
        server = _make_server()
        vendor = _make_vendor(5)
        pooch_db = _make_pooch(92, name="Buddy")
        owner = SimpleNamespace(dollars=999)
        action = _make_action("buy_pooch", "pooch", {"save_as": "bought_slot"})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[server])
            ),
            patch("src.game.manage_owner_events.coordinator.list_vendors", new=AsyncMock(return_value=[vendor])),
            patch(
                "src.game.manage_owner_events.coordinator.list_vendor_pooch_stock",
                new=AsyncMock(return_value=[pooch_db]),
            ),
            patch("src.game.manage_owner_events.coordinator.get_pooch_buy_price", new=AsyncMock(return_value=100)),
            patch(
                "src.game.manage_owner_events.coordinator.get_owner_by_discord_id", new=AsyncMock(return_value=owner)
            ),
            patch("src.game.manage_owner_events.coordinator.remove_pooch_from_vendor_stock", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.give_money_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.transfer_pooch_to_owner", new=AsyncMock()),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
        ):
            await _execute_single_action(1, action, context, rng)
        assert context.extra_data["bought_slot"] == {"pooch_ids": [92]}


# ---------------------------------------------------------------------------
# _execute_single_action: start_event
# ---------------------------------------------------------------------------


class TestStartEvent:
    @pytest.mark.asyncio
    async def test_start_event_specific_instant(self, context, rng):
        """start_event with a named instant event runs inline."""
        inner_action = _make_action("modify_money", "owner", {"amount": 10})
        followup_event = _make_event_db(event_id=20, actions=[inner_action], options=[])
        action = _make_action("start_event", "owner", {"event": "Test Event"})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.db_get_owner_event_by_name",
                new=AsyncMock(return_value=followup_event),
            ),
            patch("src.game.manage_owner_events.coordinator.give_money_to_owner", new=AsyncMock()),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.money_changed == 10

    @pytest.mark.asyncio
    async def test_start_event_unknown_event(self, context, rng):
        action = _make_action("start_event", "owner", {"event": "Nonexistent Event"})
        with patch(
            "src.game.manage_owner_events.coordinator.db_get_owner_event_by_name", new=AsyncMock(return_value=None)
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert "Error" in result.message

    @pytest.mark.asyncio
    async def test_start_event_random_event_not_found(self, context, rng):
        action = _make_action("start_event", "owner", {"random_event": True})
        with patch(
            "src.game.manage_owner_events.coordinator.get_random_eligible_owner_event_for_owner",
            new=AsyncMock(return_value=None),
        ):
            result = await _execute_single_action(1, action, context, rng)
        # Should complete without error
        assert result.success is True

    @pytest.mark.asyncio
    async def test_start_event_requires_response(self, context, rng):
        """start_event with a response-required event triggers it via trigger_specific_event."""
        import sys
        import types

        followup_event = _make_event_db(event_id=21, requires_response=True)
        started = MagicMock()
        started.active_owner_event_id = 55
        started.event_id = 21
        started.name = "Resp Event"

        # Provide a fake 'public' module so the lazy import inside the coordinator works
        fake_public = types.ModuleType("src.game.manage_owner_events.public")
        fake_public.trigger_specific_event = AsyncMock(return_value=started)

        action = _make_action("start_event", "owner", {"event": "Resp Event"})
        original = sys.modules.get("src.game.manage_owner_events.public")
        sys.modules["src.game.manage_owner_events.public"] = fake_public
        try:
            with patch(
                "src.game.manage_owner_events.coordinator.db_get_owner_event_by_name",
                new=AsyncMock(return_value=followup_event),
            ):
                result = await _execute_single_action(1, action, context, rng)
        finally:
            if original is None:
                sys.modules.pop("src.game.manage_owner_events.public", None)
            else:
                sys.modules["src.game.manage_owner_events.public"] = original

        started_list = result.extra_data.get("started_events", [])
        assert len(started_list) == 1
        assert started_list[0]["active_owner_event_id"] == 55

    @pytest.mark.asyncio
    async def test_start_event_instant_with_default_option_and_outcome(self, context, rng):
        """Instant event with a default option and outcome runs all three layers."""
        inner_outcome_action = _make_action("modify_money", "owner", {"amount": 5})
        outcome = _make_outcome(actions=[inner_outcome_action])
        opt = _make_option(option_id=1, actions=[], outcomes=[outcome], is_default=True)
        followup_event = _make_event_db(event_id=22, actions=[], options=[opt])
        action = _make_action("start_event", "owner", {"event": "Instant Event"})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.db_get_owner_event_by_name",
                new=AsyncMock(return_value=followup_event),
            ),
            patch(
                "src.game.manage_owner_events.coordinator.choose_option_outcome", new=AsyncMock(return_value=outcome)
            ),
            patch("src.game.manage_owner_events.coordinator.give_money_to_owner", new=AsyncMock()),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.money_changed == 5


# ---------------------------------------------------------------------------
# _execute_single_action: start_stray_event
# ---------------------------------------------------------------------------


class TestStartStrayEvent:
    @pytest.mark.asyncio
    async def test_start_stray_event_missing_param(self, context, rng):
        action = _make_action("start_stray_event", "owner", {})
        result = await _execute_single_action(1, action, context, rng)
        # Should log and skip, success stays True
        assert result.success is True

    @pytest.mark.asyncio
    async def test_start_stray_event_unknown(self, context, rng):
        action = _make_action("start_stray_event", "owner", {"event": "Unknown Stray Event"})
        with patch(
            "src.game.manage_owner_events.coordinator.get_stray_event_by_name", new=AsyncMock(return_value=None)
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_start_stray_event_no_servers(self, context, rng):
        stray_event = MagicMock()
        stray_event.filter = {}
        action = _make_action("start_stray_event", "owner", {"event": "Lucky Stray"})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.get_stray_event_by_name",
                new=AsyncMock(return_value=stray_event),
            ),
            patch("src.game.manage_owner_events.coordinator.list_servers_for_owner", new=AsyncMock(return_value=[])),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.success is True


# ---------------------------------------------------------------------------
# _execute_single_action: select_pooch
# ---------------------------------------------------------------------------


class TestSelectPooch:
    @pytest.mark.asyncio
    async def test_select_pooch(self, context, rng):
        action = _make_action("select_pooch", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[21])),
            patch("src.game.manage_owner_events.coordinator.handle_select_pooch", new=AsyncMock()) as mock_sel,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_sel.assert_awaited_once()


# ---------------------------------------------------------------------------
# _execute_single_action: modify_<stat>
# ---------------------------------------------------------------------------


class TestModifyStat:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "stat_action",
        [
            "modify_strength",
            "modify_cuteness",
            "modify_fluffiness",
            "modify_intelligence",
            "modify_dexterity",
            "modify_fertility",
            "modify_aggressiveness",
        ],
    )
    async def test_modify_stat(self, context, rng, stat_action):
        action = _make_action(stat_action, "pooch", {"selector": "random", "amount": 1})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[33])),
            patch("src.game.manage_owner_events.coordinator.handle_modify_stat", new=AsyncMock()) as mock_stat,
        ):
            await _execute_single_action(1, action, context, rng)
        mock_stat.assert_awaited_once()


# ---------------------------------------------------------------------------
# _execute_single_action: damn_pooch
# ---------------------------------------------------------------------------


class TestDamnPooch:
    @pytest.mark.asyncio
    async def test_damn_pooch_single(self, context, rng):
        action = _make_action("damn_pooch", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[40])),
            patch(
                "src.game.manage_owner_events.coordinator.handle_damn_pooch",
                new=AsyncMock(side_effect=lambda pids, params, r, res, ctx, attr: res.pooches_killed.append(40)),
            ) as mock_damn,
        ):
            result = await _execute_single_action(1, action, context, rng)
        mock_damn.assert_awaited_once()
        assert "damned" in result.message.lower()

    @pytest.mark.asyncio
    async def test_damn_pooch_no_kills(self, context, rng):
        """If handle_damn_pooch doesn't add kills, no message is set."""
        action = _make_action("damn_pooch", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[40])),
            patch("src.game.manage_owner_events.coordinator.handle_damn_pooch", new=AsyncMock()),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.message == ""


# ---------------------------------------------------------------------------
# _execute_single_action: revive_pooch
# ---------------------------------------------------------------------------


class TestRevivePooch:
    @pytest.mark.asyncio
    async def test_revive_pooch_kennel(self, context, rng):
        pooch = _make_pooch(50)
        action = _make_action("revive_pooch", "pooch", {"destination": "kennel"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[50])),
            patch("src.game.manage_owner_events.coordinator.revive_pooch", new=AsyncMock(return_value=pooch)),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch",
                new=AsyncMock(return_value=("kennel", "Revival K")),
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 50 in result.pooches_affected
        assert "Revival K" in result.message

    @pytest.mark.asyncio
    async def test_revive_pooch_graveyard(self, context, rng):
        pooch = _make_pooch(51)
        action = _make_action("revive_pooch", "pooch", {"destination": "graveyard"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[51])),
            patch("src.game.manage_owner_events.coordinator.revive_pooch", new=AsyncMock(return_value=pooch)),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch",
                new=AsyncMock(return_value=("graveyard", None)),
            ),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert "graveyard" in result.message.lower()

    @pytest.mark.asyncio
    async def test_revive_pooch_hell(self, context, rng):
        pooch = _make_pooch(52)
        action = _make_action("revive_pooch", "pooch", {"destination": "hell"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[52])),
            patch("src.game.manage_owner_events.coordinator.revive_pooch", new=AsyncMock(return_value=pooch)),
            patch("src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("hell", None))),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert "Hell" in result.message

    @pytest.mark.asyncio
    async def test_revive_pooch_save_as(self, context, rng):
        pooch = _make_pooch(53)
        action = _make_action("revive_pooch", "pooch", {"destination": "kennel", "save_as": "revived_slot"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[53])),
            patch("src.game.manage_owner_events.coordinator.revive_pooch", new=AsyncMock(return_value=pooch)),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
        ):
            await _execute_single_action(1, action, context, rng)
        assert 53 in context.extra_data["revived_slot"]["pooch_ids"]

    @pytest.mark.asyncio
    async def test_revive_pooch_failed(self, context, rng):
        action = _make_action("revive_pooch", "pooch", {})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[54])),
            patch("src.game.manage_owner_events.coordinator.revive_pooch", new=AsyncMock(return_value=None)),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.pooches_affected == []


# ---------------------------------------------------------------------------
# _execute_single_action: conjure_pooch
# ---------------------------------------------------------------------------


class TestConjurePooch:
    @pytest.mark.asyncio
    async def test_conjure_pooch_basic(self, context, rng):
        conjured = _make_pooch(70, name="Hellhound")
        mark = SimpleNamespace(id=999)
        action = _make_action("conjure_pooch", "owner", {})
        with (
            patch("src.game.manage_owner_events.coordinator.get_random_breed_ids", new=AsyncMock(return_value=[1])),
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=conjured)),
            patch(
                "src.game.manage_owner_events.coordinator.get_pooch_bloodskull_value", new=AsyncMock(return_value=10)
            ),
            patch("src.game.manage_owner_events.coordinator.get_mutation_by_name", new=AsyncMock(return_value=mark)),
            patch("src.game.manage_owner_events.coordinator.add_mutation_to_pooch", new=AsyncMock()),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
            patch("src.game.manage_owner_events.coordinator.delete_pooch", new=AsyncMock()),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert 70 in result.pooches_created
        assert context.selected_pooch_id == 70
        assert "conjured" in result.message.lower()

    @pytest.mark.asyncio
    async def test_conjure_pooch_num_rolls_keeps_best(self, context, rng):
        """With num_rolls=2, creates 2 pooches and keeps the one with higher bloodskull value."""
        pooch_a = _make_pooch(71, name="PoorDog")
        pooch_b = _make_pooch(72, name="BestDog")
        create_calls = [pooch_a, pooch_b]
        bloodskull_calls = {71: 5, 72: 15}
        mark = SimpleNamespace(id=998)
        action = _make_action("conjure_pooch", "owner", {"num_rolls": 2})
        with (
            patch("src.game.manage_owner_events.coordinator.get_random_breed_ids", new=AsyncMock(return_value=[1])),
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(side_effect=create_calls)),
            patch(
                "src.game.manage_owner_events.coordinator.get_pooch_bloodskull_value",
                new=AsyncMock(side_effect=lambda pid: bloodskull_calls[pid]),
            ),
            patch("src.game.manage_owner_events.coordinator.get_mutation_by_name", new=AsyncMock(return_value=mark)),
            patch("src.game.manage_owner_events.coordinator.add_mutation_to_pooch", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("town", None))),
            patch("src.game.manage_owner_events.coordinator.delete_pooch", new=AsyncMock()) as mock_del,
        ):
            result = await _execute_single_action(1, action, context, rng)
        # The worse pooch should be deleted
        mock_del.assert_awaited_once_with(71)
        assert 72 in result.pooches_created

    @pytest.mark.asyncio
    async def test_conjure_pooch_save_as(self, context, rng):
        conjured = _make_pooch(73, name="Demon")
        action = _make_action("conjure_pooch", "owner", {"save_as": "demon_slot"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_random_breed_ids", new=AsyncMock(return_value=[1])),
            patch("src.game.manage_owner_events.coordinator.create_pooch", new=AsyncMock(return_value=conjured)),
            patch("src.game.manage_owner_events.coordinator.get_pooch_bloodskull_value", new=AsyncMock(return_value=5)),
            patch("src.game.manage_owner_events.coordinator.get_mutation_by_name", new=AsyncMock(return_value=None)),
            patch(
                "src.game.manage_owner_events.coordinator.deliver_pooch", new=AsyncMock(return_value=("kennel", "K"))
            ),
            patch("src.game.manage_owner_events.coordinator.delete_pooch", new=AsyncMock()),
        ):
            await _execute_single_action(1, action, context, rng)
        assert context.extra_data["demon_slot"] == {"pooch_ids": [73]}


# ---------------------------------------------------------------------------
# _execute_single_action: sacrifice_pooch
# ---------------------------------------------------------------------------


class TestSacrificePooch:
    @pytest.mark.asyncio
    async def test_sacrifice_pooch(self, context, rng):
        pooch = _make_pooch(60, alive=True)
        action = _make_action("sacrifice_pooch", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[60])),
            patch("src.game.manage_owner_events.coordinator.get_pooch_bloodskull_value", new=AsyncMock(return_value=7)),
            patch("src.game.manage_owner_events.coordinator.give_bloodskulls_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.give_bones_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.set_pooch_dead", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.remove_pooch_from_kennel", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.damn_pooch", new=AsyncMock()),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.bloodskulls_changed == 7
        assert 60 in result.pooches_killed
        assert "sacrificed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_sacrifice_pooch_dead_skipped(self, context, rng):
        dead_pooch = _make_pooch(61, alive=False)
        action = _make_action("sacrifice_pooch", "pooch", {"selector": "random"})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[61])),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=dead_pooch)),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.bloodskulls_changed == 0
        assert result.pooches_killed == []

    @pytest.mark.asyncio
    async def test_sacrifice_multiple_pooches(self, context, rng):
        pooch_a = _make_pooch(62, alive=True)
        pooch_b = _make_pooch(63, alive=True)
        action = _make_action("sacrifice_pooch", "pooch", {"selector": "all"})
        with (
            patch(
                "src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[62, 63])
            ),
            patch(
                "src.game.manage_owner_events.coordinator.get_pooch_bloodskull_value", new=AsyncMock(side_effect=[3, 4])
            ),
            patch("src.game.manage_owner_events.coordinator.give_bloodskulls_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.give_bones_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.set_pooch_dead", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.remove_pooch_from_kennel", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.damn_pooch", new=AsyncMock()),
            patch("src.database.get_pooch_by_id", new=AsyncMock(side_effect=[pooch_a, pooch_b])),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.bloodskulls_changed == 7
        assert "2 pooches" in result.message

    @pytest.mark.asyncio
    async def test_sacrifice_with_value_multiplier(self, context, rng):
        pooch = _make_pooch(64, alive=True)
        action = _make_action("sacrifice_pooch", "pooch", {"value_multiplier": 2.0})
        with (
            patch("src.game.manage_owner_events.coordinator.get_target_pooch_ids", new=AsyncMock(return_value=[64])),
            patch("src.game.manage_owner_events.coordinator.get_pooch_bloodskull_value", new=AsyncMock(return_value=5)),
            patch("src.game.manage_owner_events.coordinator.give_bloodskulls_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.give_bones_to_owner", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.set_pooch_dead", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.remove_pooch_from_kennel", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.damn_pooch", new=AsyncMock()),
            patch("src.database.get_pooch_by_id", new=AsyncMock(return_value=pooch)),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.bloodskulls_changed == 10  # 5 * 2.0


# ---------------------------------------------------------------------------
# _execute_single_action: unknown action type
# ---------------------------------------------------------------------------


class TestUnknownActionType:
    @pytest.mark.asyncio
    async def test_unknown_action_logs_warning(self, context, rng):
        action = _make_action("totally_made_up_action", "pooch", {})
        result = await _execute_single_action(1, action, context, rng)
        # Should complete without raising
        assert result.success is True

    @pytest.mark.asyncio
    async def test_exception_sets_success_false(self, context, rng):
        """If an exception is raised inside the action, success=False is set."""
        action = _make_action("modify_money", "owner", {"amount": 50})
        with patch(
            "src.game.manage_owner_events.coordinator.give_money_to_owner",
            new=AsyncMock(side_effect=RuntimeError("DB down")),
        ):
            result = await _execute_single_action(1, action, context, rng)
        assert result.success is False
        assert "DB down" in result.message


# ---------------------------------------------------------------------------
# execute_event_actions
# ---------------------------------------------------------------------------


class TestExecuteEventActions:
    @pytest.mark.asyncio
    async def test_executes_all_actions_in_order(self, context, rng):
        order = []

        async def fake_single_action(owner_id, action, ctx, r, **kwargs):
            order.append(action.action_order)
            return OwnerEventResult()

        action_a = _make_action("modify_money", parameters={"amount": 1})
        action_a.action_order = 0
        action_b = _make_action("modify_money", parameters={"amount": 2})
        action_b.action_order = 1
        action_c = _make_action("modify_money", parameters={"amount": 3})
        action_c.action_order = 2

        with (
            patch("src.game.manage_owner_events.coordinator.get_current_season", new=AsyncMock(return_value="spring")),
            patch(
                "src.game.manage_owner_events.coordinator._execute_single_action",
                new=fake_single_action,
            ),
        ):
            await execute_event_actions(1, [action_c, action_a, action_b], context, rng)

        assert order == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_repeat_executes_multiple_times(self, context, rng):
        call_count = []

        async def fake_single_action(owner_id, action, ctx, r, **kwargs):
            call_count.append(1)
            return OwnerEventResult()

        action = _make_action("modify_money", parameters={"amount": 1})
        action.repeat = 3
        action.action_order = 0

        with (
            patch("src.game.manage_owner_events.coordinator.get_current_season", new=AsyncMock(return_value="spring")),
            patch(
                "src.game.manage_owner_events.coordinator._execute_single_action",
                new=fake_single_action,
            ),
        ):
            await execute_event_actions(1, [action], context, rng)

        assert len(call_count) == 3

    @pytest.mark.asyncio
    async def test_results_are_merged(self, context, rng):
        res_a = OwnerEventResult(money_changed=10)
        res_b = OwnerEventResult(money_changed=20)

        async def fake_single_action(owner_id, action, ctx, r, **kwargs):
            return [res_a, res_b][action.action_order]

        action_a = _make_action("modify_money", parameters={"amount": 10})
        action_a.action_order = 0
        action_b = _make_action("modify_money", parameters={"amount": 20})
        action_b.action_order = 1

        with (
            patch("src.game.manage_owner_events.coordinator.get_current_season", new=AsyncMock(return_value="spring")),
            patch(
                "src.game.manage_owner_events.coordinator._execute_single_action",
                new=fake_single_action,
            ),
        ):
            result = await execute_event_actions(1, [action_a, action_b], context, rng)

        assert result.money_changed == 30

    @pytest.mark.asyncio
    async def test_empty_actions_returns_default_result(self, context, rng):
        with patch("src.game.manage_owner_events.coordinator.get_current_season", new=AsyncMock(return_value="spring")):
            result = await execute_event_actions(1, [], context, rng)
        assert result.success is True
        assert result.money_changed == 0

    @pytest.mark.asyncio
    async def test_non_int_repeat_defaults_to_one(self, context, rng):
        call_count = []

        async def fake_single_action(owner_id, action, ctx, r, **kwargs):
            call_count.append(1)
            return OwnerEventResult()

        action = _make_action("modify_money", parameters={"amount": 1})
        action.repeat = "not_an_int"
        action.action_order = 0

        with (
            patch("src.game.manage_owner_events.coordinator.get_current_season", new=AsyncMock(return_value="spring")),
            patch(
                "src.game.manage_owner_events.coordinator._execute_single_action",
                new=fake_single_action,
            ),
        ):
            await execute_event_actions(1, [action], context, rng)

        assert len(call_count) == 1


# ---------------------------------------------------------------------------
# create_and_execute_event
# ---------------------------------------------------------------------------


class TestCreateAndExecuteEvent:
    @pytest.mark.asyncio
    async def test_instant_event_archived_after_execution(self, context, rng):
        event = _make_event_db(event_id=1, requires_response=False)
        active_event = _make_active_event(event_id=1)
        triggered = MagicMock()

        with (
            patch("src.game.manage_owner_events.coordinator.create_event_context", new=AsyncMock(return_value=context)),
            patch(
                "src.game.manage_owner_events.coordinator.create_active_owner_event",
                new=AsyncMock(return_value=active_event),
            ),
            patch("src.game.manage_owner_events.coordinator.update_active_event_result", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.archive_active_event", new=AsyncMock()) as mock_archive,
            patch(
                "src.game.manage_owner_events.coordinator.to_triggered_owner_event",
                new=AsyncMock(return_value=triggered),
            ),
        ):
            result = await create_and_execute_event(1, event, rng)

        mock_archive.assert_awaited_once_with(active_event.id)
        assert result is triggered

    @pytest.mark.asyncio
    async def test_response_required_event_not_archived(self, rng):
        context = OwnerEventContext(owner_discord_id=1)
        event = _make_event_db(event_id=2, requires_response=True, response_timeout=3600)
        active_event = _make_active_event(event_id=2)
        triggered = MagicMock()

        with (
            patch("src.game.manage_owner_events.coordinator.create_event_context", new=AsyncMock(return_value=context)),
            patch(
                "src.game.manage_owner_events.coordinator.create_active_owner_event",
                new=AsyncMock(return_value=active_event),
            ),
            patch("src.game.manage_owner_events.coordinator.update_active_event_result", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.update_active_event_context", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.archive_active_event", new=AsyncMock()) as mock_archive,
            patch("src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
            patch(
                "src.game.manage_owner_events.coordinator.to_triggered_owner_event",
                new=AsyncMock(return_value=triggered),
            ),
        ):
            result = await create_and_execute_event(1, event, rng)

        mock_archive.assert_not_awaited()
        assert result is triggered

    @pytest.mark.asyncio
    async def test_create_active_event_failure_returns_none(self, rng):
        context = OwnerEventContext(owner_discord_id=1)
        event = _make_event_db(event_id=3)

        with (
            patch("src.game.manage_owner_events.coordinator.create_event_context", new=AsyncMock(return_value=context)),
            patch(
                "src.game.manage_owner_events.coordinator.create_active_owner_event", new=AsyncMock(return_value=None)
            ),
        ):
            result = await create_and_execute_event(1, event, rng)

        assert result is None

    @pytest.mark.asyncio
    async def test_inherited_slots_are_applied(self, rng):
        context = OwnerEventContext(owner_discord_id=1)
        event = _make_event_db(event_id=4)
        active_event = _make_active_event(event_id=4)
        triggered = MagicMock()
        inherited = {"parent_slot": {"pooch_ids": [99]}}

        with (
            patch("src.game.manage_owner_events.coordinator.create_event_context", new=AsyncMock(return_value=context)),
            patch(
                "src.game.manage_owner_events.coordinator.create_active_owner_event",
                new=AsyncMock(return_value=active_event),
            ),
            patch("src.game.manage_owner_events.coordinator.update_active_event_result", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.archive_active_event", new=AsyncMock()),
            patch(
                "src.game.manage_owner_events.coordinator.to_triggered_owner_event",
                new=AsyncMock(return_value=triggered),
            ),
        ):
            await create_and_execute_event(1, event, rng, inherited_slots=inherited)

        assert context.extra_data["parent_slot"] == {"pooch_ids": [99]}

    @pytest.mark.asyncio
    async def test_response_event_sets_expires_at(self, rng):
        from datetime import datetime, timezone

        context = OwnerEventContext(owner_discord_id=1)
        event = _make_event_db(event_id=5, requires_response=True, response_timeout=7200)
        active_event = _make_active_event(event_id=5)
        triggered = MagicMock()

        create_mock = AsyncMock(return_value=active_event)

        with (
            patch("src.game.manage_owner_events.coordinator.create_event_context", new=AsyncMock(return_value=context)),
            patch("src.game.manage_owner_events.coordinator.create_active_owner_event", new=create_mock),
            patch("src.game.manage_owner_events.coordinator.update_active_event_result", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.update_active_event_context", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
            patch(
                "src.game.manage_owner_events.coordinator.to_triggered_owner_event",
                new=AsyncMock(return_value=triggered),
            ),
        ):
            await create_and_execute_event(1, event, rng)

        # expires_at should have been passed to create_active_owner_event
        call_kwargs = create_mock.call_args[1]
        expires_at = call_kwargs["expires_at"]
        assert expires_at is not None
        now = datetime.now(timezone.utc)
        diff = (expires_at - now).total_seconds()
        assert 7190 < diff <= 7200

    @pytest.mark.asyncio
    async def test_preflight_suppress_option_no_candidates(self, rng):
        """Options whose exclude_claimed filter yields no candidates should be suppressed."""
        context = OwnerEventContext(owner_discord_id=1)
        option = _make_option(option_id=55, is_visible=True, option_order=0)
        inner_action = _make_action("modify_money", parameters={"exclude_claimed": True, "filter": {}})
        inner_action.action_order = 0
        option.actions = [inner_action]
        event = _make_event_db(event_id=6, requires_response=True, options=[option])
        active_event = _make_active_event(event_id=6)
        triggered = MagicMock()

        with (
            patch("src.game.manage_owner_events.coordinator.create_event_context", new=AsyncMock(return_value=context)),
            patch(
                "src.game.manage_owner_events.coordinator.create_active_owner_event",
                new=AsyncMock(return_value=active_event),
            ),
            patch("src.game.manage_owner_events.coordinator.update_active_event_result", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.update_active_event_context", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
            patch(
                "src.game.manage_owner_events.coordinator.to_triggered_owner_event",
                new=AsyncMock(return_value=triggered),
            ),
        ):
            await create_and_execute_event(1, event, rng)

        assert 55 in context.extra_data.get("suppressed_option_ids", [])

    @pytest.mark.asyncio
    async def test_preflight_claimed_ids_written_to_context(self, rng):
        """When exclude_claimed=True and candidates exist, a slot key is written for the option."""
        context = OwnerEventContext(owner_discord_id=1)
        option = _make_option(option_id=66, is_visible=True, option_order=0)
        inner_action = _make_action("modify_money", parameters={"exclude_claimed": True, "filter": {}})
        inner_action.action_order = 0
        option.actions = [inner_action]
        event = _make_event_db(event_id=7, requires_response=True, options=[option])
        active_event = _make_active_event(event_id=7)
        triggered = MagicMock()

        with (
            patch("src.game.manage_owner_events.coordinator.create_event_context", new=AsyncMock(return_value=context)),
            patch(
                "src.game.manage_owner_events.coordinator.create_active_owner_event",
                new=AsyncMock(return_value=active_event),
            ),
            patch("src.game.manage_owner_events.coordinator.update_active_event_result", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.update_active_event_context", new=AsyncMock()),
            patch(
                "src.game.manage_owner_events.coordinator.list_matching_pooch_ids", new=AsyncMock(return_value=[77, 88])
            ),
            patch(
                "src.game.manage_owner_events.coordinator.to_triggered_owner_event",
                new=AsyncMock(return_value=triggered),
            ),
        ):
            await create_and_execute_event(1, event, rng)

        slot_key = f"_claimed_{option.id}_0"
        assert slot_key in context.extra_data
        assert context.extra_data[slot_key] in [77, 88]
        # Option should NOT be suppressed because candidates existed
        assert 66 not in context.extra_data.get("suppressed_option_ids", [])

    @pytest.mark.asyncio
    async def test_event_actions_executed_at_trigger_time(self, rng):
        context = OwnerEventContext(owner_discord_id=1)
        trigger_action = _make_action("modify_money", parameters={"amount": 25})
        trigger_action.action_order = 0
        event = _make_event_db(event_id=8, actions=[trigger_action])
        active_event = _make_active_event(event_id=8)
        triggered = MagicMock()

        with (
            patch("src.game.manage_owner_events.coordinator.create_event_context", new=AsyncMock(return_value=context)),
            patch(
                "src.game.manage_owner_events.coordinator.create_active_owner_event",
                new=AsyncMock(return_value=active_event),
            ),
            patch("src.game.manage_owner_events.coordinator.update_active_event_result", new=AsyncMock()),
            patch("src.game.manage_owner_events.coordinator.archive_active_event", new=AsyncMock()),
            patch(
                "src.game.manage_owner_events.coordinator.to_triggered_owner_event",
                new=AsyncMock(return_value=triggered),
            ),
            patch("src.game.manage_owner_events.coordinator.give_money_to_owner", new=AsyncMock()) as mock_money,
        ):
            await create_and_execute_event(1, event, rng)

        mock_money.assert_awaited_once_with(1, 25)
