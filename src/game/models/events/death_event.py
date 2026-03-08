from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.models.pooch import Pooch
    from game.models.server import Server


@dataclass(frozen=True)
class DeathEvent:
    server: Server
    pooch: Pooch
    message: str
