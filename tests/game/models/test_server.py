from unittest.mock import MagicMock

import pytest

from src.game.models.server import Server, to_server


class TestServerCreation:
    def test_basic_creation(self):
        server = Server(discord_id=111222333, event_channel_discord_id=444555666)
        assert server.discord_id == 111222333
        assert server.event_channel_discord_id == 444555666

    def test_frozen(self):
        server = Server(discord_id=1, event_channel_discord_id=2)
        with pytest.raises(AttributeError):
            server.discord_id = 999  # type: ignore[misc]

    def test_equality(self):
        s1 = Server(discord_id=1, event_channel_discord_id=2)
        s2 = Server(discord_id=1, event_channel_discord_id=2)
        assert s1 == s2

    def test_inequality(self):
        s1 = Server(discord_id=1, event_channel_discord_id=2)
        s2 = Server(discord_id=1, event_channel_discord_id=3)
        assert s1 != s2


class TestToServer:
    async def test_converts_orm_to_server(self):
        orm = MagicMock()
        orm.discord_id = 12345
        orm.event_channel_discord_id = 67890

        result = await to_server(orm)
        assert isinstance(result, Server)
        assert result.discord_id == 12345
        assert result.event_channel_discord_id == 67890
