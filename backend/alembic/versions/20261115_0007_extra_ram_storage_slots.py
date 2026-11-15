"""build_items: extra RAM kits (ram2-ram4) and drives (storage3, storage4)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("cpu", "motherboard", "ram", "gpu", "storage", "storage2", "psu", "case", "cooler")
NEW = OLD + ("ram2", "ram3", "ram4", "storage3", "storage4")


def _slots(values) -> str:
    return f"slot IN ({', '.join(repr(s) for s in values)})"


def upgrade() -> None:
    op.drop_constraint("build_item_slot", "build_items", type_="check")
    op.create_check_constraint("build_item_slot", "build_items", _slots(NEW))


def downgrade() -> None:
    op.execute("DELETE FROM build_items WHERE slot IN ('ram2', 'ram3', 'ram4', 'storage3', 'storage4')")
    op.drop_constraint("build_item_slot", "build_items", type_="check")
    op.create_check_constraint("build_item_slot", "build_items", _slots(OLD))
