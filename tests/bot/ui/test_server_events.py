"""Contract tests for src/bot/ui/server_events.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.server_events import (
    ServerEventOptionSelect,
    ServerEventParticipationView,
    ServerEventPoochSelect,
    _color_for_severity,
    _discord_timestamp,
    _format_participation_status,
    _format_server_option_line,
    _list_owner_living_pooches,
    _truncate,
    build_server_event_embed,
    build_server_event_resolution_embed,
    refresh_public_server_event_message,
    register_active_server_event_views,
)


def _make_server_event_option(
    id=1,
    label="Enter",
    description="Enter the contest",
    min_money=0,
    min_bloodskulls=0,
    requires_pooch_selection=False,
):
    option = MagicMock()
    option.id = id
    option.label = label
    option.description = description
    option.min_money = min_money
    option.min_bloodskulls = min_bloodskulls
    option.requires_pooch_selection = requires_pooch_selection
    return option


def _make_triggered_server_event(
    occurrence_id=1,
    server_discord_id=200,
    name="Sunday Pageant",
    description="A beauty contest!",
    category="contest",
    severity="moderate",
    flavor_text="",
    expires_at=None,
    max_participants=0,
    participation_count=5,
    options=None,
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
    event.max_participants = max_participants
    event.participation_count = participation_count
    event.options = options or []
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
        # Implementation: text[:max(limit-1, 0)] + "..." so truncated body is 9 chars + "..."
        assert result.endswith("...")
        assert len(result) < 2000  # significantly shorter than input

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
class TestFormatServerOptionLine:
    def test_basic_option(self):
        option = _make_server_event_option(label="Join", description="Join the event")
        result = _format_server_option_line(option)
        assert "**Join**" in result
        assert "Join the event" in result

    def test_with_money_requirement(self):
        option = _make_server_event_option(label="Enter", min_money=100)
        result = _format_server_option_line(option)
        assert "$100" in result
        assert "requires" in result.lower()

    def test_with_pooch_requirement(self):
        option = _make_server_event_option(label="Enter", requires_pooch_selection=True)
        result = _format_server_option_line(option)
        assert "a pooch" in result


@pytest.mark.contract
class TestBuildServerEventEmbed:
    async def test_basic_embed(self):
        event = _make_triggered_server_event()
        embed = await build_server_event_embed(event, include_viewer_status=False)
        assert isinstance(embed, discord.Embed)
        assert "Sunday Pageant" in embed.title

    async def test_includes_participants(self):
        event = _make_triggered_server_event(participation_count=5, max_participants=0)
        embed = await build_server_event_embed(event, include_viewer_status=False)
        participants_field = next(f for f in embed.fields if f.name == "Participants")
        # max_participants <= 0 means unlimited
        assert "\u221e" in participants_field.value  # infinity symbol

    async def test_includes_viewer_status(self):
        event = _make_triggered_server_event()
        event.viewer_participation = None
        embed = await build_server_event_embed(event, include_viewer_status=True)
        field_names = [f.name for f in embed.fields]
        assert "Your status" in field_names

    async def test_includes_options(self):
        options = [_make_server_event_option(label="Fight"), _make_server_event_option(id=2, label="Flee")]
        event = _make_triggered_server_event(options=options)
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
        assert view.timeout is None  # persistent view

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

    def test_with_participation_shows_option(self):
        option = MagicMock()
        option.label = "Donate"

        participation = MagicMock()
        participation.selected_option = option
        participation.context = MagicMock()
        participation.context.selected_pooch_id = None
        participation.rank = None
        participation.immediate_result = None
        participation.resolution_result = None
        participation.entity_references = MagicMock()
        participation.entity_references.pooches = []

        event = _make_triggered_server_event(viewer_participation=participation)
        result = _format_participation_status(event)
        assert "Donate" in result

    def test_with_rank_shows_rank(self):
        option = MagicMock()
        option.label = "Enter"

        participation = MagicMock()
        participation.selected_option = option
        participation.context = MagicMock()
        participation.context.selected_pooch_id = None
        participation.rank = 2
        participation.immediate_result = None
        participation.resolution_result = None
        participation.entity_references = MagicMock()
        participation.entity_references.pooches = []

        event = _make_triggered_server_event(viewer_participation=participation)
        result = _format_participation_status(event)
        assert "2" in result

    def test_with_immediate_result_message(self):
        option = MagicMock()
        option.label = "Compete"

        immediate_result = MagicMock()
        immediate_result.message = "You scored 42 points!"

        participation = MagicMock()
        participation.selected_option = option
        participation.context = MagicMock()
        participation.context.selected_pooch_id = None
        participation.rank = None
        participation.immediate_result = immediate_result
        participation.resolution_result = None
        participation.entity_references = MagicMock()
        participation.entity_references.pooches = []

        event = _make_triggered_server_event(viewer_participation=participation)
        result = _format_participation_status(event)
        assert "42 points" in result


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
        option = _make_server_event_option(id=1)
        pooch = MagicMock()
        pooch.id = 5
        pooch.name = "Fido"

        select = ServerEventPoochSelect(
            occurrence_id=1,
            server_discord_id=200,
            option=option,
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
        option = _make_server_event_option(id=1)
        pooch = MagicMock()
        pooch.id = 5
        pooch.name = "Fido"

        select = ServerEventPoochSelect(
            occurrence_id=1,
            server_discord_id=200,
            option=option,
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


@pytest.mark.contract
class TestServerEventOptionSelectCallback:
    async def test_callback_requires_pooch_selection_no_pooches(self):
        option = _make_server_event_option(id=1, requires_pooch_selection=True)
        select = ServerEventOptionSelect(
            occurrence_id=1,
            server_discord_id=200,
            options=[option],
        )
        # server_options dict is keyed by option.id (int), values[0] is a string -> int conversion happens in callback.
        # Ensure the dict key matches the converted int.
        select.server_options = {option.id: option}

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: [str(option.id)])),
            patch("src.bot.ui.server_events._list_owner_living_pooches", new_callable=AsyncMock, return_value=[]),
        ):
            await select.callback(interaction)
            call_args = interaction.response.send_message.call_args
            assert "living pooches" in call_args[0][0].lower()

    async def test_callback_no_pooch_needed_participates_directly(self):
        option = _make_server_event_option(id=1, requires_pooch_selection=False)
        select = ServerEventOptionSelect(
            occurrence_id=1,
            server_discord_id=200,
            options=[option],
        )
        select.server_options = {option.id: option}

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.client = MagicMock()

        with (
            patch.object(type(select), "values", new_callable=lambda: property(lambda self: [str(option.id)])),
            patch(
                "src.bot.ui.server_events.participate_in_server_event",
                new_callable=AsyncMock,
                return_value=(True, "Joined!", None),
            ),
            patch("src.bot.ui.server_events.refresh_public_server_event_message", new_callable=AsyncMock),
        ):
            await select.callback(interaction)
            interaction.response.send_message.assert_called_once()


def _call_participate_button(view, interaction):
    """Helper to call the participate_button's underlying function."""
    # discord.ui.button creates an _ItemCallback. The actual coroutine is at .callback.callback
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

    async def test_already_participated(self):
        view = ServerEventParticipationView(occurrence_id=1, server_discord_id=200)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        event = _make_triggered_server_event(occurrence_id=1)
        event.viewer_participation = MagicMock()  # already participated

        with patch("src.bot.ui.server_events.get_active_server_event", new_callable=AsyncMock, return_value=event):
            await _call_participate_button(view, interaction)
            call_args = interaction.response.send_message.call_args
            assert "already participated" in call_args[0][0].lower()

    async def test_no_options_available(self):
        view = ServerEventParticipationView(occurrence_id=1, server_discord_id=200)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        event = _make_triggered_server_event(occurrence_id=1, options=[])
        event.viewer_participation = None

        with patch("src.bot.ui.server_events.get_active_server_event", new_callable=AsyncMock, return_value=event):
            await _call_participate_button(view, interaction)
            call_args = interaction.response.send_message.call_args
            assert "not accepting" in call_args[0][0].lower()

    async def test_multiple_options_shows_select(self):
        view = ServerEventParticipationView(occurrence_id=1, server_discord_id=200)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        options = [
            _make_server_event_option(id=1, label="Option A"),
            _make_server_event_option(id=2, label="Option B"),
        ]
        event = _make_triggered_server_event(occurrence_id=1, options=options)
        event.viewer_participation = None

        with patch("src.bot.ui.server_events.get_active_server_event", new_callable=AsyncMock, return_value=event):
            await _call_participate_button(view, interaction)
            call_args = interaction.response.send_message.call_args
            assert "how to participate" in call_args[0][0].lower()
