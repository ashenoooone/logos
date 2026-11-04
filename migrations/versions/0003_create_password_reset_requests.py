"""Создаёт таблицу ограничения повторных запросов восстановления пароля.

Идентификатор ревизии: 0003
Предыдущая ревизия: 0002
Дата создания: 2026-11-04

Счётчик намеренно отдельный от ``login_attempts``: ограничение повтора
восстановления действует на нормализованный email независимо от того,
существует ли такая учётная запись. Существующие таблицы не изменяются.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_requests",
        sa.Column("email_normalized", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("email_normalized", name="pk_password_reset_requests"),
    )


def downgrade() -> None:
    op.drop_table("password_reset_requests")
