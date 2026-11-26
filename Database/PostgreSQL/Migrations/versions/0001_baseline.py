"""Baseline: start of the single NEXTRON schema history.

Creates no tables. Applying it records revision 0001 in alembic_version, which
/health/ready uses to confirm the database is migrated to the code's head.
Case and evidence tables arrive in 0002 (Step 2).

Revision ID: 0001
Revises:
Create Date: 2026-11-26
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
