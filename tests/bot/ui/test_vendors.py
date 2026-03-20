"""Contract tests for src/bot/ui/vendors.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.vendors import (
    VendorPageControls,
    VendorsMenuView,
    VendorsPageSource,
    _SellKennelControls,
    _SellKennelsPageSource,
)


def _make_vendor(id=1, name="Barker Bros"):
    vendor = MagicMock()
    vendor.id = id
    vendor.name = name
    vendor.desired_mutation_1 = None
    vendor.desired_mutation_2 = None
    vendor.desired_mutation_3 = None
    return vendor


def _make_pooch(id=1, name="Rex", alive=True):
    pooch = MagicMock()
    pooch.id = id
    pooch.name = name
    pooch.alive = alive
    return pooch


@pytest.mark.contract
class TestVendorsPageSource:
    async def test_empty_vendors(self):
        with patch("src.bot.ui.vendors.list_server_vendors", new_callable=AsyncMock, return_value=[]):
            source = VendorsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "no vendors" in embed.description.lower()

    async def test_page_count_matches_vendors(self):
        vendors = [_make_vendor(id=i) for i in range(3)]
        with patch("src.bot.ui.vendors.list_server_vendors", new_callable=AsyncMock, return_value=vendors):
            source = VendorsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()
            assert source.page_count() == 3

    async def test_render_vendor_page(self):
        vendor = _make_vendor(id=1, name="Pawsome Pete")
        pooches = [_make_pooch(id=1, name="Fido")]

        with (
            patch("src.bot.ui.vendors.list_server_vendors", new_callable=AsyncMock, return_value=[vendor]),
            patch("src.bot.ui.vendors.list_vendor_pooches", new_callable=AsyncMock, return_value=pooches),
            patch("src.bot.ui.vendors.get_pooch_buy_price", new_callable=AsyncMock, return_value=100),
        ):
            source = VendorsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert embed.title == "Pawsome Pete"
            assert "1 pooch" in embed.description


@pytest.mark.contract
class TestVendorPageControls:
    def test_empty_pooches_disables_buttons(self):
        vendor = _make_vendor()
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[],
            prices_by_pooch_id={},
        )
        assert controls.info_button.disabled is True
        assert controls.buy_button.disabled is True

    def test_with_pooches_select_enabled(self):
        vendor = _make_vendor()
        pooches = [_make_pooch(id=1)]
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=pooches,
            prices_by_pooch_id={1: 100},
        )
        assert controls.select.disabled is False

    def test_attach_adds_items(self):
        vendor = _make_vendor()
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[_make_pooch()],
            prices_by_pooch_id={1: 50},
        )
        view = MagicMock()
        view.add_item = MagicMock()
        controls.attach(view)
        # mutation_select, pooch_select, info, buy, sell
        assert view.add_item.call_count == 5

    async def test_buy_defers_and_calls_game(self):
        vendor = _make_vendor()
        pooch = _make_pooch(id=1, name="Fido")
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[pooch],
            prices_by_pooch_id={1: 50},
        )
        controls.selected_pooch = pooch

        interaction = MagicMock()
        controls.select._view = MagicMock()

        with (
            patch("src.bot.ui.vendors.buy_pooch", new_callable=AsyncMock, return_value=(True, "Purchased Fido!")),
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_buy(interaction)
            mock_r.defer.assert_called_once_with(thinking=True)


@pytest.mark.contract
class TestVendorsMenuView:
    async def test_creates_view(self):
        view = VendorsMenuView(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)


@pytest.mark.contract
class TestVendorPageControlsExtended:
    async def test_on_select_none_clears_selection(self):
        vendor = _make_vendor()
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[],
            prices_by_pooch_id={},
        )
        interaction = MagicMock()
        view = MagicMock()
        controls.select._view = view

        with (
            patch.object(type(controls.select), "values", new_callable=lambda: property(lambda self: ["__none__"])),
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_select(interaction)

        assert controls.selected_pooch is None
        assert controls.info_button.disabled is True
        assert controls.buy_button.disabled is True

    async def test_on_select_valid_enables_buttons(self):
        vendor = _make_vendor()
        pooch = _make_pooch(id=5, name="Buddy")
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[pooch],
            prices_by_pooch_id={5: 100},
        )
        interaction = MagicMock()
        controls.select._view = MagicMock()

        with (
            patch.object(type(controls.select), "values", new_callable=lambda: property(lambda self: ["5"])),
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_select(interaction)

        assert controls.selected_pooch is pooch
        assert controls.info_button.disabled is False
        assert controls.buy_button.disabled is False

    async def test_on_buy_skips_when_no_selection(self):
        vendor = _make_vendor()
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[],
            prices_by_pooch_id={},
        )
        interaction = MagicMock()

        with (
            patch("src.bot.ui.vendors.buy_pooch", new_callable=AsyncMock) as mock_buy,
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_buy(interaction)
            mock_buy.assert_not_called()

    async def test_on_buy_exception_calls_finish_with_error(self):
        vendor = _make_vendor()
        pooch = _make_pooch(id=1, name="Rex")
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[pooch],
            prices_by_pooch_id={1: 50},
        )
        controls.selected_pooch = pooch
        controls.select._view = MagicMock()
        interaction = MagicMock()

        with (
            patch("src.bot.ui.vendors.buy_pooch", new_callable=AsyncMock, side_effect=Exception("DB error")),
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.finish_with_error = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_buy(interaction)
            mock_r.finish_with_error.assert_called_once()

    async def test_on_buy_failure_shows_message(self):
        vendor = _make_vendor()
        pooch = _make_pooch(id=1, name="Rex")
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[pooch],
            prices_by_pooch_id={1: 50},
        )
        controls.selected_pooch = pooch
        controls.select._view = MagicMock()
        interaction = MagicMock()

        with (
            patch("src.bot.ui.vendors.buy_pooch", new_callable=AsyncMock, return_value=(False, "Not enough money.")),
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_buy(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "money" in msg.lower()

    async def test_on_sell_opens_kennel_page_source(self):
        vendor = _make_vendor()
        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[],
            prices_by_pooch_id={},
        )
        interaction = MagicMock()

        with (
            patch("src.bot.ui.vendors.list_owner_kennels", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_sell(interaction)
            mock_r.reply.assert_called_once()

    async def test_vendor_has_desired_mutations(self):
        vendor = _make_vendor()
        mutation = MagicMock()
        mutation.id = 10
        mutation.name = "Cataracts"
        vendor.desired_mutation_1 = mutation
        vendor.desired_mutation_2 = None
        vendor.desired_mutation_3 = None

        controls = VendorPageControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[],
            prices_by_pooch_id={},
        )
        assert controls.mutation_select.disabled is False
        option_values = [opt.value for opt in controls.mutation_select.options]
        assert "10" in option_values


@pytest.mark.contract
class TestSellKennelsPageSource:
    async def test_empty_kennels(self):
        with patch("src.bot.ui.vendors.list_owner_kennels", new_callable=AsyncMock, return_value=[]):
            vendor = _make_vendor(name="Pete")
            source = _SellKennelsPageSource(server_discord_id=200, owner_discord_id=100, vendor=vendor)
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "don't have any kennels" in embed.description

    async def test_renders_kennel_with_alive_pooches(self):
        kennel = MagicMock()
        kennel.id = 1
        kennel.name = "My Kennel"
        kennel.pooch_limit = 5

        pooch = _make_pooch(id=1, name="Fido", alive=True)

        with (
            patch("src.bot.ui.vendors.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]),
            patch("src.bot.ui.vendors.list_kennel_pooches", new_callable=AsyncMock, return_value=[pooch]),
            patch("src.bot.ui.vendors.get_pooch_sell_price", new_callable=AsyncMock, return_value=75),
        ):
            vendor = _make_vendor(name="Pete")
            source = _SellKennelsPageSource(server_discord_id=200, owner_discord_id=100, vendor=vendor)
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Pete" in embed.title
            assert "My Kennel" in embed.title


@pytest.mark.contract
class TestSellKennelControls:
    def test_empty_pooches_disables_select(self):
        vendor = _make_vendor()
        controls = _SellKennelControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[],
            prices_by_pooch_id={},
        )
        assert controls.select.disabled is True
        assert controls.sell_button.disabled is True

    def test_with_pooches_select_enabled(self):
        vendor = _make_vendor()
        pooch = _make_pooch(id=1, name="Fido")
        controls = _SellKennelControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[pooch],
            prices_by_pooch_id={1: 75},
        )
        assert controls.select.disabled is False

    async def test_on_select_valid_enables_sell(self):
        vendor = _make_vendor()
        pooch = _make_pooch(id=3, name="Max")
        controls = _SellKennelControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[pooch],
            prices_by_pooch_id={3: 50},
        )
        interaction = MagicMock()
        controls.select._view = MagicMock()

        with (
            patch.object(type(controls.select), "values", new_callable=lambda: property(lambda self: ["3"])),
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_select(interaction)

        assert controls.selected_pooch is pooch
        assert controls.sell_button.disabled is False

    async def test_on_sell_success(self):
        vendor = _make_vendor()
        pooch = _make_pooch(id=1, name="Rex")
        controls = _SellKennelControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[pooch],
            prices_by_pooch_id={1: 50},
        )
        controls.selected_pooch = pooch
        controls.select._view = MagicMock()
        interaction = MagicMock()

        with (
            patch("src.bot.ui.vendors.sell_pooch", new_callable=AsyncMock, return_value=(True, "Sold Rex!")),
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_sell(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "✅" in msg

    async def test_on_sell_exception_calls_finish_with_error(self):
        vendor = _make_vendor()
        pooch = _make_pooch(id=1)
        controls = _SellKennelControls(
            server_discord_id=200,
            owner_discord_id=100,
            vendor=vendor,
            pooches=[pooch],
            prices_by_pooch_id={1: 50},
        )
        controls.selected_pooch = pooch
        controls.select._view = MagicMock()
        interaction = MagicMock()

        with (
            patch("src.bot.ui.vendors.sell_pooch", new_callable=AsyncMock, side_effect=Exception("DB error")),
            patch("src.bot.ui.vendors.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.finish_with_error = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_sell(interaction)
            mock_r.finish_with_error.assert_called_once()
