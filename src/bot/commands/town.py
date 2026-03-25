from discord import Interaction, app_commands

from src.game import get_season

from ..ui.town import TownView

_SEASON_EMOJIS = {
    "spring": "🌸🌿",
    "summer": "☀️🌻",
    "autumn": "🍂🍁",
    "winter": "❄️⛄",
}


def register_town_command(tree: app_commands.CommandTree):
    @tree.command(name="town", description="Head straight to town.")
    async def town(interaction: Interaction):
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message("This command must be used in a server channel.", ephemeral=True)
            return

        season = await get_season()
        emojis = _SEASON_EMOJIS.get(season.lower(), "")
        await interaction.response.send_message(
            content=(
                f"**Welcome to the Town**\n"
                f"{emojis} It's currently **{season.capitalize()}**. Choose where you want to go."
            ),
            view=TownView(),
            ephemeral=False,
        )
