"""Tests for src/game/manage_owner_events/context.py"""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.manage_owner_events.context import create_event_context, deliver_pooch
from src.game.models.events.owner_events.owner_event_context import OwnerEventContext

MOD = "src.game.manage_owner_events.context"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


def _make_action(target_type: str, selector: str) -> MagicMock:
    a = MagicMock()
    a.target_type = target_type
    a.parameters = {"selector": selector}
    return a


def _make_outcome(actions=None) -> MagicMock:
    o = MagicMock()
    o.actions = actions or []
    return o


def _make_option(actions=None, outcomes=None) -> MagicMock:
    opt = MagicMock()
    opt.actions = actions or []
    opt.outcomes = outcomes or []
    return opt


def _make_event(actions=None, options=None, filter_spec=None) -> MagicMock:
    e = MagicMock()
    e.actions = actions or []
    e.options = options or []
    e.filter = filter_spec or {}
    return e


def _make_kennel(kennel_id: int, name: str = "K", pooch_limit: int = 3) -> SimpleNamespace:
    return SimpleNamespace(id=kennel_id, name=name, pooch_limit=pooch_limit)


def _make_server(discord_id: int = 100) -> SimpleNamespace:
    return SimpleNamespace(discord_id=discord_id)


# ===========================================================================
# create_event_context
# ===========================================================================


@pytest.mark.asyncio
async def test_create_event_context_basic_no_selected(rng):
    """Event with no 'selected' selectors → no selected_pooch_id / selected_kennel_id."""
    event = _make_event()
    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2])),
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[3, 4])),
    ):
        ctx = await create_event_context(1, event, rng)

    assert isinstance(ctx, OwnerEventContext)
    assert ctx.owner_discord_id == 1
    assert ctx.selected_pooch_id is None
    assert ctx.selected_kennel_id is None
    assert ctx.extra_data["candidate_kennel_ids"] == [1, 2]
    assert ctx.extra_data["candidate_pooch_ids"] == [3, 4]


@pytest.mark.asyncio
async def test_create_event_context_top_level_action_selected_pooch(rng):
    """Top-level action with target_type=pooch, selector=selected → selected_pooch_id resolved."""
    action = _make_action("pooch", "selected")
    event = _make_event(actions=[action])

    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[5])),
        patch(f"{MOD}.get_random_matching_pooch_id", new=AsyncMock(return_value=5)),
    ):
        ctx = await create_event_context(1, event, rng)

    assert ctx.selected_pooch_id == 5
    assert ctx.selected_kennel_id is None


@pytest.mark.asyncio
async def test_create_event_context_top_level_action_selected_kennel(rng):
    """Top-level action with target_type=kennel, selector=selected → selected_kennel_id resolved."""
    action = _make_action("kennel", "selected")
    event = _make_event(actions=[action])

    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[7])),
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.get_random_matching_kennel_id", new=AsyncMock(return_value=7)),
    ):
        ctx = await create_event_context(1, event, rng)

    assert ctx.selected_kennel_id == 7
    assert ctx.selected_pooch_id is None


@pytest.mark.asyncio
async def test_create_event_context_option_action_selected_pooch(rng):
    """Option-level action with selected pooch selector."""
    action = _make_action("pooch", "selected")
    option = _make_option(actions=[action])
    event = _make_event(options=[option])

    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[9])),
        patch(f"{MOD}.get_random_matching_pooch_id", new=AsyncMock(return_value=9)),
    ):
        ctx = await create_event_context(1, event, rng)

    assert ctx.selected_pooch_id == 9


@pytest.mark.asyncio
async def test_create_event_context_outcome_action_selected_pooch(rng):
    """Outcome-level action with selected pooch selector."""
    action = _make_action("pooch", "selected")
    outcome = _make_outcome(actions=[action])
    option = _make_option(outcomes=[outcome])
    event = _make_event(options=[option])

    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[11])),
        patch(f"{MOD}.get_random_matching_pooch_id", new=AsyncMock(return_value=11)),
    ):
        ctx = await create_event_context(1, event, rng)

    assert ctx.selected_pooch_id == 11


@pytest.mark.asyncio
async def test_create_event_context_applies_pooch_filter(rng):
    """When event.filter has 'pooches', that filter (minus meta keys) is forwarded."""
    action = _make_action("pooch", "selected")
    event = _make_event(
        actions=[action],
        filter_spec={"pooches": [{"min_count": 1, "description": "at least one", "alive": True}]},
    )

    captured_filter = {}

    async def _get_random_pooch(owner_id, f, rng_):
        captured_filter.update(f)
        return 42

    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[42])),
        patch(f"{MOD}.get_random_matching_pooch_id", new=AsyncMock(side_effect=_get_random_pooch)),
    ):
        await create_event_context(1, event, rng)

    # min_count and description should be stripped; alive should remain
    assert "min_count" not in captured_filter
    assert "description" not in captured_filter
    assert captured_filter.get("alive") is True


@pytest.mark.asyncio
async def test_create_event_context_applies_kennel_filter(rng):
    """When event.filter has 'kennels', that filter (minus meta keys) is forwarded."""
    action = _make_action("kennel", "selected")
    event = _make_event(
        actions=[action],
        filter_spec={"kennels": [{"min_count": 1, "max_count": 5, "full": False}]},
    )

    captured_filter = {}

    async def _get_random_kennel(owner_id, f, rng_):
        captured_filter.update(f)
        return 33

    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[33])),
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.get_random_matching_kennel_id", new=AsyncMock(side_effect=_get_random_kennel)),
    ):
        await create_event_context(1, event, rng)

    assert "min_count" not in captured_filter
    assert "max_count" not in captured_filter
    assert captured_filter.get("full") is False


@pytest.mark.asyncio
async def test_create_event_context_non_selected_selector_ignored(rng):
    """Actions with selector != 'selected' should NOT trigger pre-selection."""
    action = _make_action("pooch", "random")
    event = _make_event(actions=[action])

    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[1])),
        patch(f"{MOD}.get_random_matching_pooch_id", new=AsyncMock()) as mock_grm,
    ):
        ctx = await create_event_context(1, event, rng)

    mock_grm.assert_not_called()
    assert ctx.selected_pooch_id is None


# ===========================================================================
# deliver_pooch
# ===========================================================================


@pytest.mark.asyncio
async def test_deliver_kennel_with_space(rng):
    """Pooch goes to the first kennel with free space."""
    kennel = _make_kennel(1, name="Happy Home", pooch_limit=5)
    with (
        patch(f"{MOD}.list_kennels_for_owner", new=AsyncMock(return_value=[kennel])),
        patch(f"{MOD}.list_pooches_for_kennel", new=AsyncMock(return_value=[10, 20])),
        patch(f"{MOD}.add_pooch_to_kennel", new=AsyncMock()) as mock_add,
    ):
        dest, name = await deliver_pooch(1, 99, "kennel")

    assert dest == "kennel"
    assert name == "Happy Home"
    mock_add.assert_awaited_once_with(1, 99)


@pytest.mark.asyncio
async def test_deliver_kennel_full_falls_back_to_town(rng):
    """When all kennels are full, destination falls back to 'town'."""
    kennel = _make_kennel(1, pooch_limit=2)
    server = _make_server(discord_id=100)
    with (
        patch(f"{MOD}.list_kennels_for_owner", new=AsyncMock(return_value=[kennel])),
        patch(f"{MOD}.list_pooches_for_kennel", new=AsyncMock(return_value=[10, 20])),  # full
        patch(f"{MOD}.list_servers_for_owner", new=AsyncMock(return_value=[server])),
        patch(f"{MOD}.add_pooch_to_strays", new=AsyncMock()) as mock_strays,
    ):
        dest, name = await deliver_pooch(1, 99, "kennel")

    assert dest == "town"
    assert name is None
    mock_strays.assert_awaited_once_with(99, 100)


@pytest.mark.asyncio
async def test_deliver_kennel_no_kennels_falls_back_to_town(rng):
    """No kennels at all → falls back to town."""
    server = _make_server(discord_id=200)
    with (
        patch(f"{MOD}.list_kennels_for_owner", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.list_servers_for_owner", new=AsyncMock(return_value=[server])),
        patch(f"{MOD}.add_pooch_to_strays", new=AsyncMock()) as mock_strays,
    ):
        dest, name = await deliver_pooch(1, 7, "kennel")

    assert dest == "town"
    mock_strays.assert_awaited_once_with(7, 200)


@pytest.mark.asyncio
async def test_deliver_town_direct():
    """Direct town delivery releases pooch as stray on a random server."""
    server = _make_server(discord_id=55)
    with (
        patch(f"{MOD}.list_servers_for_owner", new=AsyncMock(return_value=[server])),
        patch(f"{MOD}.add_pooch_to_strays", new=AsyncMock()) as mock_strays,
    ):
        dest, name = await deliver_pooch(1, 42, "town")

    assert dest == "town"
    assert name is None
    mock_strays.assert_awaited_once_with(42, 55)


@pytest.mark.asyncio
async def test_deliver_town_no_servers_does_not_add_stray():
    """Town delivery with no servers should not crash and should not add to strays."""
    with (
        patch(f"{MOD}.list_servers_for_owner", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.add_pooch_to_strays", new=AsyncMock()) as mock_strays,
    ):
        dest, name = await deliver_pooch(1, 42, "town")

    assert dest == "town"
    mock_strays.assert_not_awaited()


@pytest.mark.asyncio
async def test_deliver_graveyard():
    with patch(f"{MOD}.bury_pooch", new=AsyncMock()) as mock_bury:
        dest, name = await deliver_pooch(1, 7, "graveyard")

    assert dest == "graveyard"
    assert name is None
    mock_bury.assert_awaited_once_with(1, 7)


@pytest.mark.asyncio
async def test_deliver_hell():
    with patch(f"{MOD}.damn_pooch", new=AsyncMock()) as mock_damn:
        dest, name = await deliver_pooch(1, 7, "hell")

    assert dest == "hell"
    assert name is None
    mock_damn.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_deliver_unknown_destination_falls_back_to_town():
    server = _make_server(discord_id=77)
    with (
        patch(f"{MOD}.list_servers_for_owner", new=AsyncMock(return_value=[server])),
        patch(f"{MOD}.add_pooch_to_strays", new=AsyncMock()),
    ):
        dest, name = await deliver_pooch(1, 5, "narnia")

    assert dest == "town"
    assert name is None


@pytest.mark.asyncio
async def test_deliver_destination_stripped_and_lowercased():
    """Destination string should be normalised before use."""
    with patch(f"{MOD}.damn_pooch", new=AsyncMock()) as mock_damn:
        dest, name = await deliver_pooch(1, 7, "  HELL  ")

    assert dest == "hell"
    mock_damn.assert_awaited_once()


@pytest.mark.asyncio
async def test_deliver_non_string_destination_defaults_to_town():
    """Non-string destination should fall back to 'town' path."""
    server = _make_server(discord_id=88)
    with (
        patch(f"{MOD}.list_servers_for_owner", new=AsyncMock(return_value=[server])),
        patch(f"{MOD}.add_pooch_to_strays", new=AsyncMock()),
    ):
        dest, name = await deliver_pooch(1, 5, None)  # type: ignore[arg-type]

    assert dest == "town"
