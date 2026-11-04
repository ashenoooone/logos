"""Создаёт таблицу administrators.

Идентификатор ревизии: 0001
Предыдущая ревизия:
Дата создания: 2026-11-04

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "administrators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("login", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_administrators_singleton"),
    )


def downgrade() -> None:
    op.drop_table("administrators")
