from dataclasses import dataclass

from game.models.pooch import Pooch
from game.models.server import Server


@dataclass(frozen=True)
class DeathEvent:
    server: Server
    pooch: Pooch
    message: str
