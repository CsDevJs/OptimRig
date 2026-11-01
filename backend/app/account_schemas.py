from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.compatibility_schemas import CompatibilityRequest, CompatibilityResult
from app.db.models import Slot
from app.schemas import ComponentRead, StoreRead


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    # bcrypt-era limits do not apply to argon2; the cap only blocks absurd payloads.
    password: Annotated[str, Field(min_length=8, max_length=128)]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class TokenRead(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")


BuildName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class BuildWrite(CompatibilityRequest):
    """Name plus one component ID per category; same rules as /compatibility/check."""

    name: BuildName


class BuildItemRead(BaseModel):
    category: Slot = Field(description="The slot: a category, or storage2 for a second drive")
    component: ComponentRead
    saved_price_mdl: Decimal | None = Field(description="Cheapest in-stock price when this part was added")
    saved_store: StoreRead | None
    current_price_mdl: Decimal | None = Field(description="Cheapest in-stock price now")
    current_store: StoreRead | None


class BuildSummary(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    component_count: int
    saved_total_mdl: Decimal


class BuildRead(BuildSummary):
    items: list[BuildItemRead]
    current_total_mdl: Decimal
    unpriced_categories: list[Slot] = Field(
        description="Parts with no in-stock offer now; excluded from current_total_mdl"
    )
    compatibility: CompatibilityResult
