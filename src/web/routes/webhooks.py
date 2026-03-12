from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from flask import Blueprint, abort, current_app, jsonify, request

from src.web.app import socketio
from src.web.events import broadcast_day_change

webhooks_bp = Blueprint("webhooks", __name__)


def _verify_signature(secret: str, body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature."""

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class WebhookPooch:
    id: int
    name: str
    sex: str | None = None
    alive: bool | None = None
    status: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "WebhookPooch":
        return WebhookPooch(
            id=int(data["id"]),
            name=str(data.get("name", "")),
            sex=data.get("sex"),
            alive=data.get("alive"),
            status=data.get("status"),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.sex is not None:
            out["sex"] = self.sex
        if self.alive is not None:
            out["alive"] = self.alive
        if self.status is not None:
            out["status"] = self.status
        return out


@dataclass(frozen=True)
class WebhookBirthEvent:
    type: str
    mother: WebhookPooch
    child: WebhookPooch
    message: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "WebhookBirthEvent":
        return WebhookBirthEvent(
            type="birth",
            mother=WebhookPooch.from_dict(data["mother"]),
            child=WebhookPooch.from_dict(data["child"]),
            message=str(data.get("message", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "mother": self.mother.to_dict(),
            "child": self.child.to_dict(),
            "message": self.message,
        }


@dataclass(frozen=True)
class WebhookDeathEvent:
    type: str
    pooch: WebhookPooch
    message: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "WebhookDeathEvent":
        return WebhookDeathEvent(
            type="death",
            pooch=WebhookPooch.from_dict(data["pooch"]),
            message=str(data.get("message", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "pooch": self.pooch.to_dict(),
            "message": self.message,
        }


@dataclass(frozen=True)
class WebhookOtherEvent:
    type: str
    pooch: WebhookPooch
    message: str

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "WebhookOtherEvent":
        return WebhookOtherEvent(
            type="other",
            pooch=WebhookPooch.from_dict(data["pooch"]),
            message=str(data.get("message", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "pooch": self.pooch.to_dict(),
            "message": self.message,
        }


@dataclass(frozen=True)
class WebhookDayChangeSummary:
    server_discord_id: int
    births: list[WebhookBirthEvent]
    deaths: list[WebhookDeathEvent]
    other_events: list[WebhookOtherEvent]

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "WebhookDayChangeSummary":
        births = [WebhookBirthEvent.from_dict(e) for e in data.get("births", [])]
        deaths = [WebhookDeathEvent.from_dict(e) for e in data.get("deaths", [])]
        others = [WebhookOtherEvent.from_dict(e) for e in data.get("other_events", [])]
        return WebhookDayChangeSummary(
            server_discord_id=int(data["server_discord_id"]),
            births=births,
            deaths=deaths,
            other_events=others,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "server_discord_id": self.server_discord_id,
            "births": [b.to_dict() for b in self.births],
            "deaths": [d.to_dict() for d in self.deaths],
            "other_events": [o.to_dict() for o in self.other_events],
        }


@dataclass(frozen=True)
class WebhookEnvelope:
    event: str
    data: WebhookDayChangeSummary

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> "WebhookEnvelope":
        event = str(payload.get("event", ""))
        if event != "day_change":
            raise ValueError("Unsupported webhook event")
        return WebhookEnvelope(event=event, data=WebhookDayChangeSummary.from_dict(payload["data"]))


@webhooks_bp.post("/day-change")
def day_change_webhook():
    """Receive day-change summaries from the bot and push to connected web clients."""

    secret = current_app.config.get("WEBHOOK_SECRET")
    if not secret:
        abort(503, description="Webhook secret not configured")

    body = request.get_data(cache=False)
    signature = request.headers.get("X-Pimpy-Signature", "")

    if not signature or not _verify_signature(secret, body, signature):
        abort(401, description="Invalid signature")

    try:
        payload_raw = json.loads(body.decode("utf-8"))
        envelope = WebhookEnvelope.from_dict(payload_raw)
    except Exception:
        abort(400, description="Invalid payload")

    summary_dict = envelope.data.to_dict()

    # Emit to subscribed clients
    broadcast_day_change(socketio, summary_dict)

    return jsonify({"ok": True})
