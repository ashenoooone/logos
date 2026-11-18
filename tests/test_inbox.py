"""«Входящие»: приём и дедуп, прочитанность, ответ, сбой и повтор, доступ."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
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

from logos_backend import channels, clock
from logos_backend.app import app
from logos_backend.db import _create_engine, conversations
from logos_backend.db import conversations, database_url, messages

TOKEN = "123456:" + "A" * 35
DAY = 24 * 60 * 60


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()


@pytest.fixture()
def bot_api(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Подменяет Bot API: ``state["updates"]`` — ответ getUpdates, ``fail`` — сбой отправки."""
    state: dict[str, Any] = {"updates": [], "fail": False, "sent": []}

    def fake_call(
        token: str, method: str, params: dict[str, Any], timeout: float, file: Any = None
    ) -> Any:
        if method == "getMe":
            return {"username": "logos_bot"}
        if method == "getUpdates":
            return state["updates"]
        if method in ("sendMessage", "sendDocument"):
            if state["fail"]:
                raise channels.TelegramUnavailableError
            state["sent"].append((method, params, file))
            return {"message_id": 900 + len(state["sent"])}
        return True

    monkeypatch.setattr(channels, "_call", fake_call)
    monkeypatch.setattr(channels, "download_file", lambda token, file_id, limit: b"jpeg")
    return state


def incoming(update_id: int, message_id: int, **extra: Any) -> dict[str, Any]:
    chat = {"id": 77, "type": "private", "first_name": "Мария", "last_name": "К."}
    return {
        "update_id": update_id,
        "message": {"message_id": message_id, "date": 1_700_000_000, "chat": chat, **extra},
    }


def test_receive_read_reply_and_retry(database: None, bot_api: dict[str, Any]) -> None:
    channels.connect(TOKEN, "")
    bot_api["updates"] = [
        incoming(1, 10, text="Где мой заказ?"),
        incoming(2, 11, photo=[{"file_id": "s"}, {"file_id": "big"}], caption="Вот"),
        incoming(3, 10, text="Где мой заказ?"),  # дубль по чату + message_id
        {"update_id": 4, "message": {"message_id": 1, "chat": {"id": -5, "type": "group"}}},
    ]
    channels.poll_once()

    add_active_manager("m@example.com", "correct1")
    client = TestClient(app, base_url=BASE_URL)
    assert login_manager(client, "m@example.com", "correct1").status_code == 200

    listing = client.get("/conversations").json()
    assert listing["unread_total"] == 2
    [conversation] = listing["conversations"]
    assert conversation["name"] == "Мария К."
    assert conversation["last_message"]["kind"] == "photo"
    assert conversation["last_message"]["author"] == "Мария К."
    historical_search = client.get("/conversations", params={"q": "ГДЕ МОЙ"})
    assert [item["id"] for item in historical_search.json()["conversations"]] == [
        conversation["id"]
    ]
    assert historical_search.json()["unread_total"] == 2

    thread = client.get(f"/conversations/{conversation['id']}/messages").json()
    photo = thread["messages"][1]
    assert photo["file"]["available"] is True
    attachment = client.get(f"/messages/{photo['id']}/attachment")
    assert attachment.content == b"jpeg"
    assert attachment.headers["content-type"] == "image/jpeg"

    headers = csrf_headers(client)
    assert client.post(f"/conversations/{conversation['id']}/read", headers=headers).is_success
    assert client.get("/conversations").json()["unread_total"] == 0

    sent = client.post(
        f"/conversations/{conversation['id']}/messages", json={"text": "Проверяю"}, headers=headers
    ).json()["message"]
    assert sent["status"] == "delivered"
    assert sent["author"] == "Active Manager"

    bot_api["fail"] = True
    failed = client.post(
        f"/conversations/{conversation['id']}/files?name=a.pdf&text=Накладная",
        content=b"%PDF",
        headers=headers,
    ).json()["message"]
    assert failed["status"] == "failed"
    assert failed["text"] == "Накладная"
    assert failed["author"] == "Active Manager"

    bot_api["fail"] = False
    retried = client.post(f"/messages/{failed['id']}/retry", headers=headers).json()["message"]
    assert retried["status"] == "delivered"
    assert retried["author"] == "Active Manager"
    assert bot_api["sent"][-1][2] == ("document", "a.pdf", b"%PDF")
    assert client.post(f"/messages/{failed['id']}/retry", headers=headers).status_code == 409


def test_administrator_has_no_inbox(database: None) -> None:
    add_administrator()
    client = TestClient(app, base_url=BASE_URL)
    assert login_administrator(client).status_code == 200
    assert client.get("/conversations").status_code == 403
    assert TestClient(app, base_url=BASE_URL).get("/conversations").status_code == 401


def test_pin_limit_and_cascade(database: None) -> None:
    """#12: лимит 5 на менеджера, снятие и удаление диалога освобождают место."""
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(conversations),
                [
                    {"id": number, "chat_id": number, "name": f"Клиент {number}",
                     "created_at": number, "last_message_at": number}
                    for number in range(1, 7)
                ],
            )
    finally:
        engine.dispose()
    add_active_manager("pins@example.com", "correct1")
    client = TestClient(app, base_url=BASE_URL)
    assert login_manager(client, "pins@example.com", "correct1").status_code == 200
    headers = csrf_headers(client)

    first = client.post("/conversations/1/pin", headers=headers)
    assert first.status_code == 200
    assert first.json()["pinned_at"]
    for number in range(2, 6):
        assert client.post(f"/conversations/{number}/pin", headers=headers).status_code == 200
    over_limit = client.post("/conversations/6/pin", headers=headers)
    assert over_limit.status_code == 409
    assert over_limit.json()["limit"] == 5

    pinned = [item for item in client.get("/conversations").json()["conversations"]
              if item["pinned_at"] is not None]
    assert len(pinned) == 5

    # Удаление диалога убирает закрепление без ошибки и освобождает место.
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(conversations.delete().where(conversations.c.id == 1))
    finally:
        engine.dispose()
    assert len([item for item in client.get("/conversations").json()["conversations"]
                if item["pinned_at"] is not None]) == 4
    assert client.post("/conversations/6/pin", headers=headers).status_code == 200

    assert client.delete("/conversations/6/pin", headers=headers).status_code == 200
    listing = client.get("/conversations").json()["conversations"]
    assert all(item["pinned_at"] is None for item in listing if item["id"] == 6)

def test_client_history_merges_channels_and_excludes_active(
    database: None,
) -> None:
    """#13: прошлые обращения одного клиента — общий таймлайн по каналам."""
    now = clock.now_seconds()
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            current = connection.execute(
                insert(conversations)
                .values(
                    chat_id=1,
                    name="Иван",
                    channel="telegram",
                    client_key="иван",
                    created_at=now - 10 * DAY,
                    last_message_at=now,
                )
                .returning(conversations.c.id)
            ).scalar_one()
            other = connection.execute(
                insert(conversations)
                .values(
                    chat_id=2,
                    name="Иван",
                    channel="email",
                    client_key="иван",
                    created_at=now - 3 * DAY,
                    last_message_at=now - 3 * DAY,
                )
                .returning(conversations.c.id)
            ).scalar_one()
            rows = [
                (current, "in", "Первый вопрос", now - 10 * DAY),
                (current, "out", "Ответ", now - 10 * DAY + 60),
                (other, "in", "Второй вопрос", now - 3 * DAY),
                (current, "in", "Текущий вопрос", now),
            ]
            for conversation_id, direction, text, at in rows:
                connection.execute(
                    insert(messages).values(
                        conversation_id=conversation_id,
                        direction=direction,
                        kind="text",
                        text=text,
                        created_at=at,
                    )
                )
    finally:
        engine.dispose()

    add_active_manager("history@example.com", "correct1")
    client = TestClient(app, base_url=BASE_URL)
    assert login_manager(client, "history@example.com", "correct1").status_code == 200

    history = client.get(f"/conversations/{current}/client-history").json()
    assert history["client"]["name"] == "Иван"
    assert [(item["topic"], item["channel"]) for item in history["appeals"]] == [
        ("Второй вопрос", "email"),
        ("Первый вопрос", "telegram"),
    ]
    assert {item["status"] for item in history["appeals"]} == {"closed"}
