import argparse
import asyncio

from bot import run as run_bot
from web import run as run_web_app
from database import reset_db, load_resources


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-w", "--web-app", action="store_true", help="Run the web app instead of the bot.", dest="web_app"
    )
    parser.add_argument(
        "-r", "--reset-db", action="store_true", help="Reset the database instead of launching anything.", dest="reset_db"
    )
    args = parser.parse_args()

    if args.reset_db:
        reset_db()
        asyncio.run(load_resources())
    elif args.web_app:
        run_web_app()
    else:
        run_bot()
