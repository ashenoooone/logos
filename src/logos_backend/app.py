"""FastAPI-приложение: готовность БД, аутентификация, приглашения и восстановление.

Единое приложение подключает роутеры ``web_auth``, ``web_managers`` и
``web_recovery``; отдельного приложения для продуктовых маршрутов нет.
"""


from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.body_limit import RequestBodyLimitMiddleware

from logos_backend.db import is_database_ready
from logos_backend.web_auth import router as auth_router
from logos_backend.web_managers import router as managers_router
from logos_backend.web_recovery import router as recovery_router

# Общий предохранитель запроса: превышение отклоняется до чтения и разбора
# JSON. 16 КиБ с запасом вмещают максимальные поля входа (две строки по 1024
# символа в UTF-8) и служебную обвязку.
MAX_REQUEST_BODY_BYTES = 16 * 1024

app = FastAPI(
    title="Logos",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(RequestBodyLimitMiddleware, max_body_size=MAX_REQUEST_BODY_BYTES)

app.include_router(auth_router)
app.include_router(managers_router)
app.include_router(recovery_router)


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Отдаёт ошибку поля в том же виде, что и прикладные ``422``.

    Стандартный ответ FastAPI содержит исходное значение (``input``), включая
    пароль или токен. Фронтенду нужны только имя поля и безопасное описание,
    поэтому тело ответа повторяет форму ``{"detail","field"}`` и никогда не
    возвращает отправленные значения.
    """
    errors = exc.errors()
    first = errors[0] if errors else {}
    location = [part for part in first.get("loc", ()) if part != "body"]
    field = str(location[0]) if location else "body"
    detail = str(first.get("msg", "Invalid request"))
    return JSONResponse(
        status_code=422,
        content={"detail": detail, "field": field},
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health")
def health() -> JSONResponse:
    """Сообщает о готовности мигрированной базы данных."""
    if not is_database_ready():
        return JSONResponse(status_code=503, content={"detail": "Database is not ready"})
    return JSONResponse(status_code=200, content={"status": "ok"})
