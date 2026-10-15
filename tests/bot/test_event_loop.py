"""Contract tests for src/bot/event_loop.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot import post_hourly_event_notifications


def _make_bot():
    bot = MagicMock()
    return bot


@pytest.mark.contract
class TestPostHourlyEventNotifications:
    async def test_sends_dm_for_each_event(self):
        bot = _make_bot()
        event1 = MagicMock()
        event1.active_owner_event_id = 1
        event2 = MagicMock()
        event2.active_owner_event_id = 2

        with patch("src.bot.event_loop.send_triggered_event_dm", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await post_hourly_event_notifications(bot, {100: [event1, event2]})
            assert mock_send.call_count == 2
            mock_send.assert_any_call(bot, 100, event1)
            mock_send.assert_any_call(bot, 100, event2)

    async def test_logs_warning_on_failed_delivery(self):
        bot = _make_bot()
        event = MagicMock()
        event.active_owner_event_id = 42

        with (
            patch("src.bot.event_loop.send_triggered_event_dm", new_callable=AsyncMock) as mock_send,
            patch("src.bot.event_loop.logger") as mock_logger,
        ):
            mock_send.return_value = False
            await post_hourly_event_notifications(bot, {100: [event]})
            mock_logger.warning.assert_called_once()

    async def test_empty_events_dict_does_nothing(self):
        bot = _make_bot()
        with patch("src.bot.event_loop.send_triggered_event_dm", new_callable=AsyncMock) as mock_send:
            await post_hourly_event_notifications(bot, {})
            mock_send.assert_not_called()

    async def test_multiple_owners(self):
        bot = _make_bot()
        event_a = MagicMock()
        event_a.active_owner_event_id = 1
        event_b = MagicMock()
        event_b.active_owner_event_id = 2

        with patch("src.bot.event_loop.send_triggered_event_dm", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await post_hourly_event_notifications(bot, {100: [event_a], 200: [event_b]})
            assert mock_send.call_count == 2
