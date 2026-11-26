"""Versioned visual embeddings, authoritative in PostgreSQL.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "visual_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("model_key", sa.String(160), nullable=False),
        sa.Column("vector", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("evidence_id", "model_key", name="uq_visual_embeddings_evidence_model"),
    )
    op.create_index("ix_visual_embeddings_case_model", "visual_embeddings", ["case_id", "model_key"])
    op.execute("CREATE TRIGGER visual_embeddings_append_only BEFORE UPDATE OR DELETE ON visual_embeddings FOR EACH ROW EXECUTE FUNCTION nextron_reject_mutation()")


def downgrade():
    op.drop_index("ix_visual_embeddings_case_model", table_name="visual_embeddings")
    op.drop_table("visual_embeddings")
