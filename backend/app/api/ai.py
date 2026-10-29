"""Gemini-powered advice, grounded in our own catalog and prices.

The prompts list real catalog parts so the model talks about components the
user can actually buy here, instead of inventing a parts list.
"""

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.builds import load_selection
from app.compatibility_schemas import CompatibilityRequest
from app.config import settings
from app.db.models import Availability, Category, Component, Offer
from app.db.session import get_db
from app.services import gemini

router = APIRouter(prefix="/ai", tags=["AI (Gemini)"])
DbSession = Annotated[Session, Depends(get_db)]
Generate = Callable[[str, str], str]

SYSTEM = (
    "Ești un expert în componente PC care ajută utilizatorii unui configurator din Republica Moldova. "
    "Răspunzi în limba română, concis și prietenos, în text simplu fără Markdown. "
    "Folosește doar componentele din lista primită; nu inventa alte modele sau prețuri. "
    "Când estimezi FPS, spune clar că sunt estimări aproximative."
)


def get_generate() -> Generate:
    """Dependency so tests can replace the real Gemini call."""
    return gemini.generate


class BudgetAdviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget_mdl: Annotated[int, Field(strict=True, ge=3000, le=300000)]
    brand: Literal["any", "AMD", "Intel"] = "any"


class AiAnswer(BaseModel):
    text: str
    model: str


def _cheapest(component: Component) -> str:
    prices = [o.price_mdl for o in component.offers if o.availability == Availability.IN_STOCK]
    return f"{min(prices):.0f} lei" if prices else "stoc epuizat"


def _ask(generate: Generate, prompt: str) -> AiAnswer:
    try:
        return AiAnswer(text=generate(SYSTEM, prompt), model=settings.gemini_model)
    except gemini.AiNotConfigured:
        raise HTTPException(503, detail="AI is not configured on this server (GEMINI_API_KEY is missing).") from None
    except gemini.AiUnavailable:
        raise HTTPException(502, detail="The AI service is unavailable right now. Try again later.") from None


@router.post("/budget-advice", response_model=AiAnswer,
             responses={502: {"description": "Gemini unavailable"}, 503: {"description": "AI not configured"}})
def budget_advice(payload: BudgetAdviceRequest, db: DbSession,
                  generate: Annotated[Generate, Depends(get_generate)]) -> AiAnswer:
    components = db.scalars(
        select(Component).where(Component.category.in_([Category.CPU, Category.GPU, Category.RAM]))
        .options(selectinload(Component.offers).selectinload(Offer.store)).order_by(Component.category, Component.id)
    ).all()
    catalog = "\n".join(f"- [{c.category.value}] {c.brand} {c.model}: {_cheapest(c)}" for c in components)
    brand = "oricare" if payload.brand == "any" else payload.brand
    prompt = (
        f"Buget total pentru un PC complet: {payload.budget_mdl} lei. Brand CPU preferat: {brand}.\n"
        f"Componente disponibile (cel mai mic preț în stoc):\n{catalog}\n\n"
        "În 2 paragrafe scurte: ce să prioritizeze (CPU, GPU, RAM) la acest buget și ce combinație "
        "din lista de mai sus recomanzi, ținând cont că mai trebuie placă de bază, stocare, sursă și carcasă."
    )
    return _ask(generate, prompt)


@router.post("/performance", response_model=AiAnswer,
             responses={404: {"description": "Components not found"}, 502: {"description": "Gemini unavailable"},
                        503: {"description": "AI not configured"}})
def performance(payload: CompatibilityRequest, db: DbSession,
                generate: Annotated[Generate, Depends(get_generate)]) -> AiAnswer:
    selection = load_selection(db, payload.components)
    parts = "\n".join(f"- {category.value}: {c.brand} {c.model}" for category, c in selection.items())
    prompt = (
        f"Configurația aleasă:\n{parts}\n\n"
        "Estimează performanța în jocuri populare (CS2, Cyberpunk 2077, Dota 2) la 1080p și 1440p "
        "și în aplicații de lucru, apoi dă un sfat scurt de optimizare sau upgrade. "
        "Dacă lipsesc componente importante, spune ce lipsește."
    )
    return _ask(generate, prompt)
