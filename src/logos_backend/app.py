"""FastAPI-приложение: готовность БД, аутентификация и продуктовые маршруты.

Единое приложение подключает роутеры авторизации, приглашений, профиля,
каналов, входящих и тегов. Lifespan запускает фоновый опрос Telegram.
"""


from __future__ import annotations

import re
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from logos_backend import channels, inbox
from logos_backend.db import is_database_ready
from logos_backend.web_account import router as account_router
from logos_backend.web_auth import router as auth_router
from logos_backend.web_channels import router as channels_router
from logos_backend.web_inbox import router as inbox_router
from logos_backend.web_managers import router as managers_router
from logos_backend.web_tags import router as tags_router

# Общий предохранитель запроса: превышение отклоняется до чтения и разбора
# JSON. 16 КиБ с запасом вмещают максимальные поля входа (две строки по 1024
# символа в UTF-8) и служебную обвязку.
MAX_REQUEST_BODY_BYTES = 16 * 1024
# Файл ответа клиенту (#6) — единственный маршрут с большим телом.
MAX_UPLOAD_BYTES = inbox.MAX_FILE_BYTES
UPLOAD_PATH = re.compile(r"/conversations/\d+/files")


class BodyLimit:
    """Предел тела запроса: большой только для загрузки файла ответа."""

    def __init__(self, app: ASGIApp) -> None:
        self.small = RequestBodyLimitMiddleware(app, max_body_size=MAX_REQUEST_BODY_BYTES)
        self.large = RequestBodyLimitMiddleware(app, max_body_size=MAX_UPLOAD_BYTES)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        upload = scope["type"] == "http" and UPLOAD_PATH.fullmatch(scope["path"])
        await (self.large if upload else self.small)(scope, receive, send)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Опрос Telegram в фоновом потоке; daemon не держит процесс на long poll."""
    stop = threading.Event()
    poller = threading.Thread(
        target=channels.run_poller, args=(stop,), name="telegram-poller", daemon=True
    )
    poller.start()
    try:
        yield
    finally:
        stop.set()
        poller.join(timeout=1)


app = FastAPI(
    title="Logos",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(BodyLimit)

app.include_router(auth_router)
app.include_router(managers_router)
app.include_router(account_router)
app.include_router(inbox_router)
app.include_router(tags_router)
app.include_router(channels_router)


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
