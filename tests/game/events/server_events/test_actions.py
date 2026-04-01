"""Tests for src/game/events/server_events/actions.py — server action execution."""

from __future__ import annotations

import random
from unittest.mock import AsyncMock, patch

import pytest

from src.game.events.server_events import (
    execute_server_actions,
    resolve_server_pool,
)
from src.game.models.events import ServerEventContext

MOD = "src.game.events.server_events.actions"


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


def _make_action(action_type: str, parameters: dict | None = None, repeat: int = 1) -> dict:
    """Build a server event action spec (plain dict, as expected by execute_server_actions)."""
    return {
        "action_type": action_type,
        "parameters": parameters if parameters is not None else {},
        "repeat": repeat,
    }


# ---------------------------------------------------------------------------
# execute_server_actions — empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_actions_returns_none_result(rng):
    """execute_server_actions with empty list should not raise."""
    result = await execute_server_actions(100, [], ServerEventContext(server_discord_id=100), rng)
    assert result is not None


# ---------------------------------------------------------------------------
# resolve_server_pool — saved slot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_server_pool_saved(rng):
    """
    Test resolve server pool saved.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_resolve_server_pool_saved`.
    """

    ctx = ServerEventContext(server_discord_id=100)
    ctx.saved_slots["my_slot"] = [10, 20]
    result = await resolve_server_pool(100, "saved", {}, rng, server_context=ctx, use_saved="my_slot")
    assert result == [10, 20]


@pytest.mark.asyncio
async def test_resolve_server_pool_saved_missing(rng):
    """
    Test resolve server pool saved missing.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_resolve_server_pool_saved_missing`.
    """

    ctx = ServerEventContext(server_discord_id=100)
    result = await resolve_server_pool(100, "saved", {}, rng, server_context=ctx, use_saved="no_slot")
    assert result == []


@pytest.mark.asyncio
async def test_resolve_server_pool_saved_no_context(rng):
    """
    Test resolve server pool saved no context.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_resolve_server_pool_saved_no_context`.
    """

    result = await resolve_server_pool(100, "saved", {}, rng, server_context=None, use_saved="slot")
    assert result == []


# ---------------------------------------------------------------------------
# resolve_server_pool — stray (no filter)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_server_pool_unknown_returns_empty(rng):
    """
    Test resolve server pool unknown returns empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_resolve_server_pool_unknown_returns_empty`.
    """

    result = await resolve_server_pool(100, "totally_unknown_pool", {}, rng)
    assert result == []


# ---------------------------------------------------------------------------
# execute_server_actions — kill_pooch
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

    action = _make_action("kill_pooch", {"selector": "random", "pool": "stray"})

    with (
        patch(f"{MOD}.resolve_server_pool", new=AsyncMock(return_value=[9])),
        patch(f"{MOD}.handle_kill_pooch", new=AsyncMock()) as mock_kill,
    ):
        await execute_server_actions(100, [action], ServerEventContext(server_discord_id=100), rng)

    mock_kill.assert_awaited_once()


# ---------------------------------------------------------------------------
# execute_server_actions — add_mutation
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

    action = _make_action("add_mutation", {"selector": "random", "pool": "stray", "name": "Fluffy"})

    with (
        patch(f"{MOD}.resolve_server_pool", new=AsyncMock(return_value=[7])),
        patch(f"{MOD}.handle_add_mutation", new=AsyncMock()) as mock_mut,
    ):
        await execute_server_actions(100, [action], ServerEventContext(server_discord_id=100), rng)

    mock_mut.assert_awaited_once()


# ---------------------------------------------------------------------------
# execute_server_actions — multiple actions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_actions_both_executed(rng):
    """
    Test multiple actions both executed.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_multiple_actions_both_executed`.
    """

    action1 = _make_action("kill_pooch", {"selector": "random", "pool": "stray"})
    action2 = _make_action("add_mutation", {"selector": "random", "pool": "stray", "name": "Fluffy"})

    with (
        patch(f"{MOD}.resolve_server_pool", new=AsyncMock(return_value=[11])),
        patch(f"{MOD}.handle_kill_pooch", new=AsyncMock()) as mock_kill,
        patch(f"{MOD}.handle_add_mutation", new=AsyncMock()) as mock_mut,
    ):
        await execute_server_actions(100, [action1, action2], ServerEventContext(server_discord_id=100), rng)

    mock_kill.assert_awaited_once()
    mock_mut.assert_awaited_once()
