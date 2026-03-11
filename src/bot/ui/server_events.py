from __future__ import annotations

from datetime import datetime, timezone

import discord

from src.game import (
    get_active_server_event,
    get_event_channel,
    get_or_create_owner,
    list_active_server_events,
    list_kennel_pooches,
    list_owner_kennels,
    participate_in_server_event,
)
from src.game.models import Pooch
from src.game.models.events import (
    ServerEventOption,
    ServerEventResolution,
    TriggeredServerEvent,
)

SEVERITY_COLORS: dict[str, discord.Color] = {
    "trivial": discord.Color.light_grey(),
    "minor": discord.Color.light_grey(),
    "moderate": discord.Color.blurple(),
    "major": discord.Color.orange(),
    "critical": discord.Color.red(),
}


def _color_for_severity(severity: str) -> discord.Color:
    return SEVERITY_COLORS.get(str(severity).lower(), discord.Color.blurple())


def _truncate(text: str, limit: int = 1024) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "..."


def _discord_timestamp(value: datetime | None, style: str = "R") -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return f"<t:{int(value.timestamp())}:{style}>"


def _format_server_option_line(option: ServerEventOption) -> str:
    requirements: list[str] = []
    if option.min_money > 0:
        requirements.append(f"${int(option.min_money)}")
    if option.min_bloodskulls > 0:
        requirements.append(f"{int(option.min_bloodskulls)} bloodskulls")
    if option.requires_pooch_selection:
        requirements.append("a pooch")

    line = f"**{option.label}**"
    if option.description:
        line += f" — {option.description}"
    if requirements:
        line += f" _(requires {' + '.join(requirements)})_"
    return line


def _format_participation_status(event: TriggeredServerEvent) -> str:
    if event.viewer_participation is None:
        return "You have not participated yet."

    participation = event.viewer_participation
    bits = [f"You chose **{participation.selected_option.label}**."]
    if participation.context.selected_pooch_id is not None:
        pooch_label = next(
            (
                reference.label
                for reference in participation.entity_references.pooches
                if reference.id == participation.context.selected_pooch_id
            ),
            f"Pooch #{participation.context.selected_pooch_id}",
        )
        bits.append(f"Selected pooch: **{pooch_label}**")
    if participation.rank is not None:
        bits.append(f"Rank: **#{participation.rank}**")
    if participation.immediate_result and participation.immediate_result.message:
        bits.append(participation.immediate_result.message)
    if participation.resolution_result and participation.resolution_result.message:
        bits.append(participation.resolution_result.message)
    return "\n".join(bits)


async def build_server_event_embed(event: TriggeredServerEvent, include_viewer_status: bool = True) -> discord.Embed:
    embed = discord.Embed(
        title=event.name,
        description=event.description,
        color=_color_for_severity(event.severity),
    )
    embed.add_field(name="Category", value=event.category, inline=True)
    embed.add_field(name="Ends", value=_discord_timestamp(event.expires_at), inline=True)
    cap = "∞" if event.max_participants <= 0 else str(event.max_participants)
    embed.add_field(name="Participants", value=f"{event.participation_count}/{cap}", inline=True)

    if event.flavor_text:
        embed.add_field(name="Flavor", value=_truncate(event.flavor_text), inline=False)

    if event.options:
        embed.add_field(
            name="How to participate",
            value=_truncate("\n".join(_format_server_option_line(option) for option in event.options)),
            inline=False,
        )

    if include_viewer_status:
        embed.add_field(name="Your status", value=_truncate(_format_participation_status(event)), inline=False)
    return embed


async def build_server_event_resolution_embed(resolution: ServerEventResolution) -> discord.Embed:
    embed = discord.Embed(
        title=f"{resolution.name} resolved",
        description=resolution.result_summary.message or "The server event has been resolved.",
        color=discord.Color.green(),
    )
    embed.add_field(name="Participants", value=str(resolution.participant_count), inline=True)
    winners = ", ".join(f"<@{owner_id}>" for owner_id in resolution.winner_owner_ids) or "No winners"
    embed.add_field(name="Winner(s)", value=winners, inline=False)
    return embed


async def _list_owner_living_pooches(server_discord_id: int, owner_discord_id: int) -> list[Pooch]:
    await get_or_create_owner(server_discord_id, owner_discord_id)
    pooches: list[Pooch] = []
    for kennel in await list_owner_kennels(owner_discord_id):
        pooches.extend([pooch for pooch in await list_kennel_pooches(kennel.id) if pooch.alive])
    return pooches


class ServerEventPoochSelect(discord.ui.Select):
    def __init__(self, occurrence_id: int, server_discord_id: int, option: ServerEventOption, pooches: list[Pooch]):
        self.occurrence_id = occurrence_id
        self.server_discord_id = server_discord_id
        self.option = option
        options = [
            discord.SelectOption(label=pooch.name[:100], description=f"ID {pooch.id}", value=str(pooch.id))
            for pooch in pooches[:25]
        ]
        super().__init__(placeholder="Choose a pooch...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        pooch_id = int(self.values[0])
        success, message, _summary = await participate_in_server_event(
            self.occurrence_id,
            self.server_discord_id,
            interaction.user.id,
            self.option.id,
            selected_pooch_id=pooch_id,
        )
        if not success:
            await interaction.response.send_message(message, ephemeral=True)
            return
        await interaction.response.send_message(message, ephemeral=True)
        await refresh_public_server_event_message(interaction.client, self.server_discord_id, self.occurrence_id)


class ServerEventPoochSelectView(discord.ui.View):
    def __init__(self, occurrence_id: int, server_discord_id: int, option: ServerEventOption, pooches: list[Pooch]):
        super().__init__(timeout=120)
        self.add_item(ServerEventPoochSelect(occurrence_id, server_discord_id, option, pooches))


class ServerEventOptionSelect(discord.ui.Select):
    def __init__(self, occurrence_id: int, server_discord_id: int, options: list[ServerEventOption]):
        self.occurrence_id = occurrence_id
        self.server_discord_id = server_discord_id
        self.server_options = {option.id: option for option in options}
        discord_options = []
        for option in options[:25]:
            description = option.description or "Participate in this server event"
            discord_options.append(
                discord.SelectOption(label=option.label[:100], description=description[:100], value=str(option.id))
            )
        super().__init__(
            placeholder="Choose how to participate...", min_values=1, max_values=1, options=discord_options
        )

    async def callback(self, interaction: discord.Interaction):
        option = self.server_options[int(self.values[0])]
        if option.requires_pooch_selection:
            pooches = await _list_owner_living_pooches(self.server_discord_id, interaction.user.id)
            if not pooches:
                await interaction.response.send_message("You do not have any living pooches to enter.", ephemeral=True)
                return
            await interaction.response.send_message(
                "Choose a pooch for your entry.",
                view=ServerEventPoochSelectView(self.occurrence_id, self.server_discord_id, option, pooches),
                ephemeral=True,
            )
            return

        success, message, _summary = await participate_in_server_event(
            self.occurrence_id,
            self.server_discord_id,
            interaction.user.id,
            option.id,
        )
        await interaction.response.send_message(message, ephemeral=True)
        if success:
            await refresh_public_server_event_message(interaction.client, self.server_discord_id, self.occurrence_id)


class ServerEventOptionSelectView(discord.ui.View):
    def __init__(self, occurrence_id: int, server_discord_id: int, options: list[ServerEventOption]):
        super().__init__(timeout=120)
        self.add_item(ServerEventOptionSelect(occurrence_id, server_discord_id, options))


class ServerEventParticipationView(discord.ui.View):
    def __init__(self, occurrence_id: int, server_discord_id: int):
        super().__init__(timeout=None)
        self.occurrence_id = occurrence_id
        self.server_discord_id = server_discord_id
        self.participate_button.custom_id = f"server-event-participate:{server_discord_id}:{occurrence_id}"

    @discord.ui.button(label="Participate", style=discord.ButtonStyle.primary, custom_id="server-event-participate")
    async def participate_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        event = await get_active_server_event(self.server_discord_id, interaction.user.id)
        if event is None or event.occurrence_id != self.occurrence_id:
            await interaction.response.send_message("This server event is no longer active.", ephemeral=True)
            return
        if event.viewer_participation is not None:
            await interaction.response.send_message(
                "You have already participated in this server event.", ephemeral=True
            )
            return
        if not event.options:
            await interaction.response.send_message(
                "This server event is not accepting participations.", ephemeral=True
            )
            return

        if len(event.options) == 1:
            option = event.options[0]
            if option.requires_pooch_selection:
                pooches = await _list_owner_living_pooches(self.server_discord_id, interaction.user.id)
                if not pooches:
                    await interaction.response.send_message(
                        "You do not have any living pooches to enter.", ephemeral=True
                    )
                    return
                await interaction.response.send_message(
                    "Choose a pooch for your entry.",
                    view=ServerEventPoochSelectView(self.occurrence_id, self.server_discord_id, option, pooches),
                    ephemeral=True,
                )
                return

            success, message, _summary = await participate_in_server_event(
                self.occurrence_id,
                self.server_discord_id,
                interaction.user.id,
                option.id,
            )
            await interaction.response.send_message(message, ephemeral=True)
            if success:
                await refresh_public_server_event_message(
                    interaction.client, self.server_discord_id, self.occurrence_id
                )
            return

        await interaction.response.send_message(
            "Choose how to participate.",
            view=ServerEventOptionSelectView(self.occurrence_id, self.server_discord_id, event.options),
            ephemeral=True,
        )


async def refresh_public_server_event_message(bot: discord.Client, server_discord_id: int, occurrence_id: int) -> None:
    event = await get_active_server_event(server_discord_id)
    if event is None or event.occurrence_id != occurrence_id or event.message_discord_id is None:
        return

    channel_id = await get_event_channel(server_discord_id)
    if channel_id is None:
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            return

    try:
        message = await channel.fetch_message(event.message_discord_id)
    except Exception:
        return

    await message.edit(
        embed=await build_server_event_embed(event, include_viewer_status=False),
        view=ServerEventParticipationView(event.occurrence_id, event.server_discord_id),
    )


async def register_active_server_event_views(bot: discord.Client) -> None:
    for event in await list_active_server_events():
        if event.message_discord_id is None:
            continue
        bot.add_view(
            ServerEventParticipationView(event.occurrence_id, event.server_discord_id),
            message_id=event.message_discord_id,
        )
