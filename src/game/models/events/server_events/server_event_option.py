from __future__ import annotations

from dataclasses import dataclass, field

from src.database.models import ServerEventMenu as ServerEventMenuORM
from src.database.models import ServerEventMenuOption as ServerEventMenuOptionORM


@dataclass(frozen=True)
class ServerEventMenuOption:
    id: int
    label: str
    description: str
    filter: dict
    requires: dict
    scoring: dict


@dataclass
class ServerEventMenu:
    id: int
    name: str
    label: str
    description: str
    max_uses_per_player: int  # -1 = unlimited
    depends_on: list[str] = field(default_factory=list)
    options: list[ServerEventMenuOption] = field(default_factory=list)


async def to_server_event_menu_option(option: ServerEventMenuOptionORM) -> ServerEventMenuOption:
    """
    To server event menu option.

    Parameters
    ----------
    option: Any
        The `option` value.

    Returns
    -------
    Any
        The result of calling `to_server_event_menu_option`.
    """

    return ServerEventMenuOption(
        id=option.id,
        label=option.label,
        description=option.description,
        filter=option.filter or {},
        requires=option.requires or {},
        scoring=option.scoring or {},
    )


async def to_server_event_menu(menu: ServerEventMenuORM) -> ServerEventMenu:
    """
    To server event menu.

    Parameters
    ----------
    menu: Any
        The `menu` value.

    Returns
    -------
    Any
        The result of calling `to_server_event_menu`.
    """

    return ServerEventMenu(
        id=menu.id,
        name=menu.name,
        label=menu.label,
        description=menu.description,
        max_uses_per_player=menu.max_uses_per_player,
        depends_on=list(menu.depends_on or []),
        options=[await to_server_event_menu_option(opt) for opt in sorted(menu.options, key=lambda o: o.option_order)],
    )
