"""Шаблоны ответов (#11): общие на компанию, меняет и удаляет автор.

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
        "reply_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_reply_templates_name_not_blank"),
        sa.CheckConstraint("length(trim(text)) > 0", name="ck_reply_templates_text_not_blank"),
    )


def downgrade() -> None:
    op.drop_table("reply_templates")
