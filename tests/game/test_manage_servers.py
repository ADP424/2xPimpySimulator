"""Tests for src/game/manage_servers.py — server CRUD and event channel."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.game import (
    get_event_channel,
    get_or_create_server,
    get_server,
    list_servers,
    set_event_channel,
)
from tests.conftest import make_server

# ---------------------------------------------------------------------------
# get_or_create_server
# ---------------------------------------------------------------------------


class TestGetOrCreateServer:
    @patch("src.game.manage_servers.to_server", new_callable=AsyncMock)
    @patch("src.game.manage_servers.get_server_by_discord_id", new_callable=AsyncMock)
    async def test_returns_existing_server(self, mock_get, mock_to):
        server = make_server(discord_id=200)
        mock_get.return_value = server
        mock_to.return_value = SimpleNamespace(discord_id=200)

        result = await get_or_create_server(200)
        assert result.discord_id == 200

    @patch("src.game.manage_servers.to_server", new_callable=AsyncMock)
    @patch("src.game.manage_servers.create_server", new_callable=AsyncMock)
    @patch("src.game.manage_servers.get_server_by_discord_id", new_callable=AsyncMock)
    async def test_creates_new_server(self, mock_get, mock_create, mock_to):
        mock_get.return_value = None
        new_server = make_server(discord_id=200)
        mock_create.return_value = new_server
        mock_to.return_value = SimpleNamespace(discord_id=200)

        result = await get_or_create_server(200)

        mock_create.assert_awaited_once_with(200)
        assert result.discord_id == 200

    @patch("src.game.manage_servers.to_server", new_callable=AsyncMock)
    @patch("src.game.manage_servers.get_server_by_discord_id", new_callable=AsyncMock)
    async def test_idempotent(self, mock_get, mock_to):
        """Calling twice with the same ID just returns the same server."""
        server = make_server(discord_id=200)
        mock_get.return_value = server
        mock_to.return_value = SimpleNamespace(discord_id=200)

        r1 = await get_or_create_server(200)
        r2 = await get_or_create_server(200)
        assert r1.discord_id == r2.discord_id


# ---------------------------------------------------------------------------
# get_event_channel
# ---------------------------------------------------------------------------


class TestGetEventChannel:
    @patch("src.game.manage_servers.get_server_by_discord_id", new_callable=AsyncMock)
    async def test_returns_channel_id(self, mock_get):
        mock_get.return_value = make_server(discord_id=200, event_channel_discord_id=12345)

        result = await get_event_channel(200)
        assert result == 12345

    @patch("src.game.manage_servers.get_server_by_discord_id", new_callable=AsyncMock)
    async def test_returns_none_if_no_channel(self, mock_get):
        mock_get.return_value = make_server(discord_id=200, event_channel_discord_id=None)

        result = await get_event_channel(200)
        assert result is None

    @patch("src.game.manage_servers.get_server_by_discord_id", new_callable=AsyncMock)
    async def test_returns_none_if_server_not_found(self, mock_get):
        mock_get.return_value = None

        result = await get_event_channel(200)
        assert result is None


# ---------------------------------------------------------------------------
# set_event_channel
# ---------------------------------------------------------------------------


class TestSetEventChannel:
    @patch("src.game.manage_servers.set_event_channel_discord_id", new_callable=AsyncMock)
    async def test_delegates_to_db(self, mock_set):
        await set_event_channel(200, 12345)
        mock_set.assert_awaited_once_with(200, 12345)

    @patch("src.game.manage_servers.set_event_channel_discord_id", new_callable=AsyncMock)
    async def test_can_set_different_channels(self, mock_set):
        await set_event_channel(200, 11111)
        await set_event_channel(200, 22222)
        assert mock_set.call_count == 2


# ---------------------------------------------------------------------------
# get_server / list_servers
# ---------------------------------------------------------------------------


class TestGetServer:
    @patch("src.game.manage_servers.get_server_by_discord_id", new_callable=AsyncMock)
    async def test_returns_converted_server(self, mock_get):
        mock_get.return_value = make_server(discord_id=200)

        result = await get_server(200)

        assert result.discord_id == 200
        mock_get.assert_awaited_once_with(200)

    @patch("src.game.manage_servers.create_server", new_callable=AsyncMock)
    @patch("src.game.manage_servers.get_server_by_discord_id", new_callable=AsyncMock)
    async def test_returns_none_without_creating(self, mock_get, mock_create):
        mock_get.return_value = None

        assert await get_server(200) is None
        mock_create.assert_not_awaited()


class TestListServers:
    @patch("src.game.manage_servers.db_list_servers", new_callable=AsyncMock)
    async def test_converts_every_server(self, mock_list):
        mock_list.return_value = [make_server(discord_id=1), make_server(discord_id=2)]

        result = await list_servers()

        assert [s.discord_id for s in result] == [1, 2]
