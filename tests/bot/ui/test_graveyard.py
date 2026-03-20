"""Contract tests for src/bot/ui/graveyard.py."""

from datetime import datetime, timezone
from math import ceil
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.ui.graveyard import GraveyardPageSource


def _make_pooch(id=1, name="Ghost"):
    pooch = MagicMock()
    pooch.id = id
    pooch.name = name
    return pooch


@pytest.mark.contract
class TestGraveyardPageSource:
    async def test_empty_graveyard(self):
        with patch("src.bot.ui.graveyard.list_graveyard_pooches", new_callable=AsyncMock, return_value=[]):
            source = GraveyardPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "No headstones" in embed.description

    async def test_page_count(self):
        rows = [(_make_pooch(id=i), datetime(2024, 1, i, tzinfo=timezone.utc)) for i in range(1, 16)]
        with patch("src.bot.ui.graveyard.list_graveyard_pooches", new_callable=AsyncMock, return_value=rows):
            source = GraveyardPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()
            assert source.page_count() == ceil(15 / 10)

    async def test_render_page_includes_names(self):
        rows = [
            (_make_pooch(id=1, name="Fluffy"), datetime(2024, 3, 15, tzinfo=timezone.utc)),
            (_make_pooch(id=2, name="Bones"), datetime(2024, 4, 20, tzinfo=timezone.utc)),
        ]
        with patch("src.bot.ui.graveyard.list_graveyard_pooches", new_callable=AsyncMock, return_value=rows):
            source = GraveyardPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Fluffy" in embed.description
            assert "Bones" in embed.description
            assert content == "**Your Graveyard**"

    async def test_render_includes_burial_date(self):
        buried = datetime(2024, 6, 15, tzinfo=timezone.utc)
        rows = [(_make_pooch(id=1, name="Spot"), buried)]
        with patch("src.bot.ui.graveyard.list_graveyard_pooches", new_callable=AsyncMock, return_value=rows):
            source = GraveyardPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "2024-06-15" in embed.description

    async def test_render_adds_select_control(self):
        rows = [(_make_pooch(id=1, name="Rex"), datetime(2024, 1, 1, tzinfo=timezone.utc))]
        with patch("src.bot.ui.graveyard.list_graveyard_pooches", new_callable=AsyncMock, return_value=rows):
            source = GraveyardPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            await source.render(view, 0)
            # _GraveyardControls.attach calls view.add_item
            assert view.add_item.called
