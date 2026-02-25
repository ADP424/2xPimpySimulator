import argparse

from bot import run as run_bot
from web import run as run_web_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-w", "--web-app", action="store_true", help="Run the web app instead of the bot.", dest="web_app"
    )
    args = parser.parse_args()

    if args.web_app:
        run_web_app()
    else:
        run_bot()
