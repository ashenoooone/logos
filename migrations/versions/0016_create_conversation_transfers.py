"""Добавляет передачу обращений менеджерам (#16).

Ответственный диалога, признак «в смене» у менеджера и журнал передач со
статусом «Ожидает принятия» / «Принято» / «Возвращено».

Идентификатор ревизии: 0016
Предыдущая ревизия: 0015
Дата создания: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Сырой SQL: Alembic не умеет ADD COLUMN с REFERENCES через SQLite-диалект,
    # хотя сама SQLite это поддерживает и проверяет внешний ключ.
    op.execute("ALTER TABLE managers ADD COLUMN on_shift INTEGER NOT NULL DEFAULT 1")
    op.execute(
        "ALTER TABLE conversations ADD COLUMN assignee_manager_id INTEGER "
        "REFERENCES managers(id) ON DELETE SET NULL"
    )
    op.create_table(
        "conversation_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_manager_id",
            sa.Integer(),
            sa.ForeignKey("managers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("to_manager_id", sa.Integer(), sa.ForeignKey("managers.id"), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("resolved_at", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'returned')", name="ck_transfers_status"
        ),
        sa.CheckConstraint("length(trim(comment)) > 0", name="ck_transfers_comment"),
    )
    op.create_index(
        "ix_conversation_transfers_conversation",
        "conversation_transfers",
        ["conversation_id", "id"],
    )
    # Демо: один менеджер вне смены, чтобы состояние было видно в списке передачи.
    op.get_bind().execute(
        sa.text("UPDATE managers SET on_shift = 0 WHERE email_normalized = 'igor@demo.logos'")
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_transfers_conversation", table_name="conversation_transfers"
    )
    op.drop_table("conversation_transfers")
    op.drop_column("conversations", "assignee_manager_id")
    op.drop_column("managers", "on_shift")
