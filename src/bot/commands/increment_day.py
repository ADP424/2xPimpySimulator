from discord import Interaction, app_commands

from src.bot.constants import GUILDS
from src.bot.day_change_loop import trigger_manual_day_change


def register_increment_day_command(tree: app_commands.CommandTree):
    """
    Register increment day command.

    Parameters
    ----------
    tree: Any
        The `tree` value.

    Returns
    -------
    Any
        The result of calling `register_increment_day_command`.
    """

    @tree.command(name="increment_day", description="(DEV) Manually run the day change once", guilds=GUILDS)
    async def increment_day(interaction: Interaction):
        bot = interaction.client
        if bot is None:
            await interaction.response.send_message("Bot client not available.", ephemeral=True)
            return

        # Queue the day change so we can respond immediately (day change may take time).
        await trigger_manual_day_change(bot)
        await interaction.response.send_message("✅ Queued **one** manual day change.", ephemeral=True)
