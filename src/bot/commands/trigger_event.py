from discord import Interaction, app_commands

from src.bot.constants import GUILDS
from src.bot.event_loop import post_hourly_event_notifications
from src.game import trigger_event_by_name


def register_trigger_event_command(tree: app_commands.CommandTree):
    @tree.command(
        name="trigger_event", description="(DEV) Trigger a specific event by name for yourself", guilds=GUILDS
    )
    @app_commands.describe(name="The internal name of the event to trigger")
    async def trigger_event(interaction: Interaction, name: str):
        if interaction.guild_id is None:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        triggered = await trigger_event_by_name(interaction.user.id, name)
        if triggered is None:
            await interaction.response.send_message(f"No event found with name `{name}`.", ephemeral=True)
            return

        await interaction.response.send_message(f"✅ Triggered event **{name}**. Check your DMs.", ephemeral=True)
        await post_hourly_event_notifications(interaction.client, {interaction.user.id: [triggered]})
