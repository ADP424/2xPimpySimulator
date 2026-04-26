from __future__ import annotations

from dataclasses import dataclass, field

from src.database.models.event_types import JsonObject, ServerEventContextDict


@dataclass
class ServerEventContext:
    server_discord_id: int
    featured_pooch_ids: list[int] = field(default_factory=list)
    featured_breed_ids: list[int] = field(default_factory=list)
    featured_mutation_ids: list[int] = field(default_factory=list)
    # Named save slots for server-scoped actions (e.g. save_as="revenant" stores pooch IDs here)
    saved_slots: dict[str, list[int]] = field(default_factory=dict)
    # Named save slots for owner discord IDs (e.g. save_as="winner" with save_owner stores owner IDs here)
    saved_owner_slots: dict[str, list[int]] = field(default_factory=dict)
    extra_data: JsonObject = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: ServerEventContextDict | dict) -> "ServerEventContext":
        return cls(
            server_discord_id=data.get("server_discord_id", 0),
            featured_pooch_ids=[value for value in data.get("featured_pooch_ids", [])],
            featured_breed_ids=[value for value in data.get("featured_breed_ids", [])],
            featured_mutation_ids=[value for value in data.get("featured_mutation_ids", [])],
            saved_slots=dict(data.get("saved_slots", {})),
            saved_owner_slots=dict(data.get("saved_owner_slots", {})),
            extra_data=dict(data.get("extra_data", {})),
        )

    def to_dict(self) -> ServerEventContextDict:
        return {
            "server_discord_id": self.server_discord_id,
            "featured_pooch_ids": list(self.featured_pooch_ids),
            "featured_breed_ids": list(self.featured_breed_ids),
            "featured_mutation_ids": list(self.featured_mutation_ids),
            "saved_slots": dict(self.saved_slots),
            "saved_owner_slots": dict(self.saved_owner_slots),
            "extra_data": dict(self.extra_data),
        }
