from discord import Interaction, app_commands

from src.bot.ui import ServerEventParticipationView, build_server_event_embed
from src.game import get_active_server_event


def register_server_event_command(tree: app_commands.CommandTree):
    """
    Register server event command.

    Parameters
    ----------
    tree: Any
        The `tree` value.

    Returns
    -------
    Any
        The result of calling `register_server_event_command`.
    """

    @tree.command(name="server_event", description="Show the current server-wide event")
    async def server_event(interaction: Interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        event = await get_active_server_event(interaction.guild_id, interaction.user.id)
        if event is None:
            await interaction.response.send_message("There is no active server event right now.", ephemeral=True)
            return

        await interaction.response.send_message(
            embed=await build_server_event_embed(event),
            view=ServerEventParticipationView(
                event.occurrence_id, event.server_discord_id, has_menus=bool(event.menus)
            ),
            ephemeral=True,
        )
