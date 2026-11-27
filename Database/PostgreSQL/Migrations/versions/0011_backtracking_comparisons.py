"""Persist versioned NEX-BTK local comparisons.

Revision ID: 0011
Revises: 0010
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_evidence_case_media_number", "evidence", ["case_id", "media_type", "evidence_number"])
    op.create_table(
        "backtracking_comparisons",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("case_id", sa.UUID(), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("seed_evidence_id", sa.UUID(), sa.ForeignKey("evidence.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("candidate_evidence_id", sa.UUID(), sa.ForeignKey("evidence.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("seed_sha256", sa.String(64), nullable=False),
        sa.Column("candidate_sha256", sa.String(64), nullable=False),
        sa.Column("algorithm", sa.String(64), nullable=False),
        sa.Column("fingerprint_algorithm", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("seed_evidence_id <> candidate_evidence_id", name="ck_backtracking_comparisons_distinct_evidence"),
        sa.UniqueConstraint("case_id", "seed_evidence_id", "candidate_evidence_id", "seed_sha256", "candidate_sha256",
                            "algorithm", "fingerprint_algorithm", name="uq_btk_comparison_inputs"),
    )
    op.create_index("ix_btk_comparisons_case_created", "backtracking_comparisons", ["case_id", "created_at"])
    op.execute("CREATE TRIGGER backtracking_comparisons_append_only BEFORE UPDATE OR DELETE ON backtracking_comparisons "
               "FOR EACH ROW EXECUTE FUNCTION nextron_reject_mutation()")


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS backtracking_comparisons_append_only ON backtracking_comparisons")
    op.drop_index("ix_btk_comparisons_case_created", table_name="backtracking_comparisons")
    op.drop_table("backtracking_comparisons")
    op.drop_index("ix_evidence_case_media_number", table_name="evidence")
