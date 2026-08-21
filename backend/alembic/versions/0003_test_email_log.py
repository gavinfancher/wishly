"""test_email_log

Records test reminders sent from the Account page so they can appear in history.

A separate table rather than rows in ``notification_log``: that table is the
idempotency ledger, unique on ``(event_id, days_before, occurrence_date)``, and a
synthetic row there could mark a real reminder as already-sent. A test email also
belongs to no event, which the NOT NULL ``event_id`` cannot express.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_email_log",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("resend_id", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_test_email_log"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_test_email_log_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_test_email_log_user_id", "test_email_log", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_test_email_log_user_id", table_name="test_email_log")
    op.drop_table("test_email_log")
