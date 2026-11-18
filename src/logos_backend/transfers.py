"""Передача обращения менеджерам (#16).

Ответственный хранится в ``conversations.assignee_manager_id``; каждая передача —
строка ``conversation_transfers`` со статусом ``pending`` («Ожидает принятия»),
``accepted`` («Принято») или ``returned`` («Возвращено»). Возврат отдаёт диалог
прежнему владельцу с тем же комментарием.

Менеджер «в смене» — флаг ``managers.on_shift``; вне смены выбрать нельзя.
Ответственный не ограничивает доступ: все менеджеры по-прежнему видят диалоги.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from logos_backend import clock
from logos_backend.db import (
    _create_engine,
    conversation_transfers,
    conversations,
    immediate_transaction,
    managers,
)

PENDING = "pending"
ACCEPTED = "accepted"
RETURNED = "returned"

MAX_COMMENT_LENGTH = 1000


class ConversationNotFoundError(Exception):
    """Диалога нет."""


class InvalidCommentError(Exception):
    """Комментарий пуст."""


class InvalidTargetError(Exception):
    """Выбранный менеджер не подходит: нет такого, не принял приглашение или не в смене."""


class TransferPendingError(Exception):
    """У обращения уже есть передача, ожидающая принятия."""


class NoPendingTransferError(Exception):
    """Нет передачи, ожидающей принятия."""


class TransferForbiddenError(Exception):
    """Принять или вернуть может только выбранный менеджер."""


class TransferConflictError(Exception):
    """Диалог изменён параллельно; запрос можно повторить."""


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def colleagues(manager_id: int) -> list[dict[str, object]]:
    """Активные коллеги для выбора; ожидающие приглашения не входят."""
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(managers.c.id, managers.c.name, managers.c.on_shift)
                .where(
                    managers.c.id != manager_id,
                    managers.c.password_hash.is_not(None),
                )
                .order_by(managers.c.name)
            ).all()
    finally:
        engine.dispose()
    return [{"id": row.id, "name": row.name, "on_shift": bool(row.on_shift)} for row in rows]


def _transfer_rows(connection: Connection, conversation_id: int) -> list[Any]:
    sender = managers.alias("sender")
    receiver = managers.alias("receiver")
    rows = connection.execute(
        select(
            *conversation_transfers.c,
            sender.c.name.label("from_name"),
            receiver.c.name.label("to_name"),
        )
        .select_from(
            conversation_transfers.outerjoin(
                sender, conversation_transfers.c.from_manager_id == sender.c.id
            ).outerjoin(
                receiver, conversation_transfers.c.to_manager_id == receiver.c.id
            )
        )
        .where(conversation_transfers.c.conversation_id == conversation_id)
        .order_by(conversation_transfers.c.id)
    ).mappings().all()
    return list(rows)


def _payload(row: Any) -> dict[str, object]:
    sender = None
    if row["from_manager_id"] is not None:
        sender = {"id": row["from_manager_id"], "name": row["from_name"]}
    return {
        "id": row["id"],
        "from": sender,
        "to": {"id": row["to_manager_id"], "name": row["to_name"]},
        "comment": row["comment"],
        "status": row["status"],
        "created_at": _iso(int(row["created_at"])),
        "resolved_at": _iso(int(row["resolved_at"])) if row["resolved_at"] else None,
    }


def state(connection: Connection, conversation_id: int) -> dict[str, object]:
    """Ответственный, последняя передача и журнал — для шапки диалога и ленты."""
    assignee = (
        connection.execute(
            select(managers.c.id, managers.c.name)
            .select_from(
                conversations.outerjoin(
                    managers, conversations.c.assignee_manager_id == managers.c.id
                )
            )
            .where(conversations.c.id == conversation_id)
        )
        .mappings()
        .first()
    )
    transfers = _transfer_rows(connection, conversation_id)
    return {
        "assignee": (
            {"id": assignee["id"], "name": assignee["name"]}
            if assignee is not None and assignee["id"] is not None
            else None
        ),
        "transfer": _payload(transfers[-1]) if transfers else None,
        "transfers": [_payload(row) for row in transfers],
    }


def transfer(conversation_id: int, manager_id: int, to_manager_id: int, comment: str) -> None:
    """Передаёт обращение коллеге; комментарий обязателен."""
    text = comment.strip()
    if not text:
        raise InvalidCommentError
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            seen = connection.execute(
                select(conversations.c.assignee_manager_id).where(
                    conversations.c.id == conversation_id
                )
            ).first()
            if seen is None:
                raise ConversationNotFoundError
            assignee = seen[0]
            if to_manager_id in (manager_id, assignee):
                raise InvalidTargetError
            target = connection.execute(
                select(managers.c.password_hash, managers.c.on_shift).where(
                    managers.c.id == to_manager_id
                )
            ).first()
            if target is None or target.password_hash is None or not target.on_shift:
                raise InvalidTargetError
            pending = connection.execute(
                select(conversation_transfers.c.id).where(
                    conversation_transfers.c.conversation_id == conversation_id,
                    conversation_transfers.c.status == PENDING,
                )
            ).first()
            if pending is not None:
                raise TransferPendingError
            connection.execute(
                conversation_transfers.insert().values(
                    conversation_id=conversation_id,
                    from_manager_id=assignee if assignee is not None else manager_id,
                    to_manager_id=to_manager_id,
                    comment=text,
                    status=PENDING,
                    created_at=clock.now_seconds(),
                )
            )
            connection.execute(
                update(conversations)
                .where(conversations.c.id == conversation_id)
                .values(assignee_manager_id=to_manager_id)
            )
    finally:
        engine.dispose()


def _resolve(conversation_id: int, manager_id: int, status: str) -> None:
    """Закрывает ожидающую передачу и, для возврата, отдаёт диалог прежнему владельцу."""
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            row = (
                connection.execute(
                    select(*conversation_transfers.c).where(
                        conversation_transfers.c.conversation_id == conversation_id,
                        conversation_transfers.c.status == PENDING,
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise NoPendingTransferError
            if int(row["to_manager_id"]) != manager_id:
                raise TransferForbiddenError
            resolved = connection.execute(
                update(conversation_transfers)
                .where(
                    conversation_transfers.c.id == row["id"],
                    conversation_transfers.c.status == PENDING,
                )
                .values(status=status, resolved_at=clock.now_seconds())
            ).rowcount
            if resolved != 1:
                raise TransferConflictError
            if status == RETURNED:
                connection.execute(
                    update(conversations)
                    .where(conversations.c.id == conversation_id)
                    .values(assignee_manager_id=row["from_manager_id"])
                )
    finally:
        engine.dispose()


def accept(conversation_id: int, manager_id: int) -> None:
    """Новый ответственный принимает обращение."""
    _resolve(conversation_id, manager_id, ACCEPTED)


def return_to_previous(conversation_id: int, manager_id: int) -> None:
    """Возвращает обращение прежнему владельцу с тем же комментарием."""
    _resolve(conversation_id, manager_id, RETURNED)
