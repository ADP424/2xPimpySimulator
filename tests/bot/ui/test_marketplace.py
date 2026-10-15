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

    async def test_select_has_auction_option(self):
        view = MarketplaceView(server_discord_id=200, owner_discord_id=100)
        select = next(c for c in view.children if isinstance(c, discord.ui.Select))
        values = {opt.value for opt in select.options}
        assert "auction" in values

    async def test_select_auction_replies_with_auction_house_view(self):
        from src.bot.ui.auction import AuctionHouseView

        view = MarketplaceView(server_discord_id=200, owner_discord_id=100)
        select = next(c for c in view.children if isinstance(c, discord.ui.Select))

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.send_message = AsyncMock()
        interaction.response.edit_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.message = None

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["auction"])),
            patch("src.bot.ui.marketplace.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await select.callback(interaction)

        mock_r.reply.assert_called_once()
        kwargs = mock_r.reply.call_args[1]
        assert "view" in kwargs
        assert isinstance(kwargs["view"], AuctionHouseView)

    async def test_select_construction_replies_with_construction_view(self):
        view = MarketplaceView(server_discord_id=200, owner_discord_id=100)
        select = next(c for c in view.children if isinstance(c, discord.ui.Select))

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.send_message = AsyncMock()
        interaction.response.edit_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.message = None

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["construction"])),
            patch("src.bot.ui.marketplace.InteractionResponder") as MockResponder,
            patch("src.bot.ui.marketplace.list_owner_kennels", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.marketplace.get_or_create_owner", new_callable=AsyncMock),
            patch("src.bot.ui.marketplace.get_kennel_buy_price", new_callable=AsyncMock, return_value=(200, "$200")),
            patch(
                "src.bot.ui.marketplace.get_kennel_upgrade_price", new_callable=AsyncMock, return_value=(100, "$100")
            ),
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await select.callback(interaction)

        mock_r.reply.assert_called_once()
        kwargs = mock_r.reply.call_args[1]
        assert "view" in kwargs
        assert isinstance(kwargs["view"], ConstructionCompanyView)

    async def test_on_kennel_select_enables_upgrade_when_price_available(self):
        from src.game.models.kennel import Kennel

        mock_kennel = Kennel(id=1, owner_discord_id=100, name="Kennel 1", pooch_limit=5, owner=None)

        with (
            patch("src.bot.ui.marketplace.list_owner_kennels", new_callable=AsyncMock, return_value=[mock_kennel]),
            patch("src.bot.ui.marketplace.get_or_create_owner", new_callable=AsyncMock),
            patch("src.bot.ui.marketplace.get_kennel_buy_price", new_callable=AsyncMock, return_value=(200, "$200")),
            patch(
                "src.bot.ui.marketplace.get_kennel_upgrade_price", new_callable=AsyncMock, return_value=(100, "$100")
            ),
        ):
            view = ConstructionCompanyView(server_discord_id=200, owner_discord_id=100)
            await view.build_embed()

        interaction = MagicMock()
        interaction.data = {"values": ["1"]}
        with (
            patch(
                "src.bot.ui.marketplace.get_kennel_upgrade_price", new_callable=AsyncMock, return_value=(100, "$100")
            ),
            patch("src.bot.ui.marketplace.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_kennel_select(interaction)

        assert view._upgrade_button.disabled is False

    async def test_on_kennel_select_disables_upgrade_at_max(self):
        from src.game.models.kennel import Kennel

        mock_kennel = Kennel(id=1, owner_discord_id=100, name="Kennel 1", pooch_limit=5, owner=None)

        with (
            patch("src.bot.ui.marketplace.list_owner_kennels", new_callable=AsyncMock, return_value=[mock_kennel]),
            patch("src.bot.ui.marketplace.get_or_create_owner", new_callable=AsyncMock),
            patch("src.bot.ui.marketplace.get_kennel_buy_price", new_callable=AsyncMock, return_value=(200, "$200")),
            patch(
                "src.bot.ui.marketplace.get_kennel_upgrade_price",
                new_callable=AsyncMock,
                return_value=(None, "Max level"),
            ),
        ):
            view = ConstructionCompanyView(server_discord_id=200, owner_discord_id=100)
            await view.build_embed()

        interaction = MagicMock()
        interaction.data = {"values": ["1"]}
        with (
            patch(
                "src.bot.ui.marketplace.get_kennel_upgrade_price",
                new_callable=AsyncMock,
                return_value=(None, "Max level"),
            ),
            patch("src.bot.ui.marketplace.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_kennel_select(interaction)

        assert view._upgrade_button.disabled is True

    async def test_on_upgrade_kennel_calls_game_fn(self):
        from src.game.models.kennel import Kennel

        mock_kennel = Kennel(id=1, owner_discord_id=100, name="Kennel 1", pooch_limit=5, owner=None)

        with (
            patch("src.bot.ui.marketplace.list_owner_kennels", new_callable=AsyncMock, return_value=[mock_kennel]),
            patch("src.bot.ui.marketplace.get_or_create_owner", new_callable=AsyncMock),
            patch("src.bot.ui.marketplace.get_kennel_buy_price", new_callable=AsyncMock, return_value=(200, "$200")),
            patch(
                "src.bot.ui.marketplace.get_kennel_upgrade_price", new_callable=AsyncMock, return_value=(100, "$100")
            ),
        ):
            view = ConstructionCompanyView(server_discord_id=200, owner_discord_id=100)
            await view.build_embed()

        view._selected_kennel = mock_kennel

        interaction = MagicMock()
        with (
            patch(
                "src.bot.ui.marketplace.upgrade_kennel", new_callable=AsyncMock, return_value=(True, "Upgraded!")
            ) as mock_fn,
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
            await view._on_upgrade_kennel(interaction)

        mock_fn.assert_called_once_with(100, 1)

    async def test_on_upgrade_kennel_success_refreshes(self):
        from src.game.models.kennel import Kennel

        mock_kennel = Kennel(id=1, owner_discord_id=100, name="Kennel 1", pooch_limit=5, owner=None)

        with (
            patch("src.bot.ui.marketplace.list_owner_kennels", new_callable=AsyncMock, return_value=[mock_kennel]),
            patch("src.bot.ui.marketplace.get_or_create_owner", new_callable=AsyncMock),
            patch("src.bot.ui.marketplace.get_kennel_buy_price", new_callable=AsyncMock, return_value=(200, "$200")),
            patch(
                "src.bot.ui.marketplace.get_kennel_upgrade_price", new_callable=AsyncMock, return_value=(100, "$100")
            ),
        ):
            view = ConstructionCompanyView(server_discord_id=200, owner_discord_id=100)
            await view.build_embed()

        view._selected_kennel = mock_kennel

        interaction = MagicMock()
        with (
            patch("src.bot.ui.marketplace.upgrade_kennel", new_callable=AsyncMock, return_value=(True, "Upgraded!")),
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
            await view._on_upgrade_kennel(interaction)

        mock_r.edit.assert_called()

    async def test_on_upgrade_kennel_exception_calls_finish_with_error(self):
        from src.game.models.kennel import Kennel

        mock_kennel = Kennel(id=1, owner_discord_id=100, name="Kennel 1", pooch_limit=5, owner=None)

        with (
            patch("src.bot.ui.marketplace.list_owner_kennels", new_callable=AsyncMock, return_value=[mock_kennel]),
            patch("src.bot.ui.marketplace.get_or_create_owner", new_callable=AsyncMock),
            patch("src.bot.ui.marketplace.get_kennel_buy_price", new_callable=AsyncMock, return_value=(200, "$200")),
            patch(
                "src.bot.ui.marketplace.get_kennel_upgrade_price", new_callable=AsyncMock, return_value=(100, "$100")
            ),
        ):
            view = ConstructionCompanyView(server_discord_id=200, owner_discord_id=100)
            await view.build_embed()

        view._selected_kennel = mock_kennel

        interaction = MagicMock()
        with (
            patch("src.bot.ui.marketplace.upgrade_kennel", new_callable=AsyncMock, side_effect=Exception("DB error")),
            patch("src.bot.ui.marketplace.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.finish_with_error = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_upgrade_kennel(interaction)

        mock_r.finish_with_error.assert_called_once()
