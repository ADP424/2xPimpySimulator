"""One-off database upgrades for live data (see each module)."""

from .lots_of_changes import upgrade as upgrade_lots_of_changes

__all__ = ["upgrade_lots_of_changes"]
