"""Tests for the web ownership checks in src/web/auth_utils.py."""

from unittest.mock import AsyncMock, patch

import pytest
from flask import Flask, session
from werkzeug.exceptions import HTTPException

from src.web.auth_utils import require_kennel_owner, require_pooch_owner


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test"
    return app


def _abort_code(check, target_id):
    with pytest.raises(HTTPException) as ctx:
        check(target_id)
    return ctx.value.code


@pytest.mark.parametrize(
    ("check", "game_fn"),
    [(require_pooch_owner, "src.game.owns_pooch"), (require_kennel_owner, "src.game.owns_kennel")],
)
class TestRequireOwnership:
    def test_unauthenticated_aborts_401(self, app, check, game_fn):
        with app.test_request_context():
            assert _abort_code(check, 1) == 401

    def test_missing_aborts_404(self, app, check, game_fn):
        with app.test_request_context(), patch(game_fn, new=AsyncMock(return_value=None)):
            session["discord_id"] = 100
            assert _abort_code(check, 1) == 404

    def test_wrong_owner_aborts_403(self, app, check, game_fn):
        with app.test_request_context(), patch(game_fn, new=AsyncMock(return_value=False)) as owns:
            session["discord_id"] = 100
            assert _abort_code(check, 1) == 403
        owns.assert_awaited_once_with(100, 1)

    def test_owner_passes(self, app, check, game_fn):
        with app.test_request_context(), patch(game_fn, new=AsyncMock(return_value=True)):
            session["discord_id"] = 100
            assert check(1) is None
