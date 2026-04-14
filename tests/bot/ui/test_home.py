"""Contract tests for src/bot/ui/home.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui import (
    HomeNavigationSelect,
    HomeView,
    TownButton,
    build_home_content,
)


def _make_owner(discord_id=100, dollars=500, bloodskulls=3, bones=1):
    owner = MagicMock()
    owner.discord_id = discord_id
    owner.dollars = dollars
    owner.bloodskulls = bloodskulls
    owner.bones = bones
    return owner


def _make_interaction(user_id=100, guild_id=200, response_done=False):
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.guild_id = guild_id
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=response_done)
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.channel = MagicMock()
    interaction.channel.send = AsyncMock()
    interaction.message = None
    return interaction


@pytest.mark.contract
class TestBuildHomeContent:
    async def test_includes_dollars(self):
        owner = _make_owner(dollars=500)
        with patch("src.bot.ui.home.get_or_create_owner", new_callable=AsyncMock, return_value=owner):
            content = await build_home_content(guild_id=200, user_id=100)
            assert "$500" in content

    async def test_includes_bloodskulls(self):
        owner = _make_owner(bloodskulls=7)
        with patch("src.bot.ui.home.get_or_create_owner", new_callable=AsyncMock, return_value=owner):
            content = await build_home_content(guild_id=200, user_id=100)
            assert "**7**" in content
            assert "bloodskulls" in content

    async def test_includes_bones(self):
        owner = _make_owner(bones=2)
        with patch("src.bot.ui.home.get_or_create_owner", new_callable=AsyncMock, return_value=owner):
            content = await build_home_content(guild_id=200, user_id=100)
            assert "**2**" in content
            assert "bone" in content

    async def test_includes_mention(self):
        owner = _make_owner(discord_id=100)
        with patch("src.bot.ui.home.get_or_create_owner", new_callable=AsyncMock, return_value=owner):
            content = await build_home_content(guild_id=200, user_id=100)
            assert "<@100>" in content


@pytest.mark.contract
class TestHomeView:
    async def test_creates_view_with_children(self):
        view = HomeView()
        assert isinstance(view, discord.ui.View)
        # Should have at least the navigation select and town button
        assert len(view.children) >= 2

    async def test_has_navigation_select(self):
        view = HomeView()
        selects = [child for child in view.children if isinstance(child, discord.ui.Select)]
        assert len(selects) >= 1

    async def test_has_town_button(self):
        view = HomeView()
        buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]
        assert any(b.label == "Town" for b in buttons)


@pytest.mark.contract
class TestHomeNavigationSelect:
    def test_has_kennels_and_graveyard_options(self):
        select = HomeNavigationSelect()
        option_values = [opt.value for opt in select.options]
        assert "kennels" in option_values
        assert "graveyard" in option_values


@pytest.mark.contract
class TestTownButton:
    def test_has_correct_label(self):
        button = TownButton()
        assert button.label == "Town"
        assert button.style == discord.ButtonStyle.primary

    async def test_town_button_replies_with_town_view(self):
        button = TownButton()
        interaction = _make_interaction()

        with patch("src.bot.ui.home.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await button.callback(interaction)
            mock_r.reply.assert_called_once()
            content = mock_r.reply.call_args[1]["content"]
            assert "Town" in content


@pytest.mark.contract
class TestSendHomeMenu:
    async def test_requires_guild(self):
        from src.bot.ui import send_home_menu

        interaction = _make_interaction(guild_id=None)

        with patch("src.bot.ui.home.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await send_home_menu(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "server" in msg.lower()

    async def test_sends_home_content_with_view(self):
        from src.bot.ui import send_home_menu

        owner = _make_owner(dollars=123, bloodskulls=2, bones=1)
        interaction = _make_interaction(user_id=100, guild_id=200)

        with (
            patch("src.bot.ui.home.get_or_create_owner", new_callable=AsyncMock, return_value=owner),
            patch("src.bot.ui.home.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await send_home_menu(interaction)
            call_kwargs = mock_r.reply.call_args[1]
            assert "content" in call_kwargs
            assert "$123" in call_kwargs["content"]
            assert "view" in call_kwargs


@pytest.mark.contract
class TestHomeNavigationSelectCallback:
    async def test_kennels_navigation(self):
        select = HomeNavigationSelect()
        interaction = _make_interaction(user_id=100, guild_id=200)

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["kennels"])),
            patch("src.bot.ui.kennels.list_owner_kennels", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.home.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            # Attach to a view so select.view is not None
            import discord as dc

            view = dc.ui.View()
            view.add_item(select)

            await select.callback(interaction)
            mock_r.reply.assert_called_once()

    async def test_graveyard_navigation(self):
        select = HomeNavigationSelect()
        interaction = _make_interaction(user_id=100, guild_id=200)

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["graveyard"])),
            patch("src.bot.ui.graveyard.list_graveyard_pooches", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.home.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            import discord as dc

            view = dc.ui.View()
            view.add_item(select)

            await select.callback(interaction)
            mock_r.reply.assert_called_once()
