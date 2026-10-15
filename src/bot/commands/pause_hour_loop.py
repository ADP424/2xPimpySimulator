from discord import Interaction, app_commands

from src.bot.constants import GUILDS
from src.bot.day_change_loop import is_hour_change_paused, set_hour_change_paused


def register_pause_hour_loop_command(tree: app_commands.CommandTree):
    """
    Register pause hour loop command.

    Parameters
    ----------
    tree: Any
        The `tree` value.

    Returns
    -------
    Any
        The result of calling `register_pause_hour_loop_command`.
    """

    @tree.command(name="pause_hour_loop", description="(DEV) Pause/resume the hour change loop", guilds=GUILDS)
    async def pause_hour_loop(interaction: Interaction):
        bot = interaction.client
        if bot is None:
            await interaction.response.send_message("Bot client not available.", ephemeral=True)
            return

        new_paused = not is_hour_change_paused(bot)
        await set_hour_change_paused(bot, paused=new_paused)

        if new_paused:
            await interaction.response.send_message("⏸️ Hour change loop **paused**.", ephemeral=True)
        else:
            await interaction.response.send_message("▶️ Hour change loop **resumed**.", ephemeral=True)
