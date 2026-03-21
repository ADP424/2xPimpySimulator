"""Contract tests for src/bot/ui/server_events.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.server_events import (
    ServerEventParticipationView,
    ServerEventPoochSelect,
    _color_for_severity,
    _discord_timestamp,
    _format_participation_status,
    _list_owner_living_pooches,
    _menu_is_available,
    _truncate,
    build_server_event_embed,
    build_server_event_resolution_embed,
    refresh_public_server_event_message,
    register_active_server_event_views,
)
from src.game.models.events.server_events import ServerEventMenu, ServerEventMenuOption


def _make_menu_option(id=1, label="Enter", description="Enter the contest", requires=None, scoring=None):
    return ServerEventMenuOption(
        id=id,
        label=label,
        description=description,
        filter={},
        requires=requires or {},
        scoring=scoring or {},
    )


def _make_menu(
    id=1,
    name="enter",
    label="Enter the Contest",
    description="",
    max_uses_per_player=1,
    depends_on=None,
    options=None,
):
    return ServerEventMenu(
        id=id,
        name=name,
        label=label,
        description=description,
        max_uses_per_player=max_uses_per_player,
        depends_on=depends_on or [],
        options=options or [_make_menu_option()],
    )


def _make_triggered_server_event(
    occurrence_id=1,
    server_discord_id=200,
    name="Sunday Pageant",
    description="A beauty contest!",
    category="contest",
    severity="moderate",
    flavor_text="",
    expires_at=None,
    participation_count=5,
    menus=None,
    viewer_participation=None,
    message_discord_id=None,
):
    event = MagicMock()
    event.occurrence_id = occurrence_id
    event.server_discord_id = server_discord_id
    event.name = name
    event.description = description
    event.category = category
    event.severity = severity
    event.flavor_text = flavor_text
    event.expires_at = expires_at
    event.participation_count = participation_count
    event.menus = menus if menus is not None else []
    event.viewer_participation = viewer_participation
    event.message_discord_id = message_discord_id
    return event


@pytest.mark.contract
class TestServerEventColorForSeverity:
    def test_known_severities(self):
        assert _color_for_severity("trivial") == discord.Color.light_grey()
        assert _color_for_severity("moderate") == discord.Color.blurple()
        assert _color_for_severity("major") == discord.Color.orange()
        assert _color_for_severity("critical") == discord.Color.red()

    def test_unknown_defaults_to_blurple(self):
        assert _color_for_severity("legendary") == discord.Color.blurple()


@pytest.mark.contract
class TestServerEventTruncate:
    def test_short_text(self):
        assert _truncate("hello") == "hello"

    def test_long_text(self):
        result = _truncate("x" * 2000, limit=10)
        assert result.endswith("...")
        assert len(result) < 2000

    def test_none_input(self):
        assert _truncate(None) == ""


@pytest.mark.contract
class TestServerEventDiscordTimestamp:
    def test_none_returns_dash(self):
        assert _discord_timestamp(None) == "\u2014"

    def test_datetime_formats(self):
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = _discord_timestamp(dt, "R")
        assert result.startswith("<t:")
        assert result.endswith(":R>")


@pytest.mark.contract
class TestMenuIsAvailable:
    def test_available_when_no_deps(self):
        menu = _make_menu(max_uses_per_player=1)
        assert _menu_is_available(menu, set(), {}) is True

    def test_locked_when_dep_not_used(self):
        menu = _make_menu(depends_on=["enter"])
        assert _menu_is_available(menu, set(), {}) is False

    def test_available_when_dep_used(self):
        menu = _make_menu(name="boost", depends_on=["enter"])
        assert _menu_is_available(menu, {"enter"}, {}) is True

    def test_exhausted_max_uses(self):
        menu = _make_menu(max_uses_per_player=1)
        assert _menu_is_available(menu, set(), {"enter": 1}) is False

    def test_unlimited_never_exhausted(self):
        menu = _make_menu(max_uses_per_player=-1)
        assert _menu_is_available(menu, set(), {"enter": 999}) is True


@pytest.mark.contract
class TestBuildServerEventEmbed:
    async def test_basic_embed(self):
        event = _make_triggered_server_event()
        embed = await build_server_event_embed(event, include_viewer_status=False)
        assert isinstance(embed, discord.Embed)
        assert "Sunday Pageant" in embed.title

    async def test_includes_participants(self):
        event = _make_triggered_server_event(participation_count=5)
        embed = await build_server_event_embed(event, include_viewer_status=False)
        participants_field = next(f for f in embed.fields if f.name == "Participants")
        assert "5" in participants_field.value

    async def test_includes_viewer_status(self):
        event = _make_triggered_server_event()
        event.viewer_participation = None
        embed = await build_server_event_embed(event, include_viewer_status=True)
        field_names = [f.name for f in embed.fields]
        assert "Your status" in field_names

    async def test_includes_menus(self):
        menus = [_make_menu(label="Enter"), _make_menu(id=2, name="boost", label="Boost")]
        event = _make_triggered_server_event(menus=menus)
        embed = await build_server_event_embed(event, include_viewer_status=False)
        field_names = [f.name for f in embed.fields]
        assert "How to participate" in field_names


@pytest.mark.contract
class TestBuildServerEventResolutionEmbed:
    async def test_basic_resolution(self):
        resolution = MagicMock()
        resolution.name = "Sunday Pageant"
        resolution.result_summary = MagicMock()
        resolution.result_summary.message = "The event has ended."
        resolution.participant_count = 10
        resolution.winner_owner_ids = [100, 200]

        embed = await build_server_event_resolution_embed(resolution)
        assert isinstance(embed, discord.Embed)
        assert "resolved" in embed.title.lower()
        assert embed.color == discord.Color.green()

    async def test_no_winners(self):
        resolution = MagicMock()
        resolution.name = "Empty Event"
        resolution.result_summary = MagicMock()
        resolution.result_summary.message = "Nobody won."
        resolution.participant_count = 0
        resolution.winner_owner_ids = []

        embed = await build_server_event_resolution_embed(resolution)
        winners_field = next(f for f in embed.fields if f.name == "Winner(s)")
        assert "No winners" in winners_field.value


@pytest.mark.contract
class TestServerEventParticipationView:
    async def test_creates_persistent_view(self):
        view = ServerEventParticipationView(occurrence_id=1, server_discord_id=200)
        assert view.timeout is None

    async def test_custom_id_includes_ids(self):
        view = ServerEventParticipationView(occurrence_id=42, server_discord_id=999)
        assert "999" in view.participate_button.custom_id
        assert "42" in view.participate_button.custom_id


@pytest.mark.contract
class TestRegisterActiveServerEventViews:
    async def test_registers_views_for_active_events(self):
        event = MagicMock()
        event.occurrence_id = 1
        event.server_discord_id = 200
        event.message_discord_id = 12345

        bot = MagicMock()
        bot.add_view = MagicMock()

        with patch("src.bot.ui.server_events.list_active_server_events", new_callable=AsyncMock, return_value=[event]):
            await register_active_server_event_views(bot)
            bot.add_view.assert_called_once()

    async def test_skips_events_without_message_id(self):
        event = MagicMock()
        event.occurrence_id = 1
        event.server_discord_id = 200
        event.message_discord_id = None

        bot = MagicMock()
        bot.add_view = MagicMock()

        with patch("src.bot.ui.server_events.list_active_server_events", new_callable=AsyncMock, return_value=[event]):
            await register_active_server_event_views(bot)
            bot.add_view.assert_not_called()


@pytest.mark.contract
class TestFormatParticipationStatus:
    def test_no_participation(self):
        event = _make_triggered_server_event(viewer_participation=None)
        result = _format_participation_status(event)
        assert "not participated" in result.lower()

    def test_with_submission_shows_menu_and_option(self):
        participation = MagicMock()
        participation.submissions = [
            {"menu_name": "enter", "option_label": "Buy a ticket", "selected_pooch_id": None, "immediate_result": {}}
        ]
        participation.rank = None
        participation.resolution_result = None
        participation.entity_references = MagicMock()
        participation.entity_references.pooches = []

        event = _make_triggered_server_event(viewer_participation=participation)
        result = _format_participation_status(event)
        assert "enter" in result
        assert "Buy a ticket" in result

    def test_with_rank_shows_rank(self):
        participation = MagicMock()
        participation.submissions = [
            {"menu_name": "enter", "option_label": "Enter", "selected_pooch_id": None, "immediate_result": {}}
        ]
        participation.rank = 2
        participation.resolution_result = None
        participation.entity_references = MagicMock()
        participation.entity_references.pooches = []

        event = _make_triggered_server_event(viewer_participation=participation)
        result = _format_participation_status(event)
        assert "2" in result


@pytest.mark.contract
class TestListOwnerLivingPooches:
    async def test_returns_only_alive_pooches(self):
        kennel = MagicMock()
        kennel.id = 1

        alive_pooch = MagicMock()
        alive_pooch.alive = True
        dead_pooch = MagicMock()
        dead_pooch.alive = False

        with (
            patch("src.bot.ui.server_events.get_or_create_owner", new_callable=AsyncMock),
            patch("src.bot.ui.server_events.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]),
            patch(
                "src.bot.ui.server_events.list_kennel_pooches",
                new_callable=AsyncMock,
                return_value=[alive_pooch, dead_pooch],
            ),
        ):
            result = await _list_owner_living_pooches(server_discord_id=200, owner_discord_id=100)
            assert len(result) == 1
            assert result[0].alive is True

    async def test_returns_empty_when_no_kennels(self):
        with (
            patch("src.bot.ui.server_events.get_or_create_owner", new_callable=AsyncMock),
            patch("src.bot.ui.server_events.list_owner_kennels", new_callable=AsyncMock, return_value=[]),
        ):
            result = await _list_owner_living_pooches(server_discord_id=200, owner_discord_id=100)
            assert result == []


@pytest.mark.contract
class TestRefreshPublicServerEventMessage:
    async def test_returns_if_event_is_none(self):
        bot = MagicMock()
        with patch("src.bot.ui.server_events.get_active_server_event", new_callable=AsyncMock, return_value=None):
            await refresh_public_server_event_message(bot, server_discord_id=200, occurrence_id=1)
            bot.get_channel.assert_not_called()

    async def test_returns_if_occurrence_id_mismatch(self):
        bot = MagicMock()
        event = _make_triggered_server_event(occurrence_id=99, message_discord_id=123)
        with patch("src.bot.ui.server_events.get_active_server_event", new_callable=AsyncMock, return_value=event):
            await refresh_public_server_event_message(bot, server_discord_id=200, occurrence_id=1)
            bot.get_channel.assert_not_called()

    async def test_returns_if_no_message_id(self):
        bot = MagicMock()
        event = _make_triggered_server_event(occurrence_id=1, message_discord_id=None)
        with patch("src.bot.ui.server_events.get_active_server_event", new_callable=AsyncMock, return_value=event):
            await refresh_public_server_event_message(bot, server_discord_id=200, occurrence_id=1)
            bot.get_channel.assert_not_called()

    async def test_edits_message_when_found(self):
        bot = MagicMock()
        channel = MagicMock()
        message = MagicMock()
        message.edit = AsyncMock()
        channel.fetch_message = AsyncMock(return_value=message)
        bot.get_channel = MagicMock(return_value=channel)

        event = _make_triggered_server_event(occurrence_id=42, message_discord_id=9999)
        event.server_discord_id = 200
        fake_embed = MagicMock()

        with (
            patch("src.bot.ui.server_events.get_active_server_event", new_callable=AsyncMock, return_value=event),
            patch("src.bot.ui.server_events.get_event_channel", new_callable=AsyncMock, return_value=12345),
            patch("src.bot.ui.server_events.build_server_event_embed", new_callable=AsyncMock, return_value=fake_embed),
        ):
            await refresh_public_server_event_message(bot, server_discord_id=200, occurrence_id=42)
            message.edit.assert_called_once()


@pytest.mark.contract
class TestServerEventPoochSelect:
    async def test_callback_on_success(self):
        option = _make_menu_option(id=1)
        pooch = MagicMock()
        pooch.id = 5
        pooch.name = "Fido"

        select = ServerEventPoochSelect(
            occurrence_id=1,
            server_discord_id=200,
            menu_option=option,
            pooches=[pooch],
        )

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.client = MagicMock()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["5"])),
            patch(
                "src.bot.ui.server_events.participate_in_server_event",
                new_callable=AsyncMock,
                return_value=(True, "Entered!", None),
            ),
            patch("src.bot.ui.server_events.refresh_public_server_event_message", new_callable=AsyncMock),
        ):
            await select.callback(interaction)
            interaction.response.send_message.assert_called_once()

    async def test_callback_on_failure(self):
        option = _make_menu_option(id=1)
        pooch = MagicMock()
        pooch.id = 5
        pooch.name = "Fido"

        select = ServerEventPoochSelect(
            occurrence_id=1,
            server_discord_id=200,
            menu_option=option,
            pooches=[pooch],
        )

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["5"])),
            patch(
                "src.bot.ui.server_events.participate_in_server_event",
                new_callable=AsyncMock,
                return_value=(False, "Already participated.", None),
            ),
        ):
            await select.callback(interaction)
            interaction.response.send_message.assert_called_once()


def _call_participate_button(view, interaction):
    return view.participate_button.callback.callback(view, interaction, view.participate_button)


@pytest.mark.contract
class TestServerEventParticipationViewCallback:
    async def test_event_no_longer_active(self):
        view = ServerEventParticipationView(occurrence_id=1, server_discord_id=200)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        with patch("src.bot.ui.server_events.get_active_server_event", new_callable=AsyncMock, return_value=None):
            await _call_participate_button(view, interaction)
            call_args = interaction.response.send_message.call_args
            assert "no longer active" in call_args[0][0].lower()

    async def test_no_menus_available(self):
        view = ServerEventParticipationView(occurrence_id=1, server_discord_id=200)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        event = _make_triggered_server_event(occurrence_id=1, menus=[])
        event.viewer_participation = None

        with patch("src.bot.ui.server_events.get_active_server_event", new_callable=AsyncMock, return_value=event):
            await _call_participate_button(view, interaction)
            call_args = interaction.response.send_message.call_args
            assert "not accepting" in call_args[0][0].lower()
