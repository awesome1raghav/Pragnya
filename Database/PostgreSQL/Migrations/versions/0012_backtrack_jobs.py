"""Permit bounded NEX-BTK jobs.

Revision ID: 0012
Revises: 0011
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_analysis_jobs_job_type_valid"), "analysis_jobs", type_="check")
    op.create_check_constraint(op.f("ck_analysis_jobs_job_type_valid"), "analysis_jobs",
                               "job_type IN ('INVESTIGATION_RUN', 'SOURCE_RESOLUTION', 'REPORT_GENERATION', 'PROJECTION_REBUILD', 'BACKTRACK_EXPANSION')")


def downgrade():
    op.drop_constraint(op.f("ck_analysis_jobs_job_type_valid"), "analysis_jobs", type_="check")
    op.create_check_constraint(op.f("ck_analysis_jobs_job_type_valid"), "analysis_jobs",
                               "job_type IN ('INVESTIGATION_RUN', 'SOURCE_RESOLUTION', 'REPORT_GENERATION', 'PROJECTION_REBUILD')")
