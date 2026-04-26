"""Contract tests for src/bot/ui/components/paginator.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.components.paginator import PaginatorView


class FakePageSource:
    """A minimal PageSource implementation for testing."""

    def __init__(self, pages: list[tuple[str | None, discord.Embed | None]]):
        self._pages = pages
        self._loaded = False

    async def load(self):
        self._loaded = True

    def page_count(self) -> int:
        return max(len(self._pages), 1)

    async def render(self, view, page_index):
        if not self._pages:
            return None, discord.Embed(title="Empty")
        idx = max(0, min(page_index, len(self._pages) - 1))
        return self._pages[idx]


@pytest.mark.contract
class TestPaginatorView:
    async def test_creates_view(self):
        source = FakePageSource([("Page 1", discord.Embed(title="P1"))])
        view = PaginatorView(source, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_has_prev_and_next_buttons(self):
        source = FakePageSource([("P1", None)])
        view = PaginatorView(source, owner_discord_id=100)
        labels = [child.label for child in view.children if isinstance(child, discord.ui.Button)]
        assert "\u25c0" in labels  # prev
        assert "\u25b6" in labels  # next

    async def test_build_first_page_loads_source(self):
        source = FakePageSource([("Hello", discord.Embed(title="Page"))])
        view = PaginatorView(source, owner_discord_id=100)
        content, embed = await view.build_first_page()
        assert source._loaded is True
        assert content == "Hello"
        assert embed.title == "Page"

    async def test_build_first_page_empty_source(self):
        source = FakePageSource([])
        view = PaginatorView(source, owner_discord_id=100)
        content, embed = await view.build_first_page()
        assert embed.title == "Empty"

    async def test_prev_disabled_on_first_page(self):
        source = FakePageSource([("P1", None), ("P2", None)])
        view = PaginatorView(source, owner_discord_id=100)
        await view.build_first_page()
        assert view._prev.disabled is True
        assert view._next.disabled is False

    async def test_next_disabled_on_last_page(self):
        pages = [("P1", None), ("P2", None)]
        source = FakePageSource(pages)
        view = PaginatorView(source, owner_discord_id=100)
        await view.build_first_page()
        # Manually move to last page
        view._page = 1
        view._clamp_page()
        view._update_nav_disabled()
        assert view._next.disabled is True
        assert view._prev.disabled is False

    async def test_both_disabled_on_single_page(self):
        source = FakePageSource([("Only page", None)])
        view = PaginatorView(source, owner_discord_id=100)
        await view.build_first_page()
        assert view._prev.disabled is True
        assert view._next.disabled is True

    async def test_interaction_check_owner_only(self):
        source = FakePageSource([("P", None)])
        view = PaginatorView(source, owner_discord_id=100)

        interaction_owner = MagicMock()
        interaction_owner.user = MagicMock()
        interaction_owner.user.id = 100
        assert await view.interaction_check(interaction_owner) is True

        interaction_other = MagicMock()
        interaction_other.user = MagicMock()
        interaction_other.user.id = 999
        assert await view.interaction_check(interaction_other) is False

    async def test_on_next_increments_page(self):
        pages = [("P1", discord.Embed(title="1")), ("P2", discord.Embed(title="2"))]
        source = FakePageSource(pages)
        view = PaginatorView(source, owner_discord_id=100)
        await view.build_first_page()
        assert view._page == 0

        # Simulate pressing next
        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.edit_message = AsyncMock()
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()

        with patch("src.bot.ui.components.paginator.edit_interaction", new_callable=AsyncMock):
            await view._on_next(interaction)
        assert view._page == 1

    async def test_on_prev_decrements_page(self):
        pages = [("P1", discord.Embed(title="1")), ("P2", discord.Embed(title="2"))]
        source = FakePageSource(pages)
        view = PaginatorView(source, owner_discord_id=100)
        await view.build_first_page()
        view._page = 1

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.edit_message = AsyncMock()
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()

        with patch("src.bot.ui.components.paginator.edit_interaction", new_callable=AsyncMock):
            await view._on_prev(interaction)
        assert view._page == 0
