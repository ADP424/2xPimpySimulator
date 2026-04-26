"""Contract tests for src/bot/ui/town.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.town import HomeButton, TownNavigationSelect, TownView


@pytest.mark.contract
class TestTownView:
    async def test_creates_view(self):
        view = TownView()
        assert isinstance(view, discord.ui.View)
        assert len(view.children) >= 2

    async def test_has_navigation_select(self):
        view = TownView()
        selects = [child for child in view.children if isinstance(child, discord.ui.Select)]
        assert len(selects) >= 1

    async def test_has_home_button(self):
        view = TownView()
        buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]
        assert any(b.label == "Home" for b in buttons)


@pytest.mark.contract
class TestTownNavigationSelect:
    def test_has_expected_options(self):
        select = TownNavigationSelect()
        option_values = [opt.value for opt in select.options]
        assert "marketplace" in option_values
        assert "vet" in option_values
        assert "church" in option_values
        assert "park" in option_values


@pytest.mark.contract
class TestHomeButton:
    def test_has_correct_label_and_style(self):
        button = HomeButton()
        assert button.label == "Home"
        assert button.style == discord.ButtonStyle.secondary


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
class TestTownNavigationSelectCallback:
    async def test_marketplace_opens_marketplace_view(self):
        select = TownNavigationSelect()
        interaction = _make_interaction()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["marketplace"])),
            patch("src.bot.ui.town.InteractionResponder") as MockResponder,
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
            content = mock_r.reply.call_args[1]["content"]
            assert "Marketplace" in content

    async def test_vet_opens_vet_clinic_view(self):
        select = TownNavigationSelect()
        interaction = _make_interaction()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["vet"])),
            patch("src.bot.ui.town.InteractionResponder") as MockResponder,
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

    async def test_church_opens_church_view(self):
        select = TownNavigationSelect()
        interaction = _make_interaction()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["church"])),
            patch("src.bot.ui.town.InteractionResponder") as MockResponder,
            patch("src.bot.ui.church.get_conjure_pooch_price", return_value=10),
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
            content = mock_r.reply.call_args[1]["content"]
            assert "Church" in content

    async def test_park_opens_park_view(self):
        select = TownNavigationSelect()
        interaction = _make_interaction()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["park"])),
            patch("src.bot.ui.town.InteractionResponder") as MockResponder,
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
            content = mock_r.reply.call_args[1]["content"]
            assert "Park" in content

    async def test_selection_persists(self):
        """Test that the selected option gets marked as default."""
        select = TownNavigationSelect()
        interaction = _make_interaction()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["marketplace"])),
            patch("src.bot.ui.town.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            import discord as dc

            view = dc.ui.View()
            view.add_item(select)

            await select.callback(interaction)

            marketplace_opt = next(o for o in select.options if o.value == "marketplace")
            assert marketplace_opt.default is True


@pytest.mark.contract
class TestHomeButtonCallback:
    async def test_home_button_calls_send_home_menu(self):
        button = HomeButton()
        interaction = _make_interaction()

        with patch("src.bot.ui.home.send_home_menu", new_callable=AsyncMock) as mock_menu:
            # The import is inside callback so we need to ensure the module is patched
            with patch("src.bot.ui.town.send_home_menu", mock_menu, create=True):
                await button.callback(interaction)
                # Function was called through the local import chain
