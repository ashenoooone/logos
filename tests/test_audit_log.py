"""Журнал действий (#18): доступ, фильтры, умолчание 7 дней, CSV, неизменяемость."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from support import (
    BASE_URL,
    add_active_manager,
    add_administrator,
    csrf_headers,
    login_administrator,
    login_manager,
    migrate,
)

from logos_backend import clock
from logos_backend.app import app
from logos_backend.db import audit_events, database_url


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()


def add_event(seconds_ago: int, actor_name: str, action: str = "logout") -> None:
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(audit_events).values(
                    occurred_at=clock.now_seconds() - seconds_ago,
                    actor_kind="manager",
                    actor_id=7,
                    actor_name=actor_name,
                    action=action,
                    description=f"Событие: {action}",
                    ip="10.0.0.1",
                )
            )
    finally:
        engine.dispose()


def admin_client() -> TestClient:
    add_administrator()
    client = TestClient(app, base_url=BASE_URL)
    assert login_administrator(client).status_code == 200
    return client


def test_journal_is_admin_only_and_login_is_logged(database: None) -> None:
    add_active_manager("active@example.com")
    manager = TestClient(app, base_url=BASE_URL)
    assert login_manager(manager, "active@example.com").status_code == 200
    assert manager.get("/admin/audit-log").status_code == 403
    assert TestClient(app, base_url=BASE_URL).get("/admin/audit-log").status_code == 401

    admin = admin_client()
    page = admin.get("/admin/audit-log").json()
    actions = [(event["action"], event["actor"]) for event in page["events"]]
    assert actions == [
        ("login", {"kind": "administrator", "id": 1, "name": "root"}),
        ("login", {"kind": "manager", "id": 1, "name": "Active Manager"}),
    ]
    assert page["events"][0]["ip"] == "testclient"
    # Журнал только для чтения: маршрутов изменения и удаления нет.
    assert admin.put("/admin/audit-log").status_code == 405
    assert admin.delete("/admin/audit-log").status_code == 405


def test_filters_default_period_and_retention(database: None) -> None:
    add_event(8 * 24 * 60 * 60, "Старое Имя")
    add_event(400 * 24 * 60 * 60, "Забытое Имя")
    admin = admin_client()

    page = admin.get("/admin/audit-log").json()
    assert page["total"] == 1
    assert page["events"][0]["action"] == "login"

    filtered = admin.get("/admin/audit-log", params={"actor": "manager:7"}).json()
    assert filtered["total"] == 1
    # Снимок имени на момент события сохраняется.
    assert filtered["events"][0]["actor"]["name"] == "Старое Имя"

    by_action = admin.get("/admin/audit-log", params={"action": "logout"}).json()
    assert [event["action"] for event in by_action["events"]] == ["logout"]
    # Запись старше 12 месяцев удаляется при чтении.
    assert by_action["total"] == 1

    day = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    by_week = admin.get("/admin/audit-log", params={"from": day, "to": day}).json()
    assert by_week["total"] >= 1
    assert admin.get("/admin/audit-log", params={"action": "unknown"}).status_code == 422


def test_csv_export_logs_the_export(database: None) -> None:
    admin = admin_client()
    response = admin.post(
        "/admin/audit-log/export",
        json={"actor": None, "action": None, "from": None, "to": None},
        headers=csrf_headers(admin),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Сотрудник" in response.text
    assert "root" in response.text

    events = admin.get("/admin/audit-log").json()["events"]
    assert events[0]["action"] == "export"

    add_active_manager("active@example.com")
    manager = TestClient(app, base_url=BASE_URL)
    assert login_manager(manager, "active@example.com").status_code == 200
    response = manager.post(
        "/admin/audit-log/export", json={}, headers=csrf_headers(manager)
    )
    assert response.status_code == 403
