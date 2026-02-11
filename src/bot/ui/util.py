import asyncio
from typing import Any, Callable, Optional

import discord


async def run_blocking(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(fn, *args, **kwargs)


async def edit_interaction(
    interaction: discord.Interaction,
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
):
    """
    Edit an interaction safely (since Discord only allows one response to an interaction).
    """

    if interaction.response.is_done():
        await interaction.edit_original_response(content=content, embed=embed, view=view)
    else:
        await interaction.response.edit_message(content=content, embed=embed, view=view)
