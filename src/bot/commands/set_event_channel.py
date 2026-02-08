from discord import app_commands, Interaction

from game import set_event_channel


def register_set_event_channel_command(tree: app_commands.CommandTree):
    @tree.command(name="set_event_channel", description="Set this channel as the server's day-change event channel")
    async def event_channel(interaction: Interaction):
        if interaction.guild_id is None or interaction.channel_id is None:
            await interaction.response.send_message("This command must be used in a server channel.", ephemeral=True)
            return
        await set_event_channel(int(interaction.guild_id), int(interaction.channel_id))
        await interaction.response.send_message("✅ Event channel set for this server.", ephemeral=True)
