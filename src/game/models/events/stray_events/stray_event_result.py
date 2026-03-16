from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models.event_types import JsonObject


@dataclass
class StrayEventResult:
    """Accumulated result for a single stray event execution."""

    success: bool = True
    pooches_affected: list[int] = field(default_factory=list)
    pooches_killed: list[int] = field(default_factory=list)
    pooches_created: list[int] = field(default_factory=list)
    extra_data: JsonObject = field(default_factory=dict)

    def merge(self, other: StrayEventResult) -> None:
        if not other.success:
            self.success = False
        self.pooches_affected.extend(other.pooches_affected)
        self.pooches_killed.extend(other.pooches_killed)
        self.pooches_created.extend(other.pooches_created)
        for key, value in other.extra_data.items():
            if isinstance(value, list) and isinstance(self.extra_data.get(key), list):
                self.extra_data[key].extend(value)
            else:
                self.extra_data[key] = value
