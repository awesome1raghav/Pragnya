"""Mark earlier analysis results superseded: for each module and scope only the newest result is current.

Recording never superseded results before this revision, so every re-run left its predecessors current and their
findings were listed again. This applies the rule to existing history; the protect trigger allows exactly this change.
Nothing is deleted.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        WITH ranked AS (
            SELECT r.id,
                   first_value(r.id) OVER w AS newest,
                   row_number() OVER w AS n
            FROM analysis_results r JOIN analysis_executions e ON e.id = r.execution_id
            WHERE r.superseded_at IS NULL
            WINDOW w AS (PARTITION BY r.case_id, r.module_id, e.scope_ref ORDER BY r.created_at DESC, r.id DESC)
        )
        UPDATE analysis_results a SET superseded_at = now(), superseded_by = ranked.newest
        FROM ranked WHERE a.id = ranked.id AND ranked.n > 1
    """)


def downgrade():
    pass  # superseding is the one permitted change to a result and cannot be undone (the protect trigger refuses it)
