"""Shared fixtures and setup helpers for backend behavior tests."""

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from logos_backend import clock, mail, security
from logos_backend.db import (
    create_first_admin,
    database_url,
    manager_otp_requests,
    managers,
    one_time_links,
)
from logos_backend.web_auth import CSRF_COOKIE_NAME, CSRF_HEADER_NAME

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://testserver"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_700_000_000

    def now_seconds(self) -> int:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += seconds


def alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    return config


def migrate(target: str = "head") -> None:
    command.upgrade(alembic_config(), target)


def csrf_headers(test_client: TestClient) -> dict[str, str]:
    token = test_client.cookies.get(CSRF_COOKIE_NAME)
    if token is None:
        token = str(test_client.get("/auth/csrf").json()["csrf_token"])
    return {CSRF_HEADER_NAME: token, "Origin": BASE_URL}


def add_administrator(login: str = "root", password: str = "correct1") -> None:
    create_first_admin(login=login, password_hash=security.hash_password(password))


def login_administrator(test_client: TestClient) -> Any:
    return test_client.post(
        "/auth/admin/login", json={"login": "root", "password": "correct1", "remember": False},
        headers=csrf_headers(test_client),
    )


def add_manager(email: str, password: str | None, name: str = "Manager") -> int:
    password_hash = security.hash_password(password) if password is not None else None
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            manager_id = connection.execute(
                insert(managers).values(
                    name=name,
                    email=email.strip(),
                    email_normalized=security.normalize_email(email),
                    password_hash=password_hash,
                    created_at=clock.now_seconds(),
                ).returning(managers.c.id)
            ).scalar_one()
    finally:
        engine.dispose()
    return int(manager_id)


def add_active_manager(email: str = "active@example.com", password: str = "correct1") -> int:
    return add_manager(email, password, name="Active Manager")


def add_pending_manager(
    email: str = "pending@example.com", invitation_token: str = "invitation-token"
) -> int:
    manager_id = add_manager(email, None, name="Pending Manager")
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(insert(one_time_links).values(
                token_hash=security.token_digest(invitation_token), manager_id=manager_id,
                purpose="invitation", created_at=clock.now_seconds(),
                expires_at=clock.now_seconds() + 72 * 60 * 60,
            ))
    finally:
        engine.dispose()
    return manager_id


def login_manager(test_client: TestClient, email: str, _password: str = "") -> Any:
    engine = create_engine(database_url())
    try:
        normalized = security.normalize_email(email)
        with engine.begin() as connection:
            connection.execute(
                manager_otp_requests.delete().where(
                    manager_otp_requests.c.email_normalized == normalized
                )
            )
    finally:
        engine.dispose()
    captured_codes: list[str] = []
    original_send, original_check = mail.send_manager_otp, mail.check_delivery_available

    def capture_manager_otp(recipient: str, code: str) -> None:
        captured_codes.append(code)

    mail.send_manager_otp = capture_manager_otp
    mail.check_delivery_available = lambda: None
    try:
        headers = csrf_headers(test_client)
        requested = test_client.post(
            "/auth/manager/otp/request", json={"email": email}, headers=headers
        )
        assert requested.status_code == 202
        assert captured_codes
        return test_client.post(
            "/auth/manager/otp/verify",
            json={"email": email, "code": captured_codes[-1], "remember": False},
            headers=headers,
        )
    finally:
        mail.send_manager_otp, mail.check_delivery_available = original_send, original_check
