"""Catalog schema: components, per-category specs, stores and store offers.

Each component has exactly one row in the spec table matching its category.
Spec tables use typed columns (not JSON) because the compatibility
constraints (AC-3) compare these fields directly.
"""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Native Postgres enum that stores the lowercase .value, not the member name."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class Category(str, enum.Enum):
    CPU = "cpu"
    MOTHERBOARD = "motherboard"
    RAM = "ram"
    GPU = "gpu"
    STORAGE = "storage"
    PSU = "psu"
    CASE = "case"
    COOLER = "cooler"


class Slot(str, enum.Enum):
    """A place in a build: one per category, plus an optional second drive.

    Values equal the category values (Slot.CPU == Category.CPU == "cpu"), so a dict
    keyed by slots can be read with categories."""
    CPU = "cpu"
    MOTHERBOARD = "motherboard"
    RAM = "ram"
    GPU = "gpu"
    STORAGE = "storage"
    STORAGE2 = "storage2"
    PSU = "psu"
    CASE = "case"
    COOLER = "cooler"

    @property
    def category(self) -> "Category":
        """The component category a part in this slot belongs to."""
        return Category.STORAGE if self is Slot.STORAGE2 else Category(self.value)


SLOTS = tuple(Slot)
SLOT_VALUES = tuple(s.value for s in Slot)


class Tier(str, enum.Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"


class Availability(str, enum.Enum):
    IN_STOCK = "in_stock"
    ON_ORDER = "on_order"  # "La comandă" / "Sub comandă"
    OUT_OF_STOCK = "out_of_stock"


# Allowed values for short text columns, enforced with CHECK constraints.
# Kept as text rather than enums so adding a value needs no enum migration.
MEMORY_TYPES = ("DDR4", "DDR5")
BOARD_FORM_FACTORS = ("E-ATX", "ATX", "Micro-ATX", "Mini-ITX")
PSU_FORM_FACTORS = ("ATX", "SFX")
STORAGE_TYPES = ("nvme", "sata_ssd", "hdd")
COOLER_TYPES = ("air", "aio")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _subset(column: str, values: tuple[str, ...]) -> str:
    return f"{column} <@ ARRAY[{', '.join(repr(v) for v in values)}]::text[]"


class Component(Base):
    __tablename__ = "components"
    __table_args__ = (
        UniqueConstraint("brand", "model"),
        CheckConstraint("perf_score IS NULL OR perf_score BETWEEN 0 AND 100", name="perf_score_range"),
        CheckConstraint("power_draw_w >= 0", name="power_draw_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stable human-readable key used by seed CSVs to link offers to components.
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[Category] = mapped_column(pg_enum(Category, "component_category"), index=True)
    tier: Mapped[Tier] = mapped_column(pg_enum(Tier, "component_tier"), index=True)
    brand: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(160))
    # Relative performance within the category, 0-100, entered by hand.
    perf_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    perf_source: Mapped[str | None] = mapped_column(Text)
    # Peak power the component adds to the system, used for PSU sizing.
    power_draw_w: Mapped[int] = mapped_column(default=0)
    release_year: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    offers: Mapped[list["Offer"]] = relationship(back_populates="component", cascade="all, delete-orphan")


def _spec_pk() -> Mapped[int]:
    return mapped_column(ForeignKey("components.id", ondelete="CASCADE"), primary_key=True)


class CpuSpec(Base):
    __tablename__ = "cpu_specs"
    __table_args__ = (CheckConstraint(_subset("memory_types", MEMORY_TYPES), name="cpu_memory_types"),)

    component_id: Mapped[int] = _spec_pk()
    socket: Mapped[str] = mapped_column(String(20), index=True)
    cores: Mapped[int]
    threads: Mapped[int]
    base_clock_ghz: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    boost_clock_ghz: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    tdp_w: Mapped[int]
    integrated_graphics: Mapped[bool]
    memory_types: Mapped[list[str]] = mapped_column(ARRAY(Text))
    includes_cooler: Mapped[bool]


class MotherboardSpec(Base):
    __tablename__ = "motherboard_specs"
    __table_args__ = (
        CheckConstraint(_in("memory_type", MEMORY_TYPES), name="mb_memory_type"),
        CheckConstraint(_in("form_factor", BOARD_FORM_FACTORS), name="mb_form_factor"),
    )

    component_id: Mapped[int] = _spec_pk()
    socket: Mapped[str] = mapped_column(String(20), index=True)
    chipset: Mapped[str] = mapped_column(String(20))
    form_factor: Mapped[str] = mapped_column(String(12))
    memory_type: Mapped[str] = mapped_column(String(4))
    memory_slots: Mapped[int]
    max_memory_gb: Mapped[int]
    m2_slots: Mapped[int]
    sata_ports: Mapped[int]
    wifi: Mapped[bool]


class RamSpec(Base):
    __tablename__ = "ram_specs"
    __table_args__ = (CheckConstraint(_in("memory_type", MEMORY_TYPES), name="ram_memory_type"),)

    component_id: Mapped[int] = _spec_pk()
    memory_type: Mapped[str] = mapped_column(String(4))
    capacity_gb: Mapped[int]  # total for the kit
    modules: Mapped[int]
    speed_mts: Mapped[int]
    cas_latency: Mapped[int]


class GpuSpec(Base):
    __tablename__ = "gpu_specs"

    component_id: Mapped[int] = _spec_pk()
    chipset: Mapped[str] = mapped_column(String(60))  # e.g. "GeForce RTX 4060"
    vram_gb: Mapped[int]
    length_mm: Mapped[int]
    slot_width: Mapped[Decimal] = mapped_column(Numeric(2, 1))
    tdp_w: Mapped[int]
    recommended_psu_w: Mapped[int]
    power_connectors: Mapped[str | None] = mapped_column(String(40))  # e.g. "1x 8-pin", "1x 16-pin"


class StorageSpec(Base):
    __tablename__ = "storage_specs"
    __table_args__ = (CheckConstraint(_in("storage_type", STORAGE_TYPES), name="storage_type"),)

    component_id: Mapped[int] = _spec_pk()
    storage_type: Mapped[str] = mapped_column(String(10))
    interface: Mapped[str] = mapped_column(String(20))  # e.g. "PCIe 4.0 x4", "SATA III"
    form_factor: Mapped[str] = mapped_column(String(10))  # "M.2 2280", "2.5", "3.5"
    capacity_gb: Mapped[int]
    read_mbps: Mapped[int | None]
    write_mbps: Mapped[int | None]


class PsuSpec(Base):
    __tablename__ = "psu_specs"
    __table_args__ = (
        CheckConstraint(_in("form_factor", PSU_FORM_FACTORS), name="psu_form_factor"),
        CheckConstraint("modular IN ('none', 'semi', 'full')", name="psu_modular"),
    )

    component_id: Mapped[int] = _spec_pk()
    wattage: Mapped[int]
    efficiency: Mapped[str] = mapped_column(String(20))  # e.g. "80+ Bronze"
    modular: Mapped[str] = mapped_column(String(4))
    form_factor: Mapped[str] = mapped_column(String(4))
    has_16pin: Mapped[bool]  # native 12V-2x6 / 12VHPWR connector


class CaseSpec(Base):
    __tablename__ = "case_specs"
    __table_args__ = (
        CheckConstraint(_subset("supported_board_form_factors", BOARD_FORM_FACTORS), name="case_board_ffs"),
        CheckConstraint(_in("psu_form_factor", PSU_FORM_FACTORS), name="case_psu_form_factor"),
    )

    component_id: Mapped[int] = _spec_pk()
    supported_board_form_factors: Mapped[list[str]] = mapped_column(ARRAY(Text))
    max_gpu_length_mm: Mapped[int]
    max_cooler_height_mm: Mapped[int]
    max_radiator_mm: Mapped[int | None]  # largest supported AIO radiator, NULL if none
    psu_form_factor: Mapped[str] = mapped_column(String(4))
    included_fans: Mapped[int]


class CoolerSpec(Base):
    __tablename__ = "cooler_specs"
    __table_args__ = (
        CheckConstraint(_in("cooler_type", COOLER_TYPES), name="cooler_type"),
        CheckConstraint(
            "(cooler_type = 'air' AND height_mm IS NOT NULL) OR (cooler_type = 'aio' AND radiator_mm IS NOT NULL)",
            name="cooler_dimensions",
        ),
    )

    component_id: Mapped[int] = _spec_pk()
    cooler_type: Mapped[str] = mapped_column(String(3))
    supported_sockets: Mapped[list[str]] = mapped_column(ARRAY(Text))
    height_mm: Mapped[int | None]  # air coolers
    radiator_mm: Mapped[int | None]  # AIO coolers
    max_tdp_w: Mapped[int | None]


SPEC_MODELS: dict[Category, type[Base]] = {
    Category.CPU: CpuSpec,
    Category.MOTHERBOARD: MotherboardSpec,
    Category.RAM: RamSpec,
    Category.GPU: GpuSpec,
    Category.STORAGE: StorageSpec,
    Category.PSU: PsuSpec,
    Category.CASE: CaseSpec,
    Category.COOLER: CoolerSpec,
}


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    website: Mapped[str] = mapped_column(String(200))

    offers: Mapped[list["Offer"]] = relationship(back_populates="store")


class Offer(Base):
    """A store's current price for a component. One row per (component, store)."""

    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint("component_id", "store_id"),
        CheckConstraint("price_mdl > 0", name="price_positive"),
        CheckConstraint("stock_qty IS NULL OR stock_qty >= 0", name="stock_nonneg"),
        CheckConstraint("regular_price_mdl IS NULL OR regular_price_mdl > price_mdl", name="regular_above_price"),
        CheckConstraint(
            "last_check_status IS NULL OR last_check_status IN ('ok', 'failed', 'page_gone')", name="check_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("components.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    price_mdl: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # The store's crossed-out price while the product is on sale; NULL when not on sale.
    regular_price_mdl: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    availability: Mapped[Availability] = mapped_column(pg_enum(Availability, "offer_availability"))
    # Stores rarely publish exact stock; NULL means unknown.
    stock_qty: Mapped[int | None]
    url: Mapped[str] = mapped_column(Text)
    checked_on: Mapped[date] = mapped_column(Date)  # when this price was last confirmed (by hand or by the checker)
    # Result of the last `scripts.check_offers` run for this offer; NULL if never checked.
    # On 'failed' or 'page_gone' the price and availability above are left unchanged.
    last_check_status: Mapped[str | None] = mapped_column(String(9))

    component: Mapped[Component] = relationship(back_populates="offers")
    store: Mapped[Store] = relationship(back_populates="offers")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stored lowercased so "A@x.md" and "a@x.md" are the same account.
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    builds: Mapped[list["Build"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Build(Base):
    """A configuration a user saved. Holds at most one component per slot."""

    __tablename__ = "builds"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="builds")
    items: Mapped[list["BuildItem"]] = relationship(
        back_populates="build", cascade="all, delete-orphan", order_by="BuildItem.slot"
    )


class BuildItem(Base):
    """One selected component, with the cheapest in-stock offer at the time it was added.

    The saved price lets a user see how prices moved since they saved the build.
    It is NULL when no store had the component in stock at that moment.
    """

    __tablename__ = "build_items"

    __table_args__ = (CheckConstraint(_in("slot", SLOT_VALUES), name="build_item_slot"),)

    build_id: Mapped[int] = mapped_column(ForeignKey("builds.id", ondelete="CASCADE"), primary_key=True)
    slot: Mapped[str] = mapped_column(String(12), primary_key=True)
    category: Mapped[Category] = mapped_column(pg_enum(Category, "component_category"))
    # RESTRICT: a component that appears in saved builds cannot be deleted from the catalog.
    component_id: Mapped[int] = mapped_column(ForeignKey("components.id", ondelete="RESTRICT"), index=True)
    saved_price_mdl: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    saved_store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"))

    build: Mapped[Build] = relationship(back_populates="items")
    component: Mapped[Component] = relationship()
    saved_store: Mapped[Store | None] = relationship()
