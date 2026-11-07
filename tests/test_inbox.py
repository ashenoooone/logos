"""«Входящие»: приём и дедуп, прочитанность, ответ, сбой и повтор, доступ."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support import (
    BASE_URL,
    add_active_manager,
    add_administrator,
    csrf_headers,
    login_administrator,
    login_manager,
    migrate,
)

from logos_backend import channels
from logos_backend.app import app

TOKEN = "123456:" + "A" * 35


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
