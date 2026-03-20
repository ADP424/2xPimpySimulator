"""Tests for src/bot/commands/trigger_event.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.bot.commands.conftest import capture_command_callback, make_interaction


@pytest.mark.contract
class TestTriggerEventCommand:
    async def test_requires_guild(self):
        from src.bot.commands.trigger_event import register_trigger_event_command

        callback = capture_command_callback(register_trigger_event_command)
        interaction = make_interaction()
        interaction.guild_id = None

        with patch("src.bot.commands.trigger_event.trigger_event_by_name", new_callable=AsyncMock):
            await callback(interaction, name="test_event")

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "server" in msg.lower()

    async def test_not_found_event(self):
        from src.bot.commands.trigger_event import register_trigger_event_command

        callback = capture_command_callback(register_trigger_event_command)
        interaction = make_interaction()

        with patch("src.bot.commands.trigger_event.trigger_event_by_name", new_callable=AsyncMock, return_value=None):
            await callback(interaction, name="nonexistent")

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "no event" in msg.lower()

    async def test_triggers_and_posts(self):
        from src.bot.commands.trigger_event import register_trigger_event_command

        callback = capture_command_callback(register_trigger_event_command)
        interaction = make_interaction()
        mock_event = MagicMock()

        with (
            patch(
                "src.bot.commands.trigger_event.trigger_event_by_name",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
            patch(
                "src.bot.commands.trigger_event.post_hourly_event_notifications", new_callable=AsyncMock
            ) as mock_post,
        ):
            await callback(interaction, name="heat_wave")
            mock_post.assert_called_once_with(interaction.client, {100: [mock_event]})

        interaction.response.send_message.assert_called_once()
