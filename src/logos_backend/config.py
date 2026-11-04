"""Настройки времени выполнения, читаемые из окружения процесса."""

from __future__ import annotations

import os
from pathlib import Path

DATABASE_PATH_ENV = "LOGOS_DATABASE_PATH"
DEFAULT_DATABASE_PATH = Path("data/logos.sqlite3")


def get_database_path() -> Path:
    """Возвращает настроенный путь к файлу SQLite; читается заново при каждом вызове."""
    raw = os.environ.get(DATABASE_PATH_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_DATABASE_PATH
    return Path(raw)
