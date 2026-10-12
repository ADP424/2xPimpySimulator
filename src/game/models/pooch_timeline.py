from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PoochTimelineEntry:
    kind: str
    description: str
    snapshot_at: datetime
    # Names of the injuries/mutations on record at a vet visit; None when the entry records none
    entity_names: Optional[list[str]] = None
