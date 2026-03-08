from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import discord

from bot.constants import VIEW_TIMEOUT
from game import (
    get_breed_by_id,
    get_event_history,
    get_mutation_by_id,
    get_pooch_by_id,
    respond_to_event,
)
from game.models import Pooch
from game.models.events import EventResult, TriggeredEvent

from .components import PaginatorView, build_breed_info_embed, build_mutation_info_embed
from .util import InteractionResponder, edit_interaction

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


def _color_for_severity(severity: str) -> discord.Color:
    return SEVERITY_COLORS.get(str(severity).lower(), discord.Color.blurple())


def _truncate(text: str, limit: int = 1024) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "..."


def _discord_timestamp(value: datetime | str | None, style: str = "f") -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return f"<t:{int(value.timestamp())}:{style}>"


def _format_option_line(option: dict[str, Any]) -> str:
    requirements: list[str] = []
    if option.get("min_money", 0) > 0:
        requirements.append(f"${int(option['min_money'])}")
    if option.get("min_bloodskulls", 0) > 0:
        requirements.append(f"{int(option['min_bloodskulls'])} bloodskulls")

    description = option.get("description") or ""
    line = f"**{option['label']}**"
    if description:
        line += f" — {description}"
    if requirements:
        line += f" _(requires {' + '.join(requirements)})_"
    return line


def _format_option_select_description(option: dict[str, Any]) -> str:
    lines: list[str] = []
    if option.get("description"):
        lines.append(str(option["description"]))
    costs: list[str] = []
    if option.get("min_money", 0) > 0:
        costs.append(f"${int(option['min_money'])}")
    if option.get("min_bloodskulls", 0) > 0:
        costs.append(f"{int(option['min_bloodskulls'])} skulls")
    if costs:
        lines.append("Req: " + ", ".join(costs))
    return _truncate("\n".join(lines) if lines else "No description.")


def _detail_entries(bucket: Any, *, id_key: str, value_key: str) -> list[dict[str, Any]]:
    if isinstance(bucket, list):
        return [entry for entry in bucket if isinstance(entry, dict)]
    if isinstance(bucket, dict):
        rows: list[dict[str, Any]] = []
        for raw_id, raw_value in bucket.items():
            try:
                rows.append({id_key: int(raw_id), value_key: raw_value})
            except TypeError, ValueError:
                continue
        return rows
    return []


def _signed(value: int) -> str:
    return f"{value:+d}"


def _entity_reference_lines(entity_references: dict[str, list[dict[str, Any]]]) -> list[str]:
    lines: list[str] = []
    for key, title in ENTITY_KINDS:
        items = entity_references.get(key) or []
        if not items:
            continue
        names = ", ".join(str(item.get("label") or item.get("name") or item.get("id")) for item in items[:8])
        if len(items) > 8:
            names += f", +{len(items) - 8} more"
        lines.append(f"**{title}:** {names}")
    return lines


def _format_result_summary(result: Optional[EventResult]) -> str:
    if result is None:
        return "No recorded outcome."

    extra_data = result.extra_data or {}
    selected_outcome = (
        extra_data.get("selected_outcome") if isinstance(extra_data.get("selected_outcome"), dict) else None
    )

    lines: list[str] = []
    if result.message:
        lines.append(result.message)
    elif selected_outcome is not None:
        fallback_message = (
            selected_outcome.get("message") or selected_outcome.get("description") or selected_outcome.get("label")
        )
        if fallback_message:
            lines.append(str(fallback_message))
    if selected_outcome and selected_outcome.get("label") and not result.message:
        lines.append(f"Outcome: {selected_outcome['label']}")
    if result.money_changed:
        lines.append(f"Dollars: {result.money_changed:+d}")
    if result.bloodskulls_changed:
        lines.append(f"Bloodskulls: {result.bloodskulls_changed:+d}")

    for entry in extra_data.get("created_pooches", []):
        if not isinstance(entry, dict):
            continue
        pooch_label = entry.get("pooch_name") or f"Pooch #{entry.get('pooch_id', '?')}"
        text = f"Created pooch: {pooch_label}"
        sex = entry.get("sex")
        age = entry.get("age")
        kennel_name = entry.get("kennel_name")
        extras: list[str] = []
        if sex:
            extras.append(str(sex).capitalize())
        if age is not None:
            extras.append(f"age {age}")
        if kennel_name:
            extras.append(f"kennel {kennel_name}")
        if extras:
            text += f" ({', '.join(extras)})"
        lines.append(text)
    if result.pooches_created and not extra_data.get("created_pooches"):
        lines.append(f"Pooches created: {len(result.pooches_created)}")

    for entry in _detail_entries(extra_data.get("health_changes"), id_key="pooch_id", value_key="amount"):
        name = entry.get("pooch_name") or f"Pooch #{entry.get('pooch_id', '?')}"
        amount = int(entry.get("amount", 0))
        suffix = f" (base now {entry['new_base_health']})" if entry.get("new_base_health") is not None else ""
        lines.append(f"Health: {name} {_signed(amount)}{suffix}")

    for entry in _detail_entries(extra_data.get("age_changes"), id_key="pooch_id", value_key="amount"):
        name = entry.get("pooch_name") or f"Pooch #{entry.get('pooch_id', '?')}"
        amount = int(entry.get("amount", 0))
        suffix = f" (now age {entry['new_age']})" if entry.get("new_age") is not None else ""
        lines.append(f"Age: {name} {_signed(amount)}{suffix}")

    for entry in extra_data.get("breeding_cooldown_changes", []):
        if not isinstance(entry, dict):
            continue
        name = entry.get("pooch_name") or f"Pooch #{entry.get('pooch_id', '?')}"
        lines.append(f"Breeding cooldown: {name} set to {entry.get('cooldown', 0)}")

    for entry in extra_data.get("renamed_pooches", []):
        if not isinstance(entry, dict):
            continue
        lines.append(f"Renamed: {entry.get('old_name', 'Unknown')} → {entry.get('new_name', 'Unknown')}")

    for entry in extra_data.get("transferred_pooches", []):
        if not isinstance(entry, dict):
            continue
        name = entry.get("pooch_name") or f"Pooch #{entry.get('pooch_id', '?')}"
        destination = entry.get("destination") or "new owner"
        lines.append(f"Transferred: {name} → {destination}")

    for entry in extra_data.get("mutations_added_details", []):
        if not isinstance(entry, dict):
            continue
        lines.append(f"Mutation gained: {entry.get('pooch_name', 'Unknown')} → {entry.get('mutation_name', 'Unknown')}")
    if result.mutations_added and not extra_data.get("mutations_added_details"):
        lines.append(f"Mutations added: {len(result.mutations_added)}")

    for entry in extra_data.get("mutations_removed_details", []):
        if not isinstance(entry, dict):
            continue
        lines.append(
            f"Mutation removed: {entry.get('pooch_name', 'Unknown')} → {entry.get('mutation_name', 'Unknown')}"
        )
    if result.mutations_removed and not extra_data.get("mutations_removed_details"):
        lines.append(f"Mutations removed: {len(result.mutations_removed)}")

    for entry in extra_data.get("breeds_added", []):
        if not isinstance(entry, dict):
            continue
        weight = entry.get("weight")
        suffix = f" ({int(round(float(weight) * 100))}% weight)" if weight is not None else ""
        lines.append(
            f"Breed added: {entry.get('pooch_name', 'Unknown')} → {entry.get('breed_name', 'Unknown')}{suffix}"
        )

    for entry in extra_data.get("killed_pooches", []):
        if not isinstance(entry, dict):
            continue
        lines.append(f"Lost pooch: {entry.get('pooch_name', 'Unknown')}")
    if result.pooches_killed and not extra_data.get("killed_pooches"):
        lines.append(f"Pooches lost: {len(result.pooches_killed)}")

    for entry in _detail_entries(extra_data.get("kennel_capacity_changes"), id_key="kennel_id", value_key="amount"):
        name = entry.get("kennel_name") or f"Kennel #{entry.get('kennel_id', '?')}"
        amount = int(entry.get("amount", 0))
        suffix = f" (limit {entry['new_limit']})" if entry.get("new_limit") is not None else ""
        lines.append(f"Kennel capacity: {name} {_signed(amount)}{suffix}")

    return _truncate("\n".join(lines) if lines else "No recorded outcome.")


def build_triggered_event_embed(event: TriggeredEvent) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎲 {event.name}",
        description=event.description or "No description provided.",
        color=_color_for_severity(event.severity),
    )

    if event.alt_name and event.alt_name != event.name:
        embed.add_field(name="Alt Name", value=event.alt_name, inline=True)

    details = [
        f"**Category:** {event.category.title()}",
        f"**Severity:** {event.severity.title()}",
    ]
    if event.requires_response and event.expires_at is not None:
        details.append(
            f"**Expires:** {_discord_timestamp(event.expires_at, 'R')} ({_discord_timestamp(event.expires_at)})"
        )
    embed.add_field(name="Details", value="\n".join(details), inline=False)

    if event.flavor_text:
        embed.add_field(name="Flavor", value=_truncate(event.flavor_text), inline=False)

    entity_lines = _entity_reference_lines(event.entity_references)
    if entity_lines:
        embed.add_field(name="Related", value=_truncate("\n".join(entity_lines)), inline=False)

    if event.requires_response and event.options:
        options_value = "\n".join(_format_option_line(option) for option in event.options)
        embed.add_field(name="Response Options", value=_truncate(options_value), inline=False)
        embed.set_footer(text="Choose an option from the menu below.")
    elif event.result is not None:
        embed.add_field(name="Outcome", value=_format_result_summary(event.result), inline=False)
        embed.set_footer(text="This event resolved automatically.")

    return embed


def build_resolved_event_embed(
    event: TriggeredEvent,
    *,
    result: Optional[EventResult],
    selected_option_label: Optional[str] = None,
    status_text: str = "Resolved",
) -> discord.Embed:
    embed = build_triggered_event_embed(event)
    if selected_option_label:
        embed.add_field(name="Selected Option", value=selected_option_label, inline=False)
    embed.add_field(name="Outcome", value=_format_result_summary(result), inline=False)
    embed.set_footer(text=status_text)
    return embed


def build_history_embed(record: dict[str, Any], page_index: int, page_count: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"📜 {record['name']}",
        description=record.get("description") or "No description provided.",
        color=_color_for_severity(record.get("severity", "moderate")),
    )

    details = [
        f"**Category:** {str(record.get('category', 'unknown')).title()}",
        f"**Severity:** {str(record.get('severity', 'moderate')).title()}",
        f"**Triggered:** {_discord_timestamp(record.get('triggered_at'))}",
    ]
    completed_at = record.get("completed_at") or record.get("responded_at")
    if completed_at:
        details.append(f"**Completed:** {_discord_timestamp(completed_at)}")

    if record.get("timed_out"):
        details.append("**Status:** Timed out")
    elif record.get("selected_option_label"):
        details.append(f"**Selected:** {record['selected_option_label']}")
    else:
        details.append("**Status:** Auto-resolved")

    embed.add_field(name="Details", value="\n".join(details), inline=False)

    flavor_text = record.get("flavor_text") or ""
    if flavor_text:
        embed.add_field(name="Flavor", value=_truncate(flavor_text), inline=False)

    entity_lines = _entity_reference_lines(record.get("entity_references") or {})
    if entity_lines:
        embed.add_field(name="Related", value=_truncate("\n".join(entity_lines)), inline=False)

    result = EventResult.from_dict(record.get("result_summary") or {})
    embed.add_field(name="Outcome", value=_format_result_summary(result), inline=False)
    embed.set_footer(text=f"History entry {page_index + 1}/{page_count}")
    return embed


async def _augment_entity_references(
    existing: dict[str, list[dict[str, Any]]],
    result: Optional[EventResult],
) -> dict[str, list[dict[str, Any]]]:
    references: dict[str, list[dict[str, Any]]] = {
        "pooches": list(existing.get("pooches") or []),
        "breeds": list(existing.get("breeds") or []),
        "mutations": list(existing.get("mutations") or []),
    }
    if result is None:
        return {key: value for key, value in references.items() if value}

    existing_ids = {
        key: {int(item.get("id")) for item in value if item.get("id") is not None} for key, value in references.items()
    }

    pooch_ids: set[int] = set()
    breed_ids: set[int] = set()
    mutation_ids: set[int] = set()

    pooch_ids.update(int(pooch_id) for pooch_id in result.pooches_affected)
    pooch_ids.update(int(pooch_id) for pooch_id in result.pooches_created)
    pooch_ids.update(int(pooch_id) for pooch_id in result.pooches_killed)
    mutation_ids.update(int(mutation_id) for _pooch_id, mutation_id in result.mutations_added)
    mutation_ids.update(int(mutation_id) for _pooch_id, mutation_id in result.mutations_removed)

    extra = result.extra_data or {}
    for entry in _detail_entries(extra.get("health_changes"), id_key="pooch_id", value_key="amount"):
        if entry.get("pooch_id") is not None:
            pooch_ids.add(int(entry["pooch_id"]))
    for entry in _detail_entries(extra.get("age_changes"), id_key="pooch_id", value_key="amount"):
        if entry.get("pooch_id") is not None:
            pooch_ids.add(int(entry["pooch_id"]))
    for key in ("created_pooches", "killed_pooches", "renamed_pooches", "transferred_pooches", "breeds_added"):
        for entry in extra.get(key, []):
            if not isinstance(entry, dict):
                continue
            if entry.get("pooch_id") is not None:
                pooch_ids.add(int(entry["pooch_id"]))
            if entry.get("breed_id") is not None:
                breed_ids.add(int(entry["breed_id"]))
    for key in ("mutations_added_details", "mutations_removed_details"):
        for entry in extra.get(key, []):
            if not isinstance(entry, dict):
                continue
            if entry.get("pooch_id") is not None:
                pooch_ids.add(int(entry["pooch_id"]))
            if entry.get("mutation_id") is not None:
                mutation_ids.add(int(entry["mutation_id"]))

    for pooch_id in sorted(pooch_ids):
        if pooch_id in existing_ids["pooches"]:
            continue
        label = None
        pooch = None
        try:
            pooch = await get_pooch_by_id(pooch_id)
        except Exception:
            pooch = None
        if pooch is not None:
            label = pooch.name
        else:
            for key in ("created_pooches", "killed_pooches", "transferred_pooches"):
                for entry in extra.get(key, []):
                    if (
                        isinstance(entry, dict)
                        and int(entry.get("pooch_id", -1)) == pooch_id
                        and entry.get("pooch_name")
                    ):
                        label = str(entry["pooch_name"])
                        break
                if label:
                    break
        references["pooches"].append({"id": pooch_id, "label": label or f"Pooch #{pooch_id}"})

    for breed_id in sorted(breed_ids):
        if breed_id in existing_ids["breeds"]:
            continue
        breed = await get_breed_by_id(breed_id)
        label = breed.name if breed is not None else f"Breed #{breed_id}"
        references["breeds"].append({"id": breed_id, "label": label})

    for mutation_id in sorted(mutation_ids):
        if mutation_id in existing_ids["mutations"]:
            continue
        mutation = await get_mutation_by_id(mutation_id)
        label = mutation.name if mutation is not None else f"Mutation #{mutation_id}"
        references["mutations"].append({"id": mutation_id, "label": label})

    return {key: value for key, value in references.items() if value}


async def _build_pooch_embed_from_id(pooch_id: int, fallback_label: str) -> discord.Embed:
    try:
        pooch = await get_pooch_by_id(pooch_id)
    except Exception:
        pooch = None

    if pooch is None:
        return discord.Embed(title=fallback_label, description="That pooch could not be found.")

    return _build_pooch_info_embed(pooch)


def _build_pooch_info_embed(pooch: Pooch) -> discord.Embed:
    embed = discord.Embed(title=pooch.name)
    embed.add_field(name="Age", value=str(pooch.age), inline=True)
    embed.add_field(name="Sex", value=pooch.sex.capitalize(), inline=True)
    embed.add_field(name="Health", value=str(pooch.health), inline=True)
    embed.add_field(name="Status", value=pooch.status.capitalize(), inline=True)
    owner_text = (
        f"<@{pooch.owner_discord_id}>"
        if pooch.owner_discord_id is not None
        else (pooch.vendor.name if pooch.vendor is not None else "Nobody")
    )
    embed.add_field(name="Owner", value=owner_text, inline=True)
    embed.add_field(
        name="Birthday", value=str(pooch.birthday.date()) if pooch.birthday is not None else "—", inline=True
    )

    if pooch.breeds:
        breed_text = ", ".join(
            f"{pooch_breed.breed.name} ({round(100 * pooch_breed.relative_weight)}%)" for pooch_breed in pooch.breeds
        )
    else:
        breed_text = "None"

    if pooch.mutations:
        mutation_text = ", ".join(mutation.name for mutation in pooch.mutations)
    else:
        mutation_text = "None"

    embed.add_field(name="Breeds", value=_truncate(breed_text), inline=False)
    embed.add_field(name="Mutations", value=_truncate(mutation_text), inline=False)
    return embed


class EventEntityControls:
    def __init__(self, owner_discord_id: int, entity_references: dict[str, list[dict[str, Any]]]):
        self.owner_discord_id = owner_discord_id
        self.entity_references = {key: list(entity_references.get(key) or []) for key, _title in ENTITY_KINDS}
        self.selected_kind: Optional[str] = None
        self.selected_id: Optional[int] = None
        self.selected_label: Optional[str] = None
        self.selects: dict[str, discord.ui.Select] = {}
        self.info_button = discord.ui.Button(label="Info", style=discord.ButtonStyle.primary, disabled=True)
        self.info_button.callback = self._on_info

        for kind, title in ENTITY_KINDS:
            items = self.entity_references.get(kind) or []
            if not items:
                continue
            select = discord.ui.Select(
                placeholder=f"Select {title.lower()}",
                options=[
                    discord.SelectOption(
                        label=_truncate(str(item.get("label") or item.get("name") or item.get("id")), 100),
                        value=str(item.get("id")),
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
                (
                    str(item.get("label") or item.get("name") or item.get("id"))
                    for item in self.entity_references.get(kind, [])
                    if int(item.get("id")) == self.selected_id
                ),
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
            embed = await _build_pooch_embed_from_id(
                self.selected_id, self.selected_label or f"Pooch #{self.selected_id}"
            )
        elif self.selected_kind == "breeds":
            breed = await get_breed_by_id(self.selected_id)
            if breed is None:
                embed = discord.Embed(
                    title=self.selected_label or f"Breed #{self.selected_id}",
                    description="That breed could not be found.",
                )
            else:
                embed = build_breed_info_embed(breed)
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
    def __init__(self, records: list[dict[str, Any]], owner_discord_id: int):
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
        controls = EventEntityControls(self._owner_discord_id, record.get("entity_references") or {})
        controls.attach(view, row_start=1)
        return None, build_history_embed(record, page_index, len(self._records))


class EventResponseSelect(discord.ui.Select):
    def __init__(self, owner_discord_id: int, event: TriggeredEvent):
        options = [
            discord.SelectOption(
                label=_truncate(str(option["label"]), 100),
                value=str(option["id"]),
                description=_format_option_select_description(option),
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
        option = next((item for item in self.event.options if int(item["id"]) == option_id), None)
        success, message, result = await respond_to_event(interaction.user.id, self.event.active_event_id, option_id)

        if success:
            if self.view is not None:
                self.view.stop()
            self.event.result = result
            self.event.entity_references = await _augment_entity_references(self.event.entity_references, result)
            embed = build_resolved_event_embed(
                self.event,
                result=result,
                selected_option_label=option["label"] if option is not None else None,
                status_text="Response recorded.",
            )
            next_view = EventMessageView(self.owner_discord_id, self.event, response_enabled=False)
            await interaction.response.edit_message(embed=embed, view=next_view)
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
            self.event.entity_references = await _augment_entity_references(self.event.entity_references, result)
            embed = build_resolved_event_embed(self.event, result=result, status_text=message)
            next_view = EventMessageView(self.owner_discord_id, self.event, response_enabled=False)
            await interaction.response.edit_message(embed=embed, view=next_view)
            return

        await interaction.response.send_message(message, ephemeral=True)


class EventMessageView(discord.ui.View):
    def __init__(self, owner_discord_id: int, event: TriggeredEvent, *, response_enabled: bool):
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


async def _get_dm_channel(bot: discord.Client, user_id: int) -> Optional[discord.DMChannel]:
    user = bot.get_user(user_id)
    if user is None:
        try:
            user = await bot.fetch_user(user_id)
        except Exception:
            return None

    try:
        dm_channel = user.dm_channel or await user.create_dm()
    except Exception:
        return None

    if not isinstance(dm_channel, discord.DMChannel):
        return None
    return dm_channel


async def send_triggered_event_dm(bot: discord.Client, owner_discord_id: int, event: TriggeredEvent) -> bool:
    dm_channel = await _get_dm_channel(bot, owner_discord_id)
    if dm_channel is None:
        return False

    embed = build_triggered_event_embed(event)
    if event.requires_response:
        view = EventMessageView(owner_discord_id, event, response_enabled=True)
        try:
            message = await dm_channel.send(embed=embed, view=view)
        except Exception:
            return False
        view.message = message
        return True

    view = EventMessageView(owner_discord_id, event, response_enabled=False)
    try:
        await dm_channel.send(embed=embed, view=view)
    except Exception:
        return False
    return True


async def send_all_pending_event_dms(
    bot: discord.Client, owner_discord_id: int, events: list[TriggeredEvent]
) -> tuple[int, int]:
    sent = 0
    failed = 0
    for event in events:
        if await send_triggered_event_dm(bot, owner_discord_id, event):
            sent += 1
        else:
            failed += 1
    return sent, failed


async def send_event_history_dm(bot: discord.Client, owner_discord_id: int, limit: int = 25) -> bool:
    records = await get_event_history(owner_discord_id, limit=limit)
    if not records:
        return False

    dm_channel = await _get_dm_channel(bot, owner_discord_id)
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
