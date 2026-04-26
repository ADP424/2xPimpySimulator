from __future__ import annotations

import asyncio
from typing import Any, Callable

import discord
from discord.errors import InteractionResponded, NotFound
from discord.utils import MISSING


class InteractionResponder:
    """
    Consistent interaction response patterns.

    Prefer immediate responses (send_message/edit_message) and only defer when
    you truly expect slow work. If we defer, callers should always finish with
    a followup/edit to avoid the forever "bot is thinking" state.
    """

    def __init__(self, interaction: discord.Interaction, *, ephemeral: bool = False):
        self.interaction = interaction
        self.ephemeral = ephemeral
        self._did_defer = False

    @property
    def did_defer(self) -> bool:
        return self._did_defer

    async def defer(self, *, thinking: bool = True) -> None:
        try:
            if not self.interaction.response.is_done():
                await self.interaction.response.defer(thinking=thinking, ephemeral=self.ephemeral)
                self._did_defer = True
        except InteractionResponded, NotFound, discord.HTTPException:
            return

    async def ack_update(self) -> None:
        """Silently acknowledge a component interaction (no thinking)."""
        try:
            if not self.interaction.response.is_done():
                await self.interaction.response.defer(thinking=False)
        except Exception:
            return

    async def reply(
        self,
        *,
        content: Any = MISSING,
        embed: Any = MISSING,
        view: Any = MISSING,
        mention_author: bool = False,
    ) -> None:
        kwargs = build_kwargs(content, embed, view)

        # Never send a components-only reply.
        visible_content = kwargs.get("content", MISSING)
        visible_embed = kwargs.get("embed", MISSING)
        has_visible_text = visible_content is not MISSING and visible_content not in (None, "")
        has_visible_embed = visible_embed is not MISSING and visible_embed is not None
        if not has_visible_text and not has_visible_embed:
            await self.ack_update()
            return

        try:
            if not self.interaction.response.is_done():
                await self.interaction.response.send_message(**kwargs, ephemeral=self.ephemeral)
                return
        except InteractionResponded, NotFound, discord.HTTPException:
            pass

        try:
            await self.interaction.followup.send(**kwargs, ephemeral=self.ephemeral)
            return
        except Exception:
            pass

        if self.interaction.message is not None:
            try:
                await self.interaction.message.reply(**kwargs, mention_author=mention_author)
                return
            except Exception:
                pass

        if self.interaction.channel is not None:
            try:
                await self.interaction.channel.send(**kwargs)
            except Exception:
                return

    async def edit(
        self,
        *,
        content: Any = MISSING,
        embed: Any = MISSING,
        view: Any = MISSING,
    ) -> None:
        kwargs = build_kwargs(content, embed, view)

        if self.interaction.message is not None:
            try:
                if not self.interaction.response.is_done():
                    await self.interaction.response.edit_message(**kwargs)
                else:
                    await self.interaction.message.edit(**kwargs)
                return
            except InteractionResponded, NotFound, discord.HTTPException:
                pass

        try:
            if self.interaction.response.is_done():
                await self.interaction.edit_original_response(**kwargs)
            else:
                await self.interaction.response.edit_message(**kwargs)
        except Exception:
            return

    async def finish_with_error(self, message: str = "Something went wrong.") -> None:
        """Ensure an error reaches the user, even if we already deferred."""
        try:
            if not self.interaction.response.is_done():
                await self.interaction.response.send_message(message, ephemeral=self.ephemeral)
                return
        except Exception:
            pass
        try:
            await self.interaction.followup.send(message, ephemeral=self.ephemeral)
        except Exception:
            return


async def run_blocking(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Run blocking.

    Parameters
    ----------
    fn: Any
        The `fn` value.

    Returns
    -------
    Any
        The result of calling `run_blocking`.
    """

    return await asyncio.to_thread(fn, *args, **kwargs)


def mention(discord_id: int) -> str:
    """
    Mention.

    Parameters
    ----------
    discord_id: Any
        The `discord_id` value.

    Returns
    -------
    Any
        The result of calling `mention`.
    """

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


def build_kwargs(content: Any, embed: Any, view: Any) -> dict[str, Any]:
    """
    Build kwargs.

    Parameters
    ----------
    content: Any
        The `content` value.

    embed: Any
        The `embed` value.

    view: Any
        The `view` value.

    Returns
    -------
    Any
        The result of calling `build_kwargs`.
    """

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
    kwargs = build_kwargs(content, embed, view)

    # IMPORTANT:
    # For component interactions (buttons/selects/modals), the message we want to
    # refresh is usually `interaction.message` (the message the user clicked).
    # If we defer first, `interaction.response.is_done()` becomes True, and
    # calling `edit_original_response()` will edit the *deferred response* (a
    # separate message) rather than the clicked message.
    # That is the source of the "blank message with just components" spam.
    if interaction.message is not None:
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(**kwargs)
            else:
                await interaction.message.edit(**kwargs)
            return
        except InteractionResponded, NotFound, discord.HTTPException:
            pass

    # Slash command / context menu interactions typically have no `interaction.message`.
    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(**kwargs)
        else:
            await interaction.response.edit_message(**kwargs)
        return
    except InteractionResponded, NotFound, discord.HTTPException:
        pass

    # Last resort: if we have a message object, try editing it directly.
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

    kwargs = build_kwargs(content, embed, view)
    # Guardrail: never send a "blank" reply that contains only components.
    # This can happen when callers pass content=None/embed=None while trying to
    # "refresh" a view before sending a real follow-up (e.g., opening a pooch info card).
    # If there's no visible payload, just acknowledge the interaction and return.
    visible_content = kwargs.get("content", MISSING)
    visible_embed = kwargs.get("embed", MISSING)
    has_visible_text = visible_content is not MISSING and visible_content not in (None, "")
    has_visible_embed = visible_embed is not MISSING and visible_embed is not None
    if not has_visible_text and not has_visible_embed:
        await defer_interaction(interaction)
        return

    # IMPORTANT:
    # Do **not** defer here.
    # Deferring a component interaction creates a "thinking" state that must be
    # resolved via followup/edit_original_response. If we instead fall back to
    # replying to the underlying message (interaction.message.reply), the defer
    # never resolves and you get the stuck first reply.
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(**kwargs, ephemeral=False)
            return
    except InteractionResponded:
        pass
    except NotFound:
        # Token expired; fall back to message/channel send.
        pass
    except discord.HTTPException:
        pass

    try:
        await interaction.followup.send(**kwargs, ephemeral=False)
        return
    except Exception:
        pass

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
