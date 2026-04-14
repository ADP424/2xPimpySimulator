"""Tests for src/game/events/server_events/coordinator.py."""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.events.server_events import (
    matches_rank,
    roll_outcome_chance,
    run_daily_server_event_cycle,
    trigger_daily_server_event,
)

MOD = "src.game.events.server_events.coordinator"


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


# ===========================================================================
# roll_outcome_chance
# ===========================================================================


def test_roll_outcome_chance_none_always_true(rng):
    """
    Test roll outcome chance none always true.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_roll_outcome_chance_none_always_true`.
    """

    assert roll_outcome_chance(None, rng) is True


def test_roll_outcome_chance_certain(rng):
    """
    Test roll outcome chance certain.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_roll_outcome_chance_certain`.
    """

    assert roll_outcome_chance(1.0, rng) is True


def test_roll_outcome_chance_zero_always_false(rng):
    # rng.random() > 0 always, so 0.0 always fails
    """
    Test roll outcome chance zero always false.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_roll_outcome_chance_zero_always_false`.
    """

    assert roll_outcome_chance(0.0, rng) is False


# ===========================================================================
# matches_rank
# ===========================================================================


def test_matches_rank_no_bounds_any_rank():
    """
    Test matches rank no bounds any rank.

    Returns
    -------
    Any
        The result of calling `test_matches_rank_no_bounds_any_rank`.
    """

    assert matches_rank(None, None, 1) is True
    assert matches_rank(None, None, None) is True


def test_matches_rank_within_range():
    """
    Test matches rank within range.

    Returns
    -------
    Any
        The result of calling `test_matches_rank_within_range`.
    """

    assert matches_rank(1, 3, 2) is True


def test_matches_rank_outside_range():
    """
    Test matches rank outside range.

    Returns
    -------
    Any
        The result of calling `test_matches_rank_outside_range`.
    """

    assert matches_rank(1, 3, 5) is False


def test_matches_rank_min_only():
    """
    Test matches rank min only.

    Returns
    -------
    Any
        The result of calling `test_matches_rank_min_only`.
    """

    assert matches_rank(2, None, 3) is True
    assert matches_rank(2, None, 1) is False


def test_matches_rank_max_only():
    """
    Test matches rank max only.

    Returns
    -------
    Any
        The result of calling `test_matches_rank_max_only`.
    """

    assert matches_rank(None, 3, 2) is True
    assert matches_rank(None, 3, 5) is False


def test_matches_rank_none_rank_requires_no_bounds():
    """
    Test matches rank none rank requires no bounds.

    Returns
    -------
    Any
        The result of calling `test_matches_rank_none_rank_requires_no_bounds`.
    """

    assert matches_rank(None, None, None) is True
    assert matches_rank(1, None, None) is False


# ===========================================================================
# trigger_daily_server_event
# ===========================================================================


@pytest.mark.asyncio
async def test_trigger_daily_no_eligible_event(rng):
    """
    Test trigger daily no eligible event.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_trigger_daily_no_eligible_event`.
    """

    server = SimpleNamespace(discord_id=100, current_season="spring", event_channel_discord_id=999)
    with (
        patch(f"{MOD}.get_server_by_discord_id", new=AsyncMock(return_value=server)),
        patch(f"{MOD}.get_current_season", new=AsyncMock(return_value="spring")),
        patch(f"{MOD}.list_server_events_with_weights_by_tier", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.get_active_server_event_occurrence_by_tier", new=AsyncMock(return_value=None)),
        patch(f"{MOD}.check_server_event_filter_for_server", new=AsyncMock(return_value=True)),
    ):
        result = await trigger_daily_server_event(100, "minor", rng)

    assert result is None


# ===========================================================================
# run_daily_server_event_cycle
# ===========================================================================


@pytest.mark.asyncio
async def test_run_daily_no_servers():
    """
    Test run daily no servers.

    Returns
    -------
    Any
        The result of calling `test_run_daily_no_servers`.
    """

    with (
        patch(f"{MOD}.list_active_server_event_occurrences", new=AsyncMock(return_value=[])),
        patch(f"{MOD}.list_servers", new=AsyncMock(return_value=[])),
    ):
        result = await run_daily_server_event_cycle()

    # run_daily_server_event_cycle returns (new_events, resolutions)
    assert result is not None
    new_events, resolutions = result
    assert isinstance(new_events, dict)
    assert isinstance(resolutions, list)
