"""Тестовый администратор для локальной разработки: логин ``admin``, пароль ``admin``.

Срабатывает только при ``LOGOS_DEV_ADMIN=1`` и только если администратора ещё
нет. Без переменной миграция ничего не делает: известный пароль в production —
бэкдор, там первый администратор создаётся только через ``create-admin`` (ADR-0006).

Идентификатор ревизии: 0008
Предыдущая ревизия: 0007
Дата создания: 2026-11-04
"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

from logos_backend.security import hash_password

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

DEV_LOGIN = "admin"
DEV_PASSWORD = "admin"


def upgrade() -> None:
    if os.environ.get("LOGOS_DEV_ADMIN") != "1":
        return
    op.get_bind().execute(
        sa.text(
            "INSERT OR IGNORE INTO administrators (id, login, password_hash) "
            "VALUES (1, :login, :password_hash)"
        ),
        {"login": DEV_LOGIN, "password_hash": hash_password(DEV_PASSWORD)},
    )


def downgrade() -> None:
    # Строку не удаляем: по логину не отличить тестового администратора от настоящего.
    pass
