import argparse
import asyncio

from bot import run as run_bot
from database import load_resources, reset_db
from game.change_day import refresh_moods
from web import run as run_web_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-w", "--web-app", action="store_true", help="Run the web app instead of the bot.", dest="web_app"
    )
    parser.add_argument(
        "-r",
        "--reset-db",
        action="store_true",
        help="Reset the database instead of launching anything.",
        dest="reset_db",
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
    args = parser.parse_args()

    if args.refresh_moods:
        count = asyncio.run(refresh_moods())
        print(f"Refreshed moods for {count} pooches.")
    elif args.web_app:
        run_web_app()
    elif args.reset_db:
        reset_db()
        asyncio.run(load_resources())
    elif args.update_names:
        run_bot(update_names_only=True)
    else:
        run_bot(skip_startup_day_change=args.skip_startup_day_change)
