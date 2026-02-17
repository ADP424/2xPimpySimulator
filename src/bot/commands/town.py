from discord import Interaction, app_commands

from ..ui.town import TownView


def register_town_command(tree: app_commands.CommandTree):
    @tree.command(name="town", description="Head straight to town.")
    async def town(interaction: Interaction):
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message("This command must be used in a server channel.", ephemeral=True)
            return

        await interaction.response.send_message(
            content="🏘️ **Welcome to the Town**\nChoose where you want to go.",
            view=TownView(),
            ephemeral=False,
        )
