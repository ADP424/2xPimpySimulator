from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models.event_types import EventResultDict, JsonObject


@dataclass
class OwnerEventResult:
    success: bool = True
    message: str = ""

    money_changed: int = 0
    bloodskulls_changed: int = 0
    pooches_affected: list[int] = field(default_factory=list)
    pooches_killed: list[int] = field(default_factory=list)
    pooches_created: list[int] = field(default_factory=list)
    mutations_added: list[tuple[int, int]] = field(default_factory=list)
    mutations_removed: list[tuple[int, int]] = field(default_factory=list)

    extra_data: JsonObject = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: EventResultDict) -> OwnerEventResult:
        """
        Create from a dictionary (from JSON storage).

        Parameters
        ----------
        data: EventResultDict
            The database-side event result dictionary to convert to a game OwnerEventResult object.

        Returns
        -------
        OwnerEventResult
            The new game OwnerEventResult object with the data of the input database EventResultDict.
        """

        return cls(
            success=data.get("success", True),
            message=data.get("message", ""),
            money_changed=data.get("money_changed", 0),
            bloodskulls_changed=data.get("bloodskulls_changed", 0),
            pooches_affected=list(data.get("pooches_affected", [])),
            pooches_killed=list(data.get("pooches_killed", [])),
            pooches_created=list(data.get("pooches_created", [])),
            mutations_added=[tuple(x) for x in data.get("mutations_added", [])],
            mutations_removed=[tuple(x) for x in data.get("mutations_removed", [])],
            extra_data=dict(data.get("extra_data", {})),
        )

    def to_dict(self) -> EventResultDict:
        """
        Convert to a dictionary for JSON storage.

        Returns
        -------
        EventResultDict
            A plain dictionary with the same data as this OwnerEventResult object.
        """

        return {
            "success": self.success,
            "message": self.message,
            "money_changed": self.money_changed,
            "bloodskulls_changed": self.bloodskulls_changed,
            "pooches_affected": self.pooches_affected,
            "pooches_killed": self.pooches_killed,
            "pooches_created": self.pooches_created,
            "mutations_added": [list(pair) for pair in self.mutations_added],
            "mutations_removed": [list(pair) for pair in self.mutations_removed],
            "extra_data": self.extra_data,
        }

    def merge(self, other: OwnerEventResult) -> OwnerEventResult:
        """
        Merge another result into this one.
        Numerical changes are totalled, lists are extended, messages are combined with newlines, etc.

        Parameters
        ----------
        other: OwnerEventResult
            The other OwnerEventResult object to merge into this one.

        Returns
        -------
        OwnerEventResult
            The result of the merge.
        """

        self.success = self.success and other.success
        if other.message:
            self.message = f"{self.message}\n{other.message}".strip()
        self.money_changed += other.money_changed
        self.bloodskulls_changed += other.bloodskulls_changed
        self.pooches_affected.extend(other.pooches_affected)
        self.pooches_killed.extend(other.pooches_killed)
        self.pooches_created.extend(other.pooches_created)
        self.mutations_added.extend(other.mutations_added)
        self.mutations_removed.extend(other.mutations_removed)
        for key, value in other.extra_data.items():
            if key not in self.extra_data:
                self.extra_data[key] = value
            elif isinstance(self.extra_data[key], dict) and isinstance(value, dict):
                self.extra_data[key].update(value)
            elif isinstance(self.extra_data[key], list) and isinstance(value, list):
                self.extra_data[key].extend(value)
            else:
                self.extra_data[key] = value
        return self
