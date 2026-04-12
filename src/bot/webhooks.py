from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import urllib.request
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.game.models import BirthEvent, DayChangeSummary, DeathEvent, OtherEvent, Pooch

from src.logger import get_logger

logger = get_logger("bot/webhooks")


def build_signature(secret: str, body: bytes) -> str:
    """
    Build signature.

    Parameters
    ----------
    secret: Any
        The `secret` value.

    body: Any
        The `body` value.

    Returns
    -------
    Any
        The result of calling `build_signature`.
    """

    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def serialize_pooch(pooch: Pooch) -> dict[str, Any]:
    """
    Serialize pooch.

    Parameters
    ----------
    pooch: Any
        The `pooch` value.

    Returns
    -------
    Any
        The result of calling `serialize_pooch`.
    """

    return {
        "id": pooch.id,
        "name": pooch.name,
        "sex": pooch.sex,
        "alive": pooch.alive,
        "status": pooch.status,
    }


def serialize_birth(event: BirthEvent) -> dict[str, Any]:
    """
    Serialize birth.

    Parameters
    ----------
    event: Any
        The `event` value.

    Returns
    -------
    Any
        The result of calling `serialize_birth`.
    """

    return {
        "type": "birth",
        "mother": serialize_pooch(event.mother),
        "child": serialize_pooch(event.child),
        "message": event.message,
    }


def serialize_death(event: DeathEvent) -> dict[str, Any]:
    """
    Serialize death.

    Parameters
    ----------
    event: Any
        The `event` value.

    Returns
    -------
    Any
        The result of calling `serialize_death`.
    """

    return {
        "type": "death",
        "pooch": serialize_pooch(event.pooch),
        "message": event.message,
    }


def serialize_other(event: OtherEvent) -> dict[str, Any]:
    """
    Serialize other.

    Parameters
    ----------
    event: Any
        The `event` value.

    Returns
    -------
    Any
        The result of calling `serialize_other`.
    """

    return {
        "type": "other",
        "pooch": serialize_pooch(event.pooch),
        "message": event.message,
    }


def serialize_day_change_summary(summary: DayChangeSummary) -> dict[str, Any]:
    """Serialize a DayChangeSummary for the web app webhook."""

    return {
        "server_discord_id": summary.server.discord_id,
        "births": [serialize_birth(e) for e in summary.births],
        "deaths": [serialize_death(e) for e in summary.deaths],
        "other_events": [serialize_other(e) for e in summary.other_events],
    }


def post_json(url: str, secret: str, payload: dict[str, Any]) -> None:
    """
    Post json.

    Parameters
    ----------
    url: Any
        The `url` value.

    secret: Any
        The `secret` value.

    payload: Any
        The `payload` value.
    """

    body = json.dumps(payload).encode("utf-8")
    signature = build_signature(secret, body)

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
        logger.info("Webhook URL not set. Skipping posting day change summaries to web app...")
        return

    if not secret:
        logger.info("Webhook secret not set. Skipping posting day change summaries to web app...")
        return

    tasks = []
    for summary in summaries.values():
        payload = {
            "event": "day_change",
            "data": serialize_day_change_summary(summary),
        }
        tasks.append(asyncio.to_thread(post_json, url, secret, payload))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
