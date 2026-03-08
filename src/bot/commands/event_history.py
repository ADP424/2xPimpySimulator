from discord import Interaction, app_commands

from bot.ui.events import send_event_history_dm
from game import get_event_history


def register_event_history_command(tree: app_commands.CommandTree):
    @tree.command(name="event_history", description="DM yourself your recent event history")
    @app_commands.describe(limit="How many recent history entries to include")
    async def event_history(interaction: Interaction, limit: app_commands.Range[int, 1, 50] = 25):
        records = await get_event_history(interaction.user.id, limit=limit)
        if not records:
            await interaction.response.send_message("You do not have any event history yet.", ephemeral=True)
            return

        delivered = await send_event_history_dm(interaction.client, interaction.user.id, limit=limit)
        if delivered:
            await interaction.response.send_message("📬 I sent your event history to your DMs.", ephemeral=True)
            return

        await interaction.response.send_message(
            "I couldn't send your event history. Please make sure your DMs are open.",
            ephemeral=True,
        )
