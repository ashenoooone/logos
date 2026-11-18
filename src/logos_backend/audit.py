"""Журнал действий (#18).

Записи только добавляются: API не меняет и не удаляет их. Имя сотрудника и IP
сохраняются снимком на момент события, поэтому переименование или смена адреса
не переписывают историю. Срок хранения — 12 месяцев, просроченные записи
удаляются при чтении журнала.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.engine import Connection

from logos_backend import auth, clock
from logos_backend.db import _create_engine, audit_events

RETENTION_SECONDS = 365 * 24 * 60 * 60
MAX_LIST_EVENTS = 500
MAX_EXPORT_EVENTS = 100_000

LOGIN = "login"
LOGOUT = "logout"
TAG_DELETED = "tag_deleted"
EXPORT = "export"

ACTIONS = (LOGIN, LOGOUT, TAG_DELETED, EXPORT)


def actor_name(subject: auth.Subject) -> str:
    """Подпись сотрудника в журнале: ФИО менеджера или логин администратора."""
    if subject.kind == auth.ADMINISTRATOR:
        return subject.login or "Администратор"
    return subject.name or subject.email or "Менеджер"


def actor_value(kind: str, actor_id: int) -> str:
    """Стабильный ключ фильтра «Сотрудник»."""
    return f"{kind}:{actor_id}"


def record(
    subject: auth.Subject,
    action: str,
    description: str,
    ip: str,
    now: int | None = None,
) -> None:
    """Добавляет запись; вызывается только после успешного действия."""
    timestamp = clock.now_seconds() if now is None else now
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(audit_events).values(
                    occurred_at=timestamp,
                    actor_kind=subject.kind,
                    actor_id=subject.id,
                    actor_name=actor_name(subject),
                    action=action,
                    description=description,
                    ip=ip,
                )
            )
    finally:
        engine.dispose()


def purge_expired(now: int | None = None) -> None:
    """Автоудаление записей старше 12 месяцев (при каждом чтении журнала)."""
    timestamp = clock.now_seconds() if now is None else now
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                delete(audit_events).where(
                    audit_events.c.occurred_at < timestamp - RETENTION_SECONDS
                )
            )
    finally:
        engine.dispose()


def _filters(
    actor_kind: str | None,
    actor_id: int | None,
    action: str | None,
    from_ts: int | None,
    to_ts: int | None,
) -> list[Any]:
    conditions: list[Any] = []
    if actor_kind is not None and actor_id is not None:
        conditions.append(audit_events.c.actor_kind == actor_kind)
        conditions.append(audit_events.c.actor_id == actor_id)
    if action is not None:
        conditions.append(audit_events.c.action == action)
    if from_ts is not None:
        conditions.append(audit_events.c.occurred_at >= from_ts)
    if to_ts is not None:
        conditions.append(audit_events.c.occurred_at <= to_ts)
    return conditions


def _rows(
    connection: Connection,
    conditions: list[Any],
    limit: int,
) -> list[dict[str, object]]:
    result = connection.execute(
        select(audit_events)
        .where(*conditions)
        .order_by(audit_events.c.occurred_at.desc(), audit_events.c.id.desc())
        .limit(limit)
    ).mappings()
    return [
        {
            "id": int(row["id"]),
            "occurred_at": datetime.fromtimestamp(int(row["occurred_at"]), tz=UTC).isoformat(),
            "actor": {
                "kind": str(row["actor_kind"]),
                "id": int(row["actor_id"]),
                "name": str(row["actor_name"]),
            },
            "action": str(row["action"]),
            "description": str(row["description"]),
            "ip": str(row["ip"]),
        }
        for row in result
    ]


def list_events(
    actor_kind: str | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    now: int | None = None,
) -> dict[str, object]:
    """Последние ``MAX_LIST_EVENTS`` записей, их общее число и список сотрудников."""
    purge_expired(now)
    conditions = _filters(actor_kind, actor_id, action, from_ts, to_ts)
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            total = connection.execute(
                select(func.count()).select_from(audit_events).where(*conditions)
            ).scalar_one()
            events = _rows(connection, conditions, MAX_LIST_EVENTS)
            # SQLite при MAX() берёт остальные колонки из строки с максимумом:
            # подпись = последнее имя этого сотрудника в журнале.
            actor_rows = connection.execute(
                select(
                    audit_events.c.actor_kind,
                    audit_events.c.actor_id,
                    audit_events.c.actor_name,
                    func.max(audit_events.c.occurred_at).label("last_at"),
                ).group_by(audit_events.c.actor_kind, audit_events.c.actor_id)
            ).all()
    finally:
        engine.dispose()
    actors = [
        {"kind": str(kind), "id": int(actor_id_), "name": str(name)}
        for kind, actor_id_, name, _ in actor_rows
    ]
    actors.sort(key=lambda item: (str(item["name"]).casefold(), str(item["kind"])))
    return {
        "events": events,
        "actors": actors,
        "total": int(total),
        "truncated": int(total) > len(events),
    }


def export_rows(
    actor_kind: str | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    now: int | None = None,
) -> list[dict[str, object]]:
    """Строки для CSV: те же фильтры, не более 100 000 записей."""
    purge_expired(now)
    conditions = _filters(actor_kind, actor_id, action, from_ts, to_ts)
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            return _rows(connection, conditions, MAX_EXPORT_EVENTS)
    finally:
        engine.dispose()
