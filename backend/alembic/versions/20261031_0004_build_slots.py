"""build_items: keyed by slot, so a build can hold a second drive

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLOTS = ("cpu", "motherboard", "ram", "gpu", "storage", "storage2", "psu", "case", "cooler")


def upgrade() -> None:
    op.add_column("build_items", sa.Column("slot", sa.String(12)))
    op.execute("UPDATE build_items SET slot = category::text")
    op.alter_column("build_items", "slot", nullable=False)
    op.drop_constraint("build_items_pkey", "build_items", type_="primary")
    op.create_primary_key("build_items_pkey", "build_items", ["build_id", "slot"])
    op.create_check_constraint("build_item_slot", "build_items", f"slot IN ({', '.join(repr(s) for s in SLOTS)})")


def downgrade() -> None:
    op.execute("DELETE FROM build_items WHERE slot = 'storage2'")
    op.drop_constraint("build_item_slot", "build_items", type_="check")
    op.drop_constraint("build_items_pkey", "build_items", type_="primary")
    op.create_primary_key("build_items_pkey", "build_items", ["build_id", "category"])
    op.drop_column("build_items", "slot")
