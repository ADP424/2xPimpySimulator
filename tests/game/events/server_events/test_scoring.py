"""Tests for src/game/events/server_events/scoring.py."""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.events.server_events import (
    aggregate_player_score,
    compute_submission_score,
    rank_participations,
)

MOD = "src.game.events.server_events.scoring"


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
# compute_submission_score
# ===========================================================================


@pytest.mark.asyncio
async def test_no_sources_returns_zero(rng):
    """
    Test no sources returns zero.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_no_sources_returns_zero`.
    """

    result = await compute_submission_score({}, {}, rng)
    assert result == 0.0


@pytest.mark.asyncio
async def test_random_source(rng):
    """
    Test random source.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_random_source`.
    """

    scoring = {"sources": [{"type": "random", "min": 5.0, "max": 10.0}]}
    result = await compute_submission_score({}, scoring, rng)
    assert 5.0 <= result <= 10.0


@pytest.mark.asyncio
async def test_constant_source(rng):
    """
    Test constant source.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_constant_source`.
    """

    scoring = {"sources": [{"type": "constant", "value": 42.0}]}
    result = await compute_submission_score({}, scoring, rng)
    assert result == 42.0


@pytest.mark.asyncio
async def test_multiple_sources_summed(rng):
    """
    Test multiple sources summed.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_multiple_sources_summed`.
    """

    scoring = {
        "sources": [
            {"type": "constant", "value": 10.0},
            {"type": "constant", "value": 5.0},
        ]
    }
    result = await compute_submission_score({}, scoring, rng)
    assert result == 15.0


@pytest.mark.asyncio
async def test_pooch_stat_source(rng):
    """
    Test pooch stat source.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_stat_source`.
    """

    pooch = SimpleNamespace(id=1, strength=20, base_health=10)
    scoring = {"sources": [{"type": "pooch_stat", "stat": "strength", "pivot": 10.0, "scale": 1.0, "direction": 1.0}]}
    submission = {"selected_pooch_id": 1}
    with patch(f"{MOD}.get_effective_stat", new=AsyncMock(side_effect=lambda pid, stat: getattr(pooch, stat))):
        result = await compute_submission_score(submission, scoring, rng)
    # (20 - 10) * 1.0 * 1.0 = 10.0
    assert result == 10.0


@pytest.mark.asyncio
async def test_pooch_stat_no_pooch_id_skipped(rng):
    """
    Test pooch stat no pooch id skipped.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_stat_no_pooch_id_skipped`.
    """

    scoring = {"sources": [{"type": "pooch_stat", "stat": "strength", "pivot": 10.0, "scale": 1.0, "direction": 1.0}]}
    result = await compute_submission_score({}, scoring, rng)
    assert result == 0.0


@pytest.mark.asyncio
async def test_owner_stat_source(rng):
    """
    Test owner stat source.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_owner_stat_source`.
    """

    owner = SimpleNamespace(id=1, dollars=500, money=None)
    scoring = {"sources": [{"type": "owner_stat", "stat": "money", "pivot": 100.0, "scale": 0.1, "direction": 1.0}]}
    submission = {"owner_discord_id": 1}
    with patch(f"{MOD}.get_owner_by_discord_id", new=AsyncMock(return_value=owner)):
        result = await compute_submission_score(submission, scoring, rng)
    # owner.money is None → falls back to owner.dollars = 500
    # (500 - 100) * 0.1 * 1.0 = 40.0
    assert result == 40.0


@pytest.mark.asyncio
async def test_unknown_source_type_skipped(rng):
    """
    Test unknown source type skipped.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_unknown_source_type_skipped`.
    """

    scoring = {"sources": [{"type": "totally_unknown"}]}
    result = await compute_submission_score({}, scoring, rng)
    assert result == 0.0


# ===========================================================================
# aggregate_player_score
# ===========================================================================


def test_aggregate_sum():
    """
    Test aggregate sum.

    Returns
    -------
    Any
        The result of calling `test_aggregate_sum`.
    """

    assert aggregate_player_score([3.0, 4.0, 5.0], "sum") == 12.0


def test_aggregate_average():
    """
    Test aggregate average.

    Returns
    -------
    Any
        The result of calling `test_aggregate_average`.
    """

    assert aggregate_player_score([2.0, 4.0, 6.0], "average") == 4.0


def test_aggregate_max():
    """
    Test aggregate max.

    Returns
    -------
    Any
        The result of calling `test_aggregate_max`.
    """

    assert aggregate_player_score([1.0, 7.0, 3.0], "max") == 7.0


def test_aggregate_empty_returns_zero():
    """
    Test aggregate empty returns zero.

    Returns
    -------
    Any
        The result of calling `test_aggregate_empty_returns_zero`.
    """

    assert aggregate_player_score([], "sum") == 0.0


def test_aggregate_unknown_defaults_to_sum():
    """
    Test aggregate unknown defaults to sum.

    Returns
    -------
    Any
        The result of calling `test_aggregate_unknown_defaults_to_sum`.
    """

    assert aggregate_player_score([1.0, 2.0], "unknown_method") == 3.0


# ===========================================================================
# rank_participations
# ===========================================================================


@pytest.mark.asyncio
async def test_rank_participations_single(rng):
    """
    Test rank participations single.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_rank_participations_single`.
    """

    p1 = SimpleNamespace(submissions=[{"scoring": {"sources": [{"type": "constant", "value": 10.0}]}}])
    occurrence = SimpleNamespace(participations=[p1])
    ranked = await rank_participations(occurrence, rng)
    assert len(ranked) == 1
    assert ranked[0][0] is p1
    assert ranked[0][1] == 10.0
    assert ranked[0][2] == 1  # rank 1


@pytest.mark.asyncio
async def test_rank_participations_sorted_descending(rng):
    """
    Test rank participations sorted descending.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_rank_participations_sorted_descending`.
    """

    p_high = SimpleNamespace(submissions=[{"scoring": {"sources": [{"type": "constant", "value": 100.0}]}}])
    p_low = SimpleNamespace(submissions=[{"scoring": {"sources": [{"type": "constant", "value": 5.0}]}}])
    occurrence = SimpleNamespace(participations=[p_low, p_high])
    ranked = await rank_participations(occurrence, rng)
    assert ranked[0][0] is p_high
    assert ranked[1][0] is p_low
    assert ranked[0][2] == 1
    assert ranked[1][2] == 2


@pytest.mark.asyncio
async def test_rank_participations_no_submissions_gets_zero(rng):
    """
    Test rank participations no submissions gets zero.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_rank_participations_no_submissions_gets_zero`.
    """

    p = SimpleNamespace(submissions=[])
    occurrence = SimpleNamespace(participations=[p])
    ranked = await rank_participations(occurrence, rng)
    assert ranked[0][1] == 0.0


@pytest.mark.asyncio
async def test_pooch_stat_uses_effective_stats_and_raw_for_other_fields():
    from types import SimpleNamespace

    from src.game.events.server_events.scoring import _pooch_stat

    with (
        patch(f"{MOD}.get_effective_stat", new=AsyncMock(return_value=14)) as effective,
        patch(f"{MOD}.db_get_pooch_by_id", new=AsyncMock(return_value=SimpleNamespace(age=3))),
    ):
        assert await _pooch_stat(1, "strength") == 14.0
        assert await _pooch_stat(1, "age") == 3.0
    effective.assert_awaited_once_with(1, "strength")
