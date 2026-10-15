import asyncio
import os
import random
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord

from src.bot.ui import (
    ServerEventParticipationView,
    build_server_event_embed,
    build_server_event_resolution_embed,
    make_status_view,
)
from src.game import (
    get_event_channel,
    list_all_owners,
    list_all_servers,
    run_daily_server_event_cycle,
    run_day_change,
    run_hour_change,
    run_hourly_event_check,
    run_week_change,
    set_server_event_message_id,
    update_owner_names,
)
from src.logger import get_logger

from .constants import EVENT_LOOP_INTERVAL_SECONDS
from .event_loop import post_hourly_event_notifications
from .webhooks import post_hour_change_webhooks

if TYPE_CHECKING:
    from src.game.models import HourChangeSummary, StrayEventResult


logger = get_logger("bot/day_change_loop")


def ensure_controls(bot: discord.Client):
    """
    Ensure controls.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    Returns
    -------
    Any
        The result of calling `ensure_controls`.
    """

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
    """
    Is day change paused.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    Returns
    -------
    Any
        The result of calling `is_day_change_paused`.
    """

    paused_event, _, _ = ensure_controls(bot)
    return not paused_event.is_set()


async def set_day_change_paused(bot: discord.Client, paused: bool) -> bool:
    """Set pause state. Returns the new paused state."""
    paused_event, _, _ = ensure_controls(bot)
    if paused:
        paused_event.clear()
    else:
        paused_event.set()
    return not paused_event.is_set()


async def trigger_manual_day_change(bot: discord.Client):
    """Trigger one immediate day change (even if paused)."""
    _, manual_queue, _ = ensure_controls(bot)
    manual_queue.put_nowait(1)


async def fetch_and_update_names(bot: discord.Client):
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


async def post_new_day_announcement(bot: discord.Client) -> None:
    """Post a brief 'new day' announcement to each server's event channel."""
    servers = await list_all_servers()
    for server in servers:
        channel_id = await get_event_channel(server.discord_id)
        if not channel_id:
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                logger.info(
                    f"Couldn't find event channel with ID '{channel_id}' for server with ID "
                    f"'{server.discord_id}'. Skipping day announcement..."
                )
                continue

        await channel.send(embed=discord.Embed(title="A new day has begun!", color=discord.Color.blurple()))


async def post_server_event_notifications(bot: discord.Client, owner_events: dict[int, object]):
    """
    Post server event notifications.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    owner_events: Any
        The `owner_events` value.

    Returns
    -------
    Any
        The result of calling `post_server_event_notifications`.
    """

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

        has_menus = bool(event.menus)
        message = await channel.send(
            embed=await build_server_event_embed(event, include_viewer_status=False),
            view=ServerEventParticipationView(event.occurrence_id, event.server_discord_id, has_menus=has_menus),
        )
        await set_server_event_message_id(event.occurrence_id, message.id)
        bot.add_view(
            ServerEventParticipationView(event.occurrence_id, event.server_discord_id, has_menus=has_menus),
            message_id=message.id,
        )


async def post_server_event_resolutions(bot: discord.Client, resolutions: list[object]):
    """
    Post server event resolutions.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    resolutions: Any
        The `resolutions` value.

    Returns
    -------
    Any
        The result of calling `post_server_event_resolutions`.
    """

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


_SEASON_EMOJI = {
    "spring": "🌸",
    "summer": "☀️",
    "autumn": "🍂",
    "winter": "❄️",
}


async def post_season_change_notifications(bot: discord.Client, season_advances: dict[int, str]) -> None:
    """Post a season-change announcement to each server's event channel."""
    for server_discord_id, new_season in season_advances.items():
        channel_id = await get_event_channel(server_discord_id)
        if not channel_id:
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                continue

        emoji = _SEASON_EMOJI.get(new_season, "")
        embed = discord.Embed(
            title=f"{emoji} The season has changed!",
            description=f"It is now **{new_season.capitalize()}**.",
            color=discord.Color.green(),
        )
        await channel.send(embed=embed)


async def post_stray_event_summaries(
    bot: discord.Client,
    stray_results: dict[int, list[tuple[str, StrayEventResult]]],
) -> None:
    """Post stray event results to each server's event channel (dev only)."""
    for server_discord_id, events in stray_results.items():
        channel_id = await get_event_channel(server_discord_id)
        if not channel_id:
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                continue

        lines = []
        for event_name, result in events:
            parts = [f"**[stray event]** `{event_name}`"]
            if result.pooches_affected:
                parts.append(f"affected: {result.pooches_affected}")
            if result.pooches_killed:
                parts.append(f"killed: {result.pooches_killed}")
            if result.pooches_created:
                parts.append(f"created: {result.pooches_created}")
            lines.append(" | ".join(parts))

        if lines:
            await channel.send("\n".join(lines))


async def day_change_runner(
    bot: discord.Client, stage: str, tz: str = "America/New_York", skip_startup_day_change: bool = False
):
    """
    Day change runner.

    Parameters
    ----------
    bot: Any
        The `bot` value.

    stage: Any
        The `stage` value.

    tz: Any
        The `tz` value.

    skip_startup_day_change: Any
        The `skip_startup_day_change` value.

    Returns
    -------
    Any
        The result of calling `day_change_runner`.
    """

    zone = ZoneInfo(tz)
    paused_event, manual_queue, run_lock = ensure_controls(bot)

    async def run_once():
        logger.info("Changing day...")
        stray_results = await run_day_change(rng_seed=int.from_bytes(os.urandom(8)))
        await post_new_day_announcement(bot)
        if stage == "dev":
            await post_stray_event_summaries(bot, stray_results)
        try:
            await fetch_and_update_names(bot)
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


# ---------------------------------------------------------------------------
# Hour loop
# ---------------------------------------------------------------------------


def ensure_hour_controls(bot: discord.Client):
    """Lazily build and return (paused_event, manual_queue, run_lock) for the hour loop."""
    paused_event = getattr(bot, "_hour_change_paused_event", None)
    if not isinstance(paused_event, asyncio.Event):
        paused_event = asyncio.Event()
        paused_event.set()
        bot._hour_change_paused_event = paused_event

    manual_queue = getattr(bot, "_hour_change_manual_queue", None)
    if not isinstance(manual_queue, asyncio.Queue):
        manual_queue = asyncio.Queue()
        bot._hour_change_manual_queue = manual_queue

    # Shared with the day loop so day, hour and week ticks never run at the same time
    _, _, run_lock = ensure_controls(bot)

    return paused_event, manual_queue, run_lock


def is_hour_change_paused(bot: discord.Client) -> bool:
    """Return True if the hour change loop is paused."""
    paused_event, _, _ = ensure_hour_controls(bot)
    return not paused_event.is_set()


async def set_hour_change_paused(bot: discord.Client, paused: bool) -> bool:
    """Set the hour loop's pause state. Returns the new paused state."""
    paused_event, _, _ = ensure_hour_controls(bot)
    if paused:
        paused_event.clear()
    else:
        paused_event.set()
    return not paused_event.is_set()


async def trigger_manual_hour_change(bot: discord.Client):
    """Trigger one immediate hour change (even if paused)."""
    _, manual_queue, _ = ensure_hour_controls(bot)
    manual_queue.put_nowait(1)


async def post_hour_change_summaries(bot: discord.Client, summaries: dict[int, "HourChangeSummary"]) -> None:
    """Post non-empty hour change summaries to each server's event channel."""
    for server_discord_id, summary in summaries.items():
        if summary.is_empty:
            continue
        channel_id = await get_event_channel(server_discord_id)
        if not channel_id:
            continue
        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                continue

        description_parts: list[str] = []
        if summary.births:
            description_parts.append(f"Births: **{len(summary.births)}**")
        if summary.deaths:
            description_parts.append(f"Deaths: **{len(summary.deaths)}**")
        if summary.other_events:
            description_parts.append(f"Other: **{len(summary.other_events)}**")

        view = make_status_view(
            server=summary.server,
            births=summary.births,
            deaths=summary.deaths,
            other_events=summary.other_events,
            title="Hour Change",
            description="\n".join(description_parts) or "—",
        )
        await view._source.load()
        view._page = 0
        view._update_nav_disabled()
        content, embed = await view._source.render(view, 0)
        send_kwargs: dict[str, object] = {"embed": embed, "view": view}
        if content is not None:
            send_kwargs["content"] = content
        try:
            await channel.send(**send_kwargs)
        except Exception:
            logger.exception("Failed to post hour change summary to %s", server_discord_id)


async def hour_change_runner(
    bot: discord.Client,
    stage: str,
    tz: str = "America/New_York",  # kept for parity; not yet used
) -> None:
    """
    Run one hour of game time per hour (or every few seconds in dev): ``run_hour_change``, then the owner event check.

    Posts the hour summary to the event channel only when there are events to report, and DMs triggered owner events.
    Shares the day loop's lock, so it never runs at the same time as a day or week change.
    """
    del tz  # reserved
    paused_event, manual_queue, run_lock = ensure_hour_controls(bot)

    async def run_once():
        logger.info("Ticking hour...")
        summaries = await run_hour_change(rng_seed=int.from_bytes(os.urandom(8)))
        await post_hour_change_summaries(bot, summaries)
        try:
            await post_hour_change_webhooks(summaries)
        except Exception:
            logger.exception("Failed to post hour change webhooks")

        triggered_events = await run_hourly_event_check(rng_seed=int.from_bytes(os.urandom(8)))
        await post_hourly_event_notifications(bot, triggered_events)

    bot._hour_change_run_once = run_once

    logger.info("Beginning hour change loop as %s...", stage.upper())

    while True:
        manual_task = asyncio.create_task(manual_queue.get())
        timer_task = None
        resume_task = None

        if paused_event.is_set():
            sleep_seconds = 10.0 if stage == "dev" else EVENT_LOOP_INTERVAL_SECONDS
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
                except Exception:
                    logger.exception("Manual hour change failed")
                    if stage == "dev":
                        raise
            continue

        if not paused_event.is_set():
            continue

        async with run_lock:
            try:
                await run_once()
            except Exception:
                logger.exception("Scheduled hour change failed")
                if stage == "dev":
                    raise


# ---------------------------------------------------------------------------
# Week loop
# ---------------------------------------------------------------------------


def ensure_week_controls(bot: discord.Client):
    """Lazily build and return (paused_event, manual_queue, run_lock) for the week loop."""
    paused_event = getattr(bot, "_week_change_paused_event", None)
    if not isinstance(paused_event, asyncio.Event):
        paused_event = asyncio.Event()
        paused_event.set()
        bot._week_change_paused_event = paused_event

    manual_queue = getattr(bot, "_week_change_manual_queue", None)
    if not isinstance(manual_queue, asyncio.Queue):
        manual_queue = asyncio.Queue()
        bot._week_change_manual_queue = manual_queue

    # Shared with the day loop so day, hour and week ticks never run at the same time
    _, _, run_lock = ensure_controls(bot)

    return paused_event, manual_queue, run_lock


async def trigger_manual_week_change(bot: discord.Client):
    """Enqueue an immediate week change tick."""
    _, manual_queue, _ = ensure_week_controls(bot)
    manual_queue.put_nowait(1)


async def week_change_runner(bot: discord.Client, stage: str) -> None:
    """
    Run ``run_week_change`` once every 7 days (or every few seconds in dev).

    Posts season-change and major server-event notifications to the event channel.
    Runs in parallel with the day and hour runners under a separate lock.
    """
    paused_event, manual_queue, run_lock = ensure_week_controls(bot)

    async def run_once():
        logger.info("Ticking week...")
        new_events, resolutions, season_advances = await run_week_change(
            rng=random.Random(int.from_bytes(os.urandom(8)))
        )
        await post_server_event_resolutions(bot, resolutions)
        if season_advances:
            await post_season_change_notifications(bot, season_advances)
        await post_server_event_notifications(bot, new_events)

    bot._week_change_run_once = run_once

    logger.info("Beginning week change loop as %s...", stage.upper())

    while True:
        manual_task = asyncio.create_task(manual_queue.get())
        timer_task = None
        resume_task = None

        if paused_event.is_set():
            # dev: fire every 30 seconds for easy testing; prod: every 7 days (in seconds)
            sleep_seconds = 30.0 if stage == "dev" else 7 * 24 * 3600.0
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
                except Exception:
                    logger.exception("Manual week change failed")
                    if stage == "dev":
                        raise
            continue

        if not paused_event.is_set():
            continue

        async with run_lock:
            try:
                await run_once()
            except Exception:
                logger.exception("Scheduled week change failed")
                if stage == "dev":
                    raise
