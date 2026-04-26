"""Tests for src/game/events/owner_events/outcome.py

The owner_events outcome module is a thin wrapper: it delegates
choose_option_outcome to the shared choose_weighted_outcome with an
owner-context-specific pooch ID resolver.
"""

from __future__ import annotations

import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.game.events.owner_events import choose_option_outcome
from src.game.models.events.owner_events.owner_event_context import OwnerEventContext

MOD = "src.game.events.owner_events.outcome"


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
    """
    Rng.

    Returns
    -------
    Any
        The result of calling `rng`.
    """

    return random.Random(42)


# ===========================================================================
# choose_option_outcome — delegates to choose_weighted_outcome
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

    ctx = _ctx()
    option = _make_option([])
    result = await choose_option_outcome(option, ctx, rng)
    assert result is None


@pytest.mark.asyncio
async def test_single_fixed_outcome_returned(rng):
    """
    Test single fixed outcome returned.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_single_fixed_outcome_returned`.
    """

    o = _make_outcome(chance=1.0, label="only")
    option = _make_option([o])
    result = await choose_option_outcome(option, _ctx(), rng)
    assert result is o


@pytest.mark.asyncio
async def test_all_fixed_outcomes_picks_by_chance(rng):
    """With fixed outcomes and a seeded rng, the correct outcome is chosen."""
    o1 = _make_outcome(chance=0.8, label="common")
    o2 = _make_outcome(chance=0.2, label="rare")
    option = _make_option([o1, o2])
    # rng.random() with seed 42 returns ~0.639, which falls in o1's range [0, 0.8)
    result = await choose_option_outcome(option, _ctx(), rng)
    assert result is o1


@pytest.mark.asyncio
async def test_implicit_outcomes_no_chance_returns_one(rng):
    """Outcomes with no chance and no stat_weights are treated as weight-1 entries."""
    o1 = _make_outcome(chance=None, stat_weights=None)
    o2 = _make_outcome(chance=None, stat_weights=None)
    option = _make_option([o1, o2])
    result = await choose_option_outcome(option, _ctx(), rng)
    assert result in [o1, o2]


@pytest.mark.asyncio
async def test_resolver_uses_affected_pooch_ids(rng):
    """The resolver passed to choose_weighted_outcome uses context.affected_pooch_ids for 'random'."""
    ctx = _ctx(affected=[42])
    # Stat-weighted outcome: stat lookup for pooch 42
    sw = [{"stat": "strength", "pooch": "random", "scale": 0.0, "pivot": 10.0, "direction": 1.0}]
    o = _make_outcome(chance=None, stat_weights=sw, label="weighted")
    option = _make_option([o])

    # Patch get_effective_pooch_stat so we don't need real DB
    with patch(
        "src.game.events.outcome.get_effective_pooch_stat",
        new=AsyncMock(return_value=10.0),
    ):
        result = await choose_option_outcome(option, ctx, rng)

    assert result is o


@pytest.mark.asyncio
async def test_resolver_uses_extra_data_slot(rng):
    """The resolver uses a named slot from context.extra_data when selector is a slot name."""
    ctx = _ctx()
    ctx.extra_data["my_slot"] = {"pooch_ids": [99]}
    sw = [{"stat": "cuteness", "pooch": "my_slot", "scale": 0.0, "pivot": 10.0, "direction": 1.0}]
    o = _make_outcome(chance=None, stat_weights=sw, label="slot_weighted")
    option = _make_option([o])

    with patch(
        "src.game.events.outcome.get_effective_pooch_stat",
        new=AsyncMock(return_value=10.0),
    ):
        result = await choose_option_outcome(option, ctx, rng)

    assert result is o
