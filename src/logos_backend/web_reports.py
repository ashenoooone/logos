"""HTTP-слой отчётов (#17): статистика работы менеджеров.

Только администратор. CSV собирает фронтенд из того же ответа, поэтому строки
в файле совпадают с таблицей на экране.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from logos_backend import auth, reports
from logos_backend.web_auth import require_administrator

router = APIRouter(prefix="/admin/reports")


def _json(content: dict[str, object], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=content, headers={"Cache-Control": "no-store"}
    )


@router.get("/statistics")
def statistics(
    subject: Annotated[auth.Subject, Depends(require_administrator)],
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    manager_id: int | None = None,
    channel: Literal["all", "telegram"] = "all",
) -> JSONResponse:
    try:
        report = reports.build_report(date_from, date_to, manager_id, channel)
    except reports.InvalidPeriodError:
        return _json({"detail": "Period start is after period end", "field": "from"}, 422)
    except reports.ManagerNotFoundError:
        return _json({"detail": "Manager not found"}, 404)
    return _json(report)
