"""Теги: регистр не создаёт дубль, права удаления, удаление снимает тег с диалога."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from test_password_reset import (
    BASE_URL,
    add_active_manager,
    add_administrator,
    csrf_headers,
    login_administrator,
    login_manager,
    migrate,
)

from logos_backend.app import app
from logos_backend.db import conversations, database_url


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()
    engine = create_engine(database_url())
    with engine.begin() as connection:
        connection.execute(
            insert(conversations).values(
                id=1, chat_id=77, name="Игорь", created_at=1, last_message_at=1
            )
        )
    engine.dispose()


def manager(email: str) -> TestClient:
    add_active_manager(email, "correct1")
    client = TestClient(app, base_url=BASE_URL)
    assert login_manager(client, email, "correct1").status_code == 200
    return client


def test_tags_case_permissions_and_delete(database: None) -> None:
    first, second = manager("a@example.com"), manager("b@example.com")

    response = first.post(
        "/conversations/1/tags", json={"name": " Возврат "}, headers=csrf_headers(first)
    )
    [tag] = response.json()["tags"]
    assert tag["name"] == "Возврат"
    # Другой регистр — тот же тег, второй не создаётся.
    response = second.post(
        "/conversations/1/tags", json={"name": "возврат"}, headers=csrf_headers(second)
    )
    assert response.json()["tags"] == [tag]
    assert len(second.get("/tags").json()["tags"]) == 1
    assert second.get("/conversations").json()["conversations"][0]["tags"] == [tag]

    # Чужой тег менеджер не удаляет.
    assert second.delete(f"/tags/{tag['id']}", headers=csrf_headers(second)).status_code == 403

    admin = TestClient(app, base_url=BASE_URL)
    add_administrator()
    assert login_administrator(admin).status_code == 200
    assert (
        admin.post("/admin/tags", json={"name": "ВОЗВРАТ"}, headers=csrf_headers(admin)).status_code
        == 409
    )
    standard = admin.post("/admin/tags", json={"name": "Доставка"}, headers=csrf_headers(admin))
    standard_id = next(t["id"] for t in standard.json()["tags"] if t["standard"])
    assert first.delete(f"/tags/{standard_id}", headers=csrf_headers(first)).status_code == 403
    assert first.get("/admin/tags").status_code == 403

    # Свой тег автор удаляет — он снимается с диалога.
    assert first.delete(f"/tags/{tag['id']}", headers=csrf_headers(first)).status_code == 200
    assert first.get("/conversations/1/messages").json()["conversation"]["tags"] == []
