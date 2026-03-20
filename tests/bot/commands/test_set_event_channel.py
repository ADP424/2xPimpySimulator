"""Tests for src/bot/commands/set_event_channel.py."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestSetEventChannelCommand:
    async def test_requires_guild(self):
        from src.bot.commands.set_event_channel import (
            register_set_event_channel_command,
        )

        callback = capture_command_callback(register_set_event_channel_command)
        interaction = make_interaction()
        interaction.guild_id = None
        interaction.channel_id = None

        await callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "server" in msg.lower()

    async def test_sets_channel(self):
        from src.bot.commands.set_event_channel import (
            register_set_event_channel_command,
        )

        callback = capture_command_callback(register_set_event_channel_command)
        interaction = make_interaction()

        with patch("src.bot.commands.set_event_channel.set_event_channel", new_callable=AsyncMock) as mock_set:
            await callback(interaction)
            mock_set.assert_called_once_with(200, 300)

        interaction.response.send_message.assert_called_once()
