"""Передача обращения (#16): комментарий, смена, «не в смене», возврат."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, update
from support import BASE_URL, add_active_manager, csrf_headers, login_manager, migrate

from logos_backend import clock
from logos_backend.app import app
from logos_backend.db import conversations, database_url, managers


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()


def seed_conversation() -> int:
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            return int(
                connection.execute(
                    insert(conversations)
                    .values(
                        chat_id=101,
                        name="Клиент",
                        created_at=clock.now_seconds(),
                        last_message_at=clock.now_seconds(),
                    )
                    .returning(conversations.c.id)
                ).scalar_one()
            )
    finally:
        engine.dispose()


def set_shift(manager_id: int, on_shift: bool) -> None:
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                update(managers)
                .where(managers.c.id == manager_id)
                .values(on_shift=int(on_shift))
            )
    finally:
        engine.dispose()


def test_transfer_requires_comment_blocks_off_shift_and_returns_to_owner(
    database: None,
) -> None:
    anna = add_active_manager("anna@example.com")
    igor = add_active_manager("igor@example.com")
    set_shift(igor, False)
    conversation_id = seed_conversation()

    client = TestClient(app, base_url=BASE_URL)
    assert login_manager(client, "anna@example.com").status_code == 200
    headers = csrf_headers(client)

    # Вне смены выбрать нельзя; пустой комментарий — ошибка поля.
    refused = client.post(
        f"/conversations/{conversation_id}/transfer",
        json={"to_manager_id": igor, "comment": "Передаю"},
        headers=headers,
    )
    assert refused.status_code == 422
    assert refused.json()["field"] == "to_manager_id"

    blank = client.post(
        f"/conversations/{conversation_id}/transfer",
        json={"to_manager_id": igor, "comment": "  "},
        headers=headers,
    )
    assert blank.status_code == 422
    assert blank.json()["field"] == "comment"

    set_shift(igor, True)
    sent = client.post(
        f"/conversations/{conversation_id}/transfer",
        json={"to_manager_id": igor, "comment": "Уточните доставку"},
        headers=headers,
    )
    assert sent.status_code == 200
    thread = client.get(f"/conversations/{conversation_id}/messages").json()
    assert thread["conversation"]["assignee"]["id"] == igor
    assert thread["conversation"]["transfer"]["status"] == "pending"
    assert thread["conversation"]["transfer"]["from"]["id"] == anna
    assert thread["conversation"]["transfer"]["comment"] == "Уточните доставку"
    assert [item["status"] for item in thread["transfers"]] == ["pending"]

    # Принять может только выбранный менеджер.
    assert (
        client.post(
            f"/conversations/{conversation_id}/transfer/accept", headers=headers
        ).status_code == 403
    )
    igor_client = TestClient(app, base_url=BASE_URL)
    assert login_manager(igor_client, "igor@example.com").status_code == 200
    igor_headers = csrf_headers(igor_client)
    assert (
        igor_client.post(
            f"/conversations/{conversation_id}/transfer/accept", headers=igor_headers
        ).status_code
        == 200
    )

    # Возврат отдаёт диалог прежнему владельцу с тем же комментарием.
    assert (
        igor_client.post(
            f"/conversations/{conversation_id}/transfer",
            json={"to_manager_id": anna, "comment": "Верните, пожалуйста"},
            headers=igor_headers,
        ).status_code
        == 200
    )
    returned = client.post(
        f"/conversations/{conversation_id}/transfer/return", headers=headers
    )
    assert returned.status_code == 200
    after = client.get(f"/conversations/{conversation_id}/messages").json()
    assert after["conversation"]["assignee"]["id"] == igor
    assert after["conversation"]["transfer"]["status"] == "returned"
    assert after["conversation"]["transfer"]["comment"] == "Верните, пожалуйста"
    assert [item["status"] for item in after["transfers"]] == ["accepted", "returned"]
