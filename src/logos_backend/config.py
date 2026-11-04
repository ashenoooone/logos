"""Настройки времени выполнения, читаемые из окружения процесса."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DATABASE_PATH_ENV = "LOGOS_DATABASE_PATH"
DEFAULT_DATABASE_PATH = Path("data/logos.sqlite3")
ALLOWED_ORIGINS_ENV = "LOGOS_ALLOWED_ORIGINS"

PUBLIC_BASE_URL_ENV = "LOGOS_PUBLIC_BASE_URL"
DEFAULT_PUBLIC_BASE_URL = "http://localhost:5173"

SMTP_HOST_ENV = "LOGOS_SMTP_HOST"
SMTP_PORT_ENV = "LOGOS_SMTP_PORT"
SMTP_FROM_ENV = "LOGOS_SMTP_FROM"
SMTP_USERNAME_ENV = "LOGOS_SMTP_USERNAME"
SMTP_PASSWORD_ENV = "LOGOS_SMTP_" + "PASSWORD"
SMTP_TLS_ENV = "LOGOS_SMTP_TLS"
SMTP_TIMEOUT_ENV = "LOGOS_SMTP_TIMEOUT"

DEFAULT_SMTP_HOST = "127.0.0.1"
DEFAULT_SMTP_PORT = 1026
DEFAULT_SMTP_FROM = "no-reply@logos.local"
DEFAULT_SMTP_TLS = "none"
DEFAULT_SMTP_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class SmtpSettings:
    """Параметры одного SMTP-соединения; очередь и повторы не настраиваются."""

    host: str
    port: int
    sender: str
    username: str | None
    password: str | None
    tls: str
    timeout_seconds: float


def get_database_path() -> Path:
    """Возвращает настроенный путь к файлу SQLite; читается заново при каждом вызове."""
    raw = os.environ.get(DATABASE_PATH_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_DATABASE_PATH
    return Path(raw)


def get_allowed_origins() -> tuple[str, ...]:
    """Возвращает явно разрешённые origin для проверки изменяющих запросов.

    Пустой список означает только same-origin, вычисляемый из запроса. Шаблон
    ``*`` не поддерживается: CORS с wildcard не настраивается.
    """
    raw = os.environ.get(ALLOWED_ORIGINS_ENV)
    if raw is None:
        return ()
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


def get_public_base_url() -> str:
    """Базовый публичный адрес фронтенда для ссылок в письмах."""
    raw = os.environ.get(PUBLIC_BASE_URL_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_PUBLIC_BASE_URL
    return raw.strip()


def _optional_env(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def get_smtp_settings() -> SmtpSettings:
    """Читает SMTP-настройки; неверный порт или таймаут поднимает ``ValueError``."""
    raw_port = os.environ.get(SMTP_PORT_ENV)
    port = DEFAULT_SMTP_PORT if raw_port is None or not raw_port.strip() else int(raw_port)

    raw_timeout = os.environ.get(SMTP_TIMEOUT_ENV)
    timeout = (
        DEFAULT_SMTP_TIMEOUT_SECONDS
        if raw_timeout is None or not raw_timeout.strip()
        else float(raw_timeout)
    )

    raw_tls = os.environ.get(SMTP_TLS_ENV)
    tls = DEFAULT_SMTP_TLS if raw_tls is None or not raw_tls.strip() else raw_tls.strip().lower()

    return SmtpSettings(
        host=_optional_env(SMTP_HOST_ENV) or DEFAULT_SMTP_HOST,
        port=port,
        sender=_optional_env(SMTP_FROM_ENV) or DEFAULT_SMTP_FROM,
        username=_optional_env(SMTP_USERNAME_ENV),
        password=_optional_env(SMTP_PASSWORD_ENV),
        tls=tls,
        timeout_seconds=timeout,
    )
