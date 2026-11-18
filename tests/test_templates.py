"""Шаблоны ответов: общие на компанию, менять и удалять можно только свои."""

from __future__ import annotations

from pathlib import Path

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

from logos_backend.app import app


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()


def manager(email: str) -> TestClient:
    add_active_manager(email, "correct1")
    client = TestClient(app, base_url=BASE_URL)
    assert login_manager(client, email, "correct1").status_code == 200
    return client


def test_templates_shared_and_owner_only(database: None) -> None:
    first, second = manager("a@example.com"), manager("b@example.com")

    response = first.post(
        "/templates",
        json={"name": " Доставка ", "text": "Здравствуйте, {клиент}!"},
        headers=csrf_headers(first),
    )
    assert response.status_code == 200
    [template] = response.json()["templates"]
    assert template["name"] == "Доставка"
    assert template["text"] == "Здравствуйте, {клиент}!"
    assert template["own"] is True

    shared = second.get("/templates").json()["templates"]
    assert [(item["name"], item["own"]) for item in shared] == [("Доставка", False)]

    assert second.patch(
        f"/templates/{template['id']}",
        json={"name": "Другое", "text": "Другой текст"},
        headers=csrf_headers(second),
    ).status_code == 403
    assert second.delete(
        f"/templates/{template['id']}", headers=csrf_headers(second)
    ).status_code == 403

    assert first.post(
        "/templates", json={"name": "   ", "text": "текст"}, headers=csrf_headers(first)
    ).status_code == 422
    assert first.post(
        "/templates", json={"name": "Имя", "text": "  "}, headers=csrf_headers(first)
    ).status_code == 422

    assert first.patch(
        f"/templates/{template['id']}",
        json={"name": "Возврат", "text": "Текст {номер}"},
        headers=csrf_headers(first),
    ).status_code == 200
    assert second.get("/templates").json()["templates"][0]["name"] == "Возврат"

    admin = TestClient(app, base_url=BASE_URL)
    add_administrator()
    assert login_administrator(admin).status_code == 200
    assert admin.get("/templates").status_code == 403

    assert first.delete(
        f"/templates/{template['id']}", headers=csrf_headers(first)
    ).status_code == 200
    assert second.get("/templates").json()["templates"] == []
