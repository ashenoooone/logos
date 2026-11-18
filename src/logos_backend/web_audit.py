"""HTTP-слой журнала действий (#18): только администратор, только чтение и CSV."""

from __future__ import annotations

import csv
import io
import re
from datetime import UTC, datetime
from typing import Annotated, TypedDict

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from logos_backend import audit, auth, clock
from logos_backend.web_auth import request_ip, require_administrator, require_csrf

router = APIRouter()

Administrator = Annotated[auth.Subject, Depends(require_administrator)]

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
ACTOR_PATTERN = re.compile(r"^(administrator|manager):(\d+)$")
DEFAULT_PERIOD_SECONDS = 7 * 24 * 60 * 60
MAX_QUERY_LENGTH = 64

CSV_HEADER = ("Дата и время (UTC)", "Сотрудник", "Роль", "Действие", "Описание", "IP")


class ExportBody(BaseModel):
    actor: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH)
    action: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH)
    from_: str | None = Field(default=None, alias="from", pattern=DATE_PATTERN)
    to: str | None = Field(default=None, pattern=DATE_PATTERN)


def _json(content: dict[str, object], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=content, headers={"Cache-Control": "no-store"}
    )


def _invalid(field: str, detail: str) -> JSONResponse:
    return _json({"detail": detail, "field": field}, status_code=422)


def _parse_actor(value: str | None) -> tuple[str, int] | None:
    if value is None:
        return None
    matched = ACTOR_PATTERN.fullmatch(value)
    if matched is None:
        return None
    return matched.group(1), int(matched.group(2))


def _day_start(value: str, field: str) -> int:
    try:
        moment = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(field) from exc
    return int(moment.timestamp())


def _day_end(value: str, field: str) -> int:
    return _day_start(value, field) + 24 * 60 * 60 - 1


class Filters(TypedDict):
    actor_kind: str | None
    actor_id: int | None
    action: str | None
    from_ts: int | None
    to_ts: int | None


def _filters(
    actor: str | None,
    action: str | None,
    date_from: str | None,
    date_to: str | None,
) -> Filters:
    """Общие фильтры просмотра и выгрузки; ошибки — ``ValueError`` с именем поля."""
    parsed = _parse_actor(actor)
    if actor is not None and parsed is None:
        raise ValueError("actor")
    if action is not None and action not in audit.ACTIONS:
        raise ValueError("action")

    if date_from is None and date_to is None and actor is None and action is None:
        # Умолчание критериев приёмки: без сотрудника и периода — последние 7 дней.
        now = clock.now_seconds()
        return {
            "actor_kind": None,
            "actor_id": None,
            "action": None,
            "from_ts": now - DEFAULT_PERIOD_SECONDS,
            "to_ts": now,
        }

    from_ts = _day_start(date_from, "from") if date_from is not None else None
    to_ts = _day_end(date_to, "to") if date_to is not None else None
    return {
        "actor_kind": parsed[0] if parsed else None,
        "actor_id": parsed[1] if parsed else None,
        "action": action,
        "from_ts": from_ts,
        "to_ts": to_ts,
    }


@router.get("/admin/audit-log")
def list_events(
    subject: Administrator,
    actor: Annotated[str | None, Query(max_length=MAX_QUERY_LENGTH)] = None,
    action: Annotated[str | None, Query(max_length=MAX_QUERY_LENGTH)] = None,
    date_from: Annotated[str | None, Query(alias="from", pattern=DATE_PATTERN)] = None,
    date_to: Annotated[str | None, Query(alias="to", pattern=DATE_PATTERN)] = None,
) -> JSONResponse:
    try:
        filters = _filters(actor, action, date_from, date_to)
    except ValueError as exc:
        return _invalid(str(exc), "Invalid filter value")
    return _json(audit.list_events(**filters))


@router.post("/admin/audit-log/export", dependencies=[Depends(require_csrf)])
def export_events(payload: ExportBody, subject: Administrator, request: Request) -> Response:
    try:
        filters = _filters(payload.actor, payload.action, payload.from_, payload.to)
    except ValueError as exc:
        return _invalid(str(exc), "Invalid filter value")

    rows = audit.export_rows(**filters)
    audit.record(
        subject,
        audit.EXPORT,
        f"Выгрузка журнала в CSV: {len(rows)} записей",
        request_ip(request),
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for row in rows:
        actor = row["actor"]
        assert isinstance(actor, dict)
        writer.writerow(
            (
                str(row["occurred_at"]).replace("+00:00", ""),
                str(actor["name"]),
                "Администратор" if actor["kind"] == auth.ADMINISTRATOR else "Менеджер",
                row["action"],
                row["description"],
                row["ip"],
            )
        )
    filename = f"audit-log-{datetime.now(tz=UTC).strftime('%Y%m%d')}.csv"
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
