import atexit
import os

from flask import Flask
from flask_session import Session
from flask_socketio import SocketIO

from web.async_utils import AsyncBridge

socketio = SocketIO(async_mode="threading")


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__)

    # Base configuration
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        DISCORD_CLIENT_ID=os.environ.get("DISCORD_CLIENT_ID"),
        DISCORD_CLIENT_SECRET=os.environ.get("DISCORD_CLIENT_SECRET"),
        DISCORD_REDIRECT_URI=os.environ.get("DISCORD_REDIRECT_URI"),
        PIMPY_WEBHOOK_SECRET=os.environ.get("PIMPY_WEBHOOK_SECRET"),
        SESSION_COOKIE_NAME="pooch_breeder_session",
        SESSION_TYPE="filesystem",
        SESSION_FILE_DIR=os.path.join(os.path.dirname(__file__), ".flask_session"),
        SESSION_PERMANENT=False,
    )

    Session(app)

    if config:
        app.config.update(config)

    # Initialize SocketIO
    socketio.init_app(app, cors_allowed_origins="*")

    # Register blueprints
    from web.routes.api import api_bp
    from web.routes.auth import auth_bp
    from web.routes.info import info_bp
    from web.routes.kennel import kennel_bp
    from web.routes.main import main_bp
    from web.routes.pooch import pooch_bp
    from web.routes.vendor import vendor_bp
    from web.routes.webhooks import webhooks_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(kennel_bp, url_prefix="/kennel")
    app.register_blueprint(pooch_bp, url_prefix="/pooch")
    app.register_blueprint(vendor_bp, url_prefix="/vendor")
    app.register_blueprint(info_bp, url_prefix="/info")
    app.register_blueprint(webhooks_bp, url_prefix="/webhook")

    # Register WebSocket events
    from web.events import register_events

    register_events(socketio)

    # Ensure async loop is shutdown on exit
    def _cleanup():
        try:
            AsyncBridge.get_instance().shutdown()
        except Exception:
            pass

    atexit.register(_cleanup)

    return app
