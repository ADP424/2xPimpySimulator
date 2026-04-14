from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    text,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ... import Base
from ...enums.mood import MOOD
from ...enums.sex import SEX

if TYPE_CHECKING:
    from ..relationships.graveyard_pooch import GraveyardPooch
    from ..relationships.hell_pooch import HellPooch
    from ..relationships.kennel_pooch import KennelPooch
    from ..relationships.pooch_breed import PoochBreed
    from ..relationships.pooch_disease import PoochDisease
    from ..relationships.pooch_disease_immunity import PoochDiseaseImmunity
    from ..relationships.pooch_injury import PoochInjury
    from ..relationships.pooch_mutation import PoochMutation
    from ..relationships.pooch_parentage import PoochParentage
    from ..relationships.pooch_pregnancy import PoochPregnancy
    from ..relationships.pooch_snapshot import PoochSnapshot
    from ..relationships.stray_pooch import StrayPooch
    from ..relationships.vendor_pooch_for_sale import VendorPoochForSale
    from .owner import Owner
    from .vendor import Vendor


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
        CheckConstraint("strength >= 0", name="pooch_strength_minimum"),
        CheckConstraint("cuteness >= 0", name="pooch_cuteness_minimum"),
        CheckConstraint("fluffiness >= 0", name="pooch_fluffiness_minimum"),
        CheckConstraint("intelligence >= 0", name="pooch_intelligence_minimum"),
        CheckConstraint("dexterity >= 0", name="pooch_dexterity_minimum"),
        CheckConstraint("fertility >= 0", name="pooch_fertility_minimum"),
        CheckConstraint("aggressiveness >= 0", name="pooch_aggressiveness_minimum"),
        CheckConstraint("constitution >= 0", name="pooch_constitution_minimum"),
        CheckConstraint("size >= 0", name="pooch_size_minimum"),
        CheckConstraint("breeding_cooldown >= 0", name="pooch_breeding_cooldown_minimum"),
        CheckConstraint("starvation >= 0", name="pooch_starvation_minimum"),
        CheckConstraint("mess_output >= 0", name="pooch_mess_output_minimum"),
        CheckConstraint("consumption >= 0", name="pooch_consumption_minimum"),
        CheckConstraint("rejuvenation_count >= 0", name="pooch_rejuvenation_count_minimum"),
        CheckConstraint(
            "pregnancy_timer IS NULL OR pregnancy_timer >= 0",
            name="pooch_pregnancy_timer_minimum",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(Text)
    age: Mapped[int] = mapped_column(Integer, default=0)
    sex: Mapped[str] = mapped_column(SEX)

    base_health: Mapped[int] = mapped_column(Integer, default=10)
    health_loss_age: Mapped[int] = mapped_column(Integer, default=0)

    strength: Mapped[int] = mapped_column(Integer, default=10)
    cuteness: Mapped[int] = mapped_column(Integer, default=10)
    fluffiness: Mapped[int] = mapped_column(Integer, default=10)
    intelligence: Mapped[int] = mapped_column(Integer, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, default=10)
    fertility: Mapped[int] = mapped_column(Integer, default=10)
    aggressiveness: Mapped[int] = mapped_column(Integer, default=10)
    constitution: Mapped[int] = mapped_column(Integer, default=10)

    size: Mapped[int] = mapped_column(Integer, default=10)

    breeding_cooldown: Mapped[int] = mapped_column(Integer, default=2)
    alive: Mapped[bool] = mapped_column(Boolean, default=True)
    virgin: Mapped[bool] = mapped_column(Boolean, default=True)
    vet_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    mood: Mapped[str | None] = mapped_column(MOOD, nullable=True)

    # Pregnancy: hours remaining until birth. NULL means not pregnant.
    pregnancy_timer: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    # Rejuvenation ritual: cumulative count. Each increments applies permanent
    # fertility/constitution multipliers via the stats pipeline.
    rejuvenation_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)

    # Immortality ritual flag: True = pooch cannot die of age, is infertile.
    immortal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)

    # Starvation counter. Rises when hourly food needs are unmet, decays otherwise.
    starvation: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)

    # Per-pooch mess output used by hourly kennel mess accumulation.
    mess_output: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2", default=2)

    # Per-pooch hourly food consumption, derived from size/breed/mutation params.
    consumption: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", default=1)

    # Absolute hour of birth (GlobalState.current_hour at birth). Used by the
    # hour loop to compute age increments on each 24-hour anniversary. NULL for
    # pooches created before the hour-loop migration.
    birth_hour: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)

    owner_discord_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("owners.discord_id", ondelete="SET NULL"), nullable=True
    )
    vendor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)

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

    pooch_injuries: Mapped[list[PoochInjury]] = relationship(
        "PoochInjury",
        back_populates="pooch",
        cascade="all, delete-orphan",
    )
    injuries = association_proxy("pooch_injuries", "injury")

    pooch_diseases: Mapped[list[PoochDisease]] = relationship(
        "PoochDisease",
        back_populates="pooch",
        cascade="all, delete-orphan",
    )
    diseases = association_proxy("pooch_diseases", "disease")

    pooch_disease_immunities: Mapped[list[PoochDiseaseImmunity]] = relationship(
        "PoochDiseaseImmunity",
        back_populates="pooch",
        cascade="all, delete-orphan",
    )

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

    stray_row: Mapped[StrayPooch] = relationship(
        "StrayPooch",
        back_populates="pooch",
        uselist=False,
        foreign_keys="StrayPooch.pooch_id",
    )

    vendor_pooch_for_sale_row: Mapped[VendorPoochForSale] = relationship(
        "VendorPoochForSale",
        back_populates="pooch",
        uselist=False,
        foreign_keys="VendorPoochForSale.pooch_id",
    )

    pooch_snapshots: Mapped[list[PoochSnapshot]] = relationship(
        "PoochSnapshot",
        back_populates="pooch",
        cascade="all, delete-orphan",
        order_by="PoochSnapshot.snapshot_at",
    )
