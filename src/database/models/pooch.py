from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Text, ForeignKey, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

from .base import Base
from .enums.sex import SEX

if TYPE_CHECKING:
    from .owner import Owner
    from .vendor import Vendor
    from .relationships.pooch_parentage import PoochParentage
    from .relationships.pooch_pregnancy import PoochPregnancy
    from .relationships.kennel_pooch import KennelPooch
    from .relationships.graveyard_pooch import GraveyardPooch
    from .relationships.hell_pooch import HellPooch
    from .relationships.vendor_pooch_for_sale import VendorPoochForSale
    from .static_relationships.pooch_breed import PoochBreed
    from .static_relationships.pooch_mutation import PoochMutation


class Pooch(Base):
    __tablename__ = "pooches"
    __table_args__ = (
        # A pooch cannot be owned by both a player and vendor at the same time
        CheckConstraint(
            "(owner_discord_id IS NULL) OR (vendor_id IS NULL)",
            name="pooch_owner_xor_vendor_simple",
        ),
        CheckConstraint("age >= -1", name="pooch_age_minimum"),
        CheckConstraint("base_health >= 0", name="pooch_base_health_minimum"),
        CheckConstraint("breeding_cooldown >= 0", name="pooch_breeding_cooldown_minimum"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(Text)
    age: Mapped[int] = mapped_column(Integer, default=0)
    sex: Mapped[str] = mapped_column(SEX)

    base_health: Mapped[int] = mapped_column(Integer, default=10)
    health_loss_age: Mapped[int] = mapped_column(Integer, default=0)

    breeding_cooldown: Mapped[int] = mapped_column(Integer, default=2)
    alive: Mapped[bool] = mapped_column(Boolean, default=True)
    virgin: Mapped[bool] = mapped_column(Boolean, default=True)

    owner_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="SET NULL"), nullable=True
    )
    vendor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    owner: Mapped[Owner] = relationship("Owner", back_populates="owned_pooches", foreign_keys=[owner_discord_id])
    vendor: Mapped[Vendor] = relationship("Vendor", back_populates="owned_pooches", foreign_keys=[vendor_id])

    parentage: Mapped[PoochParentage] = relationship(
        "PoochParentage",
        back_populates="child",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="PoochParentage.child_id",
    )
    father = association_proxy("parentage", "father")
    mother = association_proxy("parentage", "mother")

    pregnancies_as_mother: Mapped[list[PoochPregnancy]] = relationship(
        "PoochPregnancy",
        back_populates="mother",
        cascade="all, delete-orphan",
        foreign_keys="PoochPregnancy.mother_id",
    )
    pregnancy_as_fetus_rows: Mapped[list[PoochPregnancy]] = relationship(
        "PoochPregnancy",
        back_populates="fetus",
        cascade="all, delete-orphan",
        foreign_keys="PoochPregnancy.fetus_id",
    )
    fetuses = association_proxy("pregnancies_as_mother", "fetus")

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

    kennel_row: Mapped[KennelPooch] = relationship(
        "KennelPooch",
        back_populates="pooch",
        uselist=False,
        cascade="all, delete-orphan",
    )
    kennels = association_proxy("kennel_row", "kennel")

    graveyard_row: Mapped[GraveyardPooch] = relationship(
        "GraveyardPooch",
        back_populates="pooch",
        uselist=False,
        foreign_keys="GraveyardPooch.pooch_id",
    )

    hell_row: Mapped[HellPooch] = relationship(
        "HellPooch",
        back_populates="pooch",
        uselist=False,
        foreign_keys="HellPooch.pooch_id",
    )

    vendor_pooch_for_sale_row: Mapped[VendorPoochForSale] = relationship(
        "VendorPoochForSale",
        back_populates="pooch",
        uselist=False,
        foreign_keys="VendorPoochForSale.pooch_id",
    )
