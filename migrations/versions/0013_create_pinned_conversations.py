"""Закреплённые диалоги менеджера (#12).

Закрепление личное: у каждого менеджера свой набор, не больше пяти. Удаление
диалога снимает закрепление каскадом.

Идентификатор ревизии: 0013
Предыдущая ревизия: 0012
Дата создания: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pinned_conversations",
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("pinned_at", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_pinned_conversations_conversation",
        "pinned_conversations",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_table("pinned_conversations")
