import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# A placeholder allows database-free HTTP validation tests to import the app.
# It does not connect; catalog integration tests require TEST_DATABASE_URL.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"
)
os.environ.setdefault("JWT_SECRET", "test-only-secret-at-least-32-bytes-long")
# A fixed test key; every test gets its own vault file (see `vault` below).
os.environ.setdefault("VAULT_KEY", "dGVzdC1vbmx5LXZhdWx0LWtleS0zMi1ieXRlcy0hISE=")
# The activity log goes to a temporary folder, never the real one.
os.environ["AUDIT_LOG_DIR"] = tempfile.mkdtemp(prefix="pc-audit-")
# One allowed cross-origin site, as on GitHub Pages (see test_api.py).
os.environ.setdefault("CORS_ORIGINS", "https://site.example")

from app.db.session import get_db
from app.main import app
from app.vault import UserVault, decode_key, get_vault


@pytest.fixture(autouse=True)
def vault(tmp_path):
    """A fresh encrypted vault in a temporary folder, so tests never touch backend/data."""
    test_vault = UserVault(tmp_path / "users.vault", decode_key(os.environ["VAULT_KEY"]))
    app.dependency_overrides[get_vault] = lambda: test_vault
    yield test_vault
    app.dependency_overrides.pop(get_vault, None)


@pytest.fixture
def activity_log():
    """Returns a function that gives the activity-log lines written since the test started."""
    path = Path(os.environ["AUDIT_LOG_DIR"]) / "activity.log"
    start = path.stat().st_size if path.exists() else 0

    def new_lines() -> list[str]:
        with path.open(encoding="utf-8") as file:
            file.seek(start)
            return file.read().splitlines()
    return new_lines


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def catalog_client():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated, seeded test PostgreSQL database")
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            app.dependency_overrides[get_db] = lambda: session
            try:
                with TestClient(app) as test_client:
                    yield test_client, session
            finally:
                app.dependency_overrides.clear()
        transaction.rollback()
    engine.dispose()
