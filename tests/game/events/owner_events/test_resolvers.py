"""Tests for src/game/events/owner_events/resolvers.py"""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.game.events.owner_events import (
    get_target_kennel_ids,
    get_target_pooch_ids,
)
from src.game.models.events.owner_events.owner_event_context import OwnerEventContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(owner_id: int = 1, **kwargs) -> OwnerEventContext:
    return OwnerEventContext(owner_discord_id=owner_id, **kwargs)


def _kennel(kennel_id: int, name: str = "K") -> SimpleNamespace:
    return SimpleNamespace(id=kennel_id, name=name)


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
# get_target_pooch_ids
# ===========================================================================

MOD = "src.game.events.owner_events.resolvers"


# ---------------------------------------------------------------------------
# target_type == "owner"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_returns_all_matching_pooches(rng):
    """
    Test owner returns all matching pooches.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_owner_returns_all_matching_pooches`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3])):
        result = await get_target_pooch_ids(1, ctx, rng, "owner", "all", {})
    assert result == [1, 2, 3]


@pytest.mark.asyncio
async def test_owner_excludes_ids(rng):
    """
    Test owner excludes ids.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_owner_excludes_ids`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3])):
        result = await get_target_pooch_ids(1, ctx, rng, "owner", "all", {"_exclude_ids": [2]})
    assert result == [1, 3]


# ---------------------------------------------------------------------------
# target_type == "pooch", selector == "selected"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pooch_selected_returns_selected_id(rng):
    """
    Test pooch selected returns selected id.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_selected_returns_selected_id`.
    """

    ctx = _ctx(selected_pooch_id=7)
    result = await get_target_pooch_ids(1, ctx, rng, "pooch", "selected", {})
    assert result == [7]


@pytest.mark.asyncio
async def test_pooch_selected_no_selection_returns_empty(rng):
    """
    Test pooch selected no selection returns empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_selected_no_selection_returns_empty`.
    """

    ctx = _ctx()
    result = await get_target_pooch_ids(1, ctx, rng, "pooch", "selected", {})
    assert result == []


# ---------------------------------------------------------------------------
# target_type == "pooch", selector == "random"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pooch_random_single(rng):
    """
    Test pooch random single.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_random_single`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[10, 20, 30])):
        result = await get_target_pooch_ids(1, ctx, rng, "pooch", "random", {})
    assert len(result) == 1
    assert result[0] in [10, 20, 30]


@pytest.mark.asyncio
async def test_pooch_random_with_count(rng):
    """
    Test pooch random with count.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_random_with_count`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[10, 20, 30, 40])):
        result = await get_target_pooch_ids(1, ctx, rng, "pooch", "random", {"count": 2})
    assert len(result) == 2


@pytest.mark.asyncio
async def test_pooch_random_empty_list_returns_empty(rng):
    """
    Test pooch random empty list returns empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_random_empty_list_returns_empty`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[])):
        result = await get_target_pooch_ids(1, ctx, rng, "pooch", "random", {})
    assert result == []


@pytest.mark.asyncio
async def test_pooch_random_excludes_ids(rng):
    """
    Test pooch random excludes ids.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_random_excludes_ids`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[10, 20])):
        result = await get_target_pooch_ids(1, ctx, rng, "pooch", "random", {"_exclude_ids": [20]})
    assert result == [10]


# ---------------------------------------------------------------------------
# target_type == "pooch", selector == "all"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pooch_all_returns_all(rng):
    """
    Test pooch all returns all.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_all_returns_all`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[5, 6, 7])):
        result = await get_target_pooch_ids(1, ctx, rng, "pooch", "all", {})
    assert result == [5, 6, 7]


@pytest.mark.asyncio
async def test_pooch_all_with_exclude(rng):
    """
    Test pooch all with exclude.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_all_with_exclude`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[5, 6, 7])):
        result = await get_target_pooch_ids(1, ctx, rng, "pooch", "all", {"_exclude_ids": [6]})
    assert result == [5, 7]


# ---------------------------------------------------------------------------
# target_type == "pooch", selector == "random_exclude"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pooch_random_exclude_removes_sampled(rng):
    """random_exclude picks `count` IDs and returns the rest."""
    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2, 3, 4, 5])):
        result = await get_target_pooch_ids(1, ctx, rng, "pooch", "random_exclude", {"count": 2})
    assert len(result) == 3


@pytest.mark.asyncio
async def test_pooch_random_exclude_count_ge_total_returns_empty(rng):
    """
    Test pooch random exclude count ge total returns empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_random_exclude_count_ge_total_returns_empty`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[1, 2])):
        result = await get_target_pooch_ids(1, ctx, rng, "pooch", "random_exclude", {"count": 5})
    assert result == []


# ---------------------------------------------------------------------------
# target_type == "pooch", selector == "all_exclude"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pooch_all_exclude_returns_non_matching(rng):
    """all_exclude returns pooches not matching the filter."""
    ctx = _ctx()

    async def _list(owner_id, filter_spec):
        if filter_spec == {}:
            return [1, 2, 3, 4]
        return [2, 4]  # matched by filter

    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(side_effect=_list)):
        result = await get_target_pooch_ids(1, ctx, rng, "pooch", "all_exclude", {"filter": {"some": "val"}})
    assert set(result) == {1, 3}


@pytest.mark.asyncio
async def test_pooch_unknown_selector_returns_empty(rng):
    """
    Test pooch unknown selector returns empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_pooch_unknown_selector_returns_empty`.
    """

    ctx = _ctx()
    result = await get_target_pooch_ids(1, ctx, rng, "pooch", "bogus_selector", {})
    assert result == []


# ---------------------------------------------------------------------------
# use_saved — target_type == "pooch"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_use_saved_pooch_slot_returns_ids(rng):
    """
    Test use saved pooch slot returns ids.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_use_saved_pooch_slot_returns_ids`.
    """

    ctx = _ctx()
    ctx.extra_data["my_slot"] = {"pooch_ids": [99, 100]}
    result = await get_target_pooch_ids(1, ctx, rng, "pooch", "random", {"use_saved": "my_slot"})
    assert result == [99, 100]


@pytest.mark.asyncio
async def test_use_saved_missing_slot_returns_empty(rng):
    """
    Test use saved missing slot returns empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_use_saved_missing_slot_returns_empty`.
    """

    ctx = _ctx()
    result = await get_target_pooch_ids(1, ctx, rng, "pooch", "random", {"use_saved": "no_such_slot"})
    assert result == []


@pytest.mark.asyncio
async def test_use_saved_kennel_slot_enumerates_pooches(rng):
    """
    Test use saved kennel slot enumerates pooches.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_use_saved_kennel_slot_enumerates_pooches`.
    """

    ctx = _ctx()
    ctx.extra_data["k_slot"] = {"kennel_ids": [10, 20]}
    with patch(
        f"{MOD}.list_matching_pooch_ids_in_kennel",
        new=AsyncMock(side_effect=lambda owner, kid, f: [kid * 10]),
    ):
        result = await get_target_pooch_ids(1, ctx, rng, "kennel", "random", {"use_saved": "k_slot"})
    assert result == [100, 200]


# ---------------------------------------------------------------------------
# save_as — writes slot into context.extra_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_as_stores_pooch_ids(rng):
    """
    Test save as stores pooch ids.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_save_as_stores_pooch_ids`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[3, 4])):
        await get_target_pooch_ids(1, ctx, rng, "pooch", "all", {"save_as": "out_slot"})
    assert ctx.extra_data["out_slot"]["pooch_ids"] == [3, 4]


@pytest.mark.asyncio
async def test_save_as_with_save_kennel_stores_kennel_ids(rng):
    """
    Test save as with save kennel stores kennel ids.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_save_as_with_save_kennel_stores_kennel_ids`.
    """

    ctx = _ctx()
    kennel = _kennel(55)
    with (
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch(f"{MOD}.get_pooch_kennel", new=AsyncMock(return_value=kennel)),
    ):
        await get_target_pooch_ids(1, ctx, rng, "pooch", "all", {"save_as": "slot", "save_kennel": True})
    assert ctx.extra_data["slot"]["kennel_ids"] == [55]


@pytest.mark.asyncio
async def test_save_as_with_save_kennel_no_kennel(rng):
    """If get_pooch_kennel returns None, kennel_ids should remain empty."""
    ctx = _ctx()
    with (
        patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[7])),
        patch(f"{MOD}.get_pooch_kennel", new=AsyncMock(return_value=None)),
    ):
        await get_target_pooch_ids(1, ctx, rng, "pooch", "all", {"save_as": "slot", "save_kennel": True})
    assert ctx.extra_data["slot"]["kennel_ids"] == []


# ---------------------------------------------------------------------------
# target_type == "kennel" (resolver path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kennel_target_selected_returns_pooches_in_kennel(rng):
    """
    Test kennel target selected returns pooches in kennel.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_kennel_target_selected_returns_pooches_in_kennel`.
    """

    ctx = _ctx(selected_kennel_id=5)
    with patch(
        f"{MOD}.list_matching_pooch_ids_in_kennel",
        new=AsyncMock(return_value=[11, 12]),
    ):
        result = await get_target_pooch_ids(1, ctx, rng, "kennel", "selected", {})
    assert result == [11, 12]


@pytest.mark.asyncio
async def test_kennel_target_random_single(rng):
    """
    Test kennel target random single.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_kennel_target_random_single`.
    """

    ctx = _ctx()
    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[7])),
        patch(f"{MOD}.get_random_matching_kennel_id", new=AsyncMock(return_value=7)),
        patch(f"{MOD}.list_matching_pooch_ids_in_kennel", new=AsyncMock(return_value=[21])),
    ):
        result = await get_target_pooch_ids(1, ctx, rng, "kennel", "random", {})
    assert result == [21]


@pytest.mark.asyncio
async def test_kennel_target_all_aggregates_pooches(rng):
    """
    Test kennel target all aggregates pooches.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_kennel_target_all_aggregates_pooches`.
    """

    ctx = _ctx()

    async def _kennel_pooches(owner_id, kid, f):
        return [kid * 10]

    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2])),
        patch(f"{MOD}.list_matching_pooch_ids_in_kennel", new=AsyncMock(side_effect=_kennel_pooches)),
    ):
        result = await get_target_pooch_ids(1, ctx, rng, "kennel", "all", {})
    assert result == [10, 20]


@pytest.mark.asyncio
async def test_kennel_target_random_exclude_removes_kennel(rng):
    """
    Test kennel target random exclude removes kennel.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_kennel_target_random_exclude_removes_kennel`.
    """

    ctx = _ctx()
    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch(
            f"{MOD}.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(side_effect=lambda owner, kid, f: [kid * 10]),
        ),
    ):
        result = await get_target_pooch_ids(1, ctx, rng, "kennel", "random_exclude", {"count": 1})
    # 1 kennel excluded out of 3, pooches from remaining 2 kennels
    assert len(result) == 2


@pytest.mark.asyncio
async def test_kennel_target_all_exclude_returns_non_matching_kennels_pooches(rng):
    """
    Test kennel target all exclude returns non matching kennels pooches.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_kennel_target_all_exclude_returns_non_matching_kennels_pooches`.
    """

    ctx = _ctx()

    async def _list_kennels(owner_id, filter_spec):
        if filter_spec == {}:
            return [1, 2, 3]
        return [2]

    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(side_effect=_list_kennels)),
        patch(
            f"{MOD}.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(side_effect=lambda owner, kid, f: [kid * 10]),
        ),
    ):
        result = await get_target_pooch_ids(1, ctx, rng, "kennel", "all_exclude", {"filter": {"x": 1}})
    assert set(result) == {10, 30}


@pytest.mark.asyncio
async def test_kennel_target_pooch_selector_random(rng):
    """pooch_selector=random picks one pooch per kennel."""
    ctx = _ctx()
    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[1])),
        patch(
            f"{MOD}.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(return_value=[10, 20, 30]),
        ),
    ):
        result = await get_target_pooch_ids(
            1, ctx, rng, "kennel", "all", {"pooch_selector": "random", "pooch_count": 1}
        )
    assert len(result) == 1
    assert result[0] in [10, 20, 30]


@pytest.mark.asyncio
async def test_kennel_target_pooch_selector_random_exclude(rng):
    """pooch_selector=random_exclude excludes sampled pooches from the kennel."""
    ctx = _ctx()
    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[1])),
        patch(
            f"{MOD}.list_matching_pooch_ids_in_kennel",
            new=AsyncMock(return_value=[10, 20, 30]),
        ),
    ):
        result = await get_target_pooch_ids(
            1, ctx, rng, "kennel", "all", {"pooch_selector": "random_exclude", "pooch_count": 1}
        )
    assert len(result) == 2


# ===========================================================================
# get_target_kennel_ids
# ===========================================================================


@pytest.mark.asyncio
async def test_get_kennel_ids_owner_returns_all(rng):
    """
    Test get kennel ids owner returns all.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_owner_returns_all`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2])):
        result = await get_target_kennel_ids(1, ctx, rng, "owner", "all", {})
    assert result == [1, 2]


@pytest.mark.asyncio
async def test_get_kennel_ids_selected(rng):
    """
    Test get kennel ids selected.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_selected`.
    """

    ctx = _ctx(selected_kennel_id=9)
    result = await get_target_kennel_ids(1, ctx, rng, "kennel", "selected", {})
    assert result == [9]


@pytest.mark.asyncio
async def test_get_kennel_ids_selected_none(rng):
    """
    Test get kennel ids selected none.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_selected_none`.
    """

    ctx = _ctx()
    result = await get_target_kennel_ids(1, ctx, rng, "kennel", "selected", {})
    assert result == []


@pytest.mark.asyncio
async def test_get_kennel_ids_random_single(rng):
    """
    Test get kennel ids random single.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_random_single`.
    """

    ctx = _ctx()
    with (
        patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[3])),
        patch(f"{MOD}.get_random_matching_kennel_id", new=AsyncMock(return_value=3)),
    ):
        result = await get_target_kennel_ids(1, ctx, rng, "kennel", "random", {})
    assert result == [3]


@pytest.mark.asyncio
async def test_get_kennel_ids_random_with_count(rng):
    """
    Test get kennel ids random with count.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_random_with_count`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2, 3, 4])):
        result = await get_target_kennel_ids(1, ctx, rng, "kennel", "random", {"count": 2})
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_kennel_ids_all(rng):
    """
    Test get kennel ids all.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_all`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[5, 6])):
        result = await get_target_kennel_ids(1, ctx, rng, "kennel", "all", {})
    assert result == [5, 6]


@pytest.mark.asyncio
async def test_get_kennel_ids_random_exclude(rng):
    """
    Test get kennel ids random exclude.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_random_exclude`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2, 3, 4])):
        result = await get_target_kennel_ids(1, ctx, rng, "kennel", "random_exclude", {"count": 2})
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_kennel_ids_random_exclude_count_ge_total_empty(rng):
    """
    Test get kennel ids random exclude count ge total empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_random_exclude_count_ge_total_empty`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[1, 2])):
        result = await get_target_kennel_ids(1, ctx, rng, "kennel", "random_exclude", {"count": 5})
    assert result == []


@pytest.mark.asyncio
async def test_get_kennel_ids_all_exclude(rng):
    """
    Test get kennel ids all exclude.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_all_exclude`.
    """

    ctx = _ctx()

    async def _list(owner_id, f):
        if f == {}:
            return [1, 2, 3]
        return [1]

    with patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(side_effect=_list)):
        result = await get_target_kennel_ids(1, ctx, rng, "kennel", "all_exclude", {"filter": {"x": 1}})
    assert set(result) == {2, 3}


@pytest.mark.asyncio
async def test_get_kennel_ids_unknown_selector_empty(rng):
    """
    Test get kennel ids unknown selector empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_unknown_selector_empty`.
    """

    ctx = _ctx()
    result = await get_target_kennel_ids(1, ctx, rng, "kennel", "bogus", {})
    assert result == []


@pytest.mark.asyncio
async def test_get_kennel_ids_use_saved(rng):
    """
    Test get kennel ids use saved.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_use_saved`.
    """

    ctx = _ctx()
    ctx.extra_data["k_slot"] = {"kennel_ids": [7, 8]}
    result = await get_target_kennel_ids(1, ctx, rng, "kennel", "all", {"use_saved": "k_slot"})
    assert result == [7, 8]


@pytest.mark.asyncio
async def test_get_kennel_ids_use_saved_missing_empty(rng):
    """
    Test get kennel ids use saved missing empty.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_use_saved_missing_empty`.
    """

    ctx = _ctx()
    result = await get_target_kennel_ids(1, ctx, rng, "kennel", "all", {"use_saved": "no_slot"})
    assert result == []


@pytest.mark.asyncio
async def test_get_kennel_ids_save_as(rng):
    """
    Test get kennel ids save as.

    Parameters
    ----------
    rng: Any
        The `rng` value.

    Returns
    -------
    Any
        The result of calling `test_get_kennel_ids_save_as`.
    """

    ctx = _ctx()
    with patch(f"{MOD}.list_matching_kennel_ids", new=AsyncMock(return_value=[11, 12])):
        await get_target_kennel_ids(1, ctx, rng, "kennel", "all", {"save_as": "saved_kennels"})
    assert ctx.extra_data["saved_kennels"] == {"kennel_ids": [11, 12]}
