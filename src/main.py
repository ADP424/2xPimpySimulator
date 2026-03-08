import argparse
import asyncio

from bot import run as run_bot
from database import load_resources, reset_database
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
        dest="reset_database",
    )
    args = parser.parse_args()

    if args.web_app:
        run_web_app()
    elif args.reset_database:
        reset_database()
        asyncio.run(load_resources())
    else:
        run_bot()
