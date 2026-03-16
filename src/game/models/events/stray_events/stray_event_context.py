from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models.event_types import JsonObject


@dataclass
class StrayEventContext:
    """Per-event execution context — holds the current stray candidate pool and any saved slots."""

    server_discord_id: int
    candidate_stray_ids: list[int] = field(default_factory=list)
    affected_pooch_ids: list[int] = field(default_factory=list)
    extra_data: JsonObject = field(default_factory=dict)
