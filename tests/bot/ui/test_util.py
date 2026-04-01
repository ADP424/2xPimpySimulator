"""Contract tests for src/bot/ui/util.py."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.utils import MISSING

from src.bot.ui import (
    InteractionResponder,
    build_kwargs,
    defer_interaction,
    edit_interaction,
    mention,
    reply_to_interacted_message,
    run_blocking,
)


def _make_interaction(response_done=False):
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=response_done)
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.channel = MagicMock()
    interaction.channel.send = AsyncMock()
    interaction.message = None
    return interaction


@pytest.mark.contract
class TestMention:
    def test_formats_user_mention(self):
        assert mention(12345) == "<@12345>"

    def test_formats_zero(self):
        assert mention(0) == "<@0>"


@pytest.mark.contract
class TestBuildKwargs:
    def test_includes_set_values(self):
        result = build_kwargs("hello", MISSING, MISSING)
        assert result == {"content": "hello"}

    def test_excludes_missing(self):
        result = build_kwargs(MISSING, MISSING, MISSING)
        assert result == {}

    def test_all_set(self):
        embed = MagicMock()
        view = MagicMock()
        result = build_kwargs("text", embed, view)
        assert "content" in result
        assert "embed" in result
        assert "view" in result


@pytest.mark.contract
class TestRunBlocking:
    async def test_calls_function_in_thread(self):
        def slow_fn(x, y):
            return x + y

        result = await run_blocking(slow_fn, 3, 7)
        assert result == 10


@pytest.mark.contract
class TestDeferInteraction:
    async def test_defers_when_not_done(self):
        interaction = _make_interaction(response_done=False)
        await defer_interaction(interaction, thinking=True, ephemeral=False)
        interaction.response.defer.assert_called_once_with(thinking=True, ephemeral=False)

    async def test_skips_when_already_done(self):
        interaction = _make_interaction(response_done=True)
        await defer_interaction(interaction, thinking=True, ephemeral=False)
        interaction.response.defer.assert_not_called()

    async def test_handles_already_responded_error(self):
        interaction = _make_interaction(response_done=False)
        interaction.response.defer = AsyncMock(side_effect=discord.errors.InteractionResponded(interaction))
        await defer_interaction(interaction)  # should not raise


@pytest.mark.contract
class TestInteractionResponder:
    async def test_defer_sets_did_defer(self):
        interaction = _make_interaction(response_done=False)
        r = InteractionResponder(interaction)
        assert r.did_defer is False
        await r.defer()
        assert r.did_defer is True

    async def test_defer_skips_if_already_done(self):
        interaction = _make_interaction(response_done=True)
        r = InteractionResponder(interaction)
        await r.defer()
        assert r.did_defer is False

    async def test_reply_sends_message_if_not_done(self):
        interaction = _make_interaction(response_done=False)
        r = InteractionResponder(interaction)
        await r.reply(content="Hello!")
        interaction.response.send_message.assert_called_once()

    async def test_reply_uses_followup_if_done(self):
        interaction = _make_interaction(response_done=True)
        r = InteractionResponder(interaction)
        await r.reply(content="Hello!")
        interaction.followup.send.assert_called_once()

    async def test_reply_acks_when_no_visible_content(self):
        """Reply with empty content and no embed should just ack (defer without thinking)."""
        interaction = _make_interaction(response_done=False)
        r = InteractionResponder(interaction)
        await r.reply()  # no content or embed
        # should ack (defer without thinking)
        interaction.response.defer.assert_called_once_with(thinking=False)

    async def test_edit_when_message_present(self):
        interaction = _make_interaction(response_done=False)
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()
        r = InteractionResponder(interaction)
        await r.edit(content="Updated")
        interaction.response.edit_message.assert_called_once()

    async def test_finish_with_error_sends_message(self):
        interaction = _make_interaction(response_done=False)
        r = InteractionResponder(interaction)
        await r.finish_with_error("Oh no!")
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        assert call_args[0][0] == "Oh no!"

    async def test_finish_with_error_uses_followup_if_done(self):
        interaction = _make_interaction(response_done=True)
        r = InteractionResponder(interaction)
        await r.finish_with_error("Broke")
        interaction.followup.send.assert_called_once()

    async def test_ephemeral_flag_passed_to_reply(self):
        interaction = _make_interaction(response_done=False)
        r = InteractionResponder(interaction, ephemeral=True)
        await r.reply(content="Secret")
        call_kwargs = interaction.response.send_message.call_args[1]
        assert call_kwargs.get("ephemeral") is True


@pytest.mark.contract
class TestEditInteraction:
    async def test_edits_message_when_present_and_not_done(self):
        interaction = _make_interaction(response_done=False)
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()
        await edit_interaction(interaction, content="New content")
        interaction.response.edit_message.assert_called_once()

    async def test_edits_message_directly_when_done(self):
        interaction = _make_interaction(response_done=True)
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()
        await edit_interaction(interaction, content="New content")
        interaction.message.edit.assert_called_once()

    async def test_falls_back_to_edit_original_response(self):
        interaction = _make_interaction(response_done=True)
        interaction.message = None
        await edit_interaction(interaction, content="Fallback")
        interaction.edit_original_response.assert_called_once()


@pytest.mark.contract
class TestReplyToInteractedMessage:
    async def test_sends_response_when_not_done(self):
        interaction = _make_interaction(response_done=False)
        await reply_to_interacted_message(interaction, content="Reply!")
        interaction.response.send_message.assert_called_once()

    async def test_acks_when_no_visible_content(self):
        """When content and embed are both empty, should just ack."""
        interaction = _make_interaction(response_done=False)
        await reply_to_interacted_message(interaction)
        # Should defer (ack) instead of sending
        interaction.response.defer.assert_called_once()

    async def test_falls_back_to_followup_when_done(self):
        interaction = _make_interaction(response_done=True)
        await reply_to_interacted_message(interaction, content="Reply!")
        interaction.followup.send.assert_called_once()

    async def test_falls_back_to_message_reply(self):
        interaction = _make_interaction(response_done=True)
        interaction.followup.send = AsyncMock(side_effect=Exception("failed"))
        interaction.message = MagicMock()
        interaction.message.reply = AsyncMock()

        await reply_to_interacted_message(interaction, content="Reply!")
        interaction.message.reply.assert_called_once()

    async def test_falls_back_to_channel_send(self):
        interaction = _make_interaction(response_done=True)
        interaction.followup.send = AsyncMock(side_effect=Exception("failed"))
        interaction.message = None
        await reply_to_interacted_message(interaction, content="Reply!")
        interaction.channel.send.assert_called_once()


@pytest.mark.contract
class TestInteractionResponderExtended:
    async def test_ack_update_when_not_done(self):
        interaction = _make_interaction(response_done=False)
        r = InteractionResponder(interaction)
        await r.ack_update()
        interaction.response.defer.assert_called_once_with(thinking=False)

    async def test_ack_update_skips_when_done(self):
        interaction = _make_interaction(response_done=True)
        r = InteractionResponder(interaction)
        await r.ack_update()
        interaction.response.defer.assert_not_called()

    async def test_ack_update_handles_exception(self):
        interaction = _make_interaction(response_done=False)
        interaction.response.defer = AsyncMock(side_effect=Exception("network error"))
        r = InteractionResponder(interaction)
        await r.ack_update()  # should not raise

    async def test_reply_sends_embed_only(self):
        interaction = _make_interaction(response_done=False)
        r = InteractionResponder(interaction)
        embed = MagicMock()
        await r.reply(embed=embed)
        interaction.response.send_message.assert_called_once()

    async def test_edit_without_message_edits_original(self):
        interaction = _make_interaction(response_done=True)
        interaction.message = None
        r = InteractionResponder(interaction)
        await r.edit(content="Edited")
        interaction.edit_original_response.assert_called_once()

    async def test_reply_falls_back_to_channel_send(self):
        """Reply falls back to channel.send when all else fails."""
        interaction = _make_interaction(response_done=True)
        interaction.followup.send = AsyncMock(side_effect=Exception("failed"))
        interaction.message = None
        r = InteractionResponder(interaction)
        await r.reply(content="Last resort")
        interaction.channel.send.assert_called_once()

    async def test_defer_does_not_re_set_if_already_deferred(self):
        """Calling defer twice should still only report did_defer correctly."""
        interaction = _make_interaction(response_done=False)
        r = InteractionResponder(interaction)
        await r.defer()
        assert r.did_defer is True
        # Second defer: response is now done
        interaction.response.is_done = MagicMock(return_value=True)
        await r.defer()
        # Still deferred
        assert r.did_defer is True


@pytest.mark.contract
class TestEditInteractionExtended:
    async def test_edit_handles_interaction_responded_error(self):
        interaction = _make_interaction(response_done=False)
        interaction.message = MagicMock()
        interaction.message.edit = AsyncMock()
        interaction.response.edit_message = AsyncMock(side_effect=discord.errors.InteractionResponded(interaction))
        # Should fallback to edit_original_response or message.edit
        await edit_interaction(interaction, content="Updated")
        # Either edit_original_response or message.edit was called as fallback
        called = interaction.edit_original_response.called or interaction.message.edit.called
        assert called

    async def test_edit_no_message_and_not_done(self):
        interaction = _make_interaction(response_done=False)
        interaction.message = None
        await edit_interaction(interaction, content="New content")
        interaction.response.edit_message.assert_called_once()


@pytest.mark.contract
class TestDeferInteractionExtended:
    async def test_handles_not_found_error(self):
        interaction = _make_interaction(response_done=False)
        interaction.response.defer = AsyncMock(side_effect=discord.errors.NotFound(MagicMock(), "not found"))
        await defer_interaction(interaction)  # should not raise

    async def test_handles_http_exception(self):
        interaction = _make_interaction(response_done=False)
        interaction.response.defer = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "error"))
        await defer_interaction(interaction)  # should not raise
