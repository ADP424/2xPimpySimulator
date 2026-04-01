"""Contract tests for src/bot/ui/events.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui import (
    EventEntityControls,
    EventHistoryPageSource,
    EventMessageView,
    EventResponseSelect,
    build_history_embed,
    build_resolved_event_embed,
    build_triggered_event_embed,
    color_for_severity,
    detail_entries,
    discord_timestamp,
    entity_reference_lines,
    format_option_line,
    format_option_select_description,
    format_result_summary,
    get_dm_channel,
    send_all_pending_event_dms,
    send_event_history_dm,
    send_triggered_event_dm,
    signed,
    truncate,
)
from src.game.models.events import (
    OwnerEventContext,
    OwnerEventEntityReferences,
    OwnerEventOption,
    OwnerEventResult,
)


def _make_option(
    id=1,
    label="Accept",
    description="Accept the offer",
    min_money=0,
    min_bloodskulls=0,
    is_default=False,
    is_visible=True,
):
    return OwnerEventOption(
        id=id,
        label=label,
        description=description,
        min_money=min_money,
        min_bloodskulls=min_bloodskulls,
        is_default=is_default,
        is_visible=is_visible,
    )


def _make_triggered_event(
    requires_response=False,
    severity="moderate",
    options=None,
    result=None,
    flavor_text="",
    expires_at=None,
):
    event = MagicMock()
    event.active_owner_event_id = 1
    event.event_id = 10
    event.name = "Test Event"
    event.category = "fortune"
    event.description = "Something happened."
    event.flavor_text = flavor_text
    event.severity = severity
    event.requires_response = requires_response
    event.response_timeout = 300
    event.expires_at = expires_at
    event.context = OwnerEventContext(owner_discord_id=100)
    event.options = options or []
    event.result = result
    event.entity_references = OwnerEventEntityReferences()
    return event


@pytest.mark.contract
class TestColorForSeverity:
    def test_trivial(self):
        assert color_for_severity("trivial") == discord.Color.light_grey()

    def test_moderate(self):
        assert color_for_severity("moderate") == discord.Color.blurple()

    def test_major(self):
        assert color_for_severity("major") == discord.Color.orange()

    def test_critical(self):
        assert color_for_severity("critical") == discord.Color.red()

    def test_unknown_defaults_to_blurple(self):
        assert color_for_severity("unknown") == discord.Color.blurple()

    def test_case_insensitive(self):
        assert color_for_severity("CRITICAL") == discord.Color.red()
        assert color_for_severity("Trivial") == discord.Color.light_grey()


@pytest.mark.contract
class TestTruncate:
    def test_short_text_unchanged(self):
        assert truncate("hello") == "hello"

    def test_long_text_truncated(self):
        result = truncate("x" * 2000, limit=10)
        # Implementation: text[:max(limit-1, 0)] + "..." so truncated body is 9 chars + "..."
        assert result.endswith("...")
        assert len(result) < 2000  # significantly shorter than input

    def test_exact_limit_unchanged(self):
        text = "a" * 100
        assert truncate(text, limit=100) == text

    def test_strips_whitespace(self):
        assert truncate("  hello  ") == "hello"

    def test_empty_string(self):
        assert truncate("") == ""


@pytest.mark.contract
class TestDiscordTimestamp:
    def test_none_returns_dash(self):
        assert discord_timestamp(None) == "\u2014"

    def test_datetime_object(self):
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = discord_timestamp(dt, "f")
        assert result.startswith("<t:")
        assert result.endswith(":f>")

    def test_iso_string(self):
        result = discord_timestamp("2024-01-15T12:00:00+00:00", "R")
        assert result.startswith("<t:")
        assert result.endswith(":R>")

    def test_naive_datetime_gets_utc(self):
        dt = datetime(2024, 1, 15, 12, 0, 0)
        result = discord_timestamp(dt, "f")
        assert "<t:" in result


@pytest.mark.contract
class TestFormatOptionLine:
    def test_basic_option(self):
        option = _make_option(label="Run Away", description="Flee the scene")
        result = format_option_line(option)
        assert "**Run Away**" in result
        assert "Flee the scene" in result

    def test_option_with_money_requirement(self):
        option = _make_option(label="Buy", description="Purchase it", min_money=100)
        result = format_option_line(option)
        assert "$100" in result
        assert "requires" in result.lower()

    def test_option_with_bloodskull_requirement(self):
        option = _make_option(label="Sacrifice", description="Dark arts", min_bloodskulls=5)
        result = format_option_line(option)
        assert "5 bloodskulls" in result

    def test_option_with_both_requirements(self):
        option = _make_option(label="Both", description="Costly", min_money=50, min_bloodskulls=3)
        result = format_option_line(option)
        assert "$50" in result
        assert "3 bloodskulls" in result

    def test_option_no_description(self):
        option = _make_option(label="Simple", description="")
        result = format_option_line(option)
        assert "**Simple**" in result


@pytest.mark.contract
class TestFormatResultSummary:
    def test_none_result(self):
        result = format_result_summary(None)
        assert result == "No recorded outcome."

    def test_result_with_message(self):
        r = OwnerEventResult(message="You found gold!")
        result = format_result_summary(r)
        assert "You found gold!" in result

    def test_result_with_money_change(self):
        r = OwnerEventResult(money_changed=100)
        result = format_result_summary(r)
        assert "Dollars: +100" in result

    def test_result_with_negative_money(self):
        r = OwnerEventResult(money_changed=-50)
        result = format_result_summary(r)
        assert "Dollars: -50" in result

    def test_result_with_bloodskulls(self):
        r = OwnerEventResult(bloodskulls_changed=3)
        result = format_result_summary(r)
        assert "Bloodskulls: +3" in result

    def test_result_with_created_pooches_extra_data(self):
        r = OwnerEventResult(extra_data={"created_pooches": [{"pooch_name": "Fido", "sex": "male", "age": 0}]})
        result = format_result_summary(r)
        assert "Created pooch: Fido" in result
        assert "Male" in result

    def test_result_with_killed_pooches_extra_data(self):
        r = OwnerEventResult(
            pooches_killed=[1],
            extra_data={"killed_pooches": [{"pooch_name": "Rex"}]},
        )
        result = format_result_summary(r)
        assert "Lost pooch: Rex" in result

    def test_result_with_health_changes(self):
        r = OwnerEventResult(extra_data={"health_changes": [{"pooch_id": 1, "pooch_name": "Buddy", "amount": -5}]})
        result = format_result_summary(r)
        assert "Health: Buddy -5" in result

    def test_result_with_age_changes(self):
        r = OwnerEventResult(
            extra_data={"age_changes": [{"pooch_id": 1, "pooch_name": "Oldie", "amount": 2, "new_age": 14}]}
        )
        result = format_result_summary(r)
        assert "Age: Oldie +2" in result
        assert "now age 14" in result

    def test_result_with_mutations_added(self):
        r = OwnerEventResult(
            mutations_added=[(1, 2)],
            extra_data={"mutations_added_details": [{"pooch_name": "Spot", "mutation_name": "Cataracts"}]},
        )
        result = format_result_summary(r)
        assert "Mutation gained: Spot" in result

    def test_result_with_renamed_pooches(self):
        r = OwnerEventResult(extra_data={"renamed_pooches": [{"old_name": "Dog", "new_name": "Super Dog"}]})
        result = format_result_summary(r)
        assert "Dog" in result and "Super Dog" in result

    def test_empty_result(self):
        r = OwnerEventResult()
        result = format_result_summary(r)
        assert result == "No recorded outcome."


@pytest.mark.contract
class TestBuildTriggeredEventEmbed:
    def test_basic_embed(self):
        event = _make_triggered_event(severity="moderate")
        embed = build_triggered_event_embed(event)
        assert isinstance(embed, discord.Embed)
        assert "Test Event" in embed.title

    def test_auto_resolved_shows_outcome(self):
        result = OwnerEventResult(message="Auto result")
        event = _make_triggered_event(
            requires_response=False,
            result=result,
        )
        embed = build_triggered_event_embed(event)
        # Should have an Outcome field
        field_names = [f.name for f in embed.fields]
        assert "Outcome" in field_names

    def test_requires_response_shows_options(self):
        options = [_make_option(label="Accept"), _make_option(id=2, label="Decline")]
        event = _make_triggered_event(
            requires_response=True,
            options=options,
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        embed = build_triggered_event_embed(event)
        field_names = [f.name for f in embed.fields]
        assert "Response Options" in field_names

    def test_flavor_text_included(self):
        event = _make_triggered_event(flavor_text="A strange wind blows.")
        embed = build_triggered_event_embed(event)
        assert "A strange wind blows." in embed.description


@pytest.mark.contract
class TestBuildResolvedEventEmbed:
    def test_includes_selected_option(self):
        event = _make_triggered_event()
        result = OwnerEventResult(message="Done")
        embed = build_resolved_event_embed(event, result=result, selected_option_label="Accept")
        field_names = [f.name for f in embed.fields]
        assert "Selected Option" in field_names


@pytest.mark.contract
class TestEventMessageView:
    async def test_creates_with_response_disabled(self):
        event = _make_triggered_event(requires_response=False)
        view = EventMessageView(owner_discord_id=100, event=event, response_enabled=False)
        assert view.response_enabled is False

    async def test_creates_with_response_enabled(self):
        options = [_make_option()]
        event = _make_triggered_event(
            requires_response=True,
            options=options,
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        view = EventMessageView(owner_discord_id=100, event=event, response_enabled=True)
        assert view.response_enabled is True

    async def test_interaction_check_rejects_other_users(self):
        event = _make_triggered_event()
        view = EventMessageView(owner_discord_id=100, event=event, response_enabled=False)
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 999
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        result = await view.interaction_check(interaction)
        assert result is False

    async def test_interaction_check_allows_owner(self):
        event = _make_triggered_event()
        view = EventMessageView(owner_discord_id=100, event=event, response_enabled=False)
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 100
        result = await view.interaction_check(interaction)
        assert result is True


@pytest.mark.contract
class TestEventHistoryPageSource:
    async def test_empty_records(self):
        source = EventHistoryPageSource(records=[], owner_discord_id=100)
        view = MagicMock()
        await source.load()
        assert source.page_count() == 1
        content, embed = await source.render(view, 0)
        assert content is None
        assert isinstance(embed, discord.Embed)
        assert "No event history" in embed.description

    async def test_page_count_matches_records(self):
        records = [MagicMock() for _ in range(5)]
        source = EventHistoryPageSource(records=records, owner_discord_id=100)
        assert source.page_count() == 5


@pytest.mark.contract
class TestSendTriggeredEventDm:
    async def test_returns_false_when_no_dm_channel(self):
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(side_effect=Exception("not found"))

        event = _make_triggered_event()
        result = await send_triggered_event_dm(bot, 100, event)
        assert result is False

    async def test_returns_true_on_success(self):
        bot = MagicMock()
        user = MagicMock()
        dm_channel = MagicMock(spec=discord.DMChannel)
        dm_channel.send = AsyncMock()
        user.dm_channel = dm_channel
        bot.get_user = MagicMock(return_value=user)

        event = _make_triggered_event(requires_response=False)
        result = await send_triggered_event_dm(bot, 100, event)
        assert result is True
        dm_channel.send.assert_called_once()


@pytest.mark.contract
class TestSendAllPendingEventDms:
    async def test_counts_sent_and_failed(self):
        bot = MagicMock()
        events = [_make_triggered_event(), _make_triggered_event()]

        with patch("src.bot.ui.events.send_triggered_event_dm", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = [True, False]
            sent, failed = await send_all_pending_event_dms(bot, 100, events)
            assert sent == 1
            assert failed == 1


@pytest.mark.contract
class TestSendEventHistoryDm:
    async def test_returns_false_when_no_records(self):
        bot = MagicMock()
        with patch("src.bot.ui.events.get_event_history", new_callable=AsyncMock, return_value=[]):
            result = await send_event_history_dm(bot, 100)
            assert result is False

    async def test_returns_false_when_no_dm_channel(self):
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(side_effect=Exception("not found"))

        records = [MagicMock()]
        with patch("src.bot.ui.events.get_event_history", new_callable=AsyncMock, return_value=records):
            result = await send_event_history_dm(bot, 100)
            assert result is False

    async def test_returns_true_on_success(self):
        bot = MagicMock()
        user = MagicMock()
        dm_channel = MagicMock(spec=discord.DMChannel)
        dm_channel.send = AsyncMock()
        user.dm_channel = dm_channel
        bot.get_user = MagicMock(return_value=user)

        records = [MagicMock()]
        # Set up a proper entity references mock so EventHistoryPageSource.render works
        for r in records:
            r.entity_references = OwnerEventEntityReferences()
            r.context = OwnerEventContext(owner_discord_id=100)
            r.name = "Test"
            r.description = "desc"
            r.severity = "moderate"
            r.category = "fortune"
            r.triggered_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
            r.completed_at = None
            r.timed_out = False
            r.selected_option_label = None
            r.flavor_text = ""
            r.result_summary = OwnerEventResult(message="Done")

        with patch("src.bot.ui.events.get_event_history", new_callable=AsyncMock, return_value=records):
            result = await send_event_history_dm(bot, 100)
            assert result is True


@pytest.mark.contract
class TestSigned:
    def test_positive(self):
        assert signed(5) == "+5"

    def test_negative(self):
        assert signed(-3) == "-3"

    def test_zero(self):
        assert signed(0) == "+0"


@pytest.mark.contract
class TestDetailEntries:
    def test_list_input(self):
        data = [{"pooch_id": 1, "amount": 5}]
        result = detail_entries(data, id_key="pooch_id", value_key="amount")
        assert len(result) == 1
        assert result[0]["pooch_id"] == 1

    def test_dict_input(self):
        data = {"1": 10, "2": 20}
        result = detail_entries(data, id_key="pooch_id", value_key="amount")
        assert len(result) == 2

    def test_empty_list(self):
        assert detail_entries([], id_key="pooch_id", value_key="amount") == []

    def test_non_list_non_dict(self):
        assert detail_entries("not a list", id_key="k", value_key="v") == []


@pytest.mark.contract
class TestFormatOptionSelectDescription:
    def test_with_description(self):
        option = _make_option(label="Join", description="Join the event", min_money=0)
        result = format_option_select_description(option)
        assert "Join the event" in result

    def test_with_costs(self):
        option = _make_option(label="Pay", description="", min_money=50, min_bloodskulls=2)
        result = format_option_select_description(option)
        assert "$50" in result
        assert "2 skulls" in result

    def test_no_description_no_costs(self):
        option = _make_option(label="Simple", description="")
        result = format_option_select_description(option)
        assert "No description" in result


@pytest.mark.contract
class TestEntityReferenceLines:
    def test_empty_references(self):
        context = OwnerEventContext(owner_discord_id=100)
        refs = OwnerEventEntityReferences()
        lines = entity_reference_lines(context, refs)
        assert lines == []

    def test_with_kennel_id(self):
        context = OwnerEventContext(owner_discord_id=100, selected_kennel_id=5)
        refs = OwnerEventEntityReferences()
        lines = entity_reference_lines(context, refs)
        assert any("Kennel #5" in line for line in lines)

    def test_with_affected_kennels(self):
        context = OwnerEventContext(owner_discord_id=100, affected_kennel_ids=[3, 7])
        refs = OwnerEventEntityReferences()
        lines = entity_reference_lines(context, refs)
        assert any("Kennel #3" in line for line in lines)


@pytest.mark.contract
class TestGetDmChannel:
    async def test_returns_none_when_user_not_found(self):
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(side_effect=Exception("not found"))
        result = await get_dm_channel(bot, 999)
        assert result is None

    async def test_returns_dm_channel(self):
        bot = MagicMock()
        user = MagicMock()
        dm_channel = MagicMock(spec=discord.DMChannel)
        user.dm_channel = dm_channel
        bot.get_user = MagicMock(return_value=user)

        result = await get_dm_channel(bot, 100)
        assert result is dm_channel

    async def test_creates_dm_if_none(self):
        bot = MagicMock()
        user = MagicMock()
        dm_channel = MagicMock(spec=discord.DMChannel)
        user.dm_channel = None
        user.create_dm = AsyncMock(return_value=dm_channel)
        bot.get_user = MagicMock(return_value=user)

        result = await get_dm_channel(bot, 100)
        assert result is dm_channel
        user.create_dm.assert_called_once()


@pytest.mark.contract
class TestEventResponseSelect:
    async def test_wrong_user_is_rejected(self):
        options = [_make_option()]
        event = _make_triggered_event(requires_response=True, options=options)
        select = EventResponseSelect(owner_discord_id=100, event=event)

        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 999  # Not the owner
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        with patch.object(type(select), "values", new_callable=lambda: property(lambda self: [str(options[0].id)])):
            await select.callback(interaction)
            call_args = interaction.response.send_message.call_args
            assert "not yours" in call_args[0][0].lower()


@pytest.mark.contract
class TestEventEntityControls:
    def test_no_entity_references_no_selects(self):
        refs = OwnerEventEntityReferences()
        controls = EventEntityControls(owner_discord_id=100, entity_references=refs)
        assert len(controls.selects) == 0

    def test_info_button_starts_disabled(self):
        refs = OwnerEventEntityReferences()
        controls = EventEntityControls(owner_discord_id=100, entity_references=refs)
        assert controls.info_button.disabled is True

    def test_attach_with_no_selects_does_not_add_info_button(self):
        refs = OwnerEventEntityReferences()
        controls = EventEntityControls(owner_discord_id=100, entity_references=refs)
        view = MagicMock()
        view.add_item = MagicMock()
        controls.attach(view, row_start=0)
        # No selects, so info button should not be added
        view.add_item.assert_not_called()


@pytest.mark.contract
class TestBuildHistoryEmbed:
    def test_basic_history_embed(self):
        record = MagicMock()
        record.name = "Lost Treasure"
        record.description = "A treasure was found."
        record.severity = "moderate"
        record.category = "fortune"
        record.triggered_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
        record.completed_at = datetime(2024, 6, 2, tzinfo=timezone.utc)
        record.timed_out = False
        record.selected_option_label = "Accept"
        record.flavor_text = ""
        record.result_summary = OwnerEventResult(message="You gained $100")
        record.context = OwnerEventContext(owner_discord_id=100)
        record.entity_references = OwnerEventEntityReferences()

        embed = build_history_embed(record, page_index=0, page_count=3)
        assert isinstance(embed, discord.Embed)
        assert "Lost Treasure" in embed.title
        footer = embed.footer.text
        assert "1/3" in footer

    def test_timed_out_shows_status(self):
        record = MagicMock()
        record.name = "Expired"
        record.description = ""
        record.severity = "trivial"
        record.category = "fortune"
        record.triggered_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        record.completed_at = None
        record.timed_out = True
        record.selected_option_label = None
        record.flavor_text = ""
        record.result_summary = OwnerEventResult()
        record.context = OwnerEventContext(owner_discord_id=100)
        record.entity_references = OwnerEventEntityReferences()

        embed = build_history_embed(record, page_index=0, page_count=1)
        details_field = next(f for f in embed.fields if f.name == "Details")
        assert "Timed out" in details_field.value

    def test_auto_resolved_shows_status(self):
        record = MagicMock()
        record.name = "Auto Event"
        record.description = ""
        record.severity = "trivial"
        record.category = "fortune"
        record.triggered_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        record.completed_at = None
        record.timed_out = False
        record.selected_option_label = None
        record.flavor_text = ""
        record.result_summary = OwnerEventResult()
        record.context = OwnerEventContext(owner_discord_id=100)
        record.entity_references = OwnerEventEntityReferences()

        embed = build_history_embed(record, page_index=0, page_count=1)
        details_field = next(f for f in embed.fields if f.name == "Details")
        assert "Auto-resolved" in details_field.value


@pytest.mark.contract
class TestEventMessageViewTimeout:
    async def test_on_timeout_does_nothing_when_no_message(self):
        event = _make_triggered_event(requires_response=True, options=[_make_option()])
        event.expires_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
        view = EventMessageView(owner_discord_id=100, event=event, response_enabled=True)
        view.message = None  # No message assigned
        # Should not raise
        await view.on_timeout()

    async def test_on_timeout_edits_message(self):
        event = _make_triggered_event(requires_response=True, options=[_make_option()])
        event.expires_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
        view = EventMessageView(owner_discord_id=100, event=event, response_enabled=True)

        message = MagicMock()
        message.edit = AsyncMock()
        view.message = message

        await view.on_timeout()
        message.edit.assert_called_once()


@pytest.mark.contract
class TestFormatResultSummaryExtended:
    def test_result_with_breeding_cooldown_changes(self):
        r = OwnerEventResult(
            extra_data={"breeding_cooldown_changes": [{"pooch_name": "Max", "pooch_id": 1, "cooldown": 3}]}
        )
        result = format_result_summary(r)
        assert "Max" in result
        assert "cooldown" in result.lower()

    def test_result_with_transferred_pooches(self):
        r = OwnerEventResult(
            extra_data={"transferred_pooches": [{"pooch_name": "Spot", "pooch_id": 1, "destination": "new owner"}]}
        )
        result = format_result_summary(r)
        assert "Transferred: Spot" in result

    def test_result_with_breeds_added(self):
        r = OwnerEventResult(
            extra_data={"breeds_added": [{"pooch_name": "Rex", "breed_name": "Labrador", "weight": 0.5}]}
        )
        result = format_result_summary(r)
        assert "Breed added: Rex" in result
        assert "Labrador" in result

    def test_result_with_mutations_removed(self):
        r = OwnerEventResult(
            mutations_removed=[(1, 2)],
            extra_data={"mutations_removed_details": [{"pooch_name": "Spot", "mutation_name": "Blindness"}]},
        )
        result = format_result_summary(r)
        assert "Mutation removed: Spot" in result

    def test_result_with_kennel_capacity_changes(self):
        r = OwnerEventResult(
            extra_data={
                "kennel_capacity_changes": [{"kennel_id": 1, "kennel_name": "The Barn", "amount": 2, "new_limit": 7}]
            }
        )
        result = format_result_summary(r)
        assert "Kennel capacity: The Barn" in result
        assert "+2" in result
