"""Tests for src/bot/commands/pending_events.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestPendingEventsCommand:
    async def test_no_pending(self):
        from src.bot.commands import register_pending_events_command

        callback = capture_command_callback(register_pending_events_command)
        interaction = make_interaction()

        with patch(
            "src.bot.commands.pending_events.get_active_events_for_owner", new_callable=AsyncMock, return_value=[]
        ):
            await callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "no pending" in msg.lower()

    async def test_sends_pending_events(self):
        from src.bot.commands import register_pending_events_command

        callback = capture_command_callback(register_pending_events_command)
        interaction = make_interaction()

        with (
            patch(
                "src.bot.commands.pending_events.get_active_events_for_owner",
                new_callable=AsyncMock,
                return_value=[MagicMock()],
            ),
            patch(
                "src.bot.commands.pending_events.send_all_pending_event_dms",
                new_callable=AsyncMock,
                return_value=(1, 0),
            ),
        ):
            await callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "sent" in msg.lower()
