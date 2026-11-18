"""Отчёты (#17): период в часовом поясе компании, KPI по обращениям, фильтр."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from support import (
    BASE_URL,
    add_active_manager,
    add_administrator,
    login_administrator,
    login_manager,
    migrate,
)

from logos_backend.app import app
from logos_backend.db import conversations, database_url, messages

MSK = ZoneInfo("Europe/Moscow")


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    monkeypatch.setenv("LOGOS_TIMEZONE", "Europe/Moscow")
    migrate()


def at(day: int, hour: int, minute: int = 0) -> int:
    return int(datetime(2026, 11, day, hour, minute, tzinfo=MSK).timestamp())


def add_conversation(
    chat_id: int, name: str, incoming_at: int, replies: list[tuple[int, int]]
) -> None:
    """Диалог с одним входящим и ответами ``(manager_id, timestamp)``."""
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            conversation_id = connection.execute(
                insert(conversations)
                .values(
                    chat_id=chat_id,
                    name=name,
                    created_at=incoming_at,
                    last_message_at=max([incoming_at, *(time for _, time in replies)]),
                )
                .returning(conversations.c.id)
            ).scalar_one()
            connection.execute(
                insert(messages).values(
                    conversation_id=conversation_id,
                    direction="in",
                    kind="text",
                    text="Здравствуйте",
                    created_at=incoming_at,
                )
            )
            for manager_id, created_at in replies:
                connection.execute(
                    insert(messages).values(
                        conversation_id=conversation_id,
                        direction="out",
                        manager_id=manager_id,
                        kind="text",
                        text="Ответ",
                        status="delivered",
                        created_at=created_at,
                    )
                )
    finally:
        engine.dispose()


def admin_client() -> TestClient:
    add_administrator()
    client = TestClient(app, base_url=BASE_URL)
    assert login_administrator(client).status_code == 200
    return client


def test_period_timezone_and_manager_stats(database: None) -> None:
    first = add_active_manager("first@example.com", "correct1")
    second = add_active_manager("second@example.com", "correct1")
    # 18 ноября: два обращения первого менеджера, второе закрыто его ответом.
    add_conversation(1, "Анна", at(18, 10), [(first, at(18, 10, 4))])
    add_conversation(2, "Борис", at(18, 12), [(first, at(18, 12, 5))])
    # 19 ноября 01:30 МСК — это ещё 18 ноября по UTC: граница проверяет пояс компании.
    add_conversation(3, "Вера", at(19, 1, 30), [])
    add_conversation(4, "Глеб", at(19, 9), [(second, at(19, 9, 3))])
    client = admin_client()

    day_18 = client.get(
        "/admin/reports/statistics", params={"from": "2026-11-18", "to": "2026-11-18"}
    )
    assert day_18.status_code == 200
    report = day_18.json()
    assert report["period"] == {
        "from": "2026-11-18",
        "to": "2026-11-18",
        "timezone": "Europe/Moscow",
    }
    assert report["empty"] is False
    assert report["kpi"] == {
        "conversations": 2,
        "answered": 2,
        "closed": 2,
        "closed_percent": 100,
        "average_response_seconds": 270,
    }
    [row] = [item for item in report["managers"] if item["id"] == first]
    assert row["name"] == "Active Manager"
    assert row["conversations"] == 2
    assert row["closed"] == 2
    assert row["average_response_seconds"] == 270

    day_19 = client.get(
        "/admin/reports/statistics", params={"from": "2026-11-19", "to": "2026-11-19"}
    ).json()
    assert [
        item["id"]
        for item in day_19["managers"]
        if item["id"] is not None and item["conversations"]
    ] == [second]
    assert [item["name"] for item in day_19["managers"] if item["id"] is None] == ["Без ответа"]
    assert day_19["kpi"]["conversations"] == 2
    assert day_19["kpi"]["answered"] == 1
    assert day_19["kpi"]["closed"] == 1
    assert day_19["kpi"]["average_response_seconds"] == 180

    empty = client.get(
        "/admin/reports/statistics", params={"from": "2026-11-01", "to": "2026-11-02"}
    ).json()
    assert empty["empty"] is True
    assert empty["kpi"]["conversations"] == 0
    assert empty["managers"] == []

    filtered = client.get(
        "/admin/reports/statistics",
        params={"from": "2026-11-18", "to": "2026-11-18", "manager_id": second},
    ).json()
    assert filtered["empty"] is True
    assert filtered["managers"] == []

    invalid = client.get(
        "/admin/reports/statistics", params={"from": "2026-11-19", "to": "2026-11-18"}
    )
    assert invalid.status_code == 422
    assert invalid.json()["field"] == "from"

    manager = TestClient(app, base_url=BASE_URL)
    assert login_manager(manager, "first@example.com", "correct1").status_code == 200
    assert manager.get("/admin/reports/statistics").status_code == 403
