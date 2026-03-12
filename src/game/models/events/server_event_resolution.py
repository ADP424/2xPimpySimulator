from __future__ import annotations

from dataclasses import dataclass, field

from .event_result import EventResult


@dataclass
class ServerEventResolution:
    occurrence_id: int
    server_discord_id: int
    name: str
    participant_count: int
    winner_owner_ids: list[int] = field(default_factory=list)
    winner_pooch_ids: list[int] = field(default_factory=list)
    result_summary: EventResult = field(default_factory=EventResult)
