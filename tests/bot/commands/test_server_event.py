"""Tests for src/bot/commands/server_event.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestServerEventCommand:
    async def test_requires_guild(self):
        from src.bot.commands import register_server_event_command

        callback = capture_command_callback(register_server_event_command)
        interaction = make_interaction()
        interaction.guild_id = None

        await callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "server" in msg.lower()

    async def test_no_active_event(self):
        from src.bot.commands import register_server_event_command

        callback = capture_command_callback(register_server_event_command)
        interaction = make_interaction()

        with patch("src.bot.commands.server_event.list_active_server_events", new_callable=AsyncMock, return_value=[]):
            await callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "no active" in msg.lower()

    async def test_shows_active_event(self):
        from src.bot.commands import register_server_event_command

        callback = capture_command_callback(register_server_event_command)
        interaction = make_interaction()

        mock_event = MagicMock()
        mock_event.occurrence_id = 1
        mock_event.server_discord_id = 200

        with (
            patch(
                "src.bot.commands.server_event.list_active_server_events",
                new_callable=AsyncMock,
                return_value=[mock_event],
            ),
            patch(
                "src.bot.commands.server_event.build_server_event_embed",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
        ):
            await callback(interaction)

        interaction.response.send_message.assert_called_once()
        kwargs = interaction.response.send_message.call_args[1]
        assert "embed" in kwargs
        assert "view" in kwargs

    async def test_shows_every_active_event(self):
        """A daily and a weekly event at once: the first in the response, the second as a follow-up."""
        from src.bot.commands import register_server_event_command

        callback = capture_command_callback(register_server_event_command)
        interaction = make_interaction()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()

        events = []
        for occurrence_id in (1, 2):
            event = MagicMock()
            event.occurrence_id = occurrence_id
            event.server_discord_id = 200
            events.append(event)

        with (
            patch("src.bot.commands.server_event.list_active_server_events", new=AsyncMock(return_value=events)),
            patch("src.bot.commands.server_event.build_server_event_embed", new=AsyncMock(return_value=MagicMock())),
        ):
            await callback(interaction)

        interaction.response.send_message.assert_called_once()
        interaction.followup.send.assert_awaited_once()
        assert interaction.response.send_message.call_args.kwargs["view"].occurrence_id == 1
        assert interaction.followup.send.call_args.kwargs["view"].occurrence_id == 2
