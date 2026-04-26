from discord import Interaction, app_commands

from src.bot.ui import HomeView, build_home_content


def register_home_command(tree: app_commands.CommandTree):
    """
    Register home command.

    Parameters
    ----------
    tree: Any
        The `tree` value.

    Returns
    -------
    Any
        The result of calling `register_home_command`.
    """

    @tree.command(name="home", description="Home sweet home...")
    async def home(interaction: Interaction):
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message("This command must be used in a server channel.", ephemeral=True)
            return

        await interaction.response.send_message(
            content=await build_home_content(guild_id=interaction.guild_id, user_id=interaction.user.id),
            view=HomeView(),
            ephemeral=False,
        )
