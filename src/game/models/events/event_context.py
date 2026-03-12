from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models.event_types import EventContextDict, JsonObject


@dataclass
class EventContext:
    owner_discord_id: int

    affected_pooch_ids: list[int] = field(default_factory=list)
    affected_kennel_ids: list[int] = field(default_factory=list)

    selected_pooch_id: int | None = None
    selected_kennel_id: int | None = None

    extra_data: JsonObject = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: EventContextDict) -> EventContext:
        """
        Create from a dictionary (from JSON storage).

        Parameters
        ----------
        data: EventContextDict
            The database-side event context dictionary to convert to a game EventContext object.

        Returns
        -------
        EventContext
            The new game EventContext object with the data of the input database EventContextDict.
        """

        return cls(
            owner_discord_id=data.get("owner_discord_id", 0),
            affected_pooch_ids=list(data.get("affected_pooch_ids", [])),
            affected_kennel_ids=list(data.get("affected_kennel_ids", [])),
            selected_pooch_id=data.get("selected_pooch_id"),
            selected_kennel_id=data.get("selected_kennel_id"),
            extra_data=dict(data.get("extra_data", {})),
        )

    def to_dict(self) -> EventContextDict:
        """
        Convert to a database-side plain dictionary for JSON storage.

        Returns
        -------
        EventContextDict
            A plain dictionary with the same data as this EventContext object.
        """

        return {
            "owner_discord_id": self.owner_discord_id,
            "affected_pooch_ids": self.affected_pooch_ids,
            "affected_kennel_ids": self.affected_kennel_ids,
            "selected_pooch_id": self.selected_pooch_id,
            "selected_kennel_id": self.selected_kennel_id,
            "extra_data": self.extra_data,
        }
