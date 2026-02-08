from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Text, ForeignKey, UniqueConstraint, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKeyConstraint
from sqlalchemy.ext.associationproxy import association_proxy

from .base import Base
from .enums.sex import SEX

if TYPE_CHECKING:
    from .server import Server
    from .owner import Owner
    from .vendor import Vendor
    from .relationships.pooch_parentage import PoochParentage
    from .relationships.pooch_pregnancy import PoochPregnancy
    from .relationships.kennel_pooch import KennelPooch
    from .static_relationships.pooch_breed import PoochBreed
    from .static_relationships.pooch_mutation import PoochMutation


class Pooch(Base):
    __tablename__ = "pooches"
    __table_args__ = (
        UniqueConstraint("server_id", "id", name="pooches_server_id_id_uniq"),
        ForeignKeyConstraint(
            ["server_id", "owner_discord_id"],
            ["owners.server_id", "owners.discord_id"],
            name="pooch_owner_fk",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["server_id", "vendor_id"],
            ["vendors.server_id", "vendors.id"],
            name="pooch_vendor_fk",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "(owner_discord_id IS NULL) OR (vendor_id IS NULL)",
            name="pooch_owner_xor_vendor_simple",
        ),
        CheckConstraint("age >= -1", name="pooch_age_minimum"),
        CheckConstraint("base_health >= 0", name="pooch_base_health_minimum"),
        CheckConstraint("breeding_cooldown >= 0", name="pooch_breeding_cooldown_minimum"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    server_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(Text)
    age: Mapped[int] = mapped_column(Integer, default=0)
    sex: Mapped[str] = mapped_column(SEX)

    base_health: Mapped[int] = mapped_column(Integer, default=10)
    health_loss_age: Mapped[int] = mapped_column(Integer, default=0)

    breeding_cooldown: Mapped[int] = mapped_column(Integer, default=2)
    alive: Mapped[bool] = mapped_column(Boolean, default=True)
    virgin: Mapped[bool] = mapped_column(Boolean, default=True)

    owner_discord_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    vendor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    server: Mapped[Server] = relationship(back_populates="pooches", overlaps="owned_pooches")
    owner: Mapped[Owner | None] = relationship(back_populates="owned_pooches", overlaps="server")
    vendor: Mapped[Vendor | None] = relationship(back_populates="owned_pooches", overlaps="owned_pooches,owner,server")

    parentage: Mapped[PoochParentage | None] = relationship(
        "PoochParentage",
        back_populates="child",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="PoochParentage.server_id, PoochParentage.child_id",
    )
    father = association_proxy("parentage", "father")
    mother = association_proxy("parentage", "mother")

    pregnancies_as_mother: Mapped[list[PoochPregnancy]] = relationship(
        "PoochPregnancy",
        back_populates="mother",
        cascade="all, delete-orphan",
        foreign_keys="PoochPregnancy.server_id, PoochPregnancy.mother_id",
    )
    pregnancy_as_fetus_rows: Mapped[list[PoochPregnancy]] = relationship(
        "PoochPregnancy",
        back_populates="fetus",
        cascade="all, delete-orphan",
        foreign_keys="PoochPregnancy.server_id, PoochPregnancy.fetus_id",
        overlaps="pregnancies_as_mother",
    )
    fetuses = association_proxy("pregnancies_as_mother", "fetus")

    kennel_rows: Mapped[list[KennelPooch]] = relationship(
        "KennelPooch", back_populates="pooch", cascade="all, delete-orphan", overlaps="kennel_pooch_rows"
    )
    kennels = association_proxy("kennel_rows", "kennel")

    pooch_breeds: Mapped[list[PoochBreed]] = relationship(
        "PoochBreed",
        back_populates="pooch",
        cascade="all, delete-orphan",
    )
    breeds = association_proxy("pooch_breeds", "breed")

    pooch_mutations: Mapped[list[PoochMutation]] = relationship(
        "PoochMutation",
        back_populates="pooch",
        cascade="all, delete-orphan",
    )
    mutations = association_proxy("pooch_mutations", "mutation")

    graveyard_rows = relationship(
        "GraveyardPooch",
        back_populates="pooch",
        foreign_keys="GraveyardPooch.server_id, GraveyardPooch.pooch_id",
        overlaps="graveyard_rows",
    )

    hell_rows = relationship(
        "HellPooch", back_populates="pooch", foreign_keys="HellPooch.server_id, HellPooch.pooch_id"
    )

    vendor_pooch_for_sale_rows = relationship(
        "VendorPoochForSale",
        back_populates="pooch",
        foreign_keys="VendorPoochForSale.server_id, VendorPoochForSale.pooch_id",
    )
