"""Allow investigator reviews of versioned backtracking comparisons.

Revision ID: 0013
Revises: 0012
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_reviews_subject_type_valid"), "reviews", type_="check")
    op.create_check_constraint(op.f("ck_reviews_subject_type_valid"), "reviews",
                               "subject_type IN ('FINDING', 'RELATIONSHIP', 'CASE_CONCLUSION', 'BACKTRACK_COMPARISON')")


def downgrade():
    op.drop_constraint(op.f("ck_reviews_subject_type_valid"), "reviews", type_="check")
    op.create_check_constraint(op.f("ck_reviews_subject_type_valid"), "reviews",
                               "subject_type IN ('FINDING', 'RELATIONSHIP', 'CASE_CONCLUSION')")
