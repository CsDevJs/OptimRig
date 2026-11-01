from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.builds import router as builds_router
from app.api.catalog import router as catalog_router
from app.api.compatibility import router as compatibility_router
from app.api.purchase import router as purchase_router
from app.api.recommend import router as recommend_router
from app.db.session import get_db
from app.schemas import HealthRead

app = FastAPI(
    title="PC Configurator API",
    version="0.1.0",
    description="Read the manually maintained component catalog, check PC build compatibility, "
                "and save builds to a user account.",
)
app.include_router(catalog_router)
app.include_router(compatibility_router)
app.include_router(auth_router)
app.include_router(builds_router)
app.include_router(purchase_router)
app.include_router(recommend_router)


@app.get("/health", response_model=HealthRead, tags=["Health"])
def health() -> HealthRead:
    """Liveness: checks that the API is running without querying PostgreSQL."""
    return HealthRead(status="ok")


@app.get(
    "/health/db", response_model=HealthRead, tags=["Health"],
    responses={503: {"description": "Database unavailable"}},
)
def database_health(db: Session = Depends(get_db)) -> HealthRead:
    """Connectivity check; migrations and seed data must be applied separately."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Do not expose connection details or credentials in HTTP responses.
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return HealthRead(status="ok")
