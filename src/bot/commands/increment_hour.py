from discord import Interaction, app_commands

from src.bot.constants import GUILDS
from src.bot.day_change_loop import trigger_manual_hour_change


def register_increment_hour_command(tree: app_commands.CommandTree):
    """
    Register increment hour command.

    Parameters
    ----------
    tree: Any
        The `tree` value.

    Returns
    -------
    Any
        The result of calling `register_increment_hour_command`.
    """

    @tree.command(name="increment_hour", description="(DEV) Manually run the hour change once", guilds=GUILDS)
    async def increment_hour(interaction: Interaction):
        bot = interaction.client
        if bot is None:
            await interaction.response.send_message("Bot client not available.", ephemeral=True)
            return

        # Queue the hour change so we can respond immediately (it may take time).
        await trigger_manual_hour_change(bot)
        await interaction.response.send_message("✅ Queued **one** manual hour change.", ephemeral=True)
