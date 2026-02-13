from dataclasses import dataclass
from typing import Optional

from game.model.server import Server
from game.model.pooch import Pooch


@dataclass(frozen=True)
class BirthEvent:
    server: Server
    mother: Pooch
    child: Pooch
    failure_message: Optional[str] = None
