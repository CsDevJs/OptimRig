from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import ON_VERCEL, settings

# On Vercel each function instance is short-lived and frozen between requests, so it
# keeps no idle connections, and the database's own pooler (e.g. Neon's pooled address,
# PgBouncer) shares them. That pooler can't keep psycopg's prepared statements, so
# they're off there.
engine = create_engine(
    settings.database_url, pool_pre_ping=True,
    **({"poolclass": NullPool, "connect_args": {"prepare_threshold": None}} if ON_VERCEL else {}),
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Give each request its own session and close it even when a request fails."""
    with SessionLocal() as session:
        yield session
