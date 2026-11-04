"""Канал Telegram: подключение бота по токену, отключение и фоновый long polling.

Решения ADR-0007: один бот на установку, ``getUpdates`` вместо webhook, токен
хранится открытым текстом и наружу не отдаётся. При (пере)подключении
накопленные обновления сбрасываются: принимаются только новые сообщения.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert

from logos_backend import clock
from logos_backend.db import _create_engine, channels, immediate_transaction

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
# Формат токена BotFather: «<id бота>:<секрет>». Проверка до запроса не даёт
# подставить в URL Bot API произвольный путь.
TOKEN_PATTERN = re.compile(r"\d{1,20}:[A-Za-z0-9_-]{20,100}")
DEFAULT_NAME = "Telegram"
POLL_TIMEOUT_SECONDS = 25
REQUEST_TIMEOUT_SECONDS = 10
IDLE_SECONDS = 2.0
RETRY_SECONDS = 5.0

CONNECTED = "connected"
ERROR = "error"
DISCONNECTED = "disconnected"

ERROR_TOKEN_INVALID = "token_invalid"
ERROR_CONFLICT = "conflict"


class InvalidTokenError(Exception):
    """Токен не похож на токен бота или отклонён Bot API."""


class TelegramConflictError(Exception):
    """Обновления бота уже забирает другое приложение (HTTP 409)."""


class TelegramUnavailableError(Exception):
    """Bot API недоступен или ответил неожиданно."""


class AlreadyConnectedError(Exception):
    """Канал уже подключён; сначала его нужно отключить."""


class ChannelNotFoundError(Exception):
    """Канал ещё ни разу не подключали."""


@dataclass(frozen=True)
class Channel:
    name: str
    bot_username: str
    status: str
    error: str | None
    updated_at: int


def _call(token: str, method: str, params: dict[str, Any], timeout: float) -> Any:
    """Вызывает метод Bot API.

    Исключения поднимаются ``from None``: исходная ошибка urllib содержит URL с
    токеном и не должна попасть в трассировку или лог.
    """
    if not TOKEN_PATTERN.fullmatch(token):
        raise InvalidTokenError
    request = Request(f"{API_BASE}/bot{token}/{method}", data=urlencode(params).encode())
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except HTTPError as exc:
        if exc.code in (401, 404):
            raise InvalidTokenError from None
        if exc.code == 409:
            raise TelegramConflictError from None
        raise TelegramUnavailableError from None
    except (URLError, OSError, ValueError):
        raise TelegramUnavailableError from None
    if not isinstance(body, dict) or body.get("ok") is not True:
        raise TelegramUnavailableError
    return body.get("result")


def check_token(token: str) -> str:
    """Проверяет токен через ``getMe`` и возвращает имя бота без ``@``."""
    result = _call(token.strip(), "getMe", {}, REQUEST_TIMEOUT_SECONDS)
    if not isinstance(result, dict) or not isinstance(result.get("username"), str):
        raise TelegramUnavailableError
    return str(result["username"])


def _row_to_channel(row: Any) -> Channel:
    return Channel(
        name=str(row["name"]),
        bot_username=str(row["bot_username"]),
        status=str(row["status"]),
        error=row["error"],
        updated_at=int(row["updated_at"]),
    )


def get_channel() -> Channel | None:
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            row = connection.execute(select(channels)).mappings().first()
    finally:
        engine.dispose()
    return None if row is None else _row_to_channel(row)


def _current_status() -> str | None:
    channel = get_channel()
    return None if channel is None else channel.status


def connect(token: str, name: str, now: int | None = None) -> Channel:
    """Подключает бота; при ошибке токена канал не меняется."""
    if _current_status() == CONNECTED:
        raise AlreadyConnectedError
    token = token.strip()
    username = check_token(token)
    # Webhook мешает getUpdates; drop_pending_updates сбрасывает накопленное.
    _call(token, "deleteWebhook", {"drop_pending_updates": "true"}, REQUEST_TIMEOUT_SECONDS)

    timestamp = clock.now_seconds() if now is None else now
    values = {
        "name": name.strip() or DEFAULT_NAME,
        "bot_username": username,
        "token": token,
        "status": CONNECTED,
        "error": None,
        "update_offset": 0,
        "connected_at": timestamp,
        "updated_at": timestamp,
    }
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            status = connection.execute(select(channels.c.status)).scalar()
            if status == CONNECTED:
                raise AlreadyConnectedError
            connection.execute(
                insert(channels)
                .values(id=1, **values)
                .on_conflict_do_update(index_elements=[channels.c.id], set_=values)
            )
            row = connection.execute(select(channels)).mappings().one()
    finally:
        engine.dispose()
    return _row_to_channel(row)


def disconnect(now: int | None = None) -> Channel:
    """Отключает канал: токен стирается, строка канала остаётся."""
    timestamp = clock.now_seconds() if now is None else now
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            row = (
                connection.execute(
                    update(channels)
                    .where(channels.c.id == 1)
                    .values(status=DISCONNECTED, token=None, error=None, updated_at=timestamp)
                    .returning(*channels.c)
                )
                .mappings()
                .first()
            )
    finally:
        engine.dispose()
    if row is None:
        raise ChannelNotFoundError
    return _row_to_channel(row)


def _save_poll_result(connected_at: int, values: dict[str, Any]) -> None:
    """Пишет результат опроса, только если канал не переподключали и не отключали."""
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                update(channels)
                .where(
                    channels.c.id == 1,
                    channels.c.status == CONNECTED,
                    channels.c.connected_at == connected_at,
                )
                .values(**values)
            )
    finally:
        engine.dispose()


def poll_once() -> bool:
    """Один вызов ``getUpdates``. Возвращает ``False``, если опрашивать нечего."""
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            row = connection.execute(select(channels)).mappings().first()
    finally:
        engine.dispose()
    if row is None or row["status"] != CONNECTED or not row["token"]:
        return False

    connected_at = int(row["connected_at"])
    try:
        updates = _call(
            str(row["token"]),
            "getUpdates",
            {"offset": int(row["update_offset"]), "timeout": POLL_TIMEOUT_SECONDS},
            POLL_TIMEOUT_SECONDS + REQUEST_TIMEOUT_SECONDS,
        )
    except (InvalidTokenError, TelegramConflictError) as exc:
        code = ERROR_TOKEN_INVALID if isinstance(exc, InvalidTokenError) else ERROR_CONFLICT
        _save_poll_result(
            connected_at, {"status": ERROR, "error": code, "updated_at": clock.now_seconds()}
        )
        return True

    ids = [item["update_id"] for item in updates or [] if isinstance(item, dict)]
    if ids:
        # ponytail: обновления пока только подтверждаются; сохранение сообщений — #6.
        _save_poll_result(connected_at, {"update_offset": max(ids) + 1})
    return True


def run_poller(stop: threading.Event) -> None:
    """Фоновый цикл опроса; рассчитан на один воркер Uvicorn (ADR-0007)."""
    while not stop.is_set():
        try:
            active = poll_once()
        except TelegramUnavailableError:
            logger.warning("Telegram Bot API is unavailable, retrying")
            stop.wait(RETRY_SECONDS)
            continue
        except Exception:
            logger.exception("Telegram polling failed")
            stop.wait(RETRY_SECONDS)
            continue
        if not active:
            stop.wait(IDLE_SECONDS)
