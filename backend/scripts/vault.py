"""The users vault (run from backend/).

    python -m scripts.vault show               # id, email of every account
    python -m scripts.vault copy-to-database   # data/users.vault -> the user_vault table

`show` reads the vault the server uses (VAULT_STORAGE: the file, or the database).
`copy-to-database` copies the vault file, still encrypted, into the database that
DATABASE_URL points to, e.g. when moving to Vercel; it refuses if that database
already has a vault. The users rows (the ids saved builds point to) must be in the
same database, so copy the database first.

Needs the same VAULT_KEY as the server (from .env). Without it, or with a changed
vault, decryption fails and nothing is shown. Passwords can't be shown: only their
Argon2id hashes are stored, and a hash can't be turned back into the password.
"""

import sys

from app.config import settings
from app.vault import DatabaseVault, UserVault, VaultError, decode_key, get_vault


def show() -> None:
    vault = get_vault()
    try:
        users = vault.all()
    except VaultError as error:
        sys.exit(f"Can't read the vault: {error}")
    print(f"{len(users)} accounts in {vault.where}")
    for user in users:
        print(f"  {user.id:>5}  {user.email}")


def copy_to_database() -> None:
    from app.db.session import engine

    key = decode_key(settings.vault_key)
    source = UserVault(settings.vault_path, key)
    if not source.path.exists():
        sys.exit(f"No vault file at {source.path}")
    try:
        users = source.all()  # proves VAULT_KEY opens the file before anything is copied
    except VaultError as error:
        sys.exit(f"Can't read the vault file: {error}")
    target = DatabaseVault(engine, key)
    with target.lock:
        if target._read_text() is not None:
            sys.exit("The database already has a vault; nothing was copied.")
        target._write_text(source._read_text())
    print(f"Copied {len(users)} accounts from {source.path} to {target.where}")


def main() -> None:
    commands = {"show": show, "copy-to-database": copy_to_database}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print(__doc__)
        sys.exit(2)
    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()
