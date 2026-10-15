"""Contract tests for the hour loop in src/bot/day_change_loop.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot import (
    ensure_controls,
    ensure_hour_controls,
    ensure_week_controls,
    is_hour_change_paused,
    set_hour_change_paused,
    trigger_manual_hour_change,
)
from src.bot.day_change_loop import hour_change_runner

MOD = "src.bot.day_change_loop"


def _make_bot():
    bot = MagicMock()
    for prefix in ("day", "hour", "week"):
        for attr in ("paused_event", "manual_queue", "run_lock"):
            setattr(bot, f"_{prefix}_change_{attr}", None)
    return bot


@pytest.mark.contract
class TestHourControls:
    def test_hour_and_week_share_the_day_lock(self):
        bot = _make_bot()
        _, _, day_lock = ensure_controls(bot)
        assert ensure_hour_controls(bot)[2] is day_lock
        assert ensure_week_controls(bot)[2] is day_lock

    async def test_pause_and_resume(self):
        bot = _make_bot()
        assert is_hour_change_paused(bot) is False
        assert await set_hour_change_paused(bot, paused=True) is True
        assert is_hour_change_paused(bot) is True
        assert await set_hour_change_paused(bot, paused=False) is False

    async def test_trigger_queues_one_tick(self):
        bot = _make_bot()
        await trigger_manual_hour_change(bot)
        _, queue, _ = ensure_hour_controls(bot)
        assert queue.qsize() == 1


@pytest.mark.contract
class TestHourChangeRunOnce:
    async def _run_once(self, bot):
        task = asyncio.create_task(hour_change_runner(bot, stage="dev"))
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await bot._hour_change_run_once()

    async def test_runs_hour_change_then_owner_events(self):
        bot = _make_bot()
        summaries = {1: MagicMock()}
        triggered = {100: [MagicMock()]}
        calls = []
        with (
            patch(f"{MOD}.run_hour_change", new=AsyncMock(side_effect=lambda **_: calls.append("hour") or summaries)),
            patch(f"{MOD}.post_hour_change_summaries", new=AsyncMock()) as post_summaries,
            patch(f"{MOD}.post_hour_change_webhooks", new=AsyncMock()) as post_webhooks,
            patch(
                f"{MOD}.run_hourly_event_check",
                new=AsyncMock(side_effect=lambda **_: calls.append("events") or triggered),
            ),
            patch(f"{MOD}.post_hourly_event_notifications", new=AsyncMock()) as post_dms,
        ):
            await self._run_once(bot)

        assert calls == ["hour", "events"]
        post_summaries.assert_awaited_once_with(bot, summaries)
        post_webhooks.assert_awaited_once_with(summaries)
        post_dms.assert_awaited_once_with(bot, triggered)

    async def test_webhook_failure_does_not_skip_owner_events(self):
        bot = _make_bot()
        with (
            patch(f"{MOD}.run_hour_change", new=AsyncMock(return_value={})),
            patch(f"{MOD}.post_hour_change_summaries", new=AsyncMock()),
            patch(f"{MOD}.post_hour_change_webhooks", new=AsyncMock(side_effect=RuntimeError("down"))),
            patch(f"{MOD}.run_hourly_event_check", new=AsyncMock(return_value={})) as events,
            patch(f"{MOD}.post_hourly_event_notifications", new=AsyncMock()),
        ):
            await self._run_once(bot)
        events.assert_awaited_once()
