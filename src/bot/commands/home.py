from discord import app_commands, Interaction
from ..ui.home import HomeView


def register_home_command(tree: app_commands.CommandTree):
    @tree.command(name="home", description="Home sweet home...")
    async def home(interaction: Interaction):
        await interaction.response.send_message(
            content=f"Welcome home, <@{interaction.user.id}>!",
            view=HomeView(),
            ephemeral=True,
        )
