from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.models.pooch import Pooch
    from src.game.models.server import Server


@dataclass(frozen=True)
class OtherEvent:
    server: Server
    pooch: Pooch
    message: str
