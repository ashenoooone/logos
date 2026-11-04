"""Создаёт таблицу неподтверждённых смен email менеджера.

Идентификатор ревизии: 0004
Предыдущая ревизия: 0003
Дата создания: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("new_email", sa.Text(), nullable=False),
        sa.Column("new_email_normalized", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.CheckConstraint("expires_at > created_at", name="ck_email_changes_expiry"),
    )


def downgrade() -> None:
    op.drop_table("email_changes")
