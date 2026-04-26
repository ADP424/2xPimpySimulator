"""Shared fixtures and helpers for bot command tests."""

from unittest.mock import AsyncMock, MagicMock, patch


def make_interaction(user_id=100, guild_id=200, channel_id=300):
    """Create a mock Discord interaction suitable for testing command callbacks."""
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.guild = MagicMock()
    interaction.guild.id = guild_id
    interaction.guild_id = guild_id
    interaction.channel_id = channel_id
    interaction.client = MagicMock()
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.channel = MagicMock()
    interaction.channel.send = AsyncMock()
    interaction.message = None
    return interaction


def capture_command_callback(register_fn):
    """Register a command on a mock tree and capture the decorated callback function."""
    captured = {}

    def fake_command(**kwargs):
        def decorator(func):
            captured["callback"] = func
            return func

        return decorator

    def fake_describe(**kwargs):
        def decorator(func):
            return func

        return decorator

    tree = MagicMock()
    tree.command = fake_command

    with patch("discord.app_commands.describe", fake_describe):
        register_fn(tree)

    return captured.get("callback")
