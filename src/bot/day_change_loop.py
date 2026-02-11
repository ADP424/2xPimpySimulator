import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import discord

from game import get_event_channel, run_day_change
from logger import get_logger
from .ui.day_change_status import make_status_view

if discord.TYPE_CHECKING:
    from game.model import DayChangeSummary


logger = get_logger("bot/day_change_loop")


async def post_day_change_summaries(bot: discord.Client, summaries: dict[int, DayChangeSummary]):
    for server_id, summary in summaries.items():
        channel_id = await get_event_channel(server_id)
        if not channel_id:
            logger.info(f"Event channel not set in server with ID '{server_id}'. Skipping summaries...")
            continue

        channel = bot.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except Exception:
                logger.info(
                    f"Couldn't find event channel with ID '{channel_id}' for server with ID '{server_id}'. Skipping summaries..."
                )
                continue

        if not summary.births and not summary.deaths:
            await channel.send(embed=discord.Embed(title="🌙 Day Change", description="Nothing to report."))
            continue

        desc = f"Births: **{len(summary.births)}**\nDeaths: **{len(summary.deaths)}**"
        view = make_status_view(
            server_id=server_id,
            pooch_ids=summary.mentioned_pooch_ids,
            title="🌙 Day Change",
            description=desc,
        )

        message = await channel.send(embed=discord.Embed(title="🌙 Day Change", description=desc), view=view)

        await view._source.load()  # type: ignore
        view._page = 0  # type: ignore
        content, embed = await view._source.render(view, 0)  # type: ignore
        await message.edit(content=content, embed=embed, view=view)


async def day_change_runner(bot: discord.Client, *, stage: str, tz: str = "America/New_York"):
    zone = ZoneInfo(tz)

    async def run_once():
        logger.info("Changing day...")
        summaries = await run_day_change()
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
