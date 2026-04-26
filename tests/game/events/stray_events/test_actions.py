"""Tests for src/game/events/stray_events/actions.py — stray action execution."""

from __future__ import annotations

import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.events.stray_events import execute_stray_event_actions
from src.game.models import StrayEventContext, StrayEventResult

MOD = "src.game.events.stray_events.actions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(action_type: str, parameters: dict | None = None, repeat: int = 1) -> MagicMock:
    a = MagicMock()
    a.action_type = action_type
    a.parameters = parameters if parameters is not None else {}
    a.repeat = repeat
    a.action_order = 0
    return a


def _ctx(server_discord_id: int = 100, candidate_ids: list | None = None) -> StrayEventContext:
    return StrayEventContext(
        server_discord_id=server_discord_id,
        candidate_stray_ids=candidate_ids or [1, 2, 3],
    )


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


@pytest.fixture(autouse=True)
def mock_cancel_listing():
    """
    Mock cancel listing.

    Returns
    -------
    Any
        The result of calling `mock_cancel_listing`.
    """

    with patch(f"{MOD}.cancel_listing_for_pooch", new=AsyncMock(), create=True):
        yield


# ---------------------------------------------------------------------------
# execute_stray_event_actions — empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_actions_returns_empty_result(rng):
    """
    Test empty actions returns empty result.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_empty_actions_returns_empty_result`.
    """

    ctx = _ctx()
    result = await execute_stray_event_actions(100, [], ctx, rng)
    assert isinstance(result, StrayEventResult)


# ---------------------------------------------------------------------------
# kill_pooch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kill_pooch_action(rng):
    """
    Test kill pooch action.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_kill_pooch_action`.
    """

    ctx = _ctx(candidate_ids=[5])
    action = _make_action("kill_pooch", {"selector": "random"})
    with (
        patch(f"{MOD}.resolve_stray_target_ids", new=AsyncMock(return_value=[5])),
        patch(f"{MOD}.handle_kill_pooch", new=AsyncMock()) as mock_kill,
    ):
        await execute_stray_event_actions(100, [action], ctx, rng)
    mock_kill.assert_awaited_once()


# ---------------------------------------------------------------------------
# add_mutation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_mutation_action(rng):
    """
    Test add mutation action.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_add_mutation_action`.
    """

    ctx = _ctx(candidate_ids=[7])
    action = _make_action("add_mutation", {"selector": "random", "name": "Fluffy"})
    with (
        patch(f"{MOD}.resolve_stray_target_ids", new=AsyncMock(return_value=[7])),
        patch(f"{MOD}.handle_add_mutation", new=AsyncMock()) as mock_add_mut,
    ):
        await execute_stray_event_actions(100, [action], ctx, rng)
    mock_add_mut.assert_awaited_once()


# ---------------------------------------------------------------------------
# remove_mutation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_mutation_action(rng):
    """
    Test remove mutation action.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_remove_mutation_action`.
    """

    ctx = _ctx(candidate_ids=[8])
    action = _make_action("remove_mutation", {"selector": "random", "name": "Fluffy"})
    with (
        patch(f"{MOD}.resolve_stray_target_ids", new=AsyncMock(return_value=[8])),
        patch(f"{MOD}.handle_remove_mutation", new=AsyncMock()) as mock_rem,
    ):
        await execute_stray_event_actions(100, [action], ctx, rng)
    mock_rem.assert_awaited_once()


# ---------------------------------------------------------------------------
# modify_base_health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_base_health_action(rng):
    """
    Test modify base health action.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_modify_base_health_action`.
    """

    ctx = _ctx(candidate_ids=[9])
    action = _make_action("modify_base_health", {"selector": "all", "amount": -2})
    with (
        patch(f"{MOD}.resolve_stray_target_ids", new=AsyncMock(return_value=[9])),
        patch(f"{MOD}.handle_modify_health", new=AsyncMock()) as mock_health,
    ):
        await execute_stray_event_actions(100, [action], ctx, rng)
    mock_health.assert_awaited_once()


# ---------------------------------------------------------------------------
# repeat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_action_repeated(rng):
    """
    Test action repeated.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_action_repeated`.
    """

    ctx = _ctx(candidate_ids=[1])
    action = _make_action("kill_pooch", {"selector": "random"}, repeat=3)
    with (
        patch(f"{MOD}.resolve_stray_target_ids", new=AsyncMock(return_value=[1])),
        patch(f"{MOD}.handle_kill_pooch", new=AsyncMock()) as mock_kill,
    ):
        await execute_stray_event_actions(100, [action], ctx, rng)
    assert mock_kill.await_count == 3


# ---------------------------------------------------------------------------
# rename_pooch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_pooch_action(rng):
    """
    Test rename pooch action.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_rename_pooch_action`.
    """

    ctx = _ctx(candidate_ids=[11])
    action = _make_action("rename_pooch", {"selector": "random", "name": "Buddy"})
    with (
        patch(f"{MOD}.resolve_stray_target_ids", new=AsyncMock(return_value=[11])),
        patch(f"{MOD}.handle_rename_pooch", new=AsyncMock()) as mock_rename,
    ):
        await execute_stray_event_actions(100, [action], ctx, rng)
    mock_rename.assert_awaited_once()
