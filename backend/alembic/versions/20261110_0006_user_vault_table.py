"""user_vault: the encrypted users vault can be stored in the database

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-10

With VAULT_STORAGE=database (the default on Vercel, whose disk isn't kept) the vault
lives in this one-row table instead of data/users.vault: the same AES-256-GCM JSON,
encrypted with VAULT_KEY, which stays out of the database. With VAULT_STORAGE=file the
table stays empty.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_vault",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("envelope", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="user_vault_single_row"),
    )


def downgrade() -> None:
    op.drop_table("user_vault")
