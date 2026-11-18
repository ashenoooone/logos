"""Внутренние комментарии команды в диалоге (#15).

Идентификатор ревизии: 0015
Предыдущая ревизия: 0014
Дата создания: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # NULL — автор удалён; сам комментарий остаётся.
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        # JSON [{"id","name"}] с именем на момент отправки.
        sa.Column("mentions", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "length(trim(text)) > 0", name="ck_conversation_comments_text_not_blank"
        ),
    )
    op.create_index(
        "ix_conversation_comments_conversation",
        "conversation_comments",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_table("conversation_comments")
