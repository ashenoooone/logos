"""FastAPI-приложение с единственным эндпоинтом готовности."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from logos_backend.db import is_database_ready

app = FastAPI(
    title="Logos",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health() -> JSONResponse:
    """Сообщает о готовности мигрированной базы данных."""
    if not is_database_ready():
        return JSONResponse(status_code=503, content={"detail": "Database is not ready"})
    return JSONResponse(status_code=200, content={"status": "ok"})
