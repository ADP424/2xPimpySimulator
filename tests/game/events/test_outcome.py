"""Tests for src/game/events/outcome.py — shared weighted outcome selection."""

from __future__ import annotations

import random
from unittest.mock import AsyncMock, patch

import pytest

import src.game.events.outcome as _outcome_mod
from src.game.events import (
    choose_weighted_outcome,
    compute_outcome_stat_multiplier,
    get_effective_pooch_stat,
)

MOD = "src.game.events.outcome"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_outcome(chance=None, stat_weights=None, label="o"):
    from unittest.mock import MagicMock

    o = MagicMock()
    o.chance = chance
    o.stat_weights = stat_weights
    o.label = label
    o.description = "desc"
    o.message = "msg"
    o.actions = []
    return o


def _simple_resolver(pooch_id: int | None):
    """Return a resolver that always returns a fixed pooch_id."""

    def resolve(selector: str):
        return pooch_id

    return resolve


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
# get_effective_pooch_stat
# ===========================================================================


@pytest.mark.asyncio
async def test_get_stat_size_returns_float():
    """
    Test get stat size returns float.

    Returns
    -------
    Any
        The result of calling `test_get_stat_size_returns_float`.
    """

    with patch(f"{MOD}.get_pooch_size", new=AsyncMock(return_value=15)):
        result = await get_effective_pooch_stat("size", 1)
    assert result == 15.0


@pytest.mark.asyncio
async def test_get_stat_size_none_returns_default_10():
    """
    Test get stat size none returns default 10.

    Returns
    -------
    Any
        The result of calling `test_get_stat_size_none_returns_default_10`.
    """

    with patch(f"{MOD}.get_pooch_size", new=AsyncMock(return_value=None)):
        result = await get_effective_pooch_stat("size", 1)
    assert result == 10.0


@pytest.mark.asyncio
async def test_get_stat_known_returns_float():
    """
    Test get stat known returns float.

    Returns
    -------
    Any
        The result of calling `test_get_stat_known_returns_float`.
    """

    original = _outcome_mod._STAT_GETTERS["strength"]
    _outcome_mod._STAT_GETTERS["strength"] = AsyncMock(return_value=8)
    try:
        result = await get_effective_pooch_stat("strength", 1)
    finally:
        _outcome_mod._STAT_GETTERS["strength"] = original
    assert result == 8.0


@pytest.mark.asyncio
async def test_get_stat_unknown_returns_none():
    """
    Test get stat unknown returns none.

    Returns
    -------
    Any
        The result of calling `test_get_stat_unknown_returns_none`.
    """

    result = await get_effective_pooch_stat("totally_unknown", 1)
    assert result is None


@pytest.mark.asyncio
async def test_get_stat_known_db_none_returns_none():
    """
    Test get stat known db none returns none.

    Returns
    -------
    Any
        The result of calling `test_get_stat_known_db_none_returns_none`.
    """

    original = _outcome_mod._STAT_GETTERS["cuteness"]
    _outcome_mod._STAT_GETTERS["cuteness"] = AsyncMock(return_value=None)
    try:
        result = await get_effective_pooch_stat("cuteness", 1)
    finally:
        _outcome_mod._STAT_GETTERS["cuteness"] = original
    assert result is None


# ===========================================================================
# compute_outcome_stat_multiplier
# ===========================================================================


@pytest.mark.asyncio
async def test_stat_multiplier_empty_list_returns_1(rng):
    """
    Test stat multiplier empty list returns 1.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_stat_multiplier_empty_list_returns_1`.
    """

    result = await compute_outcome_stat_multiplier([], _simple_resolver(1), rng)
    assert result == 1.0


@pytest.mark.asyncio
async def test_stat_multiplier_skips_non_dict_entries(rng):
    """
    Test stat multiplier skips non dict entries.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_stat_multiplier_skips_non_dict_entries`.
    """

    result = await compute_outcome_stat_multiplier(["bad", 42, None], _simple_resolver(1), rng)
    assert result == 1.0


@pytest.mark.asyncio
async def test_stat_multiplier_above_pivot_increases(rng):
    """strength=20, pivot=10, scale=0.1, direction=1 → multiplier = 1 + (20-10)*0.1*1 = 2.0"""
    entry = {"stat": "strength", "pooch": "random", "scale": 0.1, "pivot": 10.0, "direction": 1.0}
    original = _outcome_mod._STAT_GETTERS["strength"]
    _outcome_mod._STAT_GETTERS["strength"] = AsyncMock(return_value=20)
    try:
        result = await compute_outcome_stat_multiplier([entry], _simple_resolver(1), rng)
    finally:
        _outcome_mod._STAT_GETTERS["strength"] = original
    assert abs(result - 2.0) < 1e-6


@pytest.mark.asyncio
async def test_stat_multiplier_clamped_to_zero(rng):
    """
    Test stat multiplier clamped to zero.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_stat_multiplier_clamped_to_zero`.
    """

    entry = {"stat": "strength", "pooch": "random", "scale": 1.0, "pivot": 10.0, "direction": 1.0}
    original = _outcome_mod._STAT_GETTERS["strength"]
    _outcome_mod._STAT_GETTERS["strength"] = AsyncMock(return_value=0)
    try:
        result = await compute_outcome_stat_multiplier([entry], _simple_resolver(1), rng)
    finally:
        _outcome_mod._STAT_GETTERS["strength"] = original
    assert result == 0.0


@pytest.mark.asyncio
async def test_stat_multiplier_no_pooch_id_skips(rng):
    """
    Test stat multiplier no pooch id skips.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_stat_multiplier_no_pooch_id_skips`.
    """

    entry = {"stat": "strength", "pooch": "random", "scale": 0.5, "pivot": 10.0, "direction": 1.0}
    result = await compute_outcome_stat_multiplier([entry], _simple_resolver(None), rng)
    assert result == 1.0


# ===========================================================================
# choose_weighted_outcome
# ===========================================================================


@pytest.mark.asyncio
async def test_no_outcomes_returns_none(rng):
    """
    Test no outcomes returns none.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_no_outcomes_returns_none`.
    """

    result = await choose_weighted_outcome([], _simple_resolver(1), rng)
    assert result is None


@pytest.mark.asyncio
async def test_all_fixed_outcomes_picks_by_chance(rng):
    """
    Test all fixed outcomes picks by chance.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_all_fixed_outcomes_picks_by_chance`.
    """

    o1 = _make_outcome(chance=0.8, label="common")
    o2 = _make_outcome(chance=0.2, label="rare")
    # rng.random() with seed 42 returns ~0.639, which falls in o1's range [0, 0.8)
    result = await choose_weighted_outcome([o1, o2], _simple_resolver(1), rng)
    assert result is o1


@pytest.mark.asyncio
async def test_all_fixed_outcomes_last_fallback(rng):
    """
    Test all fixed outcomes last fallback.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_all_fixed_outcomes_last_fallback`.
    """

    o1 = _make_outcome(chance=0.3)
    o2 = _make_outcome(chance=0.3)
    fixed_rng = random.Random(0)
    with patch.object(fixed_rng, "random", return_value=0.99):
        result = await choose_weighted_outcome([o1, o2], _simple_resolver(1), fixed_rng)
    assert result is o2


@pytest.mark.asyncio
async def test_implicit_outcomes_no_chance_no_stat_weights(rng):
    """
    Test implicit outcomes no chance no stat weights.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_implicit_outcomes_no_chance_no_stat_weights`.
    """

    o1 = _make_outcome(chance=None, stat_weights=None)
    o2 = _make_outcome(chance=None, stat_weights=None)
    result = await choose_weighted_outcome([o1, o2], _simple_resolver(1), rng)
    assert result in [o1, o2]


@pytest.mark.asyncio
async def test_raw_sum_zero_falls_back_to_rng_choice(rng):
    """When all dynamic raw_scores are 0.0, fall back to rng.choice over all outcomes."""
    sw = [{"stat": "strength", "pooch": "random", "scale": 100.0, "pivot": 10.0, "direction": 1.0}]
    o_dynamic = _make_outcome(chance=0.0, stat_weights=sw, label="zero_dynamic")

    original = _outcome_mod._STAT_GETTERS["strength"]
    _outcome_mod._STAT_GETTERS["strength"] = AsyncMock(return_value=0)
    try:
        result = await choose_weighted_outcome([o_dynamic], _simple_resolver(1), rng)
    finally:
        _outcome_mod._STAT_GETTERS["strength"] = original

    assert result is o_dynamic
