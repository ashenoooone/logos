"""Проставляет авторов ответов в демо-диалогах (``logos_backend.demo_seed``).

Сид 0009 выполняется до появления ``messages.manager_id`` (0010), поэтому ответы
демо-диалогов остались без автора. Трогает только демо-диалоги (``chat_id`` вне
диапазона Telegram) и только при наличии демо-менеджеров; иначе ничего не делает.

Идентификатор ревизии: 0011
Предыдущая ревизия: 0010
Дата создания: 2026-11-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from logos_backend.demo_seed import DEMO_CHAT_ID_BASE, MANAGERS

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    ids = [
        bind.execute(
            sa.text("SELECT id FROM managers WHERE email_normalized = :email"),
            {"email": email},
        ).scalar()
        for _, email in MANAGERS
    ]
    if None in ids:
        return
    # Один менеджер на диалог, по кругу — как в сиде.
    for index, manager_id in enumerate(ids):
        bind.execute(
            sa.text(
                "UPDATE messages SET manager_id = :manager_id "
                "WHERE direction = 'out' AND manager_id IS NULL AND conversation_id IN ("
                "SELECT id FROM conversations WHERE chat_id >= :base "
                "AND (chat_id - :base) % :count = :index)"
            ),
            {
                "manager_id": manager_id,
                "base": DEMO_CHAT_ID_BASE,
                "count": len(ids),
                "index": index,
            },
        )


def downgrade() -> None:
    # Авторов не снимаем: после работы с данными их не отличить от настоящих.
    pass
