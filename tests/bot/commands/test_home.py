"""Tests for src/bot/commands/home.py."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestHomeCommand:
    async def test_home_requires_guild(self):
        """Home command should reject DM usage."""
        from src.bot.commands.home import register_home_command

        callback = capture_command_callback(register_home_command)
        assert callback is not None

        interaction = make_interaction()
        interaction.guild_id = None
        interaction.channel_id = None

        await callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "server" in msg.lower()

    async def test_home_sends_content_and_view(self):
        """Home command should send home content with a HomeView."""
        from src.bot.commands.home import register_home_command

        callback = capture_command_callback(register_home_command)
        interaction = make_interaction()

        with patch("src.bot.commands.home.build_home_content", new_callable=AsyncMock, return_value="**Home**"):
            await callback(interaction)

        interaction.response.send_message.assert_called_once()
        kwargs = interaction.response.send_message.call_args[1]
        assert kwargs.get("content") == "**Home**"
        assert "view" in kwargs
