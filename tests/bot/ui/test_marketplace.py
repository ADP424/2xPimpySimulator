"""Contract tests for src/bot/ui/marketplace.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.marketplace import ConstructionCompanyView, MarketplaceView


@pytest.mark.contract
class TestMarketplaceView:
    async def test_creates_view(self):
        view = MarketplaceView(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_has_select_and_town_button(self):
        view = MarketplaceView(server_discord_id=200, owner_discord_id=100)
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert len(selects) >= 1
        assert any(b.label == "Town" for b in buttons)

    async def test_interaction_check_owner_only(self):
        view = MarketplaceView(server_discord_id=200, owner_discord_id=100)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True

        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False


@pytest.mark.contract
class TestConstructionCompanyView:
    async def test_creates_view(self):
        view = ConstructionCompanyView(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_interaction_check(self):
        view = ConstructionCompanyView(server_discord_id=200, owner_discord_id=100)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True

        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False

    async def test_build_embed(self):
        from src.game.models.kennel import Kennel
        from src.game.models.owner import Owner

        mock_owner = Owner(discord_id=100, discord_name="Test", dollars=500, bloodskulls=0, bones=0)
        mock_kennels = [Kennel(id=1, owner_discord_id=100, name="Kennel 1", pooch_limit=5, owner=None)]

        with (
            patch("src.bot.ui.marketplace.list_owner_kennels", new_callable=AsyncMock, return_value=mock_kennels),
            patch("src.bot.ui.marketplace.get_or_create_owner", new_callable=AsyncMock, return_value=mock_owner),
            patch("src.bot.ui.marketplace.get_kennel_buy_price", new_callable=AsyncMock, return_value=(200, "$200")),
            patch(
                "src.bot.ui.marketplace.get_kennel_upgrade_price", new_callable=AsyncMock, return_value=(100, "$100")
            ),
        ):
            view = ConstructionCompanyView(server_discord_id=200, owner_discord_id=100)
            embed = await view.build_embed()

            assert isinstance(embed, discord.Embed)
            assert embed.title == "Construction Company"
            assert "$500" in embed.description

    async def test_buy_kennel_defers_and_calls_game(self):
        with (
            patch(
                "src.bot.ui.marketplace.buy_kennel", new_callable=AsyncMock, return_value=(True, "Kennel purchased!")
            ),
            patch("src.bot.ui.marketplace.list_owner_kennels", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.marketplace.get_or_create_owner", new_callable=AsyncMock),
            patch("src.bot.ui.marketplace.get_kennel_buy_price", new_callable=AsyncMock, return_value=(200, "$200")),
            patch("src.bot.ui.marketplace.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r

            view = ConstructionCompanyView(server_discord_id=200, owner_discord_id=100)
            interaction = MagicMock()
            await view._on_buy_kennel(interaction)

            mock_r.defer.assert_called_once_with(thinking=True)
