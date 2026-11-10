"""The users vault in the database (VAULT_STORAGE=database, the default on Vercel)
and the settings that switch to it."""

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.config import Settings
from app.security import hash_password
from app.vault import DatabaseVault, DuplicateEmail, UserVault, VaultError, decode_key

KEY = decode_key(os.environ["VAULT_KEY"])
HASH = hash_password("correct horse battery")
BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture
def engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated test PostgreSQL database")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM user_vault"))
    yield engine
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM user_vault"))
    engine.dispose()


def test_database_vault_round_trip_keeps_nothing_readable(engine):
    vault = DatabaseVault(engine, KEY)
    assert vault.all() == []
    vault.add(7, "Ana@Example.com", HASH)
    with engine.connect() as connection:
        stored = connection.execute(text("SELECT envelope FROM user_vault")).scalars().all()
    assert len(stored) == 1 and "ana@example.com" not in stored[0].lower() and HASH not in stored[0]
    again = DatabaseVault(engine, KEY)  # another server instance
    assert again.find("ANA@example.com").id == 7
    with pytest.raises(DuplicateEmail):
        again.add(8, "ana@EXAMPLE.com", HASH)
    again.remove(7)
    assert vault.all() == []


def test_database_vault_needs_the_right_key(engine):
    DatabaseVault(engine, KEY).add(1, "a@example.com", HASH)
    with pytest.raises(VaultError, match="wrong VAULT_KEY"):
        DatabaseVault(engine, os.urandom(32)).all()


def test_concurrent_writers_on_different_instances_lose_nothing(engine):
    # Two server instances (separate engines, like two Vercel functions) registering
    # at once: without the shared advisory lock one save would overwrite the other.
    url = engine.url
    instances = [DatabaseVault(create_engine(url), KEY) for _ in range(2)]
    errors = []

    def register(vault, first_id):
        try:
            for user_id in range(first_id, first_id + 10):
                with vault.lock:
                    vault.check_free(f"user{user_id}@example.com")
                    vault.add(user_id, f"user{user_id}@example.com", HASH)
        except Exception as error:  # surfaced below
            errors.append(error)

    threads = [threading.Thread(target=register, args=(v, i * 100)) for i, v in enumerate(instances)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(DatabaseVault(engine, KEY).all()) == 20
    for vault in instances:
        vault._engine.dispose()


def test_lock_is_released_after_an_error(engine):
    vault = DatabaseVault(engine, KEY)
    with pytest.raises(RuntimeError):
        with vault.lock:
            with vault.lock:  # re-entrant, as in register -> add
                raise RuntimeError("boom")
    other = create_engine(engine.url)
    with other.connect() as connection:  # another session can take it immediately
        assert connection.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": 0x6F7074696D726967}).scalar()
        connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": 0x6F7074696D726967})
    other.dispose()


def test_copy_vault_file_to_database(engine, tmp_path):
    UserVault(tmp_path / "users.vault", KEY).add(3, "c@example.com", HASH)
    env = {**os.environ, "DATABASE_URL": str(engine.url.render_as_string(hide_password=False)),
           "VAULT_PATH": str(tmp_path / "users.vault")}

    def run():
        return subprocess.run([sys.executable, "-m", "scripts.vault", "copy-to-database"],
                              cwd=BACKEND, env=env, capture_output=True, text=True)

    first = run()
    assert first.returncode == 0, first.stderr
    assert "Copied 1 accounts" in first.stdout
    assert DatabaseVault(engine, KEY).find("c@example.com").id == 3
    second = run()  # never overwrites a vault that is already there
    assert second.returncode != 0 and "already has a vault" in second.stderr


@pytest.mark.parametrize("given", [
    "postgres://u:p@host/db?sslmode=require",
    "postgresql://u:p@host/db?sslmode=require",
    "postgresql+psycopg://u:p@host/db?sslmode=require",
])
def test_hosted_database_addresses_use_psycopg(given):
    settings = Settings(database_url=given)
    assert settings.database_url == "postgresql+psycopg://u:p@host/db?sslmode=require"


def test_vercel_defaults():
    # Vercel sets VERCEL=1: vault in the database, activity log to stderr, no idle pool.
    code = ("from app.config import settings; from app.db.session import engine; "
            "print(settings.vault_storage, settings.audit_log_to, type(engine.pool).__name__)")
    env = {k: v for k, v in os.environ.items() if k not in ("VAULT_STORAGE", "AUDIT_LOG_TO")}
    on = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env={**env, "VERCEL": "1"},
                        capture_output=True, text=True)
    off = subprocess.run([sys.executable, "-c", code], cwd=BACKEND,
                         env={k: v for k, v in env.items() if k != "VERCEL"}, capture_output=True, text=True)
    assert on.stdout.split() == ["database", "stderr", "NullPool"], on.stderr
    assert off.stdout.split() == ["file", "file", "QueuePool"], off.stderr


def test_activity_log_goes_to_stderr_on_vercel(tmp_path):
    env = {**os.environ, "VERCEL": "1", "AUDIT_LOG_DIR": str(tmp_path / "logs")}
    env.pop("AUDIT_LOG_TO", None)
    result = subprocess.run(
        [sys.executable, "-c", "from app.audit import log_action; log_action('LOGIN_OK', 'a@example.com', user_id=1)"],
        cwd=BACKEND, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "| LOGIN_OK | email=a@example.com | user_id=1" in result.stderr
    assert not (tmp_path / "logs").exists()  # nothing written to Vercel's read-only disk
