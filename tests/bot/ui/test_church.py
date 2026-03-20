"""Contract tests for src/bot/ui/church.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.church import (
    BasementView,
    ChurchView,
    _HellPageSource,
    _SacrificeControls,
    _SacrificeKennelsPageSource,
    _SummonRollButton,
)


@pytest.mark.contract
class TestChurchView:
    async def test_creates_view(self):
        view = ChurchView(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_has_beg_button(self):
        view = ChurchView(server_discord_id=200, owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "Beg for Money" for b in buttons)

    async def test_has_basement_button(self):
        view = ChurchView(server_discord_id=200, owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "Basement" for b in buttons)

    async def test_has_town_button(self):
        view = ChurchView(server_discord_id=200, owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "Town" for b in buttons)

    async def test_interaction_check_owner_only(self):
        view = ChurchView(server_discord_id=200, owner_discord_id=100)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True

        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False


@pytest.mark.contract
class TestBasementView:
    async def test_creates_view(self):
        with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=10):
            view = BasementView(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_has_sacrifice_button(self):
        with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=10):
            view = BasementView(server_discord_id=200, owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "Sacrifice a Pooch" for b in buttons)

    async def test_has_summon_button(self):
        with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=10):
            view = BasementView(server_discord_id=200, owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "Summon a Pooch" for b in buttons)

    async def test_has_hell_button(self):
        with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=10):
            view = BasementView(server_discord_id=200, owner_discord_id=100)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert any(b.label == "Gaze Into Hell" for b in buttons)

    async def test_interaction_check_owner_only(self):
        with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=10):
            view = BasementView(server_discord_id=200, owner_discord_id=100)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True

        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False


@pytest.mark.contract
class TestBegButton:
    async def test_beg_success_shows_amount(self):
        view = ChurchView(server_discord_id=200, owner_discord_id=100)
        beg_button = next(c for c in view.children if isinstance(c, discord.ui.Button) and c.label == "Beg for Money")

        interaction = MagicMock()

        with (
            patch("src.bot.ui.church.beg_for_money", new_callable=AsyncMock, return_value=(25, None)),
            patch("src.bot.ui.church.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await beg_button.callback(interaction)

            mock_r.reply.assert_called_once()
            msg = mock_r.reply.call_args[1]["content"]
            assert "$25" in msg

    async def test_beg_with_message(self):
        view = ChurchView(server_discord_id=200, owner_discord_id=100)
        beg_button = next(c for c in view.children if isinstance(c, discord.ui.Button) and c.label == "Beg for Money")

        interaction = MagicMock()

        with (
            patch(
                "src.bot.ui.church.beg_for_money", new_callable=AsyncMock, return_value=(0, "You already begged today.")
            ),
            patch("src.bot.ui.church.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await beg_button.callback(interaction)

            msg = mock_r.reply.call_args[1]["content"]
            assert "already begged" in msg


@pytest.mark.contract
class TestBasementButton:
    async def test_basement_button_opens_basement_view(self):
        with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=10):
            view = ChurchView(server_discord_id=200, owner_discord_id=100)
        basement_button = next(c for c in view.children if isinstance(c, discord.ui.Button) and c.label == "Basement")

        interaction = MagicMock()

        with patch("src.bot.ui.church.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=10):
                await basement_button.callback(interaction)

            mock_r.reply.assert_called_once()
            call_kwargs = mock_r.reply.call_args[1]
            assert "view" in call_kwargs
            assert isinstance(call_kwargs["view"], BasementView)


@pytest.mark.contract
class TestTownButtonInChurch:
    async def test_town_button_opens_town_view(self):
        view = ChurchView(server_discord_id=200, owner_discord_id=100)
        town_button = next(c for c in view.children if isinstance(c, discord.ui.Button) and c.label == "Town")

        interaction = MagicMock()

        with patch("src.bot.ui.church.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await town_button.callback(interaction)

            mock_r.reply.assert_called_once()
            content = mock_r.reply.call_args[1]["content"]
            assert "Town" in content


@pytest.mark.contract
class TestSummonRollButton:
    async def test_success_shows_checkmark(self):
        with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=50):
            button = _SummonRollButton(owner_discord_id=100, rolls=1)

        interaction = MagicMock()

        with (
            patch(
                "src.bot.ui.church.conjure_pooch", new_callable=AsyncMock, return_value=(True, "You summoned a pooch!")
            ),
            patch("src.bot.ui.church.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await button.callback(interaction)
            mock_r.defer.assert_called_once_with(thinking=True)
            msg = mock_r.reply.call_args[1]["content"]
            assert "✅" in msg

    async def test_failure_shows_error_message(self):
        with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=50):
            button = _SummonRollButton(owner_discord_id=100, rolls=1)

        interaction = MagicMock()

        with (
            patch(
                "src.bot.ui.church.conjure_pooch",
                new_callable=AsyncMock,
                return_value=(False, "Not enough bloodskulls."),
            ),
            patch("src.bot.ui.church.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await button.callback(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "bloodskulls" in msg.lower()

    async def test_exception_calls_finish_with_error(self):
        with patch("src.bot.ui.church.get_conjure_pooch_price", return_value=50):
            button = _SummonRollButton(owner_discord_id=100, rolls=1)

        interaction = MagicMock()

        with (
            patch("src.bot.ui.church.conjure_pooch", new_callable=AsyncMock, side_effect=Exception("DB error")),
            patch("src.bot.ui.church.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.finish_with_error = AsyncMock()
            MockResponder.return_value = mock_r

            await button.callback(interaction)
            mock_r.finish_with_error.assert_called_once()


@pytest.mark.contract
class TestHellPageSource:
    async def test_empty_hell(self):
        source = _HellPageSource(server_discord_id=200)

        with patch("src.bot.ui.church.list_hell_pooches", new_callable=AsyncMock, return_value=[]):
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Hell is quiet" in content
            assert "No pooches" in embed.description

    async def test_renders_pooch(self):
        pooch = MagicMock()
        pooch.id = 1
        pooch.name = "Damned Dog"

        with (
            patch("src.bot.ui.church.list_hell_pooches", new_callable=AsyncMock, return_value=[pooch]),
            patch("src.bot.ui.church.get_pooch_bloodskull_value", new_callable=AsyncMock, return_value=5),
            patch("src.bot.ui.church.get_or_create_server", new_callable=AsyncMock),
        ):
            source = _HellPageSource(server_discord_id=200)
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "Damned Dog" in embed.title
            assert "5" in embed.description


@pytest.mark.contract
class TestSacrificeKennelsPageSource:
    async def test_empty_kennels(self):
        with patch("src.bot.ui.church.list_owner_kennels", new_callable=AsyncMock, return_value=[]):
            source = _SacrificeKennelsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()
            assert source.page_count() == 1

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "nothing to offer" in embed.description.lower()

    async def test_renders_kennel_with_pooches(self):
        kennel = MagicMock()
        kennel.id = 1
        kennel.name = "The Barn"
        kennel.pooch_limit = 5

        pooch = MagicMock()
        pooch.id = 1
        pooch.name = "Rex"
        pooch.alive = True

        with (
            patch("src.bot.ui.church.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]),
            patch("src.bot.ui.church.list_kennel_pooches", new_callable=AsyncMock, return_value=[pooch]),
            patch("src.bot.ui.church.get_pooch_bloodskull_value", new_callable=AsyncMock, return_value=3),
        ):
            source = _SacrificeKennelsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "The Barn" in embed.title


@pytest.mark.contract
class TestSacrificeControls:
    def test_empty_pooches_shows_disabled_select(self):
        controls = _SacrificeControls(
            server_discord_id=200,
            owner_discord_id=100,
            pooches=[],
            values_by_pooch_id={},
        )
        assert controls.select.disabled is True
        assert controls.sacrifice_button.disabled is True

    def test_with_pooches_select_enabled(self):
        pooch = MagicMock()
        pooch.id = 1
        pooch.name = "Rex"
        controls = _SacrificeControls(
            server_discord_id=200,
            owner_discord_id=100,
            pooches=[pooch],
            values_by_pooch_id={1: 3},
        )
        assert controls.select.disabled is False

    async def test_on_select_none_clears_selection(self):
        controls = _SacrificeControls(
            server_discord_id=200,
            owner_discord_id=100,
            pooches=[],
            values_by_pooch_id={},
        )
        interaction = MagicMock()
        view = MagicMock()
        controls.select._view = view

        with (
            patch.object(type(controls.select), "values", new_callable=lambda: property(lambda self: ["__none__"])),
            patch("src.bot.ui.church.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_select(interaction)

        assert controls.selected is None
        assert controls.info_button.disabled is True
        assert controls.sacrifice_button.disabled is True

    async def test_on_sacrifice_success(self):
        pooch = MagicMock()
        pooch.id = 1
        pooch.name = "Rex"
        controls = _SacrificeControls(
            server_discord_id=200,
            owner_discord_id=100,
            pooches=[pooch],
            values_by_pooch_id={1: 3},
        )
        controls.selected = pooch
        view = MagicMock()
        controls.select._view = view

        interaction = MagicMock()

        with (
            patch(
                "src.bot.ui.church.sacrifice_pooch", new_callable=AsyncMock, return_value=(True, "Sacrifice complete!")
            ),
            patch("src.bot.ui.church.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_sacrifice(interaction)
            mock_r.defer.assert_called_once_with(thinking=True)
            msg = mock_r.reply.call_args[1]["content"]
            assert "✅" in msg

    async def test_on_sacrifice_failure(self):
        pooch = MagicMock()
        pooch.id = 1
        controls = _SacrificeControls(
            server_discord_id=200,
            owner_discord_id=100,
            pooches=[pooch],
            values_by_pooch_id={1: 3},
        )
        controls.selected = pooch
        controls.select._view = MagicMock()

        interaction = MagicMock()

        with (
            patch(
                "src.bot.ui.church.sacrifice_pooch",
                new_callable=AsyncMock,
                return_value=(False, "Pooch too healthy to sacrifice."),
            ),
            patch("src.bot.ui.church.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_sacrifice(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "too healthy" in msg

    async def test_on_sacrifice_exception_calls_finish_with_error(self):
        pooch = MagicMock()
        pooch.id = 1
        controls = _SacrificeControls(
            server_discord_id=200,
            owner_discord_id=100,
            pooches=[pooch],
            values_by_pooch_id={1: 3},
        )
        controls.selected = pooch
        controls.select._view = MagicMock()

        interaction = MagicMock()

        with (
            patch("src.bot.ui.church.sacrifice_pooch", new_callable=AsyncMock, side_effect=Exception("DB error")),
            patch("src.bot.ui.church.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.finish_with_error = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_sacrifice(interaction)
            mock_r.finish_with_error.assert_called_once()
