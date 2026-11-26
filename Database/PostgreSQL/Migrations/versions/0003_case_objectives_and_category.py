"""Case objectives and category (Step 1 frontend support, Flowchart B §7.4).

Existing cases get category OTHER and no objectives.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = ("MEDIA_MANIPULATION", "SYNTHETIC_MEDIA", "SOURCE_VERIFICATION", "CONTEXT_VERIFICATION", "OTHER")


def upgrade() -> None:
    op.add_column("cases", sa.Column("objectives", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("category", sa.String(length=32), server_default=sa.text("'OTHER'"), nullable=False))
    op.create_check_constraint(
        op.f("ck_cases_category_valid"), "cases", f"category IN ({', '.join(repr(c) for c in CATEGORIES)})"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_cases_category_valid"), "cases", type_="check")
    op.drop_column("cases", "category")
    op.drop_column("cases", "objectives")
