"""Единая точка получения текущего времени, подменяемая в тестах."""

from __future__ import annotations

import time


def now_seconds() -> int:
    """Возвращает текущее время Unix в секундах."""
    return int(time.time())
