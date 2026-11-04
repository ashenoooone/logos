"""Теги диалогов (#8), сортировка и сохранённые фильтры менеджера (#7).

Идентификатор ревизии: 0007
Предыдущая ревизия: 0006
Дата создания: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_normalized", sa.Text(), nullable=False, unique=True),
        # NULL — стандартный тег администратора, иначе — автор-менеджер.
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_tags_name_not_blank"),
    )
    op.create_table(
        "conversation_tags",
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("ix_conversation_tags_tag", "conversation_tags", ["tag_id"])
    op.create_table(
        "inbox_preferences",
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sort", sa.Text(), nullable=False),
        sa.CheckConstraint("sort IN ('newest', 'oldest', 'unread')", name="ck_inbox_sort"),
    )
    op.create_table(
        "saved_filters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("filters", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("manager_id", "name", name="uq_saved_filters_name"),
    )


def downgrade() -> None:
    op.drop_table("saved_filters")
    op.drop_table("inbox_preferences")
    op.drop_table("conversation_tags")
    op.drop_table("tags")
