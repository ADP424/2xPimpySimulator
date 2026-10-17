import argparse
import asyncio
import signal

from src.bot import run as run_bot
from src.database import load_resources, reset_database, upgrade_lots_of_changes
from src.game.change_day import refresh_moods
from src.game.constants import PREGNANCY_TIMER_HOURS_RANGE
from src.web import run as run_web_app


def _stop_on_sigterm(signum, frame):
    """Treat SIGTERM (kill, scripts/update.sh) like Ctrl+C so the bot and web app shut down cleanly."""
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _stop_on_sigterm)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-w", "--web-app", action="store_true", help="Run the web app instead of the bot.", dest="web_app"
    )
    parser.add_argument(
        "-r",
        "--reset-db",
        action="store_true",
        help="Reset the database instead of launching anything.",
        dest="reset_database",
    )
    parser.add_argument(
        "-n",
        "--update-names",
        action="store_true",
        help="Update owner Discord display names and exit.",
        dest="update_names",
    )
    parser.add_argument(
        "-s",
        "--skip-startup-day-change",
        action="store_true",
        help="Skip the day change that normally runs on bot startup.",
        dest="skip_startup_day_change",
    )
    parser.add_argument(
        "-m",
        "--refresh-moods",
        action="store_true",
        help="Refresh all pooch moods and exit.",
        dest="refresh_moods",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Upgrade an existing database in place (keeps all players) and exit.",
        dest="migrate",
    )
    parser.add_argument(
        "--starting-food",
        type=int,
        default=0,
        metavar="N",
        help="With --migrate: top every kennel up to at least N food units (a pooch eats 1-3 an hour).",
        dest="starting_food",
    )
    args = parser.parse_args()

    if args.migrate:
        asyncio.run(
            upgrade_lots_of_changes(pregnancy_timer_range=PREGNANCY_TIMER_HOURS_RANGE, starting_food=args.starting_food)
        )
    elif args.refresh_moods:
        count = asyncio.run(refresh_moods())
        print(f"Refreshed moods for {count} pooches.")
    elif args.web_app:
        run_web_app()
    elif args.reset_database:
        reset_database()
        asyncio.run(load_resources())
    elif args.update_names:
        run_bot(update_names_only=True)
    else:
        run_bot(skip_startup_day_change=args.skip_startup_day_change)
