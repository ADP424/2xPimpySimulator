from __future__ import annotations

from sqlalchemy.dialects.postgresql import ENUM

EVENT_SEVERITY = ENUM(
    "trivial",
    "minor",
    "moderate",
    "major",
    "critical",
    "remarkable",
    "catastrophic",
    name="event_severity",
    create_type=True,
)
