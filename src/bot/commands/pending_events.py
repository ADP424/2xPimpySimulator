from discord import Interaction, app_commands

from bot.ui.events import send_all_pending_event_dms
from game import get_active_events_for_owner


def register_pending_events_command(tree: app_commands.CommandTree):
    @tree.command(name="pending_events", description="DM yourself the events that still need a response")
    async def pending_events(interaction: Interaction):
        events = await get_active_events_for_owner(interaction.user.id, pending_only=True)
        if not events:
            await interaction.response.send_message("You have no pending events right now.", ephemeral=True)
            return

        sent, failed = await send_all_pending_event_dms(interaction.client, interaction.user.id, events)
        if sent and not failed:
            await interaction.response.send_message(
                f"📬 I sent {sent} pending event{'s' if sent != 1 else ''} to your DMs.",
                ephemeral=True,
            )
            return

        if sent:
            await interaction.response.send_message(
                f"📬 I sent {sent} pending event{'s' if sent != 1 else ''}, but {failed} could not be delivered.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "I couldn't DM your pending owner_events. Please make sure your DMs are open.",
            ephemeral=True,
        )
