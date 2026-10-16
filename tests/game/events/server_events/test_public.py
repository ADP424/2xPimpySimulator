"""Tests for src/game/events/server_events/public.py."""

from __future__ import annotations

import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MOD = "src.game.events.server_events.public"


@pytest.fixture
def rng() -> random.Random:
    """
    Rng.

    Returns
    -------
    Any
        The result of calling `rng`.
    """

    return random.Random(42)


# ---------------------------------------------------------------------------
# get_active_server_event
# ---------------------------------------------------------------------------


def _occurrence(server_discord_id=100, archived=False, resolved_at=None):
    occ = MagicMock()
    occ.server_discord_id = server_discord_id
    occ.archived = archived
    occ.resolved_at = resolved_at
    return occ


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "occurrence",
    [None, _occurrence(server_discord_id=999), _occurrence(archived=True), _occurrence(resolved_at="2026-10-15")],
    ids=["missing", "other server", "archived", "resolved"],
)
async def test_get_active_server_event_none_unless_active_on_that_server(occurrence):
    from src.game.events.server_events import get_active_server_event

    with patch(f"{MOD}.get_server_event_occurrence_by_id", new=AsyncMock(return_value=occurrence)):
        assert await get_active_server_event(server_discord_id=100, occurrence_id=7) is None


@pytest.mark.asyncio
async def test_get_active_server_event_returns_that_occurrence():
    from src.game.events.server_events import get_active_server_event

    occ = _occurrence()
    mock_triggered = MagicMock()
    with (
        patch(f"{MOD}.get_server_event_occurrence_by_id", new=AsyncMock(return_value=occ)) as fetch,
        patch(f"{MOD}.to_triggered_server_event", new=AsyncMock(return_value=mock_triggered)) as convert,
    ):
        result = await get_active_server_event(server_discord_id=100, occurrence_id=7, viewer_owner_discord_id=5)

    assert result is mock_triggered
    fetch.assert_awaited_once_with(7)
    convert.assert_awaited_once_with(occ, 5)


# ---------------------------------------------------------------------------
# list_active_server_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_server_events_empty():
    """
    Test list active server events empty.

    Returns
    -------
    Any
        The result of calling `test_list_active_server_events_empty`.
    """

    from src.game.events.server_events import list_active_server_events

    with patch(f"{MOD}.list_active_server_event_occurrences", new=AsyncMock(return_value=[])):
        result = await list_active_server_events()

    assert result == []


@pytest.mark.asyncio
async def test_list_active_server_events_converts_all():
    """
    Test list active server events converts all.

    Returns
    -------
    Any
        The result of calling `test_list_active_server_events_converts_all`.
    """

    from src.game.events.server_events import list_active_server_events

    mock_occ = MagicMock()
    mock_triggered = MagicMock()

    with (
        patch(f"{MOD}.list_active_server_event_occurrences", new=AsyncMock(return_value=[mock_occ])),
        patch(f"{MOD}.to_triggered_server_event", new=AsyncMock(return_value=mock_triggered)),
    ):
        result = await list_active_server_events()

    assert result == [mock_triggered]


@pytest.mark.asyncio
async def test_list_active_server_events_for_one_server_lists_every_tier():
    """A server can have a minor (daily) and a major (weekly) event at once; both are listed for the viewer."""
    from src.game.events.server_events import list_active_server_events

    minor, major = MagicMock(), MagicMock()
    with (
        patch(f"{MOD}.list_active_server_event_occurrences", new=AsyncMock(return_value=[minor, major])) as fetch,
        patch(f"{MOD}.to_triggered_server_event", new=AsyncMock(side_effect=lambda occ, viewer: (occ, viewer))),
    ):
        result = await list_active_server_events(100, 5)

    fetch.assert_awaited_once_with(100)
    assert result == [(minor, 5), (major, 5)]


# ---------------------------------------------------------------------------
# set_server_event_message_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_server_event_message_id():
    """
    Test set server event message id.

    Returns
    -------
    Any
        The result of calling `test_set_server_event_message_id`.
    """

    from src.game.events.server_events import set_server_event_message_id

    with patch(f"{MOD}.set_server_event_occurrence_message_discord_id", new=AsyncMock()) as mock_set:
        await set_server_event_message_id(42, 12345)

    mock_set.assert_awaited_once_with(42, 12345)


# ---------------------------------------------------------------------------
# participate_in_server_event — occurrence not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_participate_no_active_event():
    """
    Test participate no active event.

    Returns
    -------
    Any
        The result of calling `test_participate_no_active_event`.
    """

    from src.game.events.server_events import participate_in_server_event

    with patch(f"{MOD}.get_server_event_occurrence_by_id", new=AsyncMock(return_value=None)):
        success, msg, summary = await participate_in_server_event(
            occurrence_id=1,
            server_discord_id=100,
            owner_discord_id=1,
            menu_option_id=1,
        )

    assert not success
    assert summary is None


def _participation_patches(option: MagicMock):
    """Patch everything participate_in_server_event touches before its filter checks."""
    from datetime import datetime, timedelta, timezone

    occurrence = MagicMock(
        server_discord_id=100,
        server_event_id=7,
        archived=False,
        resolved_at=None,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    return [
        patch(f"{MOD}.get_server_event_occurrence_by_id", new=AsyncMock(return_value=occurrence)),
        patch(f"{MOD}.get_or_create_owner", new=AsyncMock()),
        patch(f"{MOD}.get_owner_server", new=AsyncMock(return_value=MagicMock())),
        patch(f"{MOD}.get_server_event_menu_option_by_id", new=AsyncMock(return_value=option)),
        patch(f"{MOD}.get_server_event_participation", new=AsyncMock(return_value=None)),
    ]


def _make_option(filter_spec=None, requires=None) -> MagicMock:
    menu = MagicMock(server_event_id=7, depends_on=[], max_uses_per_player=-1)
    return MagicMock(menu=menu, filter=filter_spec, requires=requires)


@pytest.mark.asyncio
async def test_participate_owner_filter_not_met():
    """An owner who fails the option filter is rejected via the database filter wrapper."""
    from contextlib import ExitStack

    from src.game.events.server_events import participate_in_server_event

    option = _make_option(filter_spec={"min_dollars": 1000})
    with ExitStack() as stack:
        for p in _participation_patches(option):
            stack.enter_context(p)
        mock_check = stack.enter_context(
            patch(f"{MOD}.check_owner_event_filter_for_owner", new=AsyncMock(return_value=False))
        )
        success, msg, summary = await participate_in_server_event(
            occurrence_id=1, server_discord_id=100, owner_discord_id=1, menu_option_id=1
        )

    assert not success
    assert msg == "You do not meet the requirements for that option."
    assert summary is None
    mock_check.assert_awaited_once_with(1, {"min_dollars": 1000})


@pytest.mark.asyncio
async def test_participate_pooch_filter_not_met():
    """A selected pooch outside the option's pooch filter is rejected via the database list wrapper."""
    from contextlib import ExitStack

    from src.game.events.server_events import participate_in_server_event

    option = _make_option(requires={"pooch": {"filter": {"min_age": 5}}})
    with ExitStack() as stack:
        for p in _participation_patches(option):
            stack.enter_context(p)
        stack.enter_context(
            patch(f"{MOD}.db_get_pooch_by_id", new=AsyncMock(return_value=MagicMock(owner_discord_id=1)))
        )
        mock_list = stack.enter_context(patch(f"{MOD}.list_matching_pooch_ids", new=AsyncMock(return_value=[2, 3])))
        success, msg, summary = await participate_in_server_event(
            occurrence_id=1, server_discord_id=100, owner_discord_id=1, menu_option_id=1, selected_pooch_id=9
        )

    assert not success
    assert msg == "That pooch does not meet the requirements."
    assert summary is None
    mock_list.assert_awaited_once_with(1, {"min_age": 5})
