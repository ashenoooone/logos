"""Заметки о клиентах (#14).

Автор — менеджер; видимость ``team`` (вся команда) или ``private`` (только я).
``version`` растёт при каждой правке и отсекает сохранение устаревшей копии.

Идентификатор ревизии: 0014
Предыдущая ревизия: 0013
Дата создания: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(text)) > 0", name="ck_client_notes_text_not_blank"),
        sa.CheckConstraint("visibility IN ('team', 'private')", name="ck_client_notes_visibility"),
        sa.CheckConstraint("version >= 1", name="ck_client_notes_version"),
    )
    op.create_index("ix_client_notes_conversation", "client_notes", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_client_notes_conversation", table_name="client_notes")
    op.drop_table("client_notes")
