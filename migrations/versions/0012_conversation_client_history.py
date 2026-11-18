"""Добавляет канал диалога и ключ клиента для истории обращений (#13).

Обращение = всплеск переписки (пауза больше суток начинает новое). История
строится по всем диалогам с тем же ``client_key``; пока канал один, ключ —
имя клиента без учёта регистра.

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
    op.add_column(
        "conversations",
        sa.Column("channel", sa.Text(), nullable=False, server_default="telegram"),
    )
    op.add_column(
        "conversations",
        sa.Column("client_key", sa.Text(), nullable=False, server_default=""),
    )
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, name FROM conversations")).all()
    for row_id, name in rows:
        bind.execute(
            sa.text("UPDATE conversations SET client_key = :key WHERE id = :id"),
            {"key": str(name or "").strip().casefold(), "id": row_id},
        )
    op.create_index("ix_conversations_client_key", "conversations", ["client_key"])


def downgrade() -> None:
    op.drop_index("ix_conversations_client_key", table_name="conversations")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("client_key")
        batch.drop_column("channel")
