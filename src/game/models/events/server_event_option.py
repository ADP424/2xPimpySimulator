from __future__ import annotations

from dataclasses import dataclass

from src.database.models import ServerEventOption as ServerEventOptionORM


@dataclass(frozen=True)
class ServerEventOption:
    id: int
    label: str
    description: str
    min_money: int
    min_bloodskulls: int
    requires_pooch_selection: bool


async def to_server_event_option(option: ServerEventOptionORM) -> ServerEventOption:
    return ServerEventOption(
        id=option.id,
        label=option.label,
        description=option.description,
        min_money=option.min_money,
        min_bloodskulls=option.min_bloodskulls,
        requires_pooch_selection=option.requires_pooch_selection,
    )
