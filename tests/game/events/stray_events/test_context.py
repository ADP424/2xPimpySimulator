"""Tests for src/game/events/stray_events/context.py — StrayEventContext and target resolution."""

from __future__ import annotations

import random
from unittest.mock import AsyncMock, patch

import pytest

from src.game.events.stray_events import resolve_stray_target_ids
from src.game.models import StrayEventContext

MOD = "src.game.events.stray_events.context"


# ---------------------------------------------------------------------------
# resolve_stray_target_ids
# ---------------------------------------------------------------------------


class TestResolveStrayTargetIds:
    @pytest.mark.asyncio
    async def test_random_selector_picks_one(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30])
        rng = random.Random(42)
        ids = await resolve_stray_target_ids(context, "random", {}, rng)
        assert len(ids) == 1
        assert ids[0] in [10, 20, 30]

    @pytest.mark.asyncio
    async def test_random_selector_with_count(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30, 40, 50])
        rng = random.Random(42)
        ids = await resolve_stray_target_ids(context, "random", {"count": 2}, rng)
        assert len(ids) == 2

    @pytest.mark.asyncio
    async def test_all_selector_returns_all(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30])
        rng = random.Random(42)
        ids = await resolve_stray_target_ids(context, "all", {}, rng)
        assert ids == [10, 20, 30]

    @pytest.mark.asyncio
    async def test_random_exclude_selector(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30, 40, 50])
        rng = random.Random(42)
        ids = await resolve_stray_target_ids(context, "random_exclude", {"count": 2}, rng)
        assert len(ids) == 3

    @pytest.mark.asyncio
    async def test_random_exclude_count_ge_total_returns_empty(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20])
        rng = random.Random(42)
        ids = await resolve_stray_target_ids(context, "random_exclude", {"count": 5}, rng)
        assert ids == []

    @pytest.mark.asyncio
    async def test_all_exclude_selector(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20])
        rng = random.Random(42)

        async def _list(server_id, filter_spec):
            if filter_spec:
                return [10, 20]  # matched by filter (pool)
            return [10, 20, 30]  # all strays (empty filter)

        with patch(f"{MOD}.list_matching_stray_pooch_ids", new=AsyncMock(side_effect=_list)):
            ids = await resolve_stray_target_ids(context, "all_exclude", {"filter": {"alive": True}}, rng)
        # pool=[10,20] (matching filter), all=[10,20,30]; exclude pool → [30]
        assert ids == [30]

    @pytest.mark.asyncio
    async def test_unknown_selector_returns_empty(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20])
        rng = random.Random(42)
        ids = await resolve_stray_target_ids(context, "bogus", {}, rng)
        assert ids == []

    @pytest.mark.asyncio
    async def test_use_saved_returns_slot_ids(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20])
        context.extra_data["my_slot"] = {"pooch_ids": [99, 100]}
        rng = random.Random(42)
        ids = await resolve_stray_target_ids(context, "all", {"use_saved": "my_slot"}, rng)
        assert ids == [99, 100]

    @pytest.mark.asyncio
    async def test_use_saved_missing_slot_returns_empty(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20])
        rng = random.Random(42)
        ids = await resolve_stray_target_ids(context, "all", {"use_saved": "no_slot"}, rng)
        assert ids == []

    @pytest.mark.asyncio
    async def test_save_as_stores_result(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30])
        rng = random.Random(42)
        await resolve_stray_target_ids(context, "all", {"save_as": "saved"}, rng)
        assert context.extra_data["saved"]["pooch_ids"] == [10, 20, 30]

    @pytest.mark.asyncio
    async def test_filter_narrows_pool(self):
        context = StrayEventContext(server_discord_id=200, candidate_stray_ids=[10, 20, 30])
        rng = random.Random(42)

        with patch(
            f"{MOD}.list_matching_stray_pooch_ids",
            new=AsyncMock(return_value=[20]),
        ):
            ids = await resolve_stray_target_ids(context, "all", {"filter": {"alive": True}}, rng)

        assert ids == [20]
