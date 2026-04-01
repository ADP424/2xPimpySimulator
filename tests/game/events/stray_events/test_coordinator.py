"""Tests for src/game/events/stray_events/coordinator.py — trigger and daily check."""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.events.stray_events import (
    run_daily_stray_event_check,
    trigger_stray_event_for_server,
)
from src.game.models import StrayEventResult

MOD = "src.game.events.stray_events.coordinator"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stray_event(name: str = "TestEvent", filter_spec: dict | None = None, actions=None) -> MagicMock:
    e = MagicMock()
    e.name = name
    e.filter = filter_spec or {}
    e.actions = actions or []
    e.outcomes = []
    return e


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


# ---------------------------------------------------------------------------
# trigger_stray_event_for_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_candidates_returns_none(rng):
    """
    Test no candidates returns none.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_no_candidates_returns_none`.
    """

    event = _make_stray_event()
    with patch(f"{MOD}.list_strays_for_server", new=AsyncMock(return_value=[])):
        result = await trigger_stray_event_for_server(100, event, rng)
    assert result is None


@pytest.mark.asyncio
async def test_with_candidates_executes_actions(rng):
    """
    Test with candidates executes actions.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_with_candidates_executes_actions`.
    """

    event = _make_stray_event()
    stray = SimpleNamespace(id=5)
    mock_result = StrayEventResult()

    with (
        patch(f"{MOD}.list_strays_for_server", new=AsyncMock(return_value=[stray])),
        patch(f"{MOD}.execute_stray_event_actions", new=AsyncMock(return_value=mock_result)),
        patch(f"{MOD}.choose_stray_event_outcome", new=AsyncMock(return_value=None)),
    ):
        result = await trigger_stray_event_for_server(100, event, rng)

    assert result is not None


@pytest.mark.asyncio
async def test_with_pooch_filter_calls_matching(rng):
    """
    Test with pooch filter calls matching.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_with_pooch_filter_calls_matching`.
    """

    event = _make_stray_event(filter_spec={"pooches": [{"alive": True, "min_count": 1}]})
    mock_result = StrayEventResult()

    with (
        patch(f"{MOD}.list_matching_stray_pooch_ids", new=AsyncMock(return_value=[10, 20])),
        patch(f"{MOD}.execute_stray_event_actions", new=AsyncMock(return_value=mock_result)),
        patch(f"{MOD}.choose_stray_event_outcome", new=AsyncMock(return_value=None)),
    ):
        result = await trigger_stray_event_for_server(100, event, rng)

    assert result is not None


@pytest.mark.asyncio
async def test_outcome_actions_merged_into_result(rng):
    """
    Test outcome actions merged into result.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_outcome_actions_merged_into_result`.
    """

    action = MagicMock()
    action.action_type = "kill_pooch"
    action.repeat = 1
    action.action_order = 0
    action.parameters = {}

    outcome = MagicMock()
    outcome.actions = [action]
    outcome.chance = 1.0
    outcome.stat_weights = None
    event = _make_stray_event()

    stray = SimpleNamespace(id=5)
    main_result = StrayEventResult()
    outcome_result = StrayEventResult()

    with (
        patch(f"{MOD}.list_strays_for_server", new=AsyncMock(return_value=[stray])),
        patch(f"{MOD}.execute_stray_event_actions", new=AsyncMock(side_effect=[main_result, outcome_result])),
        patch(f"{MOD}.choose_stray_event_outcome", new=AsyncMock(return_value=outcome)),
    ):
        result = await trigger_stray_event_for_server(100, event, rng)

    assert result is main_result  # merged in place


# ---------------------------------------------------------------------------
# run_daily_stray_event_check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_servers_returns_empty(rng):
    """
    Test no servers returns empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_no_servers_returns_empty`.
    """

    with (
        patch(f"{MOD}.list_servers", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.get_current_season", new=AsyncMock(return_value="spring")),
    ):
        result = await run_daily_stray_event_check()
    assert result == {}


@pytest.mark.asyncio
async def test_server_with_no_strays_skipped():
    """
    Test server with no strays skipped.

    Returns
    -------
    Any
        The result of calling `test_server_with_no_strays_skipped`.
    """

    server = SimpleNamespace(discord_id=100)
    with (
        patch(f"{MOD}.list_servers", new=AsyncMock(return_value=[server])),
        patch(f"{MOD}.get_current_season", new=AsyncMock(return_value="spring")),
        patch(f"{MOD}.list_strays_for_server", new=AsyncMock(return_value=[])),
    ):
        result = await run_daily_stray_event_check()
    assert result == {}


@pytest.mark.asyncio
async def test_no_eligible_event_skipped():
    """
    Test no eligible event skipped.

    Returns
    -------
    Any
        The result of calling `test_no_eligible_event_skipped`.
    """

    server = SimpleNamespace(discord_id=100)
    stray = SimpleNamespace(id=1)
    with (
        patch(f"{MOD}.list_servers", new=AsyncMock(return_value=[server])),
        patch(f"{MOD}.get_current_season", new=AsyncMock(return_value="spring")),
        patch(f"{MOD}.list_strays_for_server", new=AsyncMock(return_value=[stray])),
        patch(f"{MOD}.get_random_eligible_stray_event_for_server", new=AsyncMock(return_value=None)),
    ):
        result = await run_daily_stray_event_check()
    assert result == {}


@pytest.mark.asyncio
async def test_eligible_event_triggers():
    """
    Test eligible event triggers.

    Returns
    -------
    Any
        The result of calling `test_eligible_event_triggers`.
    """

    server = SimpleNamespace(discord_id=100)
    stray = SimpleNamespace(id=1)
    event = _make_stray_event()
    event_result = StrayEventResult()

    # Force trigger chance to always fire
    with (
        patch(f"{MOD}.list_servers", new=AsyncMock(return_value=[server])),
        patch(f"{MOD}.get_current_season", new=AsyncMock(return_value="spring")),
        patch(f"{MOD}.list_strays_for_server", new=AsyncMock(return_value=[stray])),
        patch(f"{MOD}.get_random_eligible_stray_event_for_server", new=AsyncMock(return_value=event)),
        patch(f"{MOD}.trigger_stray_event_for_server", new=AsyncMock(return_value=event_result)),
        patch(f"{MOD}.STRAY_EVENT_TRIGGER_CHANCE", new=1.0),
    ):
        result = await run_daily_stray_event_check()

    # result is dict[server_id → list[(event_name, result)]]
    assert 100 in result
    assert len(result[100]) == 1
    assert result[100][0][0] == event.name
    assert result[100][0][1] is event_result
