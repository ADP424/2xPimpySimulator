from discord import Interaction, app_commands

from src.bot.constants import GUILDS
from src.game import add_money


def register_get_money_command(tree: app_commands.CommandTree):
    @tree.command(name="get_money", description="(DEV) Give yourself money", guilds=GUILDS)
    @app_commands.describe(amount="How many dollars to add")
    async def get_money(interaction: Interaction, amount: int):
        if interaction.guild_id is None:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("Amount must be > 0.", ephemeral=True)
            return

        owner = await add_money(interaction.guild_id, interaction.user.id, amount)
        await interaction.response.send_message(
            f"✅ Added ${amount}. You now have ${owner.dollars}.",
            ephemeral=True,
        )
