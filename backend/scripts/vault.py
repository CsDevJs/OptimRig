"""Decrypt the users vault and show its accounts (run from backend/).

    python -m scripts.vault show   # id, email

Needs the same VAULT_KEY as the server (from .env). Without it, or with a changed
file, decryption fails and nothing is shown. Passwords can't be shown: only their
Argon2id hashes are stored, and a hash can't be turned back into the password.
"""

import sys

from app.vault import VaultError, get_vault


def main() -> None:
    if sys.argv[1:] != ["show"]:
        print(__doc__)
        sys.exit(2)
    vault = get_vault()
    try:
        users = vault.all()
    except VaultError as error:
        sys.exit(f"Can't read the vault: {error}")
    print(f"{len(users)} accounts in {vault.path}")
    for user in users:
        print(f"  {user.id:>5}  {user.email}")


if __name__ == "__main__":
    main()
