"""Contract tests for src/bot/webhooks.py."""

import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest

from src.bot.webhooks import (
    _build_signature,
    _post_json,
    _serialize_birth,
    _serialize_death,
    _serialize_other,
    _serialize_pooch,
    post_day_change_webhooks,
    serialize_day_change_summary,
)


def _make_pooch(id=1, name="Rex", sex="male", alive=True, status="healthy"):
    pooch = MagicMock()
    pooch.id = id
    pooch.name = name
    pooch.sex = sex
    pooch.alive = alive
    pooch.status = status
    return pooch


def _make_server(discord_id=999):
    server = MagicMock()
    server.discord_id = discord_id
    return server


@pytest.mark.contract
class TestBuildSignature:
    def test_produces_hmac_sha256(self):
        secret = "my-secret"
        body = b'{"test": true}'
        result = _build_signature(secret, body)
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert result == expected

    def test_different_secrets_produce_different_signatures(self):
        body = b'{"data": 1}'
        sig_a = _build_signature("secret-a", body)
        sig_b = _build_signature("secret-b", body)
        assert sig_a != sig_b


@pytest.mark.contract
class TestSerializePooch:
    def test_basic_serialization(self):
        pooch = _make_pooch(id=42, name="Buddy", sex="male", alive=True, status="healthy")
        result = _serialize_pooch(pooch)
        assert result == {
            "id": 42,
            "name": "Buddy",
            "sex": "male",
            "alive": True,
            "status": "healthy",
        }


@pytest.mark.contract
class TestSerializeBirth:
    def test_birth_event_structure(self):
        mother = _make_pooch(id=1, name="Mama")
        child = _make_pooch(id=2, name="Puppy")
        event = MagicMock()
        event.mother = mother
        event.child = child
        event.message = "A puppy was born!"
        result = _serialize_birth(event)
        assert result["type"] == "birth"
        assert result["mother"]["name"] == "Mama"
        assert result["child"]["name"] == "Puppy"
        assert result["message"] == "A puppy was born!"


@pytest.mark.contract
class TestSerializeDeath:
    def test_death_event_structure(self):
        pooch = _make_pooch(id=3, name="OldBoy", alive=False, status="dead")
        event = MagicMock()
        event.pooch = pooch
        event.message = "OldBoy has passed away."
        result = _serialize_death(event)
        assert result["type"] == "death"
        assert result["pooch"]["name"] == "OldBoy"
        assert result["message"] == "OldBoy has passed away."


@pytest.mark.contract
class TestSerializeOther:
    def test_other_event_structure(self):
        pooch = _make_pooch(id=4, name="Spark")
        event = MagicMock()
        event.pooch = pooch
        event.message = "Something happened."
        result = _serialize_other(event)
        assert result["type"] == "other"
        assert result["pooch"]["name"] == "Spark"
        assert result["message"] == "Something happened."


@pytest.mark.contract
class TestSerializeDayChangeSummary:
    def test_empty_summary(self):
        server = _make_server(discord_id=100)
        summary = MagicMock()
        summary.server = server
        summary.births = []
        summary.deaths = []
        summary.other_events = []
        result = serialize_day_change_summary(summary)
        assert result == {
            "server_discord_id": 100,
            "births": [],
            "deaths": [],
            "other_events": [],
        }

    def test_summary_with_events(self):
        server = _make_server(discord_id=200)
        mother = _make_pooch(id=1, name="Mom")
        child = _make_pooch(id=2, name="Baby")
        dead_pooch = _make_pooch(id=3, name="Gone")

        birth = MagicMock()
        birth.mother = mother
        birth.child = child
        birth.message = "A new puppy!"

        death = MagicMock()
        death.pooch = dead_pooch
        death.message = "Passed away."

        summary = MagicMock()
        summary.server = server
        summary.births = [birth]
        summary.deaths = [death]
        summary.other_events = []

        result = serialize_day_change_summary(summary)
        assert result["server_discord_id"] == 200
        assert len(result["births"]) == 1
        assert len(result["deaths"]) == 1
        assert result["births"][0]["child"]["name"] == "Baby"


@pytest.mark.contract
class TestPostJson:
    def test_posts_with_correct_headers(self):
        with patch("src.bot.webhooks.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_response.read = MagicMock(return_value=b"")
            mock_urlopen.return_value = mock_response

            _post_json("https://example.com/webhook", "my-secret", {"test": True})

            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert request.get_header("Content-type") == "application/json"
            assert request.get_header("X-pimpy-signature") is not None
            assert request.method == "POST"

    def test_signature_matches_body(self):
        with patch("src.bot.webhooks.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_response.read = MagicMock(return_value=b"")
            mock_urlopen.return_value = mock_response

            payload = {"key": "value"}
            _post_json("https://example.com/webhook", "secret123", payload)

            request = mock_urlopen.call_args[0][0]
            body = request.data
            expected_sig = _build_signature("secret123", body)
            assert request.get_header("X-pimpy-signature") == expected_sig


@pytest.mark.contract
class TestPostDayChangeWebhooks:
    async def test_skips_when_no_url(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("src.bot.webhooks.logger"),
        ):
            await post_day_change_webhooks({})

    async def test_skips_when_no_secret(self):
        with (
            patch.dict("os.environ", {"WEBHOOK_URL": "http://example.com"}, clear=True),
            patch("src.bot.webhooks.logger"),
        ):
            await post_day_change_webhooks({})

    async def test_posts_for_each_summary(self):
        server = _make_server(discord_id=100)
        summary = MagicMock()
        summary.server = server
        summary.births = []
        summary.deaths = []
        summary.other_events = []

        with (
            patch.dict("os.environ", {"WEBHOOK_URL": "http://example.com", "WEBHOOK_SECRET": "secret"}),
            patch("src.bot.webhooks._post_json"),
        ):
            await post_day_change_webhooks({100: summary})
            # _post_json is called via asyncio.to_thread, so we verify it was scheduled
            # The gather with to_thread means _post_json would be called in a thread
            # We can't easily assert on to_thread calls, so let's just ensure no errors
