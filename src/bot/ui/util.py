import asyncio
from datetime import datetime
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

import discord

GAME_TZ = ZoneInfo("America/New_York")
# Enough to cover the time between real day changes (midnight -> midnight), plus a buffer.
DAY_VIEW_TIMEOUT_SECONDS = 60 * 60 * 26


async def run_blocking(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(fn, *args, **kwargs)


def mention(discord_id: int) -> str:
    return f"<@{discord_id}>"


def current_day_key() -> str:
    """A simple, stable key for the current in-game day."""
    return datetime.now(tz=GAME_TZ).date().isoformat()


def persist_select_defaults(select: discord.ui.Select) -> None:
    """Ensure a Select continues to display the user's selection after a message edit.

    Discord clients only show the chosen option after an edit if the option(s) are marked as default.
    """
    selected = set(getattr(select, "values", []) or [])
    for opt in select.options:
        opt.default = opt.value in selected


async def edit_interaction(
    interaction: discord.Interaction,
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
):
    """Edit an interaction safely (Discord only allows one response to an interaction)."""
    if interaction.response.is_done():
        await interaction.edit_original_response(content=content, embed=embed, view=view)
    else:
        await interaction.response.edit_message(content=content, embed=embed, view=view)


async def reply_to_interaction_message(
    interaction: discord.Interaction,
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
    mention_author: bool = False,
):
    """Send a NEW message as a reply to the message that was interacted with."""
    if not interaction.response.is_done():
        # Acknowledge the interaction without modifying the original message.
        await interaction.response.defer(thinking=False)

    # Prefer a true reply (message reference) so the new message threads to the original.
    if interaction.channel is not None and interaction.message is not None:
        ref = interaction.message.to_reference(fail_if_not_exists=False)
        await interaction.channel.send(
            content=content,
            embed=embed,
            view=view,
            reference=ref,
            mention_author=mention_author,
        )
    else:
        # Fallback (DMs / edge cases) - still sends a new message.
        await interaction.followup.send(content=content, embed=embed, view=view)


async def expire_view_interaction(
    interaction: discord.Interaction,
    view: discord.ui.View,
    *,
    message: str = "⚠️ This message is from a previous day and can no longer be used.",
):
    """Disable the view and inform the user that the message has expired."""
    for item in view.children:
        try:
            item.disabled = True  # type: ignore[attr-defined]
        except Exception:
            pass

    # Best-effort: disable components on the old message so others don't keep clicking it.
    try:
        if interaction.message is not None:
            await interaction.message.edit(view=view)
    except Exception:
        pass

    if not interaction.response.is_done():
        await interaction.response.send_message(message, ephemeral=True)
    else:
        await interaction.followup.send(message, ephemeral=True)


class DayBoundView(discord.ui.View):
    """A View that becomes invalid after the in-game day changes (midnight America/New_York)."""

    def __init__(self, *, timeout: float = DAY_VIEW_TIMEOUT_SECONDS, day_key: Optional[str] = None):
        super().__init__(timeout=timeout)
        self.day_key = day_key or current_day_key()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.day_key != current_day_key():
            await expire_view_interaction(interaction, self)
            return False
        return True
