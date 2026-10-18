import os

from discord import Interaction, app_commands

from src.bot.constants import GUILDS
from src.bot.day_change_loop import (
    post_server_event_notifications,
    post_stray_event_summaries,
    server_event_duration,
)
from src.bot.event_loop import post_hourly_event_notifications
from src.game import (
    trigger_event_by_name,
    trigger_server_event_by_name,
    trigger_stray_event_by_name,
)

_EVENT_TYPES = ["owner", "stray", "server_minor", "server_major"]


def register_trigger_event_command(tree: app_commands.CommandTree):
    """
    Register trigger event command.

    Parameters
    ----------
    tree: Any
        The `tree` value.

    Returns
    -------
    Any
        The result of calling `register_trigger_event_command`.
    """

    @tree.command(
        name="trigger_event",
        description="(DEV) Trigger a specific event by name",
        guilds=GUILDS,
    )
    @app_commands.describe(
        event_type="Type of event to trigger",
        name="The internal name of the event to trigger",
    )
    @app_commands.choices(event_type=[app_commands.Choice(name=t, value=t) for t in _EVENT_TYPES])
    async def trigger_event(interaction: Interaction, event_type: str, name: str):
        if interaction.guild_id is None:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if event_type == "owner":
            triggered = await trigger_event_by_name(interaction.user.id, name)
            if triggered is None:
                await interaction.followup.send(f"No owner event found with name `{name}`.", ephemeral=True)
                return
            await interaction.followup.send(f"Triggered owner event **{name}**. Check your DMs.", ephemeral=True)
            await post_hourly_event_notifications(interaction.client, {interaction.user.id: [triggered]})

        elif event_type == "stray":
            result = await trigger_stray_event_by_name(interaction.guild_id, name)
            if result is None:
                await interaction.followup.send(f"No stray event found with name `{name}`.", ephemeral=True)
                return
            await interaction.followup.send(f"Triggered stray event **{name}**.", ephemeral=True)
            await post_stray_event_summaries(interaction.client, {interaction.guild_id: [(name, result)]})

        elif event_type in ("server_minor", "server_major"):
            tier = "major" if event_type == "server_major" else "minor"
            duration = server_event_duration(tier, os.getenv("STAGE", "dev").lower())
            triggered = await trigger_server_event_by_name(interaction.guild_id, name, duration=duration)
            if triggered is None:
                await interaction.followup.send(
                    f"No server event found with name `{name}`, or no event channel is set.", ephemeral=True
                )
                return
            await interaction.followup.send(f"Triggered server event **{name}**.", ephemeral=True)
            await post_server_event_notifications(interaction.client, {interaction.guild_id: triggered})

        else:
            await interaction.followup.send(f"Unknown event type `{event_type}`.", ephemeral=True)
