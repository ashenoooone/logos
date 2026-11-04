"""Профиль менеджера: подтверждение нового email и смена пароля."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_password_reset import (
    BASE_URL,
    FakeClock,
    add_active_manager,
    csrf_headers,
    login_manager,
    migrate,
)

from logos_backend import clock, mail
from logos_backend.app import app


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()


@pytest.fixture()
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(clock, "now_seconds", fake.now_seconds)
    return fake


@pytest.fixture()
def sent(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    box: list[tuple[str, str]] = []
    monkeypatch.setattr(mail, "send_email_change", lambda to, token: box.append((to, token)))
    return box


def new_client() -> TestClient:
    return TestClient(app, base_url=BASE_URL)


def test_new_email_works_only_after_confirmation(
    database: None, fake_clock: FakeClock, sent: list[tuple[str, str]]
) -> None:
    add_active_manager("old@example.com", "correct1")
    client = new_client()
    assert login_manager(client, "old@example.com", "correct1").status_code == 200

    response = client.post(
        "/account/email", json={"email": "New@example.com"}, headers=csrf_headers(client)
    )
    assert response.status_code == 202
    assert sent[-1][0] == "New@example.com"

    assert login_manager(new_client(), "new@example.com", "correct1").status_code == 401
    assert login_manager(new_client(), "old@example.com", "correct1").status_code == 200

    anonymous = new_client()
    confirm = anonymous.post(
        "/account/email/confirm", json={"token": sent[-1][1]}, headers=csrf_headers(anonymous)
    )
    assert confirm.status_code == 200
    assert login_manager(new_client(), "new@example.com", "correct1").status_code == 200
    assert login_manager(new_client(), "old@example.com", "correct1").status_code == 401

    reused = anonymous.post(
        "/account/email/confirm", json={"token": sent[-1][1]}, headers=csrf_headers(anonymous)
    )
    assert reused.status_code == 410


def test_email_link_expires_after_24_hours(
    database: None, fake_clock: FakeClock, sent: list[tuple[str, str]]
) -> None:
    add_active_manager("old@example.com", "correct1")
    client = new_client()
    login_manager(client, "old@example.com", "correct1")
    client.post("/account/email", json={"email": "new@example.com"}, headers=csrf_headers(client))

    fake_clock.advance(24 * 60 * 60)
    confirm = client.post(
        "/account/email/confirm", json={"token": sent[-1][1]}, headers=csrf_headers(client)
    )
    assert confirm.status_code == 410


def test_password_change_signs_out_other_devices_but_keeps_current(
    database: None, fake_clock: FakeClock
) -> None:
    add_active_manager("user@example.com", "correct1")
    current, other = new_client(), new_client()
    login_manager(current, "user@example.com", "correct1")
    login_manager(other, "user@example.com", "correct1")

    response = current.post(
        "/account/password",
        json={
            "current_password": "correct1",
            "new_password": "fresh-pass2",
            "new_password_confirmation": "fresh-pass2",
        },
        headers=csrf_headers(current),
    )
    assert response.status_code == 200
    assert current.get("/auth/me").status_code == 200
    assert other.get("/auth/me").status_code == 401
    assert login_manager(new_client(), "user@example.com", "fresh-pass2").status_code == 200
    assert login_manager(new_client(), "user@example.com", "correct1").status_code == 401


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"current_password": ""}, "current_password"),
        ({"current_password": "wrong999"}, "current_password"),
        ({"new_password_confirmation": "other-pass2"}, "new_password_confirmation"),
        ({"new_password": "short1", "new_password_confirmation": "short1"}, "new_password"),
    ],
)
def test_password_not_changed_on_invalid_input(
    database: None, fake_clock: FakeClock, body: dict[str, str], field: str
) -> None:
    add_active_manager("user@example.com", "correct1")
    client = new_client()
    login_manager(client, "user@example.com", "correct1")

    payload = {
        "current_password": "correct1",
        "new_password": "fresh-pass2",
        "new_password_confirmation": "fresh-pass2",
        **body,
    }
    response = client.post("/account/password", json=payload, headers=csrf_headers(client))
    assert response.status_code == 422
    assert response.json()["field"] == field
    assert login_manager(new_client(), "user@example.com", "correct1").status_code == 200
