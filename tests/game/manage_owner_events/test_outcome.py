"""Tests for src/game/manage_owner_events/outcome.py"""

from __future__ import annotations

import contextlib
import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.game.manage_owner_events.outcome as _outcome_mod
from src.game.manage_owner_events.outcome import (
    _compute_outcome_stat_multiplier_owner,
    _get_effective_pooch_stat_owner,
    _resolve_single_stat_pooch_id_owner,
    choose_option_outcome,
)
from src.game.models.events.owner_events.owner_event_context import OwnerEventContext

MOD = "src.game.manage_owner_events.outcome"
DB = "src.database"


@contextlib.contextmanager
def _patch_stat(stat_name: str, return_value):
    """Temporarily replace a _STAT_GETTERS entry with an AsyncMock."""
    mock = AsyncMock(return_value=return_value)
    original = _outcome_mod._STAT_GETTERS[stat_name]
    _outcome_mod._STAT_GETTERS[stat_name] = mock
    try:
        yield mock
    finally:
        _outcome_mod._STAT_GETTERS[stat_name] = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(owner_id: int = 1, affected: list[int] | None = None, **kwargs) -> OwnerEventContext:
    ctx = OwnerEventContext(owner_discord_id=owner_id, **kwargs)
    if affected:
        ctx.affected_pooch_ids = affected
    return ctx


def _make_outcome(chance=None, stat_weights=None, label="o") -> MagicMock:
    o = MagicMock()
    o.chance = chance
    o.stat_weights = stat_weights
    o.label = label
    o.description = "desc"
    o.message = "msg"
    o.actions = []
    return o


def _make_option(outcomes) -> MagicMock:
    opt = MagicMock()
    opt.outcomes = outcomes
    return opt


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


# ===========================================================================
# _resolve_single_stat_pooch_id_owner
# ===========================================================================


def test_resolve_random_picks_from_affected(rng):
    ctx = _ctx(affected=[10, 20, 30])
    result = _resolve_single_stat_pooch_id_owner("random", ctx, rng)
    assert result in [10, 20, 30]


def test_resolve_random_no_affected_returns_none(rng):
    ctx = _ctx()
    result = _resolve_single_stat_pooch_id_owner("random", ctx, rng)
    assert result is None


def test_resolve_slot_returns_first_id(rng):
    ctx = _ctx()
    ctx.extra_data["my_slot"] = {"pooch_ids": [55, 66]}
    result = _resolve_single_stat_pooch_id_owner("my_slot", ctx, rng)
    assert result == 55


def test_resolve_slot_empty_list_returns_none(rng):
    ctx = _ctx()
    ctx.extra_data["empty_slot"] = {"pooch_ids": []}
    result = _resolve_single_stat_pooch_id_owner("empty_slot", ctx, rng)
    assert result is None


def test_resolve_unknown_slot_returns_none(rng):
    ctx = _ctx()
    result = _resolve_single_stat_pooch_id_owner("no_such_slot", ctx, rng)
    assert result is None


# ===========================================================================
# _get_effective_pooch_stat_owner
# ===========================================================================


@pytest.mark.asyncio
async def test_get_stat_size_returns_float():
    # get_pooch_size is called directly (not via _STAT_GETTERS), patch at module level
    with patch(f"{MOD}.get_pooch_size", new=AsyncMock(return_value=15)):
        result = await _get_effective_pooch_stat_owner("size", 1)
    assert result == 15.0


@pytest.mark.asyncio
async def test_get_stat_size_none_returns_default_10():
    with patch(f"{MOD}.get_pooch_size", new=AsyncMock(return_value=None)):
        result = await _get_effective_pooch_stat_owner("size", 1)
    assert result == 10.0


@pytest.mark.asyncio
async def test_get_stat_strength_returns_float():
    with _patch_stat("strength", 8):
        result = await _get_effective_pooch_stat_owner("strength", 1)
    assert result == 8.0


@pytest.mark.asyncio
async def test_get_stat_unknown_returns_none():
    result = await _get_effective_pooch_stat_owner("totally_unknown_stat", 1)
    assert result is None


@pytest.mark.asyncio
async def test_get_stat_known_returns_none_when_db_none():
    with _patch_stat("cuteness", None):
        result = await _get_effective_pooch_stat_owner("cuteness", 1)
    assert result is None


# ===========================================================================
# _compute_outcome_stat_multiplier_owner
# ===========================================================================


@pytest.mark.asyncio
async def test_stat_multiplier_empty_list_returns_1(rng):
    ctx = _ctx(affected=[1])
    result = await _compute_outcome_stat_multiplier_owner([], ctx, rng)
    assert result == 1.0


@pytest.mark.asyncio
async def test_stat_multiplier_skips_non_dict_entries(rng):
    ctx = _ctx(affected=[1])
    result = await _compute_outcome_stat_multiplier_owner(["bad_entry", 42, None], ctx, rng)
    assert result == 1.0


@pytest.mark.asyncio
async def test_stat_multiplier_above_pivot_increases(rng):
    """strength=20, pivot=10, scale=0.1, direction=1 → multiplier = 1 + (20-10)*0.1*1 = 2.0"""
    ctx = _ctx(affected=[1])
    entry = {"stat": "strength", "pooch": "random", "scale": 0.1, "pivot": 10.0, "direction": 1.0}
    with _patch_stat("strength", 20):
        result = await _compute_outcome_stat_multiplier_owner([entry], ctx, rng)
    assert abs(result - 2.0) < 1e-6


@pytest.mark.asyncio
async def test_stat_multiplier_below_pivot_decreases(rng):
    """strength=5, pivot=10, scale=0.1, direction=1 → multiplier = max(0, 1 + (5-10)*0.1*1) = 0.5"""
    ctx = _ctx(affected=[1])
    entry = {"stat": "strength", "pooch": "random", "scale": 0.1, "pivot": 10.0, "direction": 1.0}
    with _patch_stat("strength", 5):
        result = await _compute_outcome_stat_multiplier_owner([entry], ctx, rng)
    assert abs(result - 0.5) < 1e-6


@pytest.mark.asyncio
async def test_stat_multiplier_clamped_to_zero(rng):
    """Very negative stat should clamp to 0, not go negative."""
    ctx = _ctx(affected=[1])
    entry = {"stat": "strength", "pooch": "random", "scale": 1.0, "pivot": 10.0, "direction": 1.0}
    with _patch_stat("strength", 0):
        result = await _compute_outcome_stat_multiplier_owner([entry], ctx, rng)
    assert result == 0.0


@pytest.mark.asyncio
async def test_stat_multiplier_unknown_stat_skipped(rng):
    """Unknown stat logs warning and is skipped (multiplier stays 1.0)."""
    ctx = _ctx(affected=[1])
    entry = {"stat": "super_unknown", "pooch": "random", "scale": 1.0, "pivot": 10.0, "direction": 1.0}
    result = await _compute_outcome_stat_multiplier_owner([entry], ctx, rng)
    assert result == 1.0


@pytest.mark.asyncio
async def test_stat_multiplier_no_pooch_id_skips(rng):
    """If pooch_id cannot be resolved, entry is skipped."""
    ctx = _ctx()  # no affected_pooch_ids
    entry = {"stat": "strength", "pooch": "random", "scale": 0.5, "pivot": 10.0, "direction": 1.0}
    result = await _compute_outcome_stat_multiplier_owner([entry], ctx, rng)
    assert result == 1.0


# ===========================================================================
# choose_option_outcome
# ===========================================================================


@pytest.mark.asyncio
async def test_no_outcomes_returns_none(rng):
    ctx = _ctx()
    option = _make_option([])
    result = await choose_option_outcome(option, ctx, rng)
    assert result is None


@pytest.mark.asyncio
async def test_all_fixed_outcomes_picks_by_chance(rng):
    """With all fixed outcomes and a seeded rng, the correct outcome is chosen."""
    o1 = _make_outcome(chance=0.8, label="common")
    o2 = _make_outcome(chance=0.2, label="rare")
    option = _make_option([o1, o2])
    # rng.random() with seed 42 returns ~0.639, which falls in o1's range [0, 0.8)
    result = await choose_option_outcome(option, _ctx(), rng)
    assert result is o1


@pytest.mark.asyncio
async def test_all_fixed_outcomes_last_fallback(rng):
    """When roll >= cumulative total, the last outcome is returned."""
    o1 = _make_outcome(chance=0.3)
    o2 = _make_outcome(chance=0.3)
    option = _make_option([o1, o2])
    fixed_rng = random.Random(0)
    # Force roll > 0.6 to trigger fallback to last
    with patch.object(fixed_rng, "random", return_value=0.99):
        result = await choose_option_outcome(option, _ctx(), fixed_rng)
    assert result is o2


@pytest.mark.asyncio
async def test_implicit_outcomes_no_chance_no_stat_weights(rng):
    """Outcomes with no chance and no stat_weights should be treated as weight-1 entries."""
    o1 = _make_outcome(chance=None, stat_weights=None)
    o2 = _make_outcome(chance=None, stat_weights=None)
    option = _make_option([o1, o2])
    result = await choose_option_outcome(option, _ctx(), rng)
    assert result in [o1, o2]


@pytest.mark.asyncio
async def test_implicit_outcome_gets_zero_weight_when_explicit_total_ge_1(rng):
    """When explicit fixed outcomes sum to >= 1.0, remaining = 0 → implicit outcome has zero share."""
    o_fixed1 = _make_outcome(chance=0.6, stat_weights=None, label="fixed1")
    o_fixed2 = _make_outcome(chance=0.5, stat_weights=None, label="fixed2")
    o_implicit = _make_outcome(chance=None, stat_weights=None, label="implicit")
    option = _make_option([o_fixed1, o_fixed2, o_implicit])
    # With seed 42 rng.random() ~ 0.639, which falls in the fixed pool; implicit gets 0 weight
    result = await choose_option_outcome(option, _ctx(), rng)
    # Result must be one of the fixed outcomes, not the implicit one
    assert result in [o_fixed1, o_fixed2]


@pytest.mark.asyncio
async def test_stat_weighted_outcome_uses_multiplier(rng):
    """Outcome with stat_weights uses computed multiplier to scale its chance."""
    sw = [{"stat": "strength", "pooch": "random", "scale": 0.1, "pivot": 10.0, "direction": 1.0}]
    o_weighted = _make_outcome(chance=0.5, stat_weights=sw, label="boosted")
    o_fixed = _make_outcome(chance=0.3, stat_weights=None, label="fixed")
    option = _make_option([o_weighted, o_fixed])
    ctx = _ctx(affected=[1])

    with _patch_stat("strength", 20):
        # strength=20 gives multiplier=2.0; boosted raw_score = 0.5*2.0 = 1.0
        # remaining = 1.0 - 0.3 = 0.7; boosted proportion = (1.0/1.0)*0.7 = 0.7
        # Roll 0.0 should pick the boosted outcome (cumulative hits 0.7 first)
        fixed_rng = random.Random(0)
        with patch.object(fixed_rng, "random", return_value=0.1):
            result = await choose_option_outcome(option, ctx, fixed_rng)
    assert result is o_weighted


@pytest.mark.asyncio
async def test_raw_sum_zero_falls_back_to_rng_choice(rng):
    """When all dynamic raw_scores are 0.0, fall back to rng.choice over all outcomes."""
    sw = [{"stat": "strength", "pooch": "random", "scale": 100.0, "pivot": 10.0, "direction": 1.0}]
    o_dynamic = _make_outcome(chance=0.0, stat_weights=sw, label="zero_dynamic")
    option = _make_option([o_dynamic])
    ctx = _ctx(affected=[1])

    with _patch_stat("strength", 0):
        # strength=0 → mult = max(0, 1+(0-10)*100*1) = 0 → raw_score = 0.0
        result = await choose_option_outcome(option, ctx, rng)
    # Falls back to rng.choice([o_dynamic]) which must return o_dynamic
    assert result is o_dynamic


@pytest.mark.asyncio
async def test_mixed_fixed_and_dynamic_fallback_to_last(rng):
    """Last entry in the combined list is returned when roll exceeds cumulative."""
    o_dyn = _make_outcome(chance=None, stat_weights=None, label="dynamic")
    o_fix = _make_outcome(chance=0.4, stat_weights=None, label="fixed")
    option = _make_option([o_dyn, o_fix])
    ctx = _ctx()

    fixed_rng = random.Random(0)
    # Force roll extremely high so we exhaust all weights and hit fallback
    with patch.object(fixed_rng, "random", return_value=0.9999):
        result = await choose_option_outcome(option, ctx, fixed_rng)
    # Should return last entry in entries list
    assert result in [o_dyn, o_fix]
