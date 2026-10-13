"""Smoke test: every page added or changed for bot parity renders (Jinja compiles, url_for targets exist)."""

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
