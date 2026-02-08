from dataclasses import dataclass


@dataclass(frozen=True)
class DeathEvent:
    server_id: int
    pooch_id: int
