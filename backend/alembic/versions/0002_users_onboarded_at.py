"""users.onboarded_at

Records when a user finished onboarding, so the client can stop gating the
onboarding redirect on browser ``localStorage``.

Nullable on purpose: absence *is* the signal. ``timezone`` and ``send_hour``
both carry server defaults ('UTC', 8), so neither can distinguish "never
onboarded" from "deliberately chose UTC at 08:00".

Existing rows are backfilled to ``created_at``: every user who already exists
has necessarily been through the flow, and leaving them null would bounce them
back into onboarding on their next sign-in.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("update users set onboarded_at = created_at where onboarded_at is null")


def downgrade() -> None:
    op.drop_column("users", "onboarded_at")
