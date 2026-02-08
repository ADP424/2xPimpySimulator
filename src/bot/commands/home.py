from discord import app_commands, Interaction
from game import get_or_create_owner
from ..ui.home import HomeView


def register_home_command(tree: app_commands.CommandTree):
    @tree.command(name="home", description="Home sweet home...")
    async def home(interaction: Interaction):
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message("This command must be used in a server channel.", ephemeral=True)
            return

        owner = await get_or_create_owner(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(
            content=(
                f"**<@{owner.discord_id}>'s Home**\n"
                f"You have ${owner.dollars}.\n"
                f"You have {owner.bloodskulls} bloodskulls."
            ),
            view=HomeView(),
            ephemeral=False,
        )
