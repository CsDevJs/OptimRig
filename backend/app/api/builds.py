"""Saved builds: each user can create, read, replace and delete only their own."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.account_schemas import BuildItemRead, BuildRead, BuildSummary, BuildWrite
from app.api.auth import CurrentUser
from app.api.catalog import component_response
from app.db.models import Availability, Build, BuildItem, Component, Offer, SPEC_MODELS, Slot
from app.db.session import get_db
from app.schemas import StoreRead
from app.services.compatibility import SelectedPart, check_build

router = APIRouter(prefix="/builds", tags=["Saved builds"])
DbSession = Annotated[Session, Depends(get_db)]
BuildId = Annotated[int, Path(gt=0)]
_NOT_FOUND = {404: {"description": "Build not found"}}


def load_selection(db: Session, selection: dict[Slot, int]) -> dict[Slot, Component]:
    """Fetch the chosen components; same 404/422 errors as /compatibility/check."""
    ids = list(selection.values())
    found = {c.id: c for c in db.scalars(
        select(Component).where(Component.id.in_(ids))
        .options(selectinload(Component.offers).selectinload(Offer.store))
    )}
    missing = sorted(set(ids) - found.keys())
    if missing:
        raise HTTPException(404, detail={"message": "Components not found", "component_ids": missing})
    mismatches = [
        {"component_id": cid, "expected": slot.category.value, "actual": found[cid].category.value}
        for slot, cid in selection.items() if found[cid].category != slot.category
    ]
    if mismatches:
        raise HTTPException(422, detail={"message": "Component category mismatch", "mismatches": mismatches})
    return {slot: found[cid] for slot, cid in selection.items()}


def _cheapest_in_stock(component: Component) -> Offer | None:
    offers = [o for o in component.offers if o.availability == Availability.IN_STOCK]
    return min(offers, key=lambda o: (o.price_mdl, o.store_id), default=None)


def _new_item(slot: Slot, component: Component) -> BuildItem:
    offer = _cheapest_in_stock(component)
    return BuildItem(
        slot=slot.value, category=slot.category, component=component,
        saved_price_mdl=offer.price_mdl if offer else None,
        saved_store=offer.store if offer else None,
    )


def _owned_build(db: Session, user_id: int, build_id: int) -> Build:
    build = db.scalar(
        select(Build).where(Build.id == build_id, Build.user_id == user_id)
        .options(selectinload(Build.items).selectinload(BuildItem.component)
                 .selectinload(Component.offers).selectinload(Offer.store))
    )
    # Someone else's build is reported as missing, so IDs can't be probed.
    if build is None:
        raise HTTPException(404, detail="Build not found")
    return build


def _summary(build: Build) -> dict:
    return {
        "id": build.id, "name": build.name, "created_at": build.created_at, "updated_at": build.updated_at,
        "component_count": len(build.items),
        "saved_total_mdl": sum((i.saved_price_mdl for i in build.items if i.saved_price_mdl is not None), Decimal(0)),
    }


def _build_response(db: Session, build: Build) -> BuildRead:
    items, unpriced, current_total = [], [], Decimal(0)
    # Slot order (cpu, motherboard, ..., storage, storage2, ...), not alphabetical.
    for item in sorted(build.items, key=lambda i: list(Slot).index(Slot(i.slot))):
        offer = _cheapest_in_stock(item.component)
        if offer is None:
            unpriced.append(Slot(item.slot))
        else:
            current_total += offer.price_mdl
        items.append(BuildItemRead(
            category=Slot(item.slot),
            component=component_response(item.component),
            saved_price_mdl=item.saved_price_mdl,
            saved_store=StoreRead.model_validate(item.saved_store) if item.saved_store else None,
            current_price_mdl=offer.price_mdl if offer else None,
            current_store=StoreRead.model_validate(offer.store) if offer else None,
        ))
    # Compatibility is recomputed on every read, so it reflects today's rules and specs.
    parts = {Slot(i.slot): SelectedPart(i.component, db.get(SPEC_MODELS[i.category], i.component_id))
             for i in build.items}
    return BuildRead(
        **_summary(build), items=items, current_total_mdl=current_total,
        unpriced_categories=unpriced, compatibility=check_build(parts),
    )


@router.post("", response_model=BuildRead, status_code=status.HTTP_201_CREATED)
def create_build(payload: BuildWrite, user: CurrentUser, db: DbSession) -> BuildRead:
    selection = load_selection(db, payload.components)
    build = Build(user=user, name=payload.name,
                  items=[_new_item(slot, component) for slot, component in selection.items()])
    db.add(build)
    db.commit()
    return _build_response(db, _owned_build(db, user.id, build.id))


@router.get("", response_model=list[BuildSummary])
def list_builds(user: CurrentUser, db: DbSession) -> list[dict]:
    builds = db.scalars(
        select(Build).where(Build.user_id == user.id)
        .options(selectinload(Build.items))
        .order_by(Build.updated_at.desc(), Build.id.desc())
    )
    return [_summary(build) for build in builds]


@router.get("/{build_id}", response_model=BuildRead, responses=_NOT_FOUND)
def get_build(build_id: BuildId, user: CurrentUser, db: DbSession) -> BuildRead:
    return _build_response(db, _owned_build(db, user.id, build_id))


@router.put("/{build_id}", response_model=BuildRead, responses=_NOT_FOUND)
def replace_build(build_id: BuildId, payload: BuildWrite, user: CurrentUser, db: DbSession) -> BuildRead:
    """Replace the name and the whole selection.

    Parts that stay in the same slot keep their saved price; new parts get today's.
    """
    build = _owned_build(db, user.id, build_id)
    selection = load_selection(db, payload.components)
    kept = {(i.slot, i.component_id): i for i in build.items}
    build.name = payload.name
    build.items = [kept.get((slot.value, component.id)) or _new_item(slot, component)
                   for slot, component in selection.items()]
    # Changing only items doesn't touch the builds row, so onupdate wouldn't fire.
    build.updated_at = func.now()
    db.commit()
    db.expire_all()
    return _build_response(db, _owned_build(db, user.id, build_id))


@router.delete("/{build_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_NOT_FOUND)
def delete_build(build_id: BuildId, user: CurrentUser, db: DbSession) -> Response:
    db.delete(_owned_build(db, user.id, build_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
