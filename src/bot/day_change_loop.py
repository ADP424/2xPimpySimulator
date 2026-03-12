import asyncio
import os
import random
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord

from src.game import (
    get_event_channel,
    run_daily_server_event_cycle,
    run_day_change,
    set_server_event_message_id,
)
from src.game.manage_owners import list_all_owners, update_owner_names
from src.logger import get_logger

from .ui.day_change_status import make_status_view
from .ui.server_events import (
    ServerEventParticipationView,
    build_server_event_embed,
    build_server_event_resolution_embed,
)
from .webhooks import post_day_change_webhooks

if TYPE_CHECKING:
    from src.game.models import DayChangeSummary


logger = get_logger("bot/day_change_loop")


def _ensure_controls(bot: discord.Client):
    paused_event = getattr(bot, "_day_change_paused_event", None)
    if not isinstance(paused_event, asyncio.Event):
        paused_event = asyncio.Event()
        paused_event.set()
        bot._day_change_paused_event = paused_event

    manual_queue = getattr(bot, "_day_change_manual_queue", None)
    if not isinstance(manual_queue, asyncio.Queue):
        manual_queue = asyncio.Queue()
        bot._day_change_manual_queue = manual_queue

    run_lock = getattr(bot, "_day_change_run_lock", None)
    if not isinstance(run_lock, asyncio.Lock):
        run_lock = asyncio.Lock()
        bot._day_change_run_lock = run_lock

    return paused_event, manual_queue, run_lock


def is_day_change_paused(bot: discord.Client) -> bool:
    paused_event, _, _ = _ensure_controls(bot)
    return not paused_event.is_set()


async def set_day_change_paused(bot: discord.Client, paused: bool) -> bool:
    """Set pause state. Returns the new paused state."""
    paused_event, _, _ = _ensure_controls(bot)
    if paused:
        paused_event.clear()
    else:
        paused_event.set()
    return not paused_event.is_set()


async def trigger_manual_day_change(bot: discord.Client):
    """Trigger one immediate day change (even if paused)."""
    _, manual_queue, _ = _ensure_controls(bot)
    manual_queue.put_nowait(1)


async def _fetch_and_update_names(bot: discord.Client):
    """Resolve Discord display names for all owners and pass them to the game layer."""
    owners = await list_all_owners()
    names: dict[int, str] = {}
    for owner in owners:
        try:
            user = bot.get_user(owner.discord_id) or await bot.fetch_user(owner.discord_id)
            names[owner.discord_id] = user.display_name
        except discord.NotFound:
            logger.warning(f"Owner {owner.discord_id} not found on Discord, skipping name update")
        except discord.HTTPException as e:
            logger.warning(f"Failed to fetch user {owner.discord_id}: {e}")
    await update_owner_names(names)


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
                    f"Couldn't find event channel with ID '{channel_id}' for server with ID '{server_discord_id}'. "
                    "Skipping summaries..."
                )
                continue

        if not summary.births and not summary.deaths:
            await channel.send(embed=discord.Embed(title="Day Change", description="Nothing to report."))
            continue

        description = f"Births: **{len(summary.births)}**\nDeaths: **{len(summary.deaths)}**"
        view = make_status_view(
            server=summary.server,
            births=summary.births,
            deaths=summary.deaths,
            other_events=summary.other_events,
            title="Day Change",
            description=description,
        )

        await view._source.load()
        view._page = 0
        view._update_nav_disabled()
        content, embed = await view._source.render(view, 0)

        send_kwargs: dict[str, object] = {"embed": embed, "view": view}
        if content is not None:
            send_kwargs["content"] = content
        await channel.send(**send_kwargs)


async def post_server_event_notifications(bot: discord.Client, owner_events: dict[int, object]):
    for server_discord_id, event in owner_events.items():
        channel_id = await get_event_channel(server_discord_id)
        if not channel_id:
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                continue

        message = await channel.send(
            embed=await build_server_event_embed(event, include_viewer_status=False),
            view=ServerEventParticipationView(event.occurrence_id, event.server_discord_id),
        )
        await set_server_event_message_id(event.occurrence_id, message.id)
        bot.add_view(ServerEventParticipationView(event.occurrence_id, event.server_discord_id), message_id=message.id)


async def post_server_event_resolutions(bot: discord.Client, resolutions: list[object]):
    for resolution in resolutions:
        channel_id = await get_event_channel(resolution.server_discord_id)
        if not channel_id:
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                continue

        await channel.send(embed=await build_server_event_resolution_embed(resolution))


async def day_change_runner(
    bot: discord.Client, stage: str, tz: str = "America/New_York", skip_startup_day_change: bool = False
):
    zone = ZoneInfo(tz)
    paused_event, manual_queue, run_lock = _ensure_controls(bot)

    async def run_once():
        logger.info("Changing day...")
        summaries = await run_day_change(rng_seed=int.from_bytes(os.urandom(8)))
        await post_day_change_summaries(bot, summaries)
        await post_day_change_webhooks(summaries)
        try:
            await _fetch_and_update_names(bot)
        except Exception:
            logger.exception("Failed to update owner display names")

        server_events, resolutions = await run_daily_server_event_cycle(
            rng=random.Random(int.from_bytes(os.urandom(8)))
        )
        await post_server_event_resolutions(bot, resolutions)
        await post_server_event_notifications(bot, server_events)

    bot._day_change_run_once = run_once

    logger.info(f"Beginning day change loop as {stage.upper()}...")

    if not skip_startup_day_change:
        async with run_lock:
            try:
                await run_once()
            except Exception as exception:
                logger.exception("Startup day change failed")
                logger.exception(exception)
                if stage == "dev":
                    raise exception

    while True:
        manual_task = asyncio.create_task(manual_queue.get())

        timer_task = None
        resume_task = None

        if paused_event.is_set():
            if stage == "dev":
                sleep_seconds = 60.0
            elif stage == "alpha":
                now = datetime.now(tz=zone)
                today = now.date()
                tomorrow = (now + timedelta(days=1)).date()
                candidates = [
                    datetime.combine(today, time(12, 0), tzinfo=zone),
                    datetime.combine(tomorrow, time(0, 0), tzinfo=zone),
                ]
                next_change = min(c for c in candidates if c > now)
                sleep_seconds = max((next_change - now).total_seconds(), 1.0)
                logger.info(f"Next alpha day change in {sleep_seconds:.0f}s at {next_change} ({tz})")
            else:
                now = datetime.now(tz=zone)
                tomorrow = (now + timedelta(days=1)).date()
                midnight = datetime.combine(tomorrow, time(0, 0), tzinfo=zone)
                sleep_seconds = max((midnight - now).total_seconds(), 1.0)
            timer_task = asyncio.create_task(asyncio.sleep(sleep_seconds))
            wait_tasks = {manual_task, timer_task}
        else:
            resume_task = asyncio.create_task(paused_event.wait())
            wait_tasks = {manual_task, resume_task}

        done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

        if manual_task in done:
            async with run_lock:
                try:
                    await run_once()
                except Exception as exception:
                    logger.exception(f"Manual day change failed: {exception}")
                    if stage == "dev":
                        raise exception
            continue

        if not paused_event.is_set():
            continue

        async with run_lock:
            try:
                await run_once()
            except Exception as exception:
                logger.exception(f"Scheduled day change failed: {exception}")
                if stage == "dev":
                    raise exception
