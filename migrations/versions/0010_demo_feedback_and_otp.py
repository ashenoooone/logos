"""Исправляет диалоги и добавляет авторство и менеджерский OTP."""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _is_start_command(text: str | None) -> bool:
    if text is None:
        return False
    token = text.strip().split(maxsplit=1)
    if not token:
        return False
    command = token[0].casefold()
    return command == "/start" or bool(re.fullmatch(r"/start@[a-z0-9_]+", command))


def upgrade() -> None:
    bind = op.get_bind()
    commands = bind.execute(
        sa.text(
            "SELECT id, text FROM messages "
            "WHERE direction = 'in' AND kind = 'text'"
        )
    ).all()
    remove_ids = [int(row.id) for row in commands if _is_start_command(row.text)]
    if remove_ids:
        bind.execute(
            sa.text("DELETE FROM messages WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": remove_ids},
        )
    bind.execute(
        sa.text(
            "UPDATE conversations SET last_message_at = coalesce("
            "(SELECT max(created_at) FROM messages "
            "WHERE messages.conversation_id = conversations.id), created_at)"
        )
    )
    op.add_column("messages", sa.Column("manager_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("messages") as batch:
        batch.create_foreign_key(
            "fk_messages_manager_id_managers",
            "managers",
            ["manager_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_table(
        "manager_otp_codes",
        sa.Column("manager_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_requested_at", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["manager_id"], ["managers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("manager_id"),
        sa.CheckConstraint("attempts >= 0 AND attempts <= 5", name="ck_manager_otp_attempts"),
        sa.CheckConstraint("expires_at > created_at", name="ck_manager_otp_expiry"),
    )
    op.create_table(
        "manager_otp_requests",
        sa.Column("email_normalized", sa.String(), primary_key=True),
        sa.Column("requested_at", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("manager_otp_requests")
    op.drop_table("manager_otp_codes")
    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint("fk_messages_manager_id_managers", type_="foreignkey")
        batch.drop_column("manager_id")
    # Удалённые служебные команды намеренно не восстанавливаются.
