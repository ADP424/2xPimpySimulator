"""Tests for src/game/events/server_events/arena.py."""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.events.server_events import (
    get_arena,
    handle_arena_action,
    resolve_arena_matchups,
)
from src.game.models.events import ServerEventContext

MOD = "src.game.events.server_events.arena"


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


def _make_occurrence(context: dict | None = None) -> MagicMock:
    occ = MagicMock()
    occ.id = 1
    occ.context = context or {}
    return occ


# ===========================================================================
# get_arena
# ===========================================================================


def test_get_arena_creates_defaults():
    """
    Test get arena creates defaults.

    Returns
    -------
    Any
        The result of calling `test_get_arena_creates_defaults`.
    """

    ctx = ServerEventContext(server_discord_id=100)
    arena = get_arena(ctx)
    assert "listed" in arena
    assert "matchups" in arena
    assert "fight_wins" in arena


def test_get_arena_returns_existing():
    """
    Test get arena returns existing.

    Returns
    -------
    Any
        The result of calling `test_get_arena_returns_existing`.
    """

    ctx = ServerEventContext(server_discord_id=100)
    ctx.extra_data["arena"] = {"listed": [{"pooch_id": 1}], "matchups": [], "fight_wins": {}}
    arena = get_arena(ctx)
    assert arena["listed"] == [{"pooch_id": 1}]


# ===========================================================================
# handle_arena_action — list_pooch
# ===========================================================================


@pytest.mark.asyncio
async def test_list_pooch_no_selected_returns_failure(rng):
    """
    Test list pooch no selected returns failure.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_list_pooch_no_selected_returns_failure`.
    """

    occ = _make_occurrence()
    with patch(f"{MOD}.update_server_event_occurrence_context", new=AsyncMock()):
        success, msg, _ = await handle_arena_action(occ, 1, None, "list_pooch", {}, {}, rng)
    assert not success
    assert "select" in msg.lower()


@pytest.mark.asyncio
async def test_list_pooch_not_found_returns_failure(rng):
    """
    Test list pooch not found returns failure.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_list_pooch_not_found_returns_failure`.
    """

    occ = _make_occurrence()
    with (
        patch(f"{MOD}.db_get_pooch_by_id", new=AsyncMock(return_value=None)),
        patch(f"{MOD}.update_server_event_occurrence_context", new=AsyncMock()),
    ):
        success, msg, _ = await handle_arena_action(occ, 1, 99, "list_pooch", {}, {}, rng)
    assert not success


@pytest.mark.asyncio
async def test_list_pooch_wrong_owner_returns_failure(rng):
    """
    Test list pooch wrong owner returns failure.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_list_pooch_wrong_owner_returns_failure`.
    """

    occ = _make_occurrence()
    pooch = SimpleNamespace(id=5, name="Rex", alive=True, owner_discord_id=999)
    with (
        patch(f"{MOD}.db_get_pooch_by_id", new=AsyncMock(return_value=pooch)),
        patch(f"{MOD}.update_server_event_occurrence_context", new=AsyncMock()),
    ):
        success, msg, _ = await handle_arena_action(occ, 1, 5, "list_pooch", {}, {}, rng)
    assert not success


@pytest.mark.asyncio
async def test_list_pooch_success(rng):
    """
    Test list pooch success.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_list_pooch_success`.
    """

    occ = _make_occurrence()
    pooch = SimpleNamespace(id=5, name="Rex", alive=True, owner_discord_id=1)
    with (
        patch(f"{MOD}.db_get_pooch_by_id", new=AsyncMock(return_value=pooch)),
        patch(f"{MOD}.update_server_event_occurrence_context", new=AsyncMock()),
    ):
        success, msg, result_dict = await handle_arena_action(occ, 1, 5, "list_pooch", {}, {}, rng)
    assert success
    assert "Rex" in msg
    assert result_dict.get("listed_pooch_id") == 5


@pytest.mark.asyncio
async def test_list_pooch_already_listed_returns_failure(rng):
    """
    Test list pooch already listed returns failure.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_list_pooch_already_listed_returns_failure`.
    """

    existing_arena = {"listed": [{"pooch_id": 5, "owner_id": 1}], "matchups": [], "fight_wins": {}}
    # extra_data is the key used by ServerEventContext.from_dict
    occ = _make_occurrence(context={"server_discord_id": 100, "extra_data": {"arena": existing_arena}})
    pooch = SimpleNamespace(id=5, name="Rex", alive=True, owner_discord_id=1)
    with (
        patch(f"{MOD}.db_get_pooch_by_id", new=AsyncMock(return_value=pooch)),
        patch(f"{MOD}.update_server_event_occurrence_context", new=AsyncMock()),
    ):
        success, msg, _ = await handle_arena_action(occ, 1, 5, "list_pooch", {}, {}, rng)
    assert not success
    assert "already" in msg.lower()


# ===========================================================================
# resolve_arena_matchups — smoke test
# ===========================================================================


@pytest.mark.asyncio
async def test_resolve_matchups_no_listed_returns_none(rng):
    """With no listed pooches, resolve_arena_matchups completes without error."""
    from src.game.models.events import ServerEventContext as SrvCtx

    ctx = SrvCtx(server_discord_id=100)
    ctx.extra_data["arena"] = {"listed": [], "matchups": [], "fight_wins": {}}

    with patch(f"{MOD}.update_server_event_occurrence_context", new=AsyncMock()):
        result = await resolve_arena_matchups(1, ctx, {}, rng)

    # No listed pooches → no matchups created, returns None or empty
    assert result is None or result == []
