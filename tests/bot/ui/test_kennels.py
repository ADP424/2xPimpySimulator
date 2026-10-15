"""Contract tests for src/bot/ui/kennels.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.ui.kennels import KennelPageControls, KennelsPageSource


def _make_kennel(id=1, name="Main Kennel", pooch_limit=5, owner_discord_id=100):
    from src.game.models.kennel import Kennel

    return Kennel(id=id, owner_discord_id=owner_discord_id, name=name, pooch_limit=pooch_limit, owner=None)


def _make_pooch(id=1, name="Rex", sex="male"):
    pooch = MagicMock()
    pooch.id = id
    pooch.name = name
    pooch.sex = sex
    return pooch


@pytest.mark.contract
class TestKennelsPageSource:
    async def test_load_fetches_kennels(self):
        kennels = [_make_kennel(id=1), _make_kennel(id=2)]
        with patch("src.bot.ui.kennels.list_owner_kennels", new_callable=AsyncMock, return_value=kennels):
            source = KennelsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()
            assert source._kennels == kennels

    async def test_page_count_matches_kennels(self):
        kennels = [_make_kennel(id=i) for i in range(3)]
        with patch("src.bot.ui.kennels.list_owner_kennels", new_callable=AsyncMock, return_value=kennels):
            source = KennelsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()
            assert source.page_count() == 3

    async def test_page_count_minimum_1(self):
        with patch("src.bot.ui.kennels.list_owner_kennels", new_callable=AsyncMock, return_value=[]):
            source = KennelsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()
            assert source.page_count() == 1

    async def test_render_empty(self):
        with patch("src.bot.ui.kennels.list_owner_kennels", new_callable=AsyncMock, return_value=[]):
            source = KennelsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert "don't have any kennels" in embed.description

    async def test_render_kennel_page(self):
        kennel = _make_kennel(name="The Barn", pooch_limit=3)
        pooches = [_make_pooch(id=1, name="Spot")]

        with (
            patch("src.bot.ui.kennels.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]),
            patch("src.bot.ui.kennels.list_kennel_pooches", new_callable=AsyncMock, return_value=pooches),
        ):
            source = KennelsPageSource(server_discord_id=200, owner_discord_id=100)
            await source.load()

            view = MagicMock()
            view.add_item = MagicMock()
            content, embed = await source.render(view, 0)
            assert embed.title == "The Barn"
            assert "1 / 3" in embed.description


@pytest.mark.contract
class TestKennelPageControls:
    def test_empty_pooches_disables_buttons(self):
        kennel = _make_kennel()
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[])
        assert controls.info_button.disabled is True
        assert controls.breed_button.disabled is True
        assert controls.cast_out_button.disabled is True

    def test_with_pooches_select_enabled(self):
        kennel = _make_kennel()
        pooches = [_make_pooch(id=1, name="Rex")]
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=pooches)
        assert controls.select.disabled is False

    def test_attach_adds_items(self):
        kennel = _make_kennel()
        pooches = [_make_pooch()]
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=pooches)
        view = MagicMock()
        view.add_item = MagicMock()
        controls.attach(view)
        # Should add: rename kennel button, feed button, select, info, breed, walk, rename pooch, cast out
        assert view.add_item.call_count == 8

    async def test_select_enables_action_buttons(self):
        kennel = _make_kennel()
        pooches = [_make_pooch(id=1, name="Rex")]
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=pooches)

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.edit_message = AsyncMock()
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()

        view = MagicMock()
        controls.select._view = view

        with (
            patch.object(type(controls.select), "values", new_callable=lambda: property(lambda self: ["1"])),
            patch("src.bot.ui.kennels.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_select(interaction)

        assert controls.selected_pooch is not None
        assert controls.selected_pooch.name == "Rex"
        assert controls.info_button.disabled is False
        assert controls.breed_button.disabled is False

    async def test_cast_out_calls_game_function(self):
        kennel = _make_kennel()
        pooch = _make_pooch(id=1, name="Bad Dog")
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[pooch])
        controls.selected_pooch = pooch

        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        interaction.message = None
        interaction.channel = MagicMock()
        interaction.channel.send = AsyncMock()

        with (
            patch(
                "src.bot.ui.kennels.cast_out_pooch",
                new_callable=AsyncMock,
                return_value=(True, "Bad Dog has been cast out."),
            ) as mock_cast,
            patch("src.bot.ui.kennels.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            controls.select._view = MagicMock()
            await controls._on_cast_out(interaction)

            mock_cast.assert_called_once_with(100, 1, 200)
            mock_r.reply.assert_awaited_once_with(content="Bad Dog has been cast out.")

    async def test_cast_out_failure_shows_message_without_refresh(self):
        kennel = _make_kennel()
        pooch = _make_pooch(id=1, name="Bad Dog")
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[pooch])
        controls.selected_pooch = pooch
        interaction = MagicMock()

        with (
            patch(
                "src.bot.ui.kennels.cast_out_pooch",
                new_callable=AsyncMock,
                return_value=(False, "That's not your pooch."),
            ),
            patch("src.bot.ui.kennels.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            parent_view = MagicMock()
            parent_view.refresh = AsyncMock()
            controls.select._view = parent_view
            await controls._on_cast_out(interaction)

            mock_r.reply.assert_awaited_once_with(content="That's not your pooch.")
            parent_view.refresh.assert_not_awaited()

    async def test_on_info_when_no_selection_skips(self):
        kennel = _make_kennel()
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[])
        interaction = MagicMock()

        with (
            patch("src.bot.ui.kennels.get_or_create_server", new_callable=AsyncMock) as mock_server,
            patch("src.bot.ui.kennels.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_info(interaction)
            mock_server.assert_not_called()

    async def test_on_info_with_selection_replies_with_embed(self):
        kennel = _make_kennel()
        pooch = _make_pooch(id=1, name="Rex")
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[pooch])
        controls.selected_pooch = pooch
        interaction = MagicMock()

        mock_server = MagicMock()
        mock_owner = MagicMock()

        with (
            patch("src.bot.ui.kennels.get_or_create_server", new_callable=AsyncMock, return_value=mock_server),
            patch("src.bot.ui.kennels.get_or_create_owner", new_callable=AsyncMock, return_value=mock_owner),
            patch("src.bot.ui.kennels.PoochInfoView") as MockPoochInfoView,
            patch("src.bot.ui.kennels.InteractionResponder") as MockResponder,
        ):
            mock_view = MagicMock()
            mock_view.build_embed = AsyncMock(return_value=MagicMock())
            MockPoochInfoView.return_value = mock_view

            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await controls._on_info(interaction)
            mock_r.reply.assert_called_once()

    async def test_on_breed_no_selection_skips(self):
        kennel = _make_kennel()
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[])
        interaction = MagicMock()

        with patch("src.bot.ui.kennels.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_breed(interaction)
            mock_r.reply.assert_not_called()

    async def test_on_breed_no_valid_mates(self):
        kennel = _make_kennel()
        pooch = _make_pooch(id=1, name="Rex", sex="male")
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[pooch])
        controls.selected_pooch = pooch
        interaction = MagicMock()

        with patch("src.bot.ui.kennels.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_breed(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "no valid mates" in msg.lower()

    async def test_on_breed_shows_mate_view(self):
        kennel = _make_kennel()
        pooch_male = _make_pooch(id=1, name="Rex", sex="male")
        pooch_female = _make_pooch(id=2, name="Bella", sex="female")
        controls = KennelPageControls(
            server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[pooch_male, pooch_female]
        )
        controls.selected_pooch = pooch_male
        interaction = MagicMock()

        with (
            patch("src.bot.ui.kennels.InteractionResponder") as MockResponder,
            patch("src.bot.ui.kennels.get_breeding_chance", new=AsyncMock(return_value=0.4)) as chance,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_breed(interaction)
            mock_r.reply.assert_called_once()
            call_kwargs = mock_r.reply.call_args[1]
            assert "view" in call_kwargs
            assert "(40% chance)" in call_kwargs["view"].select.placeholder
        chance.assert_awaited_once_with(1)

    async def test_noop_replies_coming_soon(self):
        kennel = _make_kennel()
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[])
        interaction = MagicMock()

        with patch("src.bot.ui.kennels.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._noop(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "soon" in msg.lower()

    async def test_cast_out_skips_when_no_selection(self):
        kennel = _make_kennel()
        controls = KennelPageControls(server_discord_id=200, owner_discord_id=100, kennel=kennel, pooches=[])
        interaction = MagicMock()

        with (
            patch("src.bot.ui.kennels.cast_out_pooch", new_callable=AsyncMock) as mock_cast,
            patch("src.bot.ui.kennels.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await controls._on_cast_out(interaction)
            mock_cast.assert_not_called()


@pytest.mark.contract
class TestRenameKennelModal:
    async def test_wrong_owner_is_rejected(self):
        from src.bot.ui.kennels import _RenameKennelModal

        modal = _RenameKennelModal(
            owner_discord_id=100,
            kennel_id=1,
            current_name="Old Name",
            parent_view=MagicMock(),
        )

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 999

        with patch("src.bot.ui.kennels.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await modal.on_submit(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "not your kennel" in msg.lower()

    async def test_rename_success(self):
        from src.bot.ui.kennels import _RenameKennelModal

        modal = _RenameKennelModal(
            owner_discord_id=100,
            kennel_id=1,
            current_name="Old Name",
            parent_view=MagicMock(),
        )
        modal.name = MagicMock()
        modal.name.value = "New Kennel Name"

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100

        with (
            patch("src.bot.ui.kennels.rename_kennel", new_callable=AsyncMock, return_value=True),
            patch("src.bot.ui.kennels.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await modal.on_submit(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "✅" in msg
            assert "New Kennel Name" in msg


@pytest.mark.contract
class TestRenamePoochModal:
    async def test_wrong_owner_is_rejected(self):
        from src.bot.ui.kennels import _RenamePoochModal

        modal = _RenamePoochModal(
            owner_discord_id=100,
            pooch_id=1,
            current_name="Old Name",
            parent_view=MagicMock(),
        )

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 999

        with patch("src.bot.ui.kennels.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await modal.on_submit(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "not your pooch" in msg.lower()

    async def test_rename_success(self):
        from src.bot.ui.kennels import _RenamePoochModal

        modal = _RenamePoochModal(
            owner_discord_id=100,
            pooch_id=1,
            current_name="Old Name",
            parent_view=MagicMock(),
        )
        modal.name = MagicMock()
        modal.name.value = "Super Pooch"

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100

        with (
            patch("src.bot.ui.kennels.rename_pooch", new_callable=AsyncMock, return_value=True),
            patch("src.bot.ui.kennels.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r

            await modal.on_submit(interaction)
            msg = mock_r.reply.call_args[1]["content"]
            assert "✅" in msg
            assert "Super Pooch" in msg
