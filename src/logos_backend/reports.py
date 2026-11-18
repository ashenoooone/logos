"""Статистика работы менеджеров (#17).

KPI считаются по обращениям, а не по сообщениям: обращение — это диалог,
в котором за период было хотя бы одно входящее сообщение. Период задаётся
датами в часовом поясе компании (``LOGOS_TIMEZONE``, по умолчанию Москва).

Отдельного статуса «закрыто» в MVP нет, поэтому закрытым считается обращение,
последнее сообщение периода в котором — ответ менеджера. Обращение закрепляется
за менеджером, отправившим первый ответ в периоде: это позволяет показать
таблицу по менеджерам без назначения ответственного (ADR-0007).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from logos_backend import clock
from logos_backend.config import get_company_timezone
from logos_backend.db import _create_engine, managers, messages

IN = "in"
OUT = "out"

# Запасной пояс, если в окружении нет базы IANA (например, минимальный Docker-образ).
FALLBACK_TIMEZONE = timezone(timedelta(hours=3), "MSK")


class InvalidPeriodError(Exception):
    """Начало периода позже конца."""


class ManagerNotFoundError(Exception):
    """Менеджера из фильтра нет."""


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    timezone_name: str


@dataclass(frozen=True)
class ConversationStats:
    """Одно обращение периода; ``manager_id`` — кто ответил первым (если ответ был)."""

    manager_id: int | None
    response_seconds: int | None
    closed: bool


@dataclass(frozen=True)
class MessageRow:
    id: int
    conversation_id: int
    direction: str
    manager_id: int | None
    created_at: int


def _zone(name: str) -> ZoneInfo | timezone:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return FALLBACK_TIMEZONE


def resolve_period(start: date | None, end: date | None) -> Period:
    """Период из фильтра; по умолчанию — текущий месяц в часовом поясе компании."""
    timezone_name = get_company_timezone()
    zone = _zone(timezone_name)
    today = datetime.fromtimestamp(clock.now_seconds(), tz=zone).date()
    resolved_start = start or today.replace(day=1)
    resolved_end = end or today
    if resolved_start > resolved_end:
        raise InvalidPeriodError
    return Period(resolved_start, resolved_end, timezone_name)


def _epoch_bounds(period: Period) -> tuple[int, int]:
    zone = _zone(period.timezone_name)
    start = datetime.combine(period.start, time.min, tzinfo=zone)
    end = datetime.combine(period.end + timedelta(days=1), time.min, tzinfo=zone)
    return int(start.timestamp()), int(end.timestamp())


def _conversation_stats(period: Period) -> list[ConversationStats]:
    """Обращения периода: у каждого первый ответ и последнее сообщение периода."""
    start, end = _epoch_bounds(period)
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            rows = (
                connection.execute(
                    select(
                        messages.c.id,
                        messages.c.conversation_id,
                        messages.c.direction,
                        messages.c.manager_id,
                        messages.c.created_at,
                    )
                    .where(messages.c.created_at >= start, messages.c.created_at < end)
                    .order_by(messages.c.created_at, messages.c.id)
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()

    grouped: dict[int, list[MessageRow]] = defaultdict(list)
    for row in rows:
        message = MessageRow(
            id=int(row["id"]),
            conversation_id=int(row["conversation_id"]),
            direction=str(row["direction"]),
            manager_id=int(row["manager_id"]) if row["manager_id"] is not None else None,
            created_at=int(row["created_at"]),
        )
        grouped[message.conversation_id].append(message)

    result: list[ConversationStats] = []
    for items in grouped.values():
        incoming = [item for item in items if item.direction == IN]
        if not incoming:
            continue
        first_incoming = incoming[0].created_at
        reply = next(
            (
                item
                for item in items
                if item.direction == OUT
                and item.manager_id is not None
                and item.created_at >= first_incoming
            ),
            None,
        )
        close_time = max(item.created_at for item in items)
        last_direction = max(
            (item for item in items if item.created_at == close_time),
            key=lambda item: item.id,
        ).direction
        result.append(
            ConversationStats(
                manager_id=reply.manager_id if reply is not None else None,
                response_seconds=(
                    reply.created_at - first_incoming if reply is not None else None
                ),
                closed=last_direction == OUT,
            )
        )
    return result


def _summary(stats: list[ConversationStats]) -> dict[str, int | None]:
    answered = [item.response_seconds for item in stats if item.response_seconds is not None]
    closed = sum(1 for item in stats if item.closed)
    average = round(sum(answered) / len(answered)) if answered else None
    return {
        "conversations": len(stats),
        "answered": len(answered),
        "closed": closed,
        "closed_percent": round(closed * 100 / len(stats)) if stats else 0,
        "average_response_seconds": average,
    }


def build_report(
    start: date | None,
    end: date | None,
    manager_id: int | None,
    channel: str,
) -> dict[str, object]:
    """Собирает KPI и строки таблицы по менеджерам; фильтры уже проверены HTTP-слоем."""
    period = resolve_period(start, end)
    stats = _conversation_stats(period)

    engine = _create_engine()
    try:
        with engine.connect() as connection:
            manager_rows = (
                connection.execute(
                    select(managers.c.id, managers.c.name).order_by(
                        managers.c.name, managers.c.id
                    )
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()

    manager_names = {int(row["id"]): str(row["name"]) for row in manager_rows}
    if manager_id is not None and manager_id not in manager_names:
        raise ManagerNotFoundError

    # Канал пока один — Telegram; фильтр «Все каналы» и «Telegram» дают одинаковые
    # цифры, но форма ответа сохраняет выбор в шапке CSV.
    filtered = (
        stats if manager_id is None else [item for item in stats if item.manager_id == manager_id]
    )
    summary = _summary(filtered)

    table: list[dict[str, object]] = []
    if summary["conversations"]:
        selected = (
            [(manager_id, manager_names[manager_id])]
            if manager_id is not None
            else sorted(manager_names.items(), key=lambda item: item[1])
        )
        for item_id, name in selected:
            own = [item for item in filtered if item.manager_id == item_id]
            table.append({"id": item_id, "name": name, **_summary(own)})
        table.sort(
            key=lambda row: (-cast(int, row["conversations"]), str(row["name"]))
        )
        attributed = sum(cast(int, row["conversations"]) for row in table)
        unanswered = (summary["conversations"] or 0) - attributed
        if manager_id is None and unanswered:
            closed_attributed = sum(cast(int, row["closed"]) for row in table)
            closed = max(0, (summary["closed"] or 0) - closed_attributed)
            table.append(
                {
                    "id": None,
                    "name": "Без ответа",
                    "conversations": unanswered,
                    "answered": 0,
                    "closed": closed,
                    "closed_percent": round(closed * 100 / unanswered),
                    "average_response_seconds": None,
                }
            )

    return {
        "period": {
            "from": period.start.isoformat(),
            "to": period.end.isoformat(),
            "timezone": period.timezone_name,
        },
        "filters": {
            "manager_id": manager_id,
            "manager_name": manager_names.get(manager_id) if manager_id is not None else None,
            "channel": channel,
        },
        "empty": summary["conversations"] == 0,
        "kpi": summary,
        "managers": table,
    }
