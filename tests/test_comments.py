"""Внутренние комментарии (#15): тред команды и недоступное упоминание."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, insert
from support import BASE_URL, add_active_manager, csrf_headers, login_manager, migrate

from logos_backend import clock
from logos_backend.app import app
from logos_backend.db import conversations, database_url, managers


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()


def test_comment_is_internal_and_marks_missing_mention(database: None) -> None:
    add_active_manager("author@example.com", "correct1")
    colleague_id = add_active_manager("colleague@example.com", "correct1")
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                managers.update()
                .where(managers.c.email_normalized == "colleague@example.com")
                .values(name="Анна")
            )
            conversation_id = connection.execute(
                insert(conversations)
                .values(
                    chat_id=501,
                    name="Клиент",
                    created_at=clock.now_seconds(),
                    last_message_at=clock.now_seconds(),
                )
                .returning(conversations.c.id)
            ).scalar_one()
    finally:
        engine.dispose()

    client = TestClient(app, base_url=BASE_URL)
    assert login_manager(client, "author@example.com", "correct1").status_code == 200
    headers = csrf_headers(client)

    response = client.post(
        f"/conversations/{conversation_id}/comments",
        json={"text": "Анна, посмотри заказ @Анна"},
        headers=headers,
    )
    assert response.status_code == 200
    comment = response.json()["comment"]
    assert comment["author"] == "Active Manager"
    assert comment["mentions"] == [
        {"id": colleague_id, "name": "Анна", "available": True}
    ]
    # Клиенту ничего не уходит: переписка диалога пуста.
    assert client.get(f"/conversations/{conversation_id}/messages").json()["messages"] == []

    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(delete(managers).where(managers.c.id == colleague_id))
    finally:
        engine.dispose()

    thread = client.get(f"/conversations/{conversation_id}/comments").json()
    assert thread["comments"][0]["mentions"] == [
        {"id": colleague_id, "name": "Анна", "available": False}
    ]
    assert [item["name"] for item in thread["colleagues"]] == []
