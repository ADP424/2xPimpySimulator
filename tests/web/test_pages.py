"""Smoke test: every page added or changed for bot parity renders (Jinja compiles, url_for targets exist)."""

from unittest.mock import AsyncMock, patch

import pytest

from src.web.app import create_app

PAGES = [
    "/events/",
    "/events/server",
    "/info/clinic",
    "/info/clinic/patients",
    "/info/clinic/patients/1",
    "/info/injuries",
    "/info/injuries/1",
    "/info/diseases",
    "/info/diseases/1",
    "/pooch/1",
    "/kennel/1",
    "/kennel/1/breed",
    "/auction/sale/1",
    "/auction/create-sale",
]


@pytest.fixture(scope="module")
def page_client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["discord_id"] = 1
            session["current_server_id"] = 100
            session["current_server_name"] = "Test Server"
        yield client


@pytest.mark.parametrize("path", PAGES)
def test_page_renders(page_client, path):
    resp = page_client.get(path)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]


def test_town_shows_season_and_event_links(page_client):
    with patch("src.game.get_season", new=AsyncMock(return_value="autumn")):
        resp = page_client.get("/town")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "🍂🍁 It's currently <strong>Autumn</strong>." in body
    assert 'href="/events/server"' in body and 'href="/events/"' in body


def test_home_has_bones_and_events(page_client):
    with patch("src.game.list_servers", new=AsyncMock(return_value=[])):
        resp = page_client.get("/home")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'id="owner-bones"' in body and 'id="nav-bones"' in body
    assert 'href="/events/"' in body
