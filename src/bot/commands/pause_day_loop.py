from discord import Interaction, app_commands

from bot.constants import GUILDS
from bot.day_change_loop import is_day_change_paused, set_day_change_paused


def register_pause_day_loop_command(tree: app_commands.CommandTree):
    @tree.command(name="pause_day_loop", description="(DEV) Pause/resume the day change loop", guilds=GUILDS)
    async def pause_day_loop(interaction: Interaction):
        bot = interaction.client
        if bot is None:
            await interaction.response.send_message("Bot client not available.", ephemeral=True)
            return

        new_paused = not is_day_change_paused(bot)  # type: ignore
        await set_day_change_paused(bot, paused=new_paused)  # type: ignore

        if new_paused:
            await interaction.response.send_message("⏸️ Day change loop **paused**.", ephemeral=True)
        else:
            await interaction.response.send_message("▶️ Day change loop **resumed**.", ephemeral=True)
