"""Public catalog responses, separate from the database models."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.db.models import Availability, Category, Tier


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StoreRead(ReadModel):
    id: int
    slug: str
    name: str
    website: str


class OfferRead(ReadModel):
    id: int
    store: StoreRead
    price_mdl: Decimal
    regular_price_mdl: Decimal | None = Field(description="Store's crossed-out price while on sale; null otherwise")
    availability: Availability
    stock_qty: int | None
    url: str
    checked_on: date
    last_check_status: Literal["ok", "failed", "page_gone"] | None = Field(
        description="Result of the last automatic check; null if never checked")

    @computed_field
    @property
    def on_sale(self) -> bool:
        return self.regular_price_mdl is not None


class ComponentRead(ReadModel):
    id: int
    slug: str
    category: Category
    tier: Tier
    brand: str
    model: str
    perf_score: Decimal | None
    perf_source: str | None
    power_draw_w: int
    release_year: int | None
    created_at: datetime
    updated_at: datetime
    offers: list[OfferRead]


class ComponentPage(BaseModel):
    items: list["ComponentDetail"]
    total: int
    limit: int
    offset: int


class SpecRead(ReadModel):
    # Reject unrelated shapes when validating the specs union below.
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CpuSpecRead(SpecRead):
    socket: str
    cores: int
    threads: int
    base_clock_ghz: Decimal
    boost_clock_ghz: Decimal
    tdp_w: int
    integrated_graphics: bool
    memory_types: list[str]
    includes_cooler: bool


class MotherboardSpecRead(SpecRead):
    socket: str
    chipset: str
    form_factor: str
    memory_type: str
    memory_slots: int
    max_memory_gb: int
    m2_slots: int
    sata_ports: int
    wifi: bool


class RamSpecRead(SpecRead):
    memory_type: str
    capacity_gb: int
    modules: int
    speed_mts: int
    cas_latency: int


class GpuSpecRead(SpecRead):
    chipset: str
    vram_gb: int
    length_mm: int
    slot_width: Decimal
    tdp_w: int
    recommended_psu_w: int
    power_connectors: str | None


class StorageSpecRead(SpecRead):
    storage_type: str
    interface: str
    form_factor: str
    capacity_gb: int
    read_mbps: int | None
    write_mbps: int | None


class PsuSpecRead(SpecRead):
    wattage: int
    efficiency: str
    modular: str
    form_factor: str
    has_16pin: bool


class CaseSpecRead(SpecRead):
    supported_board_form_factors: list[str]
    max_gpu_length_mm: int
    max_cooler_height_mm: int
    max_radiator_mm: int | None
    psu_form_factor: str
    included_fans: int


class CoolerSpecRead(SpecRead):
    cooler_type: str
    supported_sockets: list[str]
    height_mm: int | None
    radiator_mm: int | None
    max_tdp_w: int | None


SPEC_SCHEMAS: dict[Category, type[SpecRead]] = {
    Category.CPU: CpuSpecRead,
    Category.MOTHERBOARD: MotherboardSpecRead,
    Category.RAM: RamSpecRead,
    Category.GPU: GpuSpecRead,
    Category.STORAGE: StorageSpecRead,
    Category.PSU: PsuSpecRead,
    Category.CASE: CaseSpecRead,
    Category.COOLER: CoolerSpecRead,
}


class ComponentDetail(ComponentRead):
    # NULL explicitly signals incomplete manually entered catalog data.
    specs: (
        CpuSpecRead | MotherboardSpecRead | RamSpecRead | GpuSpecRead
        | StorageSpecRead | PsuSpecRead | CaseSpecRead | CoolerSpecRead | None
    )


class HealthRead(BaseModel):
    status: str


ComponentPage.model_rebuild()
