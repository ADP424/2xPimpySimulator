import os

from dotenv import load_dotenv

from src.web.app import create_app, socketio


def run():
    load_dotenv()
    app = create_app()
    port = int(os.environ.get("WEB_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    socketio.run(app, host="0.0.0.0", port=port, debug=debug, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    run()
