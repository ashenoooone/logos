"""Внутренние комментарии команды в диалоге (#15).

Комментарии хранятся отдельно от ``messages``: не отправляются клиенту, не
влияют на непрочитанность, порядок списка и выгрузку переписки. Упоминание —
это ``@Имя`` в тексте; имя на момент отправки сохраняется рядом с id, поэтому
уволенный или удалённый коллега не «пропадает» из комментария, а отмечается
как недоступный.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.engine import Connection, RowMapping

from logos_backend import clock
from logos_backend.db import (
    _create_engine,
    conversation_comments,
    conversations,
    immediate_transaction,
    managers,
)

MAX_TEXT_LENGTH = 4096


class ConversationNotFoundError(Exception):
    """Диалога нет."""


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _payload(
    row: RowMapping, author: str | None, available: set[int]
) -> dict[str, object]:
    mentions = json.loads(str(row["mentions"]))
    return {
        "id": row["id"],
        "text": row["text"],
        "author": author,
        "created_at": _iso(int(row["created_at"])),
        "mentions": [
            {"id": mention["id"], "name": mention["name"], "available": mention["id"] in available}
            for mention in mentions
        ],
    }


def _find_mentions(connection: Connection, text: str) -> list[dict[str, object]]:
    """Упоминания ``@Имя`` по актуальному списку менеджеров, в порядке текста."""
    rows = connection.execute(select(managers.c.id, managers.c.name)).all()
    # Длинные имена первыми: «@Анна Мария» не должна давать ещё и «@Анна».
    candidates = sorted(rows, key=lambda row: len(str(row.name)), reverse=True)
    spans: list[tuple[int, int]] = []
    found: list[tuple[int, dict[str, object]]] = []
    for row in candidates:
        name = str(row.name)
        token = f"@{name}"
        start = 0
        while (index := text.find(token, start)) != -1:
            end = index + len(token)
            if all(end <= begin or index >= finish for begin, finish in spans):
                spans.append((index, end))
                found.append((index, {"id": int(row.id), "name": name}))
            start = index + 1
    found.sort(key=lambda item: item[0])
    return [mention for _, mention in found]


def list_comments(conversation_id: int, manager_id: int) -> dict[str, object]:
    """Тред команды и коллеги для @упоминания; текущий менеджер в подсказках не нужен."""
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                select(conversations.c.id).where(conversations.c.id == conversation_id)
            ).first()
            if exists is None:
                raise ConversationNotFoundError
            rows = (
                connection.execute(
                    select(*conversation_comments.c, managers.c.name.label("manager_name"))
                    .select_from(
                        conversation_comments.outerjoin(
                            managers, conversation_comments.c.manager_id == managers.c.id
                        )
                    )
                    .where(conversation_comments.c.conversation_id == conversation_id)
                    .order_by(conversation_comments.c.id)
                )
                .mappings()
                .all()
            )
            available = {
                int(existing)
                for existing in connection.execute(
                    select(managers.c.id).where(
                        managers.c.id.in_([row["manager_id"] for row in rows if row["manager_id"]])
                    )
                ).scalars()
            }
            colleagues = [
                {"id": int(id_), "name": name}
                for id_, name in connection.execute(
                    select(managers.c.id, managers.c.name)
                    .where(managers.c.password_hash.is_not(None), managers.c.id != manager_id)
                    .order_by(managers.c.name)
                ).all()
            ]
    finally:
        engine.dispose()
    return {
        "comments": [
            _payload(row, row["manager_name"], available) for row in rows
        ],
        "colleagues": colleagues,
    }


def add_comment(conversation_id: int, manager_id: int, text: str) -> dict[str, object]:
    """Сохраняет комментарий команды; клиенту ничего не отправляется."""
    now = clock.now_seconds()
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            exists = connection.execute(
                select(conversations.c.id).where(conversations.c.id == conversation_id)
            ).first()
            if exists is None:
                raise ConversationNotFoundError
            mentions = _find_mentions(connection, text)
            row = (
                connection.execute(
                    conversation_comments.insert()
                    .values(
                        conversation_id=conversation_id,
                        manager_id=manager_id,
                        text=text,
                        mentions=json.dumps(mentions, ensure_ascii=False),
                        created_at=now,
                    )
                    .returning(*conversation_comments.c)
                )
                .mappings()
                .one()
            )
            author = connection.execute(
                select(managers.c.name).where(managers.c.id == manager_id)
            ).scalar()
    finally:
        engine.dispose()
    return _payload(row, author, {cast(int, mention["id"]) for mention in mentions})
