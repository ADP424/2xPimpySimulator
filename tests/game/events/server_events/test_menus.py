"""Tests for src/game/events/server_events/menus.py."""

from __future__ import annotations

from types import SimpleNamespace

from src.game.events.server_events import (
    get_menu_uses_left,
    get_missing_menu_prerequisite,
    get_use_count_per_menu,
    get_used_menu_names,
    is_menu_exhausted,
    menu_is_available,
)


def _menu(name="enter", depends_on=None, max_uses_per_player=-1):
    return SimpleNamespace(name=name, depends_on=depends_on, max_uses_per_player=max_uses_per_player)


SUBMISSIONS = [{"menu_name": "enter"}, {"menu_name": "boost"}, {"menu_name": "boost"}]


class TestSubmissionSummaries:
    def test_used_menu_names(self):
        assert get_used_menu_names(SUBMISSIONS) == {"enter", "boost"}

    def test_used_menu_names_none(self):
        assert get_used_menu_names(None) == set()

    def test_use_count_per_menu(self):
        assert get_use_count_per_menu(SUBMISSIONS) == {"enter": 1, "boost": 2}

    def test_use_count_per_menu_none(self):
        assert get_use_count_per_menu(None) == {}


class TestMenuRules:
    def test_missing_prerequisite(self):
        assert get_missing_menu_prerequisite(_menu(depends_on=["enter", "boost"]), {"enter"}) == "boost"

    def test_no_missing_prerequisite_when_depends_on_is_none(self):
        assert get_missing_menu_prerequisite(_menu(depends_on=None), set()) is None

    def test_exhausted(self):
        assert is_menu_exhausted(_menu(name="boost", max_uses_per_player=2), {"boost": 2}) is True

    def test_unlimited_never_exhausted(self):
        assert is_menu_exhausted(_menu(max_uses_per_player=-1), {"enter": 999}) is False

    def test_uses_left(self):
        assert get_menu_uses_left(_menu(name="boost", max_uses_per_player=3), {"boost": 1}) == 2

    def test_uses_left_unlimited(self):
        assert get_menu_uses_left(_menu(max_uses_per_player=-1), {}) is None

    def test_available(self):
        assert menu_is_available(_menu(name="boost", depends_on=["enter"], max_uses_per_player=1), {"enter"}, {})

    def test_unavailable_when_prerequisite_missing(self):
        assert not menu_is_available(_menu(depends_on=["enter"]), set(), {})

    def test_unavailable_when_exhausted(self):
        assert not menu_is_available(_menu(max_uses_per_player=1), {"enter"}, {"enter": 1})
