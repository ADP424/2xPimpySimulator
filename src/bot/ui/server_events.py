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
    ServerEventResolution,
    TriggeredServerEvent,
)
from src.game.models.events.server_events import ServerEventMenu, ServerEventMenuOption

SEVERITY_COLORS: dict[str, discord.Color] = {
    "trivial": discord.Color.light_grey(),
    "minor": discord.Color.light_grey(),
    "moderate": discord.Color.blurple(),
    "major": discord.Color.orange(),
    "critical": discord.Color.red(),
}


def _color_for_severity(severity: str) -> discord.Color:
    return SEVERITY_COLORS.get(severity.lower(), discord.Color.blurple())


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


def _get_used_menu_names(event: TriggeredServerEvent) -> set[str]:
    """Return menu names already submitted by the viewer."""
    if event.viewer_participation is None:
        return set()
    return {str(sub.get("menu_name", "")) for sub in (event.viewer_participation.submissions or [])}


def _get_use_count_per_menu(event: TriggeredServerEvent) -> dict[str, int]:
    """Return a count of how many times each menu has been used by the viewer."""
    counts: dict[str, int] = {}
    if event.viewer_participation is not None:
        for sub in event.viewer_participation.submissions or []:
            name = str(sub.get("menu_name", ""))
            counts[name] = counts.get(name, 0) + 1
    return counts


def _menu_is_available(menu: ServerEventMenu, used_names: set[str], use_counts: dict[str, int]) -> bool:
    """Return True if the viewer can currently use this menu."""
    # depends_on: all prerequisite menu names must have been used
    for req in menu.depends_on:
        if req not in used_names:
            return False
    # max_uses_per_player: -1 = unlimited
    if menu.max_uses_per_player >= 0:
        if use_counts.get(menu.name, 0) >= menu.max_uses_per_player:
            return False
    return True


def _format_menu_line(menu: ServerEventMenu, available: bool, uses_left: int | None) -> str:
    status = "✅" if available else "🔒"
    line = f"{status} **{menu.label}**"
    if menu.description:
        line += f" — {menu.description}"
    if menu.depends_on:
        line += f" _(requires: {', '.join(menu.depends_on)})_"
    if uses_left is not None and uses_left >= 0:
        line += f" _(uses left: {uses_left})_"
    if menu.options:
        for opt in menu.options:
            req_parts: list[str] = []
            if opt.requires.get("pooch"):
                req_parts.append("a pooch")
            opt_line = f"  • **{opt.label}**"
            if opt.description:
                opt_line += f" — {opt.description}"
            if req_parts:
                opt_line += f" _(requires {' + '.join(req_parts)})_"
            line += f"\n{opt_line}"
    return line


def _format_participation_status(event: TriggeredServerEvent) -> str:
    if event.viewer_participation is None:
        return "You have not participated yet."

    participation = event.viewer_participation
    submissions = list(participation.submissions or [])
    if not submissions:
        return "You have participated."

    lines: list[str] = []
    for sub in submissions:
        menu_name = sub.get("menu_name", "?")
        option_label = sub.get("option_label", "?")
        lines.append(f"**{menu_name}**: {option_label}")
        pid = sub.get("selected_pooch_id")
        if pid is not None:
            pooch_label = next(
                (ref.label for ref in participation.entity_references.pooches if ref.id == pid),
                f"Pooch #{pid}",
            )
            lines.append(f"  Pooch: **{pooch_label}**")
        sub_result = sub.get("immediate_result") or {}
        msg = sub_result.get("message") if isinstance(sub_result, dict) else None
        if msg:
            lines.append(f"  {msg}")

    if participation.rank is not None:
        lines.append(f"Rank: **#{participation.rank}**")
    if participation.resolution_result and participation.resolution_result.message:
        lines.append(participation.resolution_result.message)

    return "\n".join(lines)


async def build_server_event_embed(event: TriggeredServerEvent, include_viewer_status: bool = True) -> discord.Embed:
    embed = discord.Embed(
        title=event.name,
        description=event.description,
        color=_color_for_severity(event.severity),
    )
    embed.add_field(name="Category", value=event.category, inline=True)
    embed.add_field(name="Ends", value=_discord_timestamp(event.expires_at), inline=True)
    embed.add_field(name="Participants", value=str(event.participation_count), inline=True)

    if event.flavor_text:
        embed.add_field(name="Flavor", value=_truncate(event.flavor_text), inline=False)

    if event.menus:
        used_names = _get_used_menu_names(event)
        use_counts = _get_use_count_per_menu(event)
        menu_lines: list[str] = []
        for menu in event.menus:
            available = _menu_is_available(menu, used_names, use_counts)
            uses_left: int | None = None
            if menu.max_uses_per_player >= 0:
                uses_left = menu.max_uses_per_player - use_counts.get(menu.name, 0)
            menu_lines.append(_format_menu_line(menu, available, uses_left))
        embed.add_field(
            name="How to participate",
            value=_truncate("\n".join(menu_lines)),
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


# ---------------------------------------------------------------------------
# Per-menu pooch selection
# ---------------------------------------------------------------------------


class ServerEventPoochSelect(discord.ui.Select):
    def __init__(
        self,
        occurrence_id: int,
        server_discord_id: int,
        menu_option: ServerEventMenuOption,
        pooches: list[Pooch],
    ):
        self.occurrence_id = occurrence_id
        self.server_discord_id = server_discord_id
        self.menu_option = menu_option
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
            self.menu_option.id,
            selected_pooch_id=pooch_id,
        )
        if not success:
            await interaction.response.send_message(message, ephemeral=True)
            return
        await interaction.response.send_message(message, ephemeral=True)
        await refresh_public_server_event_message(interaction.client, self.server_discord_id, self.occurrence_id)


class ServerEventPoochSelectView(discord.ui.View):
    def __init__(
        self,
        occurrence_id: int,
        server_discord_id: int,
        menu_option: ServerEventMenuOption,
        pooches: list[Pooch],
    ):
        super().__init__(timeout=120)
        self.add_item(ServerEventPoochSelect(occurrence_id, server_discord_id, menu_option, pooches))


# ---------------------------------------------------------------------------
# Per-menu option selection
# ---------------------------------------------------------------------------


class ServerEventMenuOptionSelect(discord.ui.Select):
    """Dropdown to pick which option to use within a given menu."""

    def __init__(
        self,
        occurrence_id: int,
        server_discord_id: int,
        menu: ServerEventMenu,
    ):
        self.occurrence_id = occurrence_id
        self.server_discord_id = server_discord_id
        self.menu = menu
        self._option_map = {str(opt.id): opt for opt in menu.options}
        discord_options = [
            discord.SelectOption(
                label=opt.label[:100],
                description=(opt.description or "")[:100],
                value=str(opt.id),
            )
            for opt in menu.options[:25]
        ]
        super().__init__(
            placeholder=f"Choose an option for '{menu.label}'...",
            min_values=1,
            max_values=1,
            options=discord_options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_opt = self._option_map[self.values[0]]

        if selected_opt.requires.get("pooch"):
            pooches = await _list_owner_living_pooches(self.server_discord_id, interaction.user.id)
            if not pooches:
                await interaction.response.send_message("You do not have any living pooches to enter.", ephemeral=True)
                return
            await interaction.response.send_message(
                "Choose a pooch for your entry.",
                view=ServerEventPoochSelectView(self.occurrence_id, self.server_discord_id, selected_opt, pooches),
                ephemeral=True,
            )
            return

        success, message, _summary = await participate_in_server_event(
            self.occurrence_id,
            self.server_discord_id,
            interaction.user.id,
            selected_opt.id,
        )
        await interaction.response.send_message(message, ephemeral=True)
        if success:
            await refresh_public_server_event_message(interaction.client, self.server_discord_id, self.occurrence_id)


class ServerEventMenuOptionSelectView(discord.ui.View):
    def __init__(self, occurrence_id: int, server_discord_id: int, menu: ServerEventMenu):
        super().__init__(timeout=120)
        self.add_item(ServerEventMenuOptionSelect(occurrence_id, server_discord_id, menu))


# ---------------------------------------------------------------------------
# Menu selection (if multiple menus are available)
# ---------------------------------------------------------------------------


class ServerEventMenuSelect(discord.ui.Select):
    """Dropdown to pick which menu to use when multiple menus are available."""

    def __init__(
        self,
        occurrence_id: int,
        server_discord_id: int,
        available_menus: list[ServerEventMenu],
    ):
        self.occurrence_id = occurrence_id
        self.server_discord_id = server_discord_id
        self._menu_map = {str(m.id): m for m in available_menus}
        discord_options = [
            discord.SelectOption(
                label=m.label[:100],
                description=(m.description or "")[:100],
                value=str(m.id),
            )
            for m in available_menus[:25]
        ]
        super().__init__(
            placeholder="Choose a menu to use...",
            min_values=1,
            max_values=1,
            options=discord_options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_menu = self._menu_map[self.values[0]]

        if len(selected_menu.options) == 1:
            single_opt = selected_menu.options[0]
            if single_opt.requires.get("pooch"):
                pooches = await _list_owner_living_pooches(self.server_discord_id, interaction.user.id)
                if not pooches:
                    await interaction.response.send_message(
                        "You do not have any living pooches to enter.", ephemeral=True
                    )
                    return
                await interaction.response.send_message(
                    "Choose a pooch for your entry.",
                    view=ServerEventPoochSelectView(self.occurrence_id, self.server_discord_id, single_opt, pooches),
                    ephemeral=True,
                )
                return
            success, message, _summary = await participate_in_server_event(
                self.occurrence_id,
                self.server_discord_id,
                interaction.user.id,
                single_opt.id,
            )
            await interaction.response.send_message(message, ephemeral=True)
            if success:
                await refresh_public_server_event_message(
                    interaction.client, self.server_discord_id, self.occurrence_id
                )
            return

        await interaction.response.send_message(
            f"Choose an option for **{selected_menu.label}**.",
            view=ServerEventMenuOptionSelectView(self.occurrence_id, self.server_discord_id, selected_menu),
            ephemeral=True,
        )


class ServerEventMenuSelectView(discord.ui.View):
    def __init__(self, occurrence_id: int, server_discord_id: int, available_menus: list[ServerEventMenu]):
        super().__init__(timeout=120)
        self.add_item(ServerEventMenuSelect(occurrence_id, server_discord_id, available_menus))


# ---------------------------------------------------------------------------
# Main participation view (persistent)
# ---------------------------------------------------------------------------


class ServerEventParticipationView(discord.ui.View):
    def __init__(self, occurrence_id: int, server_discord_id: int, has_menus: bool = True):
        super().__init__(timeout=None)
        self.occurrence_id = occurrence_id
        self.server_discord_id = server_discord_id
        if has_menus:
            self.participate_button.custom_id = f"server-event-participate:{server_discord_id}:{occurrence_id}"
        else:
            self.remove_item(self.participate_button)

    @discord.ui.button(label="Participate", style=discord.ButtonStyle.primary, custom_id="server-event-participate")
    async def participate_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        event = await get_active_server_event(self.server_discord_id, interaction.user.id)
        if event is None or event.occurrence_id != self.occurrence_id:
            await interaction.response.send_message("This server event is no longer active.", ephemeral=True)
            return

        if not event.menus:
            await interaction.response.send_message(
                "This server event is not accepting participations.", ephemeral=True
            )
            return

        # Determine which menus are currently available to this player
        used_names = _get_used_menu_names(event)
        use_counts = _get_use_count_per_menu(event)
        available_menus = [m for m in event.menus if _menu_is_available(m, used_names, use_counts)]

        if not available_menus:
            await interaction.response.send_message("There are no menus available to you right now.", ephemeral=True)
            return

        if len(available_menus) == 1:
            selected_menu = available_menus[0]

            if len(selected_menu.options) == 1:
                single_opt = selected_menu.options[0]
                if single_opt.requires.get("pooch"):
                    pooches = await _list_owner_living_pooches(self.server_discord_id, interaction.user.id)
                    if not pooches:
                        await interaction.response.send_message(
                            "You do not have any living pooches to enter.", ephemeral=True
                        )
                        return
                    await interaction.response.send_message(
                        "Choose a pooch for your entry.",
                        view=ServerEventPoochSelectView(
                            self.occurrence_id, self.server_discord_id, single_opt, pooches
                        ),
                        ephemeral=True,
                    )
                    return
                success, message, _summary = await participate_in_server_event(
                    self.occurrence_id,
                    self.server_discord_id,
                    interaction.user.id,
                    single_opt.id,
                )
                await interaction.response.send_message(message, ephemeral=True)
                if success:
                    await refresh_public_server_event_message(
                        interaction.client, self.server_discord_id, self.occurrence_id
                    )
                return

            await interaction.response.send_message(
                f"Choose an option for **{selected_menu.label}**.",
                view=ServerEventMenuOptionSelectView(self.occurrence_id, self.server_discord_id, selected_menu),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Choose a menu to use.",
            view=ServerEventMenuSelectView(self.occurrence_id, self.server_discord_id, available_menus),
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
        view=ServerEventParticipationView(event.occurrence_id, event.server_discord_id, has_menus=bool(event.menus)),
    )


async def register_active_server_event_views(bot: discord.Client) -> None:
    for event in await list_active_server_events():
        if event.message_discord_id is None:
            continue
        bot.add_view(
            ServerEventParticipationView(event.occurrence_id, event.server_discord_id, has_menus=bool(event.menus)),
            message_id=event.message_discord_id,
        )
