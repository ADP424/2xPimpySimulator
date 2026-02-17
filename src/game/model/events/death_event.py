from dataclasses import dataclass

from game.model.pooch import Pooch
from game.model.server import Server


@dataclass(frozen=True)
class DeathEvent:
    server: Server
    pooch: Pooch
