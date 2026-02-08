from dataclasses import dataclass


@dataclass(frozen=True)
class BirthEvent:
    server_id: int
    mother_id: int
    child_id: int
