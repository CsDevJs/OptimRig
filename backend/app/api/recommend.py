from decimal import Decimal
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
from app.services.tiers import ENTRY_PURPOSES, may_be_empty, pair_allowed, part_allowed
from app.services.recommend import (
    PERFORMANCE_MIX, WEIGHTS, Candidate, compatible_builds, criteria, SHOWN_BUILDS, prefilter, rank_builds, spread_in_range,
)

router = APIRouter(tags=["Recommendations"])
# Parts per slot for the build search, tried in turn while fewer than six builds are found.
SEARCH_CAPS = (5, 8, 12)
# No wider retry after a search that already ranked this many builds: the next one would be
# about ten times larger (10 s to a minute on the full catalog).
MAX_RETRY_ALTERNATIVES = 5000



def chip(x: Candidate | None) -> str | None:
    """The CPU model ('Ryzen 5 7600', Box and Tray alike) or GPU chipset ('GeForce RTX 5060')."""
    if x is None:
        return None
    if isinstance(x.part.spec, GpuSpec):
        return x.part.spec.chipset
    return cpu_chip(x.part.component.model) or x.part.component.model


@router.post("/recommendations", response_model=RecommendResult)
def recommend(payload: RecommendRequest, db: Annotated[Session, Depends(get_db)]) -> RecommendResult:
    """Rank every compatible build priced between min_mdl and max_mdl with TOPSIS.

    Alternatives are complete builds that pass all modeled compatibility rules and
    the purpose's tier rules (services.tiers; editing and workstation fall back to their
    entry-level rules when none is found), using only parts with an in-stock
    offer, from 5 parts per slot (8, then 12, when that gives fewer than 6
    different builds; see recommend.prefilter). Criteria: price
    (min), performance (max), estimated consumption (min).
    """
    purpose = payload.purpose
    catalog = db.scalars(select(Component).options(selectinload(Component.offers)).order_by(Component.id))
    specs = {c: {s.component_id: s for s in db.scalars(select(m))} for c, m in SPEC_MODELS.items()}
    candidates: list[Candidate] = []
    for component in catalog:
        prices = [o.price_mdl for o in component.offers if o.availability == Availability.IN_STOCK]
        if not prices:
            continue
        if component.category == Category.CPU and payload.cpu_brand and component.brand != payload.cpu_brand:
            continue
        candidates.append(Candidate(SelectedPart(component, specs[component.category].get(component.id)), min(prices)))

    # Editing and workstation fall back to entry-level rules when theirs leave no build
    # in the range (a low budget), so the page still offers builds that do the work.
    for entry in (False, True) if purpose in ENTRY_PURPOSES else (False,):
        builds, values, shown = _search(candidates, payload.min_mdl, payload.max_mdl, purpose, entry)
        if shown:
            break
    ranked = []
    for rank, score in shown:
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
        alternatives=len(builds), entry_level=entry and bool(ranked), builds=ranked,
    )


def _search(candidates: list[Candidate], low: Decimal, high: Decimal, purpose, entry: bool):
    """The compatible builds priced between `low` and `high` under the purpose's rules
    (`entry`: its entry-level rules), their criteria, and the ones to show."""
    domains: dict[Slot, list[Candidate]] = {s: [] for s in Slot}
    for candidate in candidates:
        for slot in Slot:
            if slot.category == candidate.part.component.category and part_allowed(purpose, slot, candidate, entry):
                domains[slot].append(candidate)
    optional = tuple(s for s in Slot if may_be_empty(purpose, s, entry))
    rule = partial(pair_allowed, purpose, entry=entry)

    # A large catalog makes too many builds to list; keep the best parts of each slot first.
    # When that leaves fewer than six different builds in the range, retry with more
    # parts per slot, as long as the search stays small enough to answer quickly.
    for cap in SEARCH_CAPS:
        picked = prefilter(domains, high, purpose, cap=cap, optional=optional, extra=rule)
        builds = list(compatible_builds(picked, high, optional, rule, floor=low))
        scores = rank_builds(builds, purpose)
        # Up to six variants spread from the low to the high end of the range, each with its own
        # CPU chip + GPU chip pair (not just another card maker or Box/Tray packaging).
        values = [criteria(b, purpose) for b in builds]
        pairs = [(chip(b[Slot.CPU]), chip(b[Slot.GPU])) for b in builds]
        # When there aren't 6 new pairs (office often has no GPU), other RAM or storage sizes count as variety.
        setups = [pair + (b[Slot.RAM].part.spec.capacity_gb,
                          sum(b[s].part.spec.capacity_gb for s in (Slot.STORAGE, Slot.STORAGE2) if b.get(s)))
                  for pair, b in zip(pairs, builds)]
        shown = spread_in_range(scores, [v[0] for v in values], pairs, low, high, setups=setups)
        if len(shown) >= SHOWN_BUILDS or len(builds) > MAX_RETRY_ALTERNATIVES:
            break
    return builds, values, shown
