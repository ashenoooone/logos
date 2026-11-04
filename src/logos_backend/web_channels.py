"""Раздел «Каналы» администратора: Telegram-бот по токену (#5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from logos_backend import auth, channels
from logos_backend.web_auth import require_administrator, require_csrf

MAX_TOKEN_LENGTH = 200
MAX_CHANNEL_NAME_LENGTH = 200

router = APIRouter()


class TokenRequest(BaseModel):
    token: str = Field(max_length=MAX_TOKEN_LENGTH)


class ConnectRequest(BaseModel):
    token: str = Field(max_length=MAX_TOKEN_LENGTH)
    name: str = Field(default="", max_length=MAX_CHANNEL_NAME_LENGTH)


def _json(content: dict[str, object], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=content, headers={"Cache-Control": "no-store"}
    )


def _channel_payload(channel: channels.Channel | None) -> dict[str, object]:
    """Состояние канала без токена; «ни разу не подключали» = ``disconnected``."""
    if channel is None:
        return {
            "provider": "telegram",
            "name": None,
            "bot_username": None,
            "status": channels.DISCONNECTED,
            "error": None,
            "updated_at": None,
        }
    return {
        "provider": "telegram",
        "name": channel.name,
        "bot_username": channel.bot_username,
        "status": channel.status,
        "error": channel.error,
        "updated_at": datetime.fromtimestamp(channel.updated_at, tz=UTC).isoformat(),
    }


def _invalid_token() -> JSONResponse:
    return _json({"detail": "Invalid bot token", "field": "token"}, status_code=422)


def _unavailable() -> JSONResponse:
    return _json({"detail": "Telegram Bot API is unavailable"}, status_code=502)


@router.get("/admin/channels")
def get_channel(
    subject: Annotated[auth.Subject, Depends(require_administrator)],
) -> JSONResponse:
    return _json({"channel": _channel_payload(channels.get_channel())})


@router.post("/admin/channels/telegram/check", dependencies=[Depends(require_csrf)])
def check_token(
    payload: TokenRequest,
    subject: Annotated[auth.Subject, Depends(require_administrator)],
) -> JSONResponse:
    """Проверяет токен без сохранения — кнопка «Проверить подключение»."""
    try:
        username = channels.check_token(payload.token)
    except channels.InvalidTokenError:
        return _invalid_token()
    except (channels.TelegramUnavailableError, channels.TelegramConflictError):
        return _unavailable()
    return _json({"bot_username": username})


@router.post("/admin/channels/telegram", dependencies=[Depends(require_csrf)])
def connect(
    payload: ConnectRequest,
    subject: Annotated[auth.Subject, Depends(require_administrator)],
) -> JSONResponse:
    """Подключает или переподключает бота; неверный токен канал не меняет."""
    try:
        channel = channels.connect(payload.token, payload.name)
    except channels.InvalidTokenError:
        return _invalid_token()
    except channels.AlreadyConnectedError:
        return _json({"detail": "Channel is already connected"}, status_code=409)
    except (channels.TelegramUnavailableError, channels.TelegramConflictError):
        return _unavailable()
    return _json({"channel": _channel_payload(channel)})


@router.post("/admin/channels/telegram/disconnect", dependencies=[Depends(require_csrf)])
def disconnect(
    subject: Annotated[auth.Subject, Depends(require_administrator)],
) -> JSONResponse:
    try:
        channel = channels.disconnect()
    except channels.ChannelNotFoundError:
        return _json({"detail": "Channel not found"}, status_code=404)
    return _json({"channel": _channel_payload(channel)})
