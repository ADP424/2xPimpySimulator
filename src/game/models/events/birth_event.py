from dataclasses import dataclass

from game.models.pooch import Pooch
from game.models.server import Server


@dataclass(frozen=True)
class BirthEvent:
    server: Server
    mother: Pooch
    child: Pooch
    message: str
