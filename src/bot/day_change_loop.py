import asyncio
from datetime import datetime, time, timedelta
import os
from zoneinfo import ZoneInfo

import discord

from game import get_event_channel, run_day_change
from logger import get_logger
from .ui.day_change_status import make_status_view

if discord.TYPE_CHECKING:
    from game.model import DayChangeSummary


logger = get_logger("bot/day_change_loop")


async def post_day_change_summaries(bot: discord.Client, summaries: dict[int, DayChangeSummary]):
    for server_discord_id, summary in summaries.items():
        channel_id = await get_event_channel(server_discord_id)
        if not channel_id:
            logger.info(f"Event channel not set in server with ID '{server_discord_id}'. Skipping summaries...")
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                logger.info(
                    f"Couldn't find event channel with ID '{channel_id}' for server with ID '{server_discord_id}'. Skipping summaries..."
                )
                continue

        if not summary.births and not summary.deaths:
            await channel.send(embed=discord.Embed(title="🌙 Day Change", description="Nothing to report."))
            continue

        desc = f"Births: **{len(summary.births)}**\nDeaths: **{len(summary.deaths)}**"
        view = make_status_view(
            server=summary.server,
            pooches=summary.mentioned_pooches,
            title="🌙 Day Change",
            description=desc,
        )

        # Build the first page *before* sending so paginator button disabled-states
        # are correct on the initial message (there is no interaction object here).
        await view._source.load()  # type: ignore
        view._page = 0  # type: ignore
        view._update_nav_disabled()  # type: ignore
        content, embed = await view._source.render(view, 0)  # type: ignore

        send_kwargs: dict[str, object] = {"embed": embed, "view": view}
        if content is not None:
            send_kwargs["content"] = content
        await channel.send(**send_kwargs)  # type: ignore


async def day_change_runner(bot: discord.Client, *, stage: str, tz: str = "America/New_York"):
    zone = ZoneInfo(tz)

    async def run_once():
        logger.info("Changing day...")
        summaries = await run_day_change(rng_seed=int.from_bytes(os.urandom(8)))
        await post_day_change_summaries(bot, summaries)

    if stage == "dev":
        logger.info("Beginning day change loop as DEV...")
        while True:
            await run_once()
            await asyncio.sleep(60)
    else:
        logger.info("Beginning day change loop as PROD...")
        while True:
            now = datetime.now(tz=zone)
            tomorrow = (now + timedelta(days=1)).date()
            midnight = datetime.combine(tomorrow, time(0, 0), tzinfo=zone)
            sleep_seconds = max((midnight - now).total_seconds(), 1.0)
            await asyncio.sleep(sleep_seconds)
            await run_once()
