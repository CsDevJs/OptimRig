from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import SPEC_MODELS, Availability, Category, Component, GpuSpec, Slot
from app.db.session import get_db
from app.recommend_schemas import CriteriaWeights, RankedBuild, RecommendRequest, RecommendResult
from app.services.catalog_normalize import cpu_chip
from app.services.compatibility import SelectedPart
from app.services.tiers import may_be_empty, pair_allowed, part_allowed
from app.services.recommend import (
    PERFORMANCE_MIX, WEIGHTS, Candidate, compatible_builds, criteria, prefilter, rank_builds, spread_by_price,
)

router = APIRouter(tags=["Recommendations"])



def chip(x: Candidate | None) -> str | None:
    """The CPU model ('Ryzen 5 7600', Box and Tray alike) or GPU chipset ('GeForce RTX 5060')."""
    if x is None:
        return None
    if isinstance(x.part.spec, GpuSpec):
        return x.part.spec.chipset
    return cpu_chip(x.part.component.model) or x.part.component.model


@router.post("/recommendations", response_model=RecommendResult)
def recommend(payload: RecommendRequest, db: Annotated[Session, Depends(get_db)]) -> RecommendResult:
    """Rank every compatible build within budget with TOPSIS.

    Alternatives are complete builds that pass all modeled compatibility rules and
    the purpose's tier rules (services.tiers), using only parts with an in-stock
    offer, from at most 5 parts per slot (see recommend.prefilter). Criteria: price
    (min), performance (max), estimated consumption (min).
    """
    purpose = payload.purpose
    catalog = db.scalars(select(Component).options(selectinload(Component.offers)).order_by(Component.id))
    specs = {c: {s.component_id: s for s in db.scalars(select(m))} for c, m in SPEC_MODELS.items()}
    domains: dict[Slot, list[Candidate]] = {s: [] for s in Slot}
    for component in catalog:
        prices = [o.price_mdl for o in component.offers if o.availability == Availability.IN_STOCK]
        if not prices:
            continue
        if component.category == Category.CPU and payload.cpu_brand and component.brand != payload.cpu_brand:
            continue
        candidate = Candidate(SelectedPart(component, specs[component.category].get(component.id)), min(prices))
        for slot in Slot:
            if slot.category == component.category and part_allowed(purpose, slot, candidate):
                domains[slot].append(candidate)
    optional = tuple(s for s in Slot if may_be_empty(purpose, s))
    rule = partial(pair_allowed, purpose)

    # A large catalog makes too many builds to list; keep the best parts of each slot first.
    domains = prefilter(domains, payload.budget_mdl, purpose, optional=optional, extra=rule)
    builds = list(compatible_builds(domains, payload.budget_mdl, optional, rule))
    scores = rank_builds(builds, payload.purpose)
    # Six variants spread from cheap to near the budget, each with its own CPU chip + GPU
    # chip pair (not just another card maker or Box/Tray packaging).
    values = [criteria(b, payload.purpose) for b in builds]
    pairs = [(chip(b[Slot.CPU]), chip(b[Slot.GPU])) for b in builds]
    # When there aren't 6 new pairs (office has no GPU), other RAM or storage sizes count as variety.
    setups = [pair + (b[Slot.RAM].part.spec.capacity_gb,
                      sum(b[s].part.spec.capacity_gb for s in (Slot.STORAGE, Slot.STORAGE2) if b.get(s)))
              for pair, b in zip(pairs, builds)]
    ranked = []
    for rank, score in spread_by_price(scores, [v[0] for v in values], pairs, payload.budget_mdl, setups=setups):
        build = builds[score.index]
        price, performance, power = values[score.index]
        ranked.append(RankedBuild(
            rank=rank, components={c: x and x.part.component.id for c, x in build.items()},
            price_mdl=price, performance=round(performance, 2), power_w=power,
            distance_best=score.distance_best, distance_worst=score.distance_worst, closeness=score.closeness,
        ))
    price_w, performance_w, power_w = WEIGHTS[payload.purpose]
    cpu_share, gpu_share = PERFORMANCE_MIX[payload.purpose]
    return RecommendResult(
        weights=CriteriaWeights(price=price_w, performance=performance_w, power=power_w),
        performance_mix={"cpu": cpu_share, "gpu": gpu_share},
        alternatives=len(builds), builds=ranked,
    )
