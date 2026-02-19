import asyncio
from typing import Any, Callable

import discord
from discord.errors import InteractionResponded, NotFound
from discord.utils import MISSING


async def run_blocking(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(fn, *args, **kwargs)


def mention(discord_id: int) -> str:
    return f"<@{discord_id}>"


async def defer_interaction(
    interaction: discord.Interaction,
    thinking: bool = True,
    ephemeral: bool = False,
) -> None:
    """
    Acknowledge an interaction early, safely.
    Safe to call even if the interaction was already acknowledged/expired.
    """
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=thinking, ephemeral=ephemeral)
    except InteractionResponded, NotFound, discord.HTTPException:
        # Already responded, expired token, or other transient HTTP failure.
        return


def _build_kwargs(content: Any, embed: Any, view: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if content is not MISSING:
        kwargs["content"] = content
    if embed is not MISSING:
        kwargs["embed"] = embed
    if view is not MISSING:
        kwargs["view"] = view
    return kwargs


async def edit_interaction(
    interaction: discord.Interaction,
    content: Any = MISSING,
    embed: Any = MISSING,
    view: Any = MISSING,
) -> None:
    """
    Edit the message associated with an interaction.
    Works whether or not it's been deferred, and falls back to editing the
    underlying message if the interaction token has expired.
    """
    kwargs = _build_kwargs(content, embed, view)

    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(**kwargs)
        else:
            await interaction.response.edit_message(**kwargs)
        return
    except InteractionResponded:
        try:
            await interaction.edit_original_response(**kwargs)
            return
        except Exception:
            pass
    except NotFound:
        pass
    except discord.HTTPException:
        pass

    if interaction.message is not None:
        try:
            await interaction.message.edit(**kwargs)
            return
        except Exception:
            pass


async def reply_to_interacted_message(
    interaction: discord.Interaction,
    content: Any = MISSING,
    embed: Any = MISSING,
    view: Any = MISSING,
    *,
    mention_author: bool = False,
) -> None:
    """
    Send a message in response to an interaction, lifecycle-safe.
    Prefer calling `await defer_interaction(...)` first in component callbacks.
    """

    kwargs = _build_kwargs(content, embed, view)

    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs, ephemeral=False)
            return
    except NotFound:
        # Token expired, fall back with defer
        pass
    except discord.HTTPException:
        pass

    await defer_interaction(interaction)

    if interaction.message is not None:
        try:
            await interaction.message.reply(**kwargs, mention_author=mention_author)
            return
        except discord.HTTPException:
            pass

    if interaction.channel is not None:
        try:
            await interaction.channel.send(**kwargs)
            return
        except discord.HTTPException:
            pass

    try:
        await interaction.followup.send(**kwargs)
    except Exception:
        return
