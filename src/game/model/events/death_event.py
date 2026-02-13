from dataclasses import dataclass

from game.model.server import Server
from game.model.pooch import Pooch


@dataclass(frozen=True)
class DeathEvent:
    server: Server
    pooch: Pooch
