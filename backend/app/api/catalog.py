"""Read the catalog; no calls to external stores."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Category, Component, Offer, SPEC_MODELS, Store, Tier
from app.db.session import get_db
from app.schemas import (
    ComponentDetail, ComponentPage, ComponentRead, SPEC_SCHEMAS, StoreRead,
)

router = APIRouter(tags=["Catalog"])
DbSession = Annotated[Session, Depends(get_db)]


def component_response(component: Component) -> ComponentRead:
    response = ComponentRead.model_validate(component)
    response.offers.sort(key=lambda offer: (offer.price_mdl, offer.store.id))
    return response


@router.get("/components", response_model=ComponentPage)
def list_components(
    db: DbSession,
    category: Category | None = None,
    tier: Tier | None = None,
    brand: Annotated[str | None, Query(min_length=1, max_length=60, pattern=r"\S")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ComponentPage:
    filters = []
    if category is not None:
        filters.append(Component.category == category)
    if tier is not None:
        filters.append(Component.tier == tier)
    if brand is not None:
        filters.append(func.lower(Component.brand) == brand.strip().lower())

    total = db.scalar(select(func.count()).select_from(Component).where(*filters))
    components = db.scalars(
        select(Component)
        .where(*filters)
        .options(selectinload(Component.offers).selectinload(Offer.store))
        .order_by(Component.id)
        .limit(limit)
        .offset(offset)
    ).all()
    # Specs come with each item, so a client can load the whole catalog in a few requests.
    specs = {}
    for category in {c.category for c in components}:
        model = SPEC_MODELS[category]
        ids = [c.id for c in components if c.category == category]
        specs.update({s.component_id: s for s in db.scalars(select(model).where(model.component_id.in_(ids)))})
    return ComponentPage(
        items=[_detail(component, specs.get(component.id)) for component in components],
        total=total, limit=limit, offset=offset,
    )


def _detail(component: Component, spec) -> ComponentDetail:
    specs = SPEC_SCHEMAS[component.category].model_validate(spec) if spec is not None else None
    return ComponentDetail(**component_response(component).model_dump(), specs=specs)


@router.get("/components/{component_id}", response_model=ComponentDetail)
def get_component(
    component_id: Annotated[int, Path(gt=0)], db: DbSession,
) -> ComponentDetail:
    component = db.scalar(
        select(Component)
        .where(Component.id == component_id)
        .options(selectinload(Component.offers).selectinload(Offer.store))
    )
    if component is None:
        raise HTTPException(status_code=404, detail="Component not found")

    return _detail(component, db.get(SPEC_MODELS[component.category], component.id))


@router.get("/stores", response_model=list[StoreRead])
def list_stores(db: DbSession):
    return db.scalars(select(Store).order_by(Store.name, Store.id)).all()
