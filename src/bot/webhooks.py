from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import urllib.request
from typing import Any

from game.models.events.birth_event import BirthEvent
from game.models.events.day_change_summary import DayChangeSummary
from game.models.events.death_event import DeathEvent
from game.models.events.other_event import OtherEvent
from game.models.pooch import Pooch
from logger import get_logger

logger = get_logger("bot/webhooks")


def _build_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _serialize_pooch(pooch: Pooch) -> dict[str, Any]:
    return {
        "id": pooch.id,
        "name": pooch.name,
        "sex": pooch.sex,
        "alive": pooch.alive,
        "status": pooch.status,
    }


def _serialize_birth(event: BirthEvent) -> dict[str, Any]:
    return {
        "type": "birth",
        "mother": _serialize_pooch(event.mother),
        "child": _serialize_pooch(event.child),
        "message": event.message,
    }


def _serialize_death(event: DeathEvent) -> dict[str, Any]:
    return {
        "type": "death",
        "pooch": _serialize_pooch(event.pooch),
        "message": event.message,
    }


def _serialize_other(event: OtherEvent) -> dict[str, Any]:
    return {
        "type": "other",
        "pooch": _serialize_pooch(event.pooch),
        "message": event.message,
    }


def serialize_day_change_summary(summary: DayChangeSummary) -> dict[str, Any]:
    """Serialize a DayChangeSummary for the web app webhook."""

    return {
        "server_discord_id": summary.server.discord_id,
        "births": [_serialize_birth(e) for e in summary.births],
        "deaths": [_serialize_death(e) for e in summary.deaths],
        "other_events": [_serialize_other(e) for e in summary.other_events],
    }


def _post_json(url: str, secret: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    signature = _build_signature(secret, body)

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Pimpy-Signature": signature,
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


async def post_day_change_webhooks(summaries: dict[int, DayChangeSummary]) -> None:
    """Post each day-change summary to the configured web app webhook endpoint."""

    url = os.environ.get("WEBHOOK_URL")
    secret = os.environ.get("WEBHOOK_SECRET")

    if not url:
        logger.log("Webhook URL not set. Skipping posting day change summaries to web app...")
        return

    if not secret:
        logger.log("Webhook secret not set. Skipping posting day change summaries to web app...")
        return

    tasks = []
    for summary in summaries.values():
        payload = {
            "event": "day_change",
            "data": serialize_day_change_summary(summary),
        }
        tasks.append(asyncio.to_thread(_post_json, url, secret, payload))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
