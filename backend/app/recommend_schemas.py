from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import Slot
from app.services.recommend import Purpose


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_mdl: Decimal = Field(ge=0, max_digits=10, decimal_places=2, description="Lowest total price of a shown build")
    max_mdl: Decimal = Field(gt=0, max_digits=10, decimal_places=2, description="Highest total price of a shown build")
    purpose: Purpose = Field(description="Chooses the criteria weights and the CPU/GPU performance mix")
    cpu_brand: Literal["AMD", "Intel"] | None = Field(default=None, description="Only builds with this CPU brand")


    @model_validator(mode="after")
    def range_in_order(self):
        if self.min_mdl > self.max_mdl:
            raise ValueError("min_mdl must not be above max_mdl")
        return self


class CriteriaWeights(BaseModel):
    price: float
    performance: float
    power: float


class RankedBuild(BaseModel):
    rank: int = Field(description="Position in the TOPSIS ranking of all alternatives")
    components: dict[Slot, int | None] = Field(description="null: no separate GPU or cooler, or no second drive (storage2)")
    price_mdl: Decimal = Field(description="Sum of each part's cheapest in-stock offer")
    performance: float
    power_w: int = Field(description="Estimated consumption: recorded peak draw, PSU excluded")
    distance_best: float = Field(description="Euclidean distance to the ideal solution (D+)")
    distance_worst: float = Field(description="Euclidean distance to the anti-ideal solution (D-)")
    closeness: float = Field(description="D- / (D+ + D-); higher is better")


class RecommendResult(BaseModel):
    weights: CriteriaWeights
    performance_mix: dict[Literal["cpu", "gpu"], float]
    entry_level: bool = Field(default=False, description="True: the purpose's own rules left no build in the range, so these follow its entry-level rules (editing, workstation)")
    alternatives: int = Field(description="Compatible builds priced between min_mdl and max_mdl that were ranked")
    builds: list[RankedBuild] = Field(description="Up to 6 builds priced between min_mdl and max_mdl, cheapest first: the best-ranked build of each of 6 equal price bands of the range, each with a different CPU chip + GPU chip pair; fewer when there are not 6 different builds")
