import asyncio
from typing import Any, Callable

import discord
from discord.utils import MISSING


async def run_blocking(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(fn, *args, **kwargs)


def mention(discord_id: int) -> str:
    return f"<@{discord_id}>"


async def edit_interaction(
    interaction: discord.Interaction,
    content: Any = MISSING,
    embed: Any = MISSING,
    view: Any = MISSING,
):
    """
    Edit an interaction safely (since Discord only allows one response to an interaction).
    """

    kwargs: dict[str, Any] = {}
    if content is not MISSING:
        kwargs["content"] = content
    if embed is not MISSING:
        kwargs["embed"] = embed
    if view is not MISSING:
        kwargs["view"] = view

    if interaction.response.is_done():
        await interaction.edit_original_response(**kwargs)
    else:
        await interaction.response.edit_message(**kwargs)


async def reply_to_interacted_message(
    interaction: discord.Interaction,
    content: Any = MISSING,
    embed: Any = MISSING,
    view: Any = MISSING,
    mention_author: bool = False,
):
    if not interaction.response.is_done():
        await interaction.response.defer()

    kwargs: dict[str, Any] = {}
    if content is not MISSING:
        kwargs["content"] = content
    if embed is not MISSING:
        kwargs["embed"] = embed
    if view is not MISSING:
        kwargs["view"] = view

    if interaction.message is not None:
        await interaction.message.reply(**kwargs, mention_author=mention_author)
        return

    if interaction.channel is not None:
        await interaction.channel.send(**kwargs)
        return

    await interaction.followup.send(**kwargs)
