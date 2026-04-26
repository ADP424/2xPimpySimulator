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


@pytest.mark.asyncio
async def test_get_active_server_event_none():
    """
    Test get active server event none.

    Returns
    -------
    Any
        The result of calling `test_get_active_server_event_none`.
    """

    from src.game.events.server_events import get_active_server_event

    with patch(f"{MOD}.get_active_server_event_occurrence", new=AsyncMock(return_value=None)):
        result = await get_active_server_event(100)

    assert result is None


@pytest.mark.asyncio
async def test_get_active_server_event_returns_triggered():
    """
    Test get active server event returns triggered.

    Returns
    -------
    Any
        The result of calling `test_get_active_server_event_returns_triggered`.
    """

    from src.game.events.server_events import get_active_server_event

    mock_occ = MagicMock()
    mock_triggered = MagicMock()

    with (
        patch(f"{MOD}.get_active_server_event_occurrence", new=AsyncMock(return_value=mock_occ)),
        patch(f"{MOD}.to_triggered_server_event", new=AsyncMock(return_value=mock_triggered)),
    ):
        result = await get_active_server_event(100)

    assert result is mock_triggered


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
