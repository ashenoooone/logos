"""Заметки о клиентах: порядок, видимость, права правки и защита от устаревшей версии."""

from __future__ import annotations

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


def test_notes_visibility_permissions_and_conflict(database: None) -> None:
    first, second = manager("a@example.com"), manager("b@example.com")

    created = first.post(
        "/conversations/1/notes",
        json={"text": " Первая заметка "},
        headers=csrf_headers(first),
    )
    assert created.status_code == 201
    [note] = created.json()["notes"]
    assert note["text"] == "Первая заметка"
    assert note["visibility"] == "team"
    assert note["author"] == "Active Manager"
    assert note["own"] is True and note["editable"] is True
    assert note["version"] == 1

    second_note = first.post(
        "/conversations/1/notes", json={"text": "Вторая"}, headers=csrf_headers(first)
    ).json()["notes"][0]
    assert second_note["text"] == "Вторая"  # новые сверху

    # Чужую заметку видно, но менять и удалять нельзя.
    visible = second.get("/conversations/1/notes").json()["notes"]
    assert [item["text"] for item in visible] == ["Вторая", "Первая заметка"]
    assert visible[0]["editable"] is False
    assert (
        second.put(
            f"/conversations/1/notes/{note['id']}",
            json={"text": "Чужая правка", "visibility": "team", "version": 1},
            headers=csrf_headers(second),
        ).status_code
        == 403
    )
    assert (
        second.delete(
            f"/conversations/1/notes/{note['id']}", headers=csrf_headers(second)
        ).status_code
        == 403
    )

    # Приватная заметка не видна другому менеджеру.
    assert (
        first.post(
            "/conversations/1/notes",
            json={"text": "Только моё", "visibility": "private"},
            headers=csrf_headers(first),
        ).status_code
        == 201
    )
    assert [item["text"] for item in second.get("/conversations/1/notes").json()["notes"]] == [
        "Вторая",
        "Первая заметка",
    ]

    # Устаревшая версия не перезаписывает чужую правку: возвращается актуальная.
    updated = first.put(
        f"/conversations/1/notes/{note['id']}",
        json={"text": "Первая, правка", "visibility": "team", "version": 1},
        headers=csrf_headers(first),
    )
    assert updated.status_code == 200
    assert updated.json()["notes"][-1]["version"] == 2
    conflict = first.put(
        f"/conversations/1/notes/{note['id']}",
        json={"text": "Устаревшая правка", "visibility": "team", "version": 1},
        headers=csrf_headers(first),
    )
    assert conflict.status_code == 409
    assert conflict.json()["note"]["version"] == 2
    assert conflict.json()["note"]["text"] == "Первая, правка"

    # Пустой текст не создаёт заметку.
    blank = first.post(
        "/conversations/1/notes", json={"text": "   "}, headers=csrf_headers(first)
    )
    assert blank.status_code == 422

    # Администратор видит приватные и правит любую заметку.
    admin = TestClient(app, base_url=BASE_URL)
    add_administrator()
    assert login_administrator(admin).status_code == 200
    admin_notes = admin.get("/conversations/1/notes").json()["notes"]
    assert len(admin_notes) == 3
    assert (
        admin.put(
            f"/conversations/1/notes/{note['id']}",
            json={"text": "Правка администратора", "visibility": "team", "version": 2},
            headers=csrf_headers(admin),
        ).status_code
        == 200
    )
