from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base

if TYPE_CHECKING:
    from ..server import Server
    from ..owner import Owner


class OwnerServer(Base):
    __tablename__ = "owner_servers"

    server_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("servers.discord_id", ondelete="CASCADE"), primary_key=True
    )
    owner_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="CASCADE"), primary_key=True
    )

    server: Mapped[Server] = relationship(
        "Server", foreign_keys=[server_discord_id], back_populates="owner_server_rows"
    )
    owner: Mapped[Owner] = relationship("Owner", foreign_keys=[owner_discord_id], back_populates="owner_server_rows")
