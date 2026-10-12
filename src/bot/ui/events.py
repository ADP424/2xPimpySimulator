from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import discord

from src.bot.constants import VIEW_TIMEOUT
from src.game import (
    describe_owner_event_result,
    get_breed_by_id,
    get_event_history,
    get_mutation_by_id,
    get_pending_event,
    get_pooch_by_id,
    respond_to_event,
)
from src.game.models.events import (
    OwnerEventContext,
    OwnerEventEntityReferences,
    OwnerEventHistory,
    OwnerEventOption,
    OwnerEventResult,
    TriggeredOwnerEvent,
    resolve_owner_event_entity_references,
)
from src.logger import get_logger

from .components import PaginatorView, build_breed_info_embed, build_mutation_info_embed
from .pooch_info import PoochInfoView
from .util import InteractionResponder, edit_interaction

logger = get_logger("bot/ui/events")

SEVERITY_COLORS: dict[str, discord.Color] = {
    "trivial": discord.Color.light_grey(),
    "moderate": discord.Color.blurple(),
    "major": discord.Color.orange(),
    "critical": discord.Color.red(),
}


ENTITY_KINDS: tuple[tuple[str, str], ...] = (
    ("pooches", "Pooches"),
    ("breeds", "Breeds"),
    ("mutations", "Mutations"),
)


def color_for_severity(severity: str) -> discord.Color:
    """
    Color for severity.

    Parameters
    ----------
    severity: Any
        The `severity` value.

    Returns
    -------
    Any
        The result of calling `color_for_severity`.
    """

    return SEVERITY_COLORS.get(severity.lower(), discord.Color.blurple())


def truncate(text: str, limit: int = 1024) -> str:
    """
    Truncate.

    Parameters
    ----------
    text: Any
        The `text` value.

    limit: Any
        The `limit` value.

    Returns
    -------
    Any
        The result of calling `truncate`.
    """

    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "..."


def discord_timestamp(value: datetime | str | None, style: str = "f") -> str:
    """
    Discord timestamp.

    Parameters
    ----------
    value: Any
        The `value` value.

    style: Any
        The `style` value.

    Returns
    -------
    Any
        The result of calling `discord_timestamp`.
    """

    if value is None:
        return "—"
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return f"<t:{int(value.timestamp())}:{style}>"


def format_option_line(option: OwnerEventOption) -> str:
    """
    Format option line.

    Parameters
    ----------
    option: Any
        The `option` value.

    Returns
    -------
    Any
        The result of calling `format_option_line`.
    """

    requirements: list[str] = []
    if option.min_money > 0:
        requirements.append(f"${option.min_money}")
    if option.min_bloodskulls > 0:
        requirements.append(f"{option.min_bloodskulls} bloodskulls")

    description = option.description or ""
    line = f"**{option.label}**"
    if description:
        line += f" — {description}"
    if requirements:
        line += f" _(requires {' + '.join(requirements)})_"
    return line


def format_option_select_description(option: OwnerEventOption) -> str:
    """
    Format option select description.

    Parameters
    ----------
    option: Any
        The `option` value.

    Returns
    -------
    Any
        The result of calling `format_option_select_description`.
    """

    # Full descriptions live in the embed's "Response Options" field (no char limit there).
    # The select description is limited to 100 chars, so only show cost requirements here.
    costs: list[str] = []
    if option.min_money > 0:
        costs.append(f"${option.min_money}")
    if option.min_bloodskulls > 0:
        costs.append(f"{option.min_bloodskulls} skulls")
    return truncate("Req: " + ", ".join(costs) if costs else "See details above.", 100)


def detail_entries(bucket: Any, *, id_key: str, value_key: str) -> list[dict[str, Any]]:
    """
    Detail entries.

    Parameters
    ----------
    bucket: Any
        The `bucket` value.

    id_key: Any
        The `id_key` value.

    value_key: Any
        The `value_key` value.

    Returns
    -------
    Any
        The result of calling `detail_entries`.
    """

    if isinstance(bucket, list):
        return [entry for entry in bucket if isinstance(entry, dict)]
    if isinstance(bucket, dict):
        rows: list[dict[str, Any]] = []
        for raw_id, raw_value in bucket.items():
            try:
                rows.append({id_key: raw_id, value_key: raw_value})
            except TypeError, ValueError:
                continue
        return rows
    return []


def signed(value: int) -> str:
    """
    Signed.

    Parameters
    ----------
    value: Any
        The `value` value.

    Returns
    -------
    Any
        The result of calling `signed`.
    """

    return f"{value:+d}"


def entity_reference_lines(context: OwnerEventContext, entity_references: OwnerEventEntityReferences) -> list[str]:
    """
    Entity reference lines.

    Parameters
    ----------
    context: Any
        The `context` value.

    entity_references: Any
        The `entity_references` value.

    Returns
    -------
    Any
        The result of calling `entity_reference_lines`.
    """

    lines: list[str] = []

    for kind, title in ENTITY_KINDS:
        items = entity_references.for_kind(kind)[:8]
        if not items:
            continue

        names = ", ".join(reference.label for reference in items)
        total_items = len(entity_references.for_kind(kind))
        if total_items > 8:
            names += f", +{total_items - 8} more"
        lines.append(f"**{title}:** {names}")

    kennel_bits: list[str] = []
    if context.selected_kennel_id is not None:
        kennel_bits.append(f"Kennel #{context.selected_kennel_id}")
    for kennel_id in context.affected_kennel_ids:
        label = f"Kennel #{kennel_id}"
        if label not in kennel_bits:
            kennel_bits.append(label)
    if kennel_bits:
        lines.append(
            f"**Kennels:** {', '.join(kennel_bits[:8])}"
            + (f", +{len(kennel_bits) - 8} more" if len(kennel_bits) > 8 else "")
        )

    return lines


def format_result_summary(
    result: Optional[OwnerEventResult],
    entity_references: Optional[OwnerEventEntityReferences] = None,
) -> str:
    """
    Format result summary.

    Parameters
    ----------
    result: Any
        The `result` value.

    entity_references: Any
        The `entity_references` value.

    Returns
    -------
    Any
        The result of calling `format_result_summary`.
    """

    description = describe_owner_event_result(result, entity_references)
    lines = ([f"*{description.headline}*"] if description.headline else []) + description.lines
    return truncate("\n".join(lines) if lines else "No recorded outcome.")


def _featured_pooch_name(event: TriggeredOwnerEvent) -> str | None:
    """Return the name of the featured pooch for this event, if any."""
    pooch_id = event.featured_pooch_id
    if pooch_id is None:
        return None
    for ref in event.entity_references.pooches:
        if ref.id == pooch_id:
            return ref.label
    return f"Pooch #{pooch_id}"


def build_triggered_event_embed(event: TriggeredOwnerEvent) -> discord.Embed:
    """
    Build triggered event embed.

    Parameters
    ----------
    event: Any
        The `event` value.

    Returns
    -------
    Any
        The result of calling `build_triggered_event_embed`.
    """

    description_parts = [event.description or "No description provided."]
    if event.flavor_text:
        description_parts.append(f"*{event.flavor_text.strip()}*")
    featured = _featured_pooch_name(event)
    if featured:
        description_parts.append(f"**Pooch: {featured}**")
    embed = discord.Embed(
        title=f"🎲 {event.name}",
        description="\n".join(description_parts),
        color=color_for_severity(event.severity),
    )

    details = [
        f"**Category:** {event.category.title()}",
        f"**Severity:** {event.severity.title()}",
    ]
    if event.requires_response and event.expires_at is not None:
        details.append(
            f"**Expires:** {discord_timestamp(event.expires_at, 'R')} ({discord_timestamp(event.expires_at)})"
        )
    embed.add_field(name="Details", value="\n".join(details), inline=False)

    entity_lines = entity_reference_lines(event.context, event.entity_references)
    if entity_lines:
        embed.add_field(name="Related", value=truncate("\n".join(entity_lines)), inline=False)

    if event.requires_response and event.options:
        options_value = "\n".join(format_option_line(option) for option in event.options)
        embed.add_field(name="Response Options", value=truncate(options_value), inline=False)
        embed.set_footer(text="Choose an option from the menu below.")
    elif event.result is not None:
        embed.add_field(
            name="Outcome", value=format_result_summary(event.result, event.entity_references), inline=False
        )
        embed.set_footer(text="This event resolved automatically.")

    return embed


def build_resolved_event_embed(
    event: TriggeredOwnerEvent,
    *,
    result: Optional[OwnerEventResult],
    selected_option_label: Optional[str] = None,
    status_text: str = "Resolved",
) -> discord.Embed:
    """
    Build resolved event embed.

    Parameters
    ----------
    event: Any
        The `event` value.

    result: Any
        The `result` value.

    selected_option_label: Any
        The `selected_option_label` value.

    status_text: Any
        The `status_text` value.

    Returns
    -------
    Any
        The result of calling `build_resolved_event_embed`.
    """

    embed = build_triggered_event_embed(event)
    if selected_option_label:
        embed.add_field(name="Selected Option", value=selected_option_label, inline=False)
    embed.add_field(name="Outcome", value=format_result_summary(result, event.entity_references), inline=False)
    embed.set_footer(text=status_text)
    return embed


def build_history_embed(record: OwnerEventHistory, page_index: int, page_count: int) -> discord.Embed:
    """
    Build history embed.

    Parameters
    ----------
    record: Any
        The `record` value.

    page_index: Any
        The `page_index` value.

    page_count: Any
        The `page_count` value.

    Returns
    -------
    Any
        The result of calling `build_history_embed`.
    """

    history_description_parts = [record.description or "No description provided."]
    if record.flavor_text:
        history_description_parts.append(f"*{record.flavor_text.strip()}*")
    embed = discord.Embed(
        title=f"📜 {record.name}",
        description="\n".join(history_description_parts),
        color=color_for_severity(record.severity),
    )

    details = [
        f"**Category:** {record.category.title()}",
        f"**Severity:** {record.severity.title()}",
        f"**Triggered:** {discord_timestamp(record.triggered_at)}",
    ]
    completed_at = record.completed_at
    if completed_at:
        details.append(f"**Completed:** {discord_timestamp(completed_at)}")

    if record.timed_out:
        details.append("**Status:** Timed out")
    elif record.selected_option_label:
        details.append(f"**Selected:** {record.selected_option_label}")
    else:
        details.append("**Status:** Auto-resolved")

    embed.add_field(name="Details", value="\n".join(details), inline=False)

    entity_lines = entity_reference_lines(record.context, record.entity_references)
    if entity_lines:
        embed.add_field(name="Related", value=truncate("\n".join(entity_lines)), inline=False)

    embed.add_field(
        name="Outcome", value=format_result_summary(record.result_summary, record.entity_references), inline=False
    )
    embed.set_footer(text=f"History entry {page_index + 1}/{page_count}")
    return embed


async def _build_pooch_embed_from_id(
    pooch_id: int, fallback_label: str
) -> tuple[discord.Embed, Optional[PoochInfoView]]:
    try:
        pooch = await get_pooch_by_id(pooch_id)
    except Exception:
        pooch = None

    if pooch is None:
        return discord.Embed(title=fallback_label, description="That pooch could not be found."), None

    view = PoochInfoView(server=None, pooch=pooch, owner=None)
    embed = await view.build_embed()
    return embed, view


class EventEntityControls:
    def __init__(self, owner_discord_id: int, entity_references: OwnerEventEntityReferences):
        self.owner_discord_id = owner_discord_id
        self.entity_references = entity_references
        self.selected_kind: Optional[str] = None
        self.selected_id: Optional[int] = None
        self.selected_label: Optional[str] = None
        self.selects: dict[str, discord.ui.Select] = {}
        self.info_button = discord.ui.Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.info_button.callback = self._on_info

        for kind, title in ENTITY_KINDS:
            items = self.entity_references.for_kind(kind)
            if not items:
                continue
            select = discord.ui.Select(
                placeholder=f"Select {title.lower()}",
                options=[
                    discord.SelectOption(
                        label=truncate(item.label, 100),
                        value=str(item.id),
                    )
                    for item in items[:25]
                ],
                min_values=1,
                max_values=1,
            )
            select.callback = self._make_select_callback(kind)
            self.selects[kind] = select

    def attach(self, view: discord.ui.View, row_start: int) -> None:
        row = row_start
        for kind, _title in ENTITY_KINDS:
            select = self.selects.get(kind)
            if select is None:
                continue
            select.row = row
            row += 1
            view.add_item(select)
        if self.selects:
            self.info_button.row = min(row, 4)
            view.add_item(self.info_button)

    def _make_select_callback(self, kind: str):
        async def callback(interaction: discord.Interaction):
            value = self.selects[kind].values[0]
            self.selected_kind = kind
            self.selected_id = int(value)
            self.selected_label = next(
                (item.label for item in self.entity_references.for_kind(kind) if item.id == self.selected_id),
                f"{kind[:-1].title()} #{value}",
            )
            self.info_button.disabled = False
            for other_kind, select in self.selects.items():
                for option in select.options:
                    option.default = other_kind == kind and option.value == value
            await edit_interaction(interaction, view=self.selects[kind].view)

        return callback

    async def _on_info(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self.selected_kind is None or self.selected_id is None:
            return

        if self.selected_kind == "pooches":
            embed, pooch_view = await _build_pooch_embed_from_id(
                self.selected_id, self.selected_label or f"Pooch #{self.selected_id}"
            )
            if pooch_view is not None:
                await r.reply(embed=embed, view=pooch_view)
            else:
                await r.reply(embed=embed)
        elif self.selected_kind == "breeds":
            breed = await get_breed_by_id(self.selected_id)
            if breed is None:
                embed = discord.Embed(
                    title=self.selected_label or f"Breed #{self.selected_id}",
                    description="That breed could not be found.",
                )
            else:
                embed = build_breed_info_embed(breed)
            await r.reply(embed=embed)
        else:
            mutation = await get_mutation_by_id(self.selected_id)
            if mutation is None:
                embed = discord.Embed(
                    title=self.selected_label or f"Mutation #{self.selected_id}",
                    description="That mutation could not be found.",
                )
            else:
                embed = build_mutation_info_embed(mutation)
            await r.reply(embed=embed)


class EventHistoryPageSource:
    def __init__(self, records: list[OwnerEventHistory], owner_discord_id: int):
        self._records = records
        self._owner_discord_id = owner_discord_id

    async def load(self):
        return None

    def page_count(self) -> int:
        return max(len(self._records), 1)

    async def render(self, view: discord.ui.View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._records:
            embed = discord.Embed(title="📜 Event History", description="No event history found yet.")
            return None, embed

        record = self._records[page_index]

        controls = EventEntityControls(self._owner_discord_id, record.entity_references)
        controls.attach(view, row_start=1)
        return None, build_history_embed(record, page_index, len(self._records))


class EventResponseSelect(discord.ui.Select):
    def __init__(self, owner_discord_id: int, event: TriggeredOwnerEvent):
        options = [
            discord.SelectOption(
                label=truncate(option.label, 100),
                value=str(option.id),
                description=format_option_select_description(option),
            )
            for option in event.options[:25]
        ]
        super().__init__(placeholder="Choose how to respond", min_values=1, max_values=1, options=options, row=0)
        self.owner_discord_id = owner_discord_id
        self.event = event

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_discord_id:
            await interaction.response.send_message("This event is not yours.", ephemeral=True)
            return

        option_id = int(self.values[0])
        option = next((item for item in self.event.options if item.id == option_id), None)
        success, message, result = await respond_to_event(
            interaction.user.id, self.event.active_owner_event_id, option_id
        )

        if success:
            if self.view is not None:
                self.view.stop()
            self.event.result = result
            self.event.entity_references = await resolve_owner_event_entity_references(
                self.event.context, result, existing=self.event.entity_references
            )
            embed = build_resolved_event_embed(
                self.event,
                result=result,
                selected_option_label=option.label if option is not None else None,
                status_text="Response recorded.",
            )
            next_view = EventMessageView(self.owner_discord_id, self.event, response_enabled=False)
            await interaction.response.edit_message(embed=embed, view=next_view)
            for entry in (result.extra_data or {}).get("started_events", []):
                followup = await get_pending_event(self.owner_discord_id, entry.get("active_owner_event_id"))
                if followup is not None:
                    await send_triggered_event_dm(interaction.client, self.owner_discord_id, followup)
            return

        terminal_messages = {
            "This event has expired.",
            "You have already responded to this event.",
            "Event not found.",
        }
        if message in terminal_messages:
            if self.view is not None:
                self.view.stop()
            self.event.result = result
            self.event.entity_references = await resolve_owner_event_entity_references(
                self.event.context, result, existing=self.event.entity_references
            )
            embed = build_resolved_event_embed(self.event, result=result, status_text=message)
            next_view = EventMessageView(self.owner_discord_id, self.event, response_enabled=False)
            await interaction.response.edit_message(embed=embed, view=next_view)
            return

        await interaction.response.send_message(message, ephemeral=True)


class EventMessageView(discord.ui.View):
    def __init__(self, owner_discord_id: int, event: TriggeredOwnerEvent, *, response_enabled: bool):
        timeout: Optional[float]
        if response_enabled and event.expires_at is not None:
            remaining = (event.expires_at - datetime.now(timezone.utc)).total_seconds()
            timeout = max(1.0, remaining)
        else:
            timeout = VIEW_TIMEOUT

        super().__init__(timeout=timeout)
        self.owner_discord_id = owner_discord_id
        self.event = event
        self.response_enabled = response_enabled and event.requires_response and bool(event.options)
        self.message: Optional[discord.Message] = None

        if self.response_enabled:
            self.add_item(EventResponseSelect(owner_discord_id, event))
            controls = EventEntityControls(owner_discord_id, event.entity_references)
            controls.attach(self, row_start=1)
        else:
            controls = EventEntityControls(owner_discord_id, event.entity_references)
            controls.attach(self, row_start=0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_discord_id:
            await interaction.response.send_message("This event is not yours.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        if not self.response_enabled or self.message is None:
            return
        try:
            replacement = EventMessageView(self.owner_discord_id, self.event, response_enabled=False)
            embed = build_resolved_event_embed(
                self.event, result=self.event.result, status_text="This event is no longer interactive."
            )
            await self.message.edit(embed=embed, view=replacement)
        except Exception:
            return


async def get_dm_channel(bot: discord.Client, user_id: int) -> Optional[discord.DMChannel]:
    """
    Get dm channel.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    user_id: Any
        The `user_id` value.

    Returns
    -------
    Any
        The result of calling `get_dm_channel`.
    """

    user = bot.get_user(user_id)
    if user is None:
        try:
            user = await bot.fetch_user(user_id)
        except Exception as exc:
            logger.warning("Could not fetch user %s for DM: %s", user_id, exc)
            return None

    try:
        dm_channel = user.dm_channel or await user.create_dm()
    except Exception as exc:
        logger.warning("Could not open DM channel for user %s: %s", user_id, exc)
        return None

    if not isinstance(dm_channel, discord.DMChannel):
        return None
    return dm_channel


async def send_triggered_event_dm(bot: discord.Client, owner_discord_id: int, event: TriggeredOwnerEvent) -> bool:
    """
    Send triggered event dm.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    owner_discord_id: Any
        The `owner_discord_id` value.

    event: Any
        The `event` value.

    Returns
    -------
    Any
        The result of calling `send_triggered_event_dm`.
    """

    dm_channel = await get_dm_channel(bot, owner_discord_id)
    if dm_channel is None:
        logger.warning("No DM channel available for owner %s.", owner_discord_id)
        return False

    embed = build_triggered_event_embed(event)
    if event.requires_response:
        view = EventMessageView(owner_discord_id, event, response_enabled=True)
        try:
            message = await dm_channel.send(embed=embed, view=view)
        except Exception as exc:
            logger.warning("Failed to send event DM to owner %s: %s", owner_discord_id, exc)
            return False
        view.message = message
        return True

    view = EventMessageView(owner_discord_id, event, response_enabled=False)
    try:
        await dm_channel.send(embed=embed, view=view)
    except Exception as exc:
        logger.warning("Failed to send event DM to owner %s: %s", owner_discord_id, exc)
        return False
    return True


async def send_all_pending_event_dms(
    bot: discord.Client, owner_discord_id: int, events: list[TriggeredOwnerEvent]
) -> tuple[int, int]:
    """
    Send all pending event dms.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    owner_discord_id: Any
        The `owner_discord_id` value.

    events: Any
        The `events` value.

    Returns
    -------
    Any
        The result of calling `send_all_pending_event_dms`.
    """

    sent = 0
    failed = 0
    for event in events:
        if await send_triggered_event_dm(bot, owner_discord_id, event):
            sent += 1
        else:
            failed += 1
    return sent, failed


async def send_event_history_dm(bot: discord.Client, owner_discord_id: int, limit: int = 25) -> bool:
    """
    Send event history dm.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    owner_discord_id: Any
        The `owner_discord_id` value.

    limit: Any
        The `limit` value.

    Returns
    -------
    Any
        The result of calling `send_event_history_dm`.
    """

    records = await get_event_history(owner_discord_id, limit=limit)
    if not records:
        return False

    dm_channel = await get_dm_channel(bot, owner_discord_id)
    if dm_channel is None:
        return False

    source = EventHistoryPageSource(records, owner_discord_id)
    view = PaginatorView(source, owner_discord_id=owner_discord_id)
    content, embed = await view.build_first_page()
    send_kwargs: dict[str, Any] = {"view": view}
    if content is not None:
        send_kwargs["content"] = content
    if embed is not None:
        send_kwargs["embed"] = embed
    try:
        await dm_channel.send(**send_kwargs)
    except Exception:
        return False
    return True
