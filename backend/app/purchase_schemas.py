from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.compatibility_schemas import CompatibilityRequest
from app.db.models import Slot
from app.schemas import StoreRead


class PurchasePlanRequest(CompatibilityRequest):
    """One component ID per category, same rules as /compatibility/check."""


class PlannedItem(BaseModel):
    category: Slot
    component_id: int
    component_name: str
    store: StoreRead
    price_mdl: Decimal
    url: str


class UnplannedItem(BaseModel):
    category: Slot
    component_id: int
    reason: Literal["no_offer_in_stock"]


class StoreSubtotal(BaseModel):
    store: StoreRead
    part_count: int
    subtotal_mdl: Decimal


class PurchasePlanRead(BaseModel):
    status: Literal["complete", "partial"] = Field(description="partial: some parts have no in-stock offer")
    items: list[PlannedItem]
    unplanned: list[UnplannedItem]
    stores: list[StoreSubtotal]
    total_mdl: Decimal
