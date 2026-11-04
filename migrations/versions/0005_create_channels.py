"""Создаёт таблицу канала Telegram (один бот на установку).

Идентификатор ревизии: 0005
Предыдущая ревизия: 0004
Дата создания: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("bot_username", sa.Text(), nullable=False),
        sa.Column("token", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("update_offset", sa.Integer(), nullable=False),
        sa.Column("connected_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_channels_single"),
        sa.CheckConstraint(
            "status IN ('connected', 'error', 'disconnected')", name="ck_channels_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("channels")
