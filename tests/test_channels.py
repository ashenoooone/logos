"""Канал Telegram: подключение по токену, сбой опроса, отключение."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support import BASE_URL, add_administrator, csrf_headers, migrate

from logos_backend import channels
from logos_backend.app import app

TOKEN = "123456:" + "A" * 35


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()


@pytest.fixture()
def bot_api(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Подменяет Bot API: ``state["invalid"]`` — токены, которые API отклоняет."""
    state: dict[str, Any] = {"invalid": set(), "calls": []}

    def fake_call(token: str, method: str, params: dict[str, Any], timeout: float) -> Any:
        state["calls"].append(method)
        if not channels.TOKEN_PATTERN.fullmatch(token) or token in state["invalid"]:
            raise channels.InvalidTokenError
        if method == "getMe":
            return {"username": "logos_support_bot"}
        if method == "getUpdates":
            return [{"update_id": 41}]
        return True

    monkeypatch.setattr(channels, "_call", fake_call)
    return state


def admin_client() -> TestClient:
    add_administrator()
    client = TestClient(app, base_url=BASE_URL)
    response = client.post(
        "/auth/admin/login",
        json={"login": "root", "password": "correct1", "remember": False},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    return client


def test_connect_poll_failure_and_disconnect(database: None, bot_api: dict[str, Any]) -> None:
    client = admin_client()

    response = client.post(
        "/admin/channels/telegram",
        json={"token": TOKEN, "name": "Поддержка"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["channel"]["status"] == "connected"
    assert TOKEN not in response.text
    assert TOKEN not in client.get("/admin/channels").text

    assert channels.poll_once() is True
    bot_api["invalid"].add(TOKEN)
    assert channels.poll_once() is True
    channel = client.get("/admin/channels").json()["channel"]
    assert (channel["status"], channel["error"]) == ("error", "token_invalid")

    response = client.post("/admin/channels/telegram/disconnect", headers=csrf_headers(client))
    assert response.json()["channel"]["status"] == "disconnected"
    assert channels.poll_once() is False


def test_invalid_token_does_not_connect(database: None, bot_api: dict[str, Any]) -> None:
    client = admin_client()
    for token in ("not-a-token", "999:" + "B" * 35):
        bot_api["invalid"].add(token)
        response = client.post(
            "/admin/channels/telegram", json={"token": token}, headers=csrf_headers(client)
        )
        assert response.status_code == 422
        assert response.json()["field"] == "token"
    assert client.get("/admin/channels").json()["channel"]["status"] == "disconnected"


def test_channels_require_administrator(database: None) -> None:
    client = TestClient(app, base_url=BASE_URL)
    assert client.get("/admin/channels").status_code == 401
