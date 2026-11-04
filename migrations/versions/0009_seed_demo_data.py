"""Фейковые данные для демонстрации продукта (``logos_backend.demo_seed``).

Срабатывает только при ``LOGOS_DEMO_SEED=1`` (``scripts/dev.sh`` и
``scripts/up.sh`` ставят его по умолчанию) и только на пустой базе. Без
переменной ничего не делает: известные пароли в production недопустимы.

Идентификатор ревизии: 0009
Предыдущая ревизия: 0008
Дата создания: 2026-11-04
"""

from __future__ import annotations

import os

from alembic import op

from logos_backend import clock
from logos_backend.demo_seed import seed

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if os.environ.get("LOGOS_DEMO_SEED") == "1":
        seed(op.get_bind(), clock.now_seconds())


def downgrade() -> None:
    # Демо-строки не удаляем: после работы с ними их не отличить от настоящих.
    pass
