"""Журнал действий (#18): неизменяемые записи с именем и IP на момент события.

Идентификатор ревизии: 0012
Предыдущая ревизия: 0011
Дата создания: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurred_at", sa.Integer(), nullable=False),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("actor_name", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=False),
        # Внешнего ключа нет: запись хранит снимок имени и переживает удаление.
        sa.CheckConstraint(
            "actor_kind IN ('administrator', 'manager')", name="ck_audit_events_actor_kind"
        ),
    )
    op.create_index("ix_audit_events_occurred", "audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_occurred", table_name="audit_events")
    op.drop_table("audit_events")
