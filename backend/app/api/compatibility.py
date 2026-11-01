from typing import Annotated

from app.compatibility_schemas import FilterRequest, FilterResult
from app.db.models import Category, Slot
from app.services.ac3 import filter_catalog
from app.services.compatibility import LIMITATIONS

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compatibility_schemas import CompatibilityRequest, CompatibilityResult
from app.db.models import Component, SPEC_MODELS
from app.db.session import get_db
from app.services.compatibility import SelectedPart, check_build

router = APIRouter(tags=["Compatibility"])


@router.post("/compatibility/check", response_model=CompatibilityResult)
def check_compatibility(payload: CompatibilityRequest, db: Annotated[Session, Depends(get_db)]):
    ids = list(payload.components.values())
    components = {component.id: component for component in db.scalars(
        select(Component).where(Component.id.in_(ids))
    )}
    missing = sorted(set(ids) - components.keys())
    if missing:
        raise HTTPException(status_code=404, detail={
            "message": "Components not found", "component_ids": missing,
        })
    mismatches = [
        {"component_id": component_id, "expected": slot.category.value,
         "actual": components[component_id].category.value}
        for slot, component_id in payload.components.items()
        if components[component_id].category != slot.category
    ]
    if mismatches:
        raise HTTPException(status_code=422, detail={
            "message": "Component category mismatch", "mismatches": mismatches,
        })
    parts = {
        slot: SelectedPart(components[component_id], db.get(SPEC_MODELS[slot.category], component_id))
        for slot, component_id in payload.components.items()
    }
    return check_build(parts)


@router.post("/compatibility/filter", response_model=FilterResult)
def filter_compatibility(payload: FilterRequest, db: Annotated[Session, Depends(get_db)]):
    catalog = list(db.scalars(select(Component).order_by(Component.id)))
    by_id = {part.id: part for part in catalog}
    missing = sorted(set(payload.components.values()) - by_id.keys())
    if missing:
        raise HTTPException(404, detail={"message": "Components not found", "component_ids": missing})
    mismatches = [
        {"component_id": component_id, "expected": slot.category.value,
         "actual": by_id[component_id].category.value}
        for slot, component_id in payload.components.items()
        if by_id[component_id].category != slot.category
    ]
    if mismatches:
        raise HTTPException(422, detail={"message": "Component category mismatch", "mismatches": mismatches})
    specs = {category: {spec.component_id: spec for spec in db.scalars(select(model))}
             for category, model in SPEC_MODELS.items()}
    domains = {}
    for slot in Slot:
        domains[slot] = [SelectedPart(part, specs[slot.category].get(part.id)) for part in catalog
                         if part.category == slot.category and
                         (slot not in payload.components or part.id == payload.components[slot])]
        if slot in (Slot.GPU, Slot.COOLER, Slot.STORAGE2) and slot not in payload.components:
            domains[slot].append(None)
    filtered = filter_catalog(domains)
    ids = {category: [None if part is None else part.component.id for part in values]
           for category, values in filtered.items()}
    empty = [category for category, values in ids.items() if not values]
    return FilterResult(
        status="inconsistent" if empty else "arc_consistent", domains=ids,
        removed={category: [part.component.id for part in values
                           if part is not None and part.component.id not in ids[category]]
                 for category, values in domains.items()},
        empty_categories=empty,
        limitations=LIMITATIONS + [
            "Arc consistency is not proof of a complete valid build. Run /compatibility/check on final selections.",
            "Budget, stock, and total PSU demand are not AC-3 binary constraints.",
            "Null in a GPU or cooler domain means no separate component; CPU capabilities constrain this choice.",
            "storage2 is an optional second drive; null means none. Two drives also need two board connectors, "
            "which /compatibility/check verifies.",
        ],
    )
