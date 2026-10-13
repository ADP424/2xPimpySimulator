"""Shared fixtures for web route tests: the API blueprint on a bare Flask app with a logged-in session."""

import asyncio
from unittest.mock import patch

import pytest
from flask import Flask

from src.web.routes.api import api_bp

VIEWER_ID = 1
SERVER_ID = 100


def _run_sync(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(api_bp, url_prefix="/api")

    with patch("src.web.routes.api.run_async", side_effect=_run_sync):
        with app.test_client() as test_client:
            with test_client.session_transaction() as session:
                session["discord_id"] = VIEWER_ID
                session["current_server_id"] = SERVER_ID
            yield test_client
