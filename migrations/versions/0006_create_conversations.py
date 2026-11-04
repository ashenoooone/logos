"""Создаёт диалоги и сообщения «Входящих» (#6).

Идентификатор ревизии: 0006
Предыдущая ревизия: 0005
Дата создания: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("last_message_at", sa.Integer(), nullable=False),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.Integer(), nullable=True),
        sa.CheckConstraint("direction IN ('in', 'out')", name="ck_messages_direction"),
        sa.CheckConstraint(
            "kind IN ('text', 'photo', 'document', 'unsupported')", name="ck_messages_kind"
        ),
        sa.CheckConstraint(
            "(direction = 'in' AND status IS NULL) OR "
            "(direction = 'out' AND status IN ('sending', 'delivered', 'failed'))",
            name="ck_messages_status",
        ),
    )
    op.create_index("ix_messages_conversation", "messages", ["conversation_id", "id"])
    op.create_index(
        "uq_messages_incoming",
        "messages",
        ["conversation_id", "telegram_message_id"],
        unique=True,
        sqlite_where=sa.text("direction = 'in'"),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
