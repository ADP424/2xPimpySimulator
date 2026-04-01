"""Contract tests for src/bot/day_change_loop.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot import (
    ensure_controls,
    fetch_and_update_names,
    is_day_change_paused,
    post_day_change_summaries,
    post_server_event_notifications,
    post_server_event_resolutions,
    post_stray_event_summaries,
    set_day_change_paused,
    trigger_manual_day_change,
)


def _make_bot():
    """Create a mock bot with no pre-existing control attributes."""
    bot = MagicMock()
    # Remove any auto-created attributes so ensure_controls creates fresh ones
    for attr in ("_day_change_paused_event", "_day_change_manual_queue", "_day_change_run_lock"):
        if hasattr(bot, attr):
            delattr(bot, attr)
    # MagicMock auto-creates attributes on access, so we need to use spec or side_effect
    bot._day_change_paused_event = None
    bot._day_change_manual_queue = None
    bot._day_change_run_lock = None
    return bot


@pytest.mark.contract
class TestEnsureControls:
    def test_creates_event_queue_and_lock(self):
        bot = _make_bot()
        paused_event, manual_queue, run_lock = ensure_controls(bot)
        assert isinstance(paused_event, asyncio.Event)
        assert isinstance(manual_queue, asyncio.Queue)
        assert isinstance(run_lock, asyncio.Lock)

    def test_paused_event_starts_set(self):
        """Paused event should start in 'set' state (not paused)."""
        bot = _make_bot()
        paused_event, _, _ = ensure_controls(bot)
        assert paused_event.is_set()

    def test_reuses_existing_controls(self):
        bot = _make_bot()
        paused1, queue1, lock1 = ensure_controls(bot)
        paused2, queue2, lock2 = ensure_controls(bot)
        assert paused1 is paused2
        assert queue1 is queue2
        assert lock1 is lock2


@pytest.mark.contract
class TestIsDayChangePaused:
    def test_not_paused_by_default(self):
        bot = _make_bot()
        assert is_day_change_paused(bot) is False


@pytest.mark.contract
class TestSetDayChangePaused:
    async def test_pause(self):
        bot = _make_bot()
        result = await set_day_change_paused(bot, paused=True)
        assert result is True
        assert is_day_change_paused(bot) is True

    async def test_unpause(self):
        bot = _make_bot()
        await set_day_change_paused(bot, paused=True)
        result = await set_day_change_paused(bot, paused=False)
        assert result is False
        assert is_day_change_paused(bot) is False

    async def test_toggle_returns_new_state(self):
        bot = _make_bot()
        paused = await set_day_change_paused(bot, paused=True)
        assert paused is True
        unpaused = await set_day_change_paused(bot, paused=False)
        assert unpaused is False


@pytest.mark.contract
class TestTriggerManualDayChange:
    async def test_puts_item_in_queue(self):
        bot = _make_bot()
        _, manual_queue, _ = ensure_controls(bot)
        assert manual_queue.empty()

        await trigger_manual_day_change(bot)
        assert not manual_queue.empty()
        value = manual_queue.get_nowait()
        assert value == 1

    async def test_multiple_triggers_queue_multiple(self):
        bot = _make_bot()
        _, manual_queue, _ = ensure_controls(bot)

        await trigger_manual_day_change(bot)
        await trigger_manual_day_change(bot)
        assert manual_queue.qsize() == 2


def _make_owner_stub(discord_id: int):
    owner = MagicMock()
    owner.discord_id = discord_id
    return owner


@pytest.mark.contract
class TestFetchAndUpdateNames:
    async def test_calls_update_with_names(self):
        bot = MagicMock()
        user = MagicMock()
        user.display_name = "CoolUser"
        bot.get_user = MagicMock(return_value=user)

        owners = [_make_owner_stub(111), _make_owner_stub(222)]

        with (
            patch("src.bot.day_change_loop.list_all_owners", new_callable=AsyncMock, return_value=owners),
            patch("src.bot.day_change_loop.update_owner_names", new_callable=AsyncMock) as mock_update,
        ):
            await fetch_and_update_names(bot)
            mock_update.assert_called_once_with({111: "CoolUser", 222: "CoolUser"})

    async def test_skips_not_found_users(self):
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(side_effect=discord.NotFound(MagicMock(), "not found"))

        owners = [_make_owner_stub(999)]

        with (
            patch("src.bot.day_change_loop.list_all_owners", new_callable=AsyncMock, return_value=owners),
            patch("src.bot.day_change_loop.update_owner_names", new_callable=AsyncMock) as mock_update,
        ):
            await fetch_and_update_names(bot)
            # Should still call update, but with empty dict since the user wasn't found
            mock_update.assert_called_once_with({})

    async def test_skips_http_exception_users(self):
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "error"))

        owners = [_make_owner_stub(888)]

        with (
            patch("src.bot.day_change_loop.list_all_owners", new_callable=AsyncMock, return_value=owners),
            patch("src.bot.day_change_loop.update_owner_names", new_callable=AsyncMock) as mock_update,
        ):
            await fetch_and_update_names(bot)
            mock_update.assert_called_once_with({})

    async def test_uses_get_user_first(self):
        bot = MagicMock()
        user = MagicMock()
        user.display_name = "LocalUser"
        bot.get_user = MagicMock(return_value=user)
        bot.fetch_user = AsyncMock()  # should not be called

        owners = [_make_owner_stub(555)]

        with (
            patch("src.bot.day_change_loop.list_all_owners", new_callable=AsyncMock, return_value=owners),
            patch("src.bot.day_change_loop.update_owner_names", new_callable=AsyncMock),
        ):
            await fetch_and_update_names(bot)
            bot.fetch_user.assert_not_called()


@pytest.mark.contract
class TestPostDayChangeSummaries:
    async def test_skips_server_with_no_event_channel(self):
        bot = MagicMock()
        summary = MagicMock()
        summary.births = []
        summary.deaths = []

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=None):
            await post_day_change_summaries(bot, {200: summary})
            bot.get_channel.assert_not_called()

    async def test_sends_nothing_to_report_when_empty(self):
        bot = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=channel)

        summary = MagicMock()
        summary.births = []
        summary.deaths = []

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=12345):
            await post_day_change_summaries(bot, {200: summary})
            channel.send.assert_called_once()
            call_kwargs = channel.send.call_args[1]
            embed = call_kwargs["embed"]
            assert "Nothing to report" in embed.description

    async def test_fetches_channel_if_not_cached(self):
        bot = MagicMock()
        bot.get_channel = MagicMock(return_value=None)
        channel = MagicMock()
        channel.send = AsyncMock()
        bot.fetch_channel = AsyncMock(return_value=channel)

        summary = MagicMock()
        summary.births = []
        summary.deaths = []

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=12345):
            await post_day_change_summaries(bot, {200: summary})
            bot.fetch_channel.assert_called_once_with(12345)

    async def test_skips_when_channel_fetch_fails(self):
        bot = MagicMock()
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(side_effect=Exception("not found"))

        summary = MagicMock()
        summary.births = []
        summary.deaths = []

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=12345):
            # Should not raise
            await post_day_change_summaries(bot, {200: summary})


@pytest.mark.contract
class TestPostServerEventNotifications:
    async def test_skips_server_with_no_channel(self):
        bot = MagicMock()

        event = MagicMock()
        event.occurrence_id = 1
        event.server_discord_id = 200

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=None):
            await post_server_event_notifications(bot, {200: event})
            bot.get_channel.assert_not_called()

    async def test_posts_and_registers_view(self):
        bot = MagicMock()
        channel = MagicMock()
        message = MagicMock()
        message.id = 9999
        channel.send = AsyncMock(return_value=message)
        bot.get_channel = MagicMock(return_value=channel)
        bot.add_view = MagicMock()

        event = MagicMock()
        event.occurrence_id = 1
        event.server_discord_id = 200

        fake_embed = MagicMock()

        with (
            patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=12345),
            patch("src.bot.day_change_loop.build_server_event_embed", new_callable=AsyncMock, return_value=fake_embed),
            patch("src.bot.day_change_loop.set_server_event_message_id", new_callable=AsyncMock),
        ):
            await post_server_event_notifications(bot, {200: event})
            channel.send.assert_called_once()
            bot.add_view.assert_called_once()


@pytest.mark.contract
class TestPostServerEventResolutions:
    async def test_skips_resolution_with_no_channel(self):
        bot = MagicMock()
        resolution = MagicMock()
        resolution.server_discord_id = 200

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=None):
            await post_server_event_resolutions(bot, [resolution])
            bot.get_channel.assert_not_called()

    async def test_sends_resolution_embed(self):
        bot = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=channel)

        resolution = MagicMock()
        resolution.server_discord_id = 200
        fake_embed = MagicMock()

        with (
            patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=12345),
            patch(
                "src.bot.day_change_loop.build_server_event_resolution_embed",
                new_callable=AsyncMock,
                return_value=fake_embed,
            ),
        ):
            await post_server_event_resolutions(bot, [resolution])
            channel.send.assert_called_once()


@pytest.mark.contract
class TestPostStrayEventSummaries:
    async def test_skips_server_with_no_channel(self):
        bot = MagicMock()
        result = MagicMock()
        result.pooches_affected = []
        result.pooches_killed = []
        result.pooches_created = []

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=None):
            await post_stray_event_summaries(bot, {200: [("stray_event", result)]})
            bot.get_channel.assert_not_called()

    async def test_posts_stray_event_lines(self):
        bot = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=channel)

        result = MagicMock()
        result.pooches_affected = [1]
        result.pooches_killed = []
        result.pooches_created = []

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=12345):
            await post_stray_event_summaries(bot, {200: [("stray_encounter", result)]})
            channel.send.assert_called_once()
            content = channel.send.call_args[0][0]
            assert "stray_encounter" in content

    async def test_posts_killed_info_in_lines(self):
        bot = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=channel)

        result = MagicMock()
        result.pooches_affected = []
        result.pooches_killed = [1, 2]
        result.pooches_created = []

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=12345):
            await post_stray_event_summaries(bot, {200: [("street_fight", result)]})
            content = channel.send.call_args[0][0]
            assert "killed" in content

    async def test_skips_posting_when_no_events(self):
        bot = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=channel)

        with patch("src.bot.day_change_loop.get_event_channel", new_callable=AsyncMock, return_value=12345):
            await post_stray_event_summaries(bot, {200: []})
            channel.send.assert_not_called()
