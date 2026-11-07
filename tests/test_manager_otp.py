"""Критические сценарии одноразового входа менеджера."""

import secrets
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from support import BASE_URL, add_active_manager, add_manager, csrf_headers, migrate

from logos_backend import auth, mail
from logos_backend.app import app
from logos_backend.db import database_url, manager_otp_codes, manager_otp_requests


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()


@pytest.fixture()
def captured_code(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    codes: list[str] = []

    def capture(_recipient: str, code: str) -> None:
        codes.append(code)

    monkeypatch.setattr(mail, "check_delivery_available", lambda: None)
    monkeypatch.setattr(mail, "send_manager_otp", capture)
    return codes

 

def request(client: TestClient, email: str) -> Any:
    return client.post(
        "/auth/manager/otp/request", json={"email": email}, headers=csrf_headers(client)
    )


def verify(client: TestClient, email: str, code: str) -> Any:
    return client.post(
        "/auth/manager/otp/verify",
        json={"email": email, "code": code},
        headers=csrf_headers(client),
    )


def test_code_authenticates_once_and_pending_or_unknown_are_neutral(
    database: Path, captured_code: list[str]
) -> None:
    add_active_manager("User@example.com", "password1")
    add_manager("pending@example.com", None)
    client = TestClient(app, base_url=BASE_URL)

    assert request(client, "user@example.com").status_code == 202
    code = captured_code[-1]
    accepted = verify(client, " USER@example.COM ", code)
    assert accepted.status_code == 200
    assert accepted.json()["subject"]["type"] == "manager"
    assert verify(TestClient(app, base_url=BASE_URL), "user@example.com", code).status_code == 401

    pending_client = TestClient(app, base_url=BASE_URL)
    unknown_client = TestClient(app, base_url=BASE_URL)
    pending = request(pending_client, "pending@example.com")
    unknown = request(unknown_client, "absent@example.com")
    assert pending.status_code == unknown.status_code == 202
    assert pending.json() == unknown.json()
    assert len(captured_code) == 3
    assert verify(pending_client, "pending@example.com", captured_code[1]).status_code == 401
    assert verify(unknown_client, "absent@example.com", captured_code[2]).status_code == 401

def test_attempts_persist_and_resend_invalidates_previous_code(
    database: Path, captured_code: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    add_active_manager("user@example.com", "password1")
    client = TestClient(app, base_url=BASE_URL)
    digits = iter("111111222222333333")
    monkeypatch.setattr(secrets, "choice", lambda _alphabet: next(digits))
    assert request(client, "user@example.com").status_code == 202
    previous = captured_code[-1]
    assert request(client, "user@example.com").status_code == 429

    # Advance beyond cooldown while retaining deterministic time independent of process wall clock.
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            # The request throttle is keyed separately; set its timestamp at the schema layer.
            connection.execute(manager_otp_requests.update().values(requested_at=0))
    finally:
        engine.dispose()
    assert request(client, "user@example.com").status_code == 202
    replacement = captured_code[-1]
    assert replacement != previous
    assert verify(client, "user@example.com", previous).status_code == 401
    for _ in range(auth.OTP_MAX_ATTEMPTS):
        assert verify(client, "user@example.com", "000000").status_code == 401
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            attempts = connection.execute(select(manager_otp_codes.c.attempts)).scalar_one()
    finally:
        engine.dispose()
    assert attempts == auth.OTP_MAX_ATTEMPTS
    assert verify(client, "user@example.com", replacement).status_code == 401


def test_expired_code_and_smtp_outage_are_safe(
    database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_active_manager("expired@example.com", "password1")
    client = TestClient(app, base_url=BASE_URL)
    delivered: list[str] = []
    monkeypatch.setattr(mail, "check_delivery_available", lambda: None)
    monkeypatch.setattr(mail, "send_manager_otp", lambda _email, code: delivered.append(code))
    assert request(client, "expired@example.com").status_code == 202
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            stored = str(connection.execute(select(manager_otp_codes.c.code_hash)).scalar_one())
            created_at = int(
                connection.execute(select(manager_otp_codes.c.created_at)).scalar_one()
            )
            connection.execute(
                manager_otp_codes.update().values(
                    created_at=created_at - auth.OTP_TTL_SECONDS,
                    expires_at=created_at,
                )
            )
    finally:
        engine.dispose()
    assert delivered[0] not in stored
    assert verify(client, "expired@example.com", delivered[0]).status_code == 401

    def fail_sending(_email: str, _code: str) -> None:
        raise mail.MailDeliveryError()

    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(manager_otp_requests.update().values(requested_at=0))
    finally:
        engine.dispose()
    monkeypatch.setattr(mail, "send_manager_otp", fail_sending)
    failed = request(TestClient(app, base_url=BASE_URL), "expired@example.com")
    assert failed.status_code == 503
    assert failed.json() == {"detail": "Email delivery is temporarily unavailable"}
    assert delivered[0] not in failed.text
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            stored_request = connection.execute(
                select(manager_otp_requests.c.requested_at).where(
                    manager_otp_requests.c.email_normalized == "expired@example.com"
                )
            ).scalar_one()
            stored_code = connection.execute(
                select(manager_otp_codes.c.code_hash).where(
                    manager_otp_codes.c.manager_id == 1
                )
            ).scalar_one()
    finally:
        engine.dispose()
    assert stored_request > 0
    assert delivered[0] not in str(stored_code)

    monkeypatch.setattr(
        mail, "check_delivery_available",
        lambda: (_ for _ in ()).throw(mail.MailDeliveryError()),
    )
    outage = request(TestClient(app, base_url=BASE_URL), "unknown@example.com")
    assert outage.status_code == 503
    assert delivered[0] not in outage.text
