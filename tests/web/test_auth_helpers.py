"""Tests for the web ownership-check helpers in src/web/auth_utils.py."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask
from werkzeug.exceptions import HTTPException

from src.web.auth_utils import (
    require_kennel_owner,
    require_owner,
    require_pooch_owner,
    require_server_visible_pooch,
)


@pytest.fixture
def app_with_session():
    app = Flask(__name__)
    app.secret_key = "test"
    return app


def _make_pooch(owner_id=100):
    return SimpleNamespace(id=1, owner_discord_id=owner_id)


def _make_kennel(owner_id=100):
    return SimpleNamespace(id=10, owner_discord_id=owner_id)


class TestRequirePoochOwner:
    def test_unauthenticated_aborts_401(self, app_with_session):
        with app_with_session.test_request_context():
            with pytest.raises(HTTPException) as ctx:
                require_pooch_owner(1)
            assert ctx.value.code == 401

    def test_pooch_not_found_aborts_404(self, app_with_session):
        with app_with_session.test_request_context():
            from flask import session

            session["discord_id"] = 100
            with patch("src.web.async_utils.run_async", return_value=None):
                with pytest.raises(HTTPException) as ctx:
                    require_pooch_owner(1)
                assert ctx.value.code == 404

    def test_wrong_owner_aborts_403(self, app_with_session):
        with app_with_session.test_request_context():
            from flask import session

            session["discord_id"] = 100
            pooch = _make_pooch(owner_id=999)
            with patch("src.web.async_utils.run_async", return_value=pooch):
                with pytest.raises(HTTPException) as ctx:
                    require_pooch_owner(1)
                assert ctx.value.code == 403

    def test_correct_owner_returns_pooch(self, app_with_session):
        with app_with_session.test_request_context():
            from flask import session

            session["discord_id"] = 100
            pooch = _make_pooch(owner_id=100)
            with patch("src.web.async_utils.run_async", return_value=pooch):
                result = require_pooch_owner(1)
                assert result is pooch


class TestRequireKennelOwner:
    def test_correct_owner_returns_kennel(self, app_with_session):
        with app_with_session.test_request_context():
            from flask import session

            session["discord_id"] = 100
            kennel = _make_kennel(owner_id=100)
            with patch("src.web.async_utils.run_async", return_value=kennel):
                result = require_kennel_owner(10)
                assert result is kennel

    def test_wrong_owner_aborts_403(self, app_with_session):
        with app_with_session.test_request_context():
            from flask import session

            session["discord_id"] = 100
            kennel = _make_kennel(owner_id=999)
            with patch("src.web.async_utils.run_async", return_value=kennel):
                with pytest.raises(HTTPException) as ctx:
                    require_kennel_owner(10)
                assert ctx.value.code == 403


class TestRequireOwner:
    def test_matches_session(self, app_with_session):
        with app_with_session.test_request_context():
            from flask import session

            session["discord_id"] = 100
            assert require_owner(100) == 100

    def test_mismatch_aborts_403(self, app_with_session):
        with app_with_session.test_request_context():
            from flask import session

            session["discord_id"] = 100
            with pytest.raises(HTTPException) as ctx:
                require_owner(999)
            assert ctx.value.code == 403


class TestRequireServerVisiblePooch:
    def test_owner_can_always_see_own_pooch(self, app_with_session):
        with app_with_session.test_request_context():
            from flask import session

            session["discord_id"] = 100
            pooch = _make_pooch(owner_id=100)
            with patch("src.web.async_utils.run_async", return_value=pooch):
                assert require_server_visible_pooch(1) is pooch
