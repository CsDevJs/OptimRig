"""users: email and password move to the encrypted users vault

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03

Email, username and password are kept in the AES-256-GCM vault file (app/vault.py);
the table keeps only the id that saved builds point to. Existing accounts can't be
moved: their passwords were stored as one-way hashes. The upgrade refuses to run
while accounts exist, so none are silently lost.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM users")).scalar()
    if count:
        raise RuntimeError(f"{count} accounts exist; their hashed passwords can't be moved to the vault. "
                           "Delete them (or keep revision 0004) before upgrading.")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")


def downgrade() -> None:
    op.execute("DELETE FROM users")
    op.add_column("users", sa.Column("email", sa.String(254), nullable=False, unique=True))
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=False))
