"""Поведенческие тесты B2: приглашения, SMTP-ошибки и установка пароля."""

from __future__ import annotations

import smtplib
import threading
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from logos_backend import clock, mail, security
from logos_backend.app import app
from logos_backend.db import (
    create_first_admin,
    database_url,
    managers,
    one_time_links,
    sessions,
)
from logos_backend.invitations import INVITATION_TTL_SECONDS
from logos_backend.web_auth import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://testserver"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_700_000_000

    def now_seconds(self) -> int:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += seconds


class Mailbox:
    """Заменяет только сетевую отправку, сохраняя состояние ссылок в БД."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = False

    def send(self, recipient: str, name: str, token: str) -> None:
        if self.fail:
            raise mail.MailDeliveryError("SMTP is unavailable")
        self.sent.append((recipient, name, token))

    @property
    def last_token(self) -> str:
        return self.sent[-1][2]


def alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    return config


def migrate(target: str = "head") -> None:
    command.upgrade(alembic_config(), target)


@pytest.fixture()
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "logos.sqlite3"
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(path))
    migrate()
    return path


@pytest.fixture()
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(clock, "now_seconds", fake.now_seconds)
    return fake


@pytest.fixture()
def mailbox(monkeypatch: pytest.MonkeyPatch) -> Mailbox:
    box = Mailbox()
    monkeypatch.setattr(mail, "send_invitation", box.send)
    return box


@pytest.fixture()
def client(database: Path) -> TestClient:
    return TestClient(app, base_url=BASE_URL)


def bootstrap_csrf(client: TestClient) -> str:
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE_NAME)
    if token is None:
        token = bootstrap_csrf(client)
    return {CSRF_HEADER_NAME: token, "Origin": BASE_URL}


def add_administrator(login: str = "root", password: str = "correct1") -> None:
    create_first_admin(login=login, password_hash=security.hash_password(password))


def login_administrator(client: TestClient) -> None:
    response = client.post(
        "/auth/admin/login",
        json={"login": "root", "password": "correct1", "remember": False},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200


def login_manager(client: TestClient, email: str, password: str) -> Any:
    from support import login_manager as authenticate_manager

    return authenticate_manager(client, email, password)


def add_active_manager(email: str = "active@example.com", password: str = "correct1") -> None:
    """Готовит активного менеджера напрямую в БД, минуя продуктовый сценарий."""
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(managers).values(
                    name="Active Manager",
                    email=email.strip(),
                    email_normalized=security.normalize_email(email),
                    password_hash=security.hash_password(password),
                    created_at=clock.now_seconds(),
                )
            )
    finally:
        engine.dispose()


def create_manager(
    client: TestClient,
    name: str = "Иван Петров",
    email: str = "ivan@example.com",
    **extra: object,
) -> Any:
    return client.post(
        "/admin/managers",
        json={"name": name, "email": email, **extra},
        headers=csrf_headers(client),
    )


def reissue(client: TestClient, manager_id: int, email: str | None = None) -> Any:
    return client.post(
        f"/admin/managers/{manager_id}/invitation",
        json={"email": email},
        headers=csrf_headers(client),
    )


def accept(
    client: TestClient,
    token: str,
    password: str = "correct1",
    confirmation: str | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    return client.post(
        "/invitations/accept",
        json={
            "token": token,
            "password": password,
            "password_confirmation": password if confirmation is None else confirmation,
        },
        headers=csrf_headers(client) if headers is None else headers,
    )


def preview(
    client: TestClient,
    token: str,
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    return client.post(
        "/invitations/preview",
        json={"token": token},
        headers=csrf_headers(client) if headers is None else headers,
    )


def manager_count() -> int:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return len(connection.execute(select(managers.c.id)).all())
    finally:
        engine.dispose()


def manager_session_count(manager_id: int) -> int:
    """Считает сессии конкретного менеджера, не смешивая их с сессией администратора."""
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return len(
                connection.execute(
                    select(sessions.c.id).where(sessions.c.manager_id == manager_id)
                ).all()
            )
    finally:
        engine.dispose()


def manager_row(manager_id: int) -> Any:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return (
                connection.execute(select(managers).where(managers.c.id == manager_id))
                .mappings()
                .one()
            )
    finally:
        engine.dispose()


def link_rows(manager_id: int) -> list[Any]:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return list(
                connection.execute(
                    select(one_time_links)
                    .where(one_time_links.c.manager_id == manager_id)
                    .order_by(one_time_links.c.id)
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()


def test_administrator_lists_and_creates_managers_but_manager_cannot(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    add_active_manager("existing@example.com")

    assert client.get("/admin/managers").status_code == 401

    manager_client = TestClient(app, base_url=BASE_URL)
    assert login_manager(manager_client, "existing@example.com", "correct1").status_code == 200
    assert manager_client.get("/admin/managers").status_code == 403
    forbidden = create_manager(manager_client, email="new@example.com")
    assert forbidden.status_code == 403
    assert manager_count() == 1

    login_administrator(client)
    listing = client.get("/admin/managers")
    assert listing.status_code == 200
    managers_payload = listing.json()["managers"]
    assert [item["email"] for item in managers_payload] == ["existing@example.com"]
    assert managers_payload[0]["role"] == "manager"
    assert managers_payload[0]["status"] == "active"

    created = create_manager(client, email="New@Example.com", role="administrator")
    assert created.status_code == 201
    body = created.json()
    assert body["manager"]["email"] == "New@Example.com"
    assert body["manager"]["role"] == "manager"
    assert body["manager"]["status"] == "pending"
    assert body["delivery"] == {"status": "sent"}
    assert mailbox.sent[0][0] == "New@Example.com"
    assert mailbox.last_token not in created.text
    assert mailbox.last_token not in client.get("/admin/managers").text
    assert manager_count() == 2


def test_invalid_or_taken_email_does_not_create_manager(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    login_administrator(client)

    invalid = create_manager(client, email="not-an-email")
    assert invalid.status_code == 422
    assert invalid.json()["field"] == "email"
    assert manager_count() == 0

    blank_name = create_manager(client, name="   ", email="valid@example.com")
    assert blank_name.status_code == 422
    assert blank_name.json()["field"] == "name"
    assert manager_count() == 0

    first = create_manager(client, email="User@Example.com")
    assert first.status_code == 201

    duplicate = create_manager(client, name="Другой", email="user@example.COM")
    assert duplicate.status_code == 422
    assert duplicate.json()["field"] == "email"
    assert manager_count() == 1
    assert len(mailbox.sent) == 1

    add_active_manager("taken@example.com")
    taken = create_manager(client, email="Taken@Example.com")
    assert taken.status_code == 422
    assert taken.json()["field"] == "email"
    assert manager_count() == 2


def test_pending_invitation_can_be_corrected_and_old_link_is_revoked(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    login_administrator(client)
    assert create_manager(client, email="Old@Example.com").status_code == 201
    manager_id = int(client.get("/admin/managers").json()["managers"][0]["id"])
    old_token = mailbox.last_token

    corrected = reissue(client, manager_id, "Corrected@Example.com")
    assert corrected.status_code == 200
    assert corrected.json()["manager"]["id"] == manager_id
    assert corrected.json()["manager"]["email"] == "Corrected@Example.com"
    assert corrected.json()["delivery"] == {"status": "sent"}
    assert mailbox.sent[-1][0] == "Corrected@Example.com"
    new_token = mailbox.last_token

    assert manager_count() == 1
    assert preview(client, old_token).status_code == 410
    invitation_client = TestClient(app, base_url=BASE_URL)
    assert accept(invitation_client, old_token).status_code == 410

    active_preview = preview(client, new_token)
    assert active_preview.status_code == 200
    assert active_preview.json()["email"] == "Corrected@Example.com"

    rows = link_rows(manager_id)
    assert len(rows) == 2
    assert rows[0]["revoked_at"] is not None
    assert rows[1]["revoked_at"] is None
    assert all(row["token_hash"] != new_token for row in rows)

    other = create_manager(client, name="Другой", email="other@example.com")
    assert other.status_code == 201
    other_id = int(other.json()["manager"]["id"])
    conflict = reissue(client, manager_id, "OTHER@example.com")
    assert conflict.status_code == 422
    assert conflict.json()["field"] == "email"
    assert manager_row(manager_id)["email"] == "Corrected@Example.com"
    assert manager_row(other_id)["email"] == "other@example.com"
    assert preview(client, new_token).status_code == 200


def test_active_manager_cannot_be_reissued_and_expired_invitation_can(
    client: TestClient,
    database: Path,
    mailbox: Mailbox,
    fake_clock: FakeClock,
) -> None:
    add_administrator()
    login_administrator(client)
    assert create_manager(client, email="pending@example.com").status_code == 201
    manager_id = int(client.get("/admin/managers").json()["managers"][0]["id"])
    first_token = mailbox.last_token

    fake_clock.advance(INVITATION_TTL_SECONDS)
    assert preview(client, first_token).status_code == 410

    after_expiry = reissue(client, manager_id)
    assert after_expiry.status_code == 200
    assert after_expiry.json()["manager"]["id"] == manager_id
    second_token = mailbox.last_token
    assert second_token != first_token
    assert preview(client, second_token).status_code == 200

    manager_client = TestClient(app, base_url=BASE_URL)
    assert accept(manager_client, second_token).status_code == 200
    assert manager_row(manager_id)["password_hash"] is not None

    refused = reissue(client, manager_id)
    assert refused.status_code == 409
    assert manager_count() == 1


def test_smtp_failure_keeps_pending_manager_and_retry_uses_same_record(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    login_administrator(client)

    mailbox.fail = True
    failed = create_manager(client, email="retry@example.com")
    assert failed.status_code == 502
    body = failed.json()
    assert body["detail"] == "Invitation email could not be delivered"
    assert body["delivery"] == {"status": "failed"}
    manager_id = int(body["manager"]["id"])
    assert body["manager"]["status"] == "pending"
    assert manager_count() == 1
    assert manager_row(manager_id)["password_hash"] is None
    listing = client.get("/admin/managers").json()["managers"]
    assert [item["id"] for item in listing] == [manager_id]

    mailbox.fail = False
    retried = reissue(client, manager_id)
    assert retried.status_code == 200
    assert retried.json()["manager"]["id"] == manager_id
    assert retried.json()["delivery"] == {"status": "sent"}
    assert manager_count() == 1
    assert mailbox.sent[-1][0] == "retry@example.com"

    manager_client = TestClient(app, base_url=BASE_URL)
    assert accept(manager_client, mailbox.last_token).status_code == 200
    assert manager_session_count(manager_id) == 1
    assert client.get("/auth/me").status_code == 200


def test_invitation_expiry_boundary_is_exactly_seventy_two_hours(
    client: TestClient,
    database: Path,
    mailbox: Mailbox,
    fake_clock: FakeClock,
) -> None:
    add_administrator()
    login_administrator(client)
    created_at = fake_clock.now
    assert create_manager(client, email="boundary@example.com").status_code == 201
    manager_id = int(client.get("/admin/managers").json()["managers"][0]["id"])
    token = mailbox.last_token
    assert link_rows(manager_id)[0]["expires_at"] == created_at + INVITATION_TTL_SECONDS

    fake_clock.advance(INVITATION_TTL_SECONDS - 1)
    assert preview(client, token).status_code == 200

    fake_clock.advance(1)
    assert preview(client, token).status_code == 410
    stale_accept = accept(TestClient(app, base_url=BASE_URL), token)
    assert stale_accept.status_code == 410
    assert manager_row(manager_id)["password_hash"] is None
    assert manager_session_count(manager_id) == 0
    assert client.get("/auth/me").status_code == 200


def test_invitation_cannot_be_reused(client: TestClient, database: Path, mailbox: Mailbox) -> None:
    add_administrator()
    login_administrator(client)
    assert create_manager(client, email="once@example.com").status_code == 201
    manager_id = int(client.get("/admin/managers").json()["managers"][0]["id"])
    token = mailbox.last_token

    first = TestClient(app, base_url=BASE_URL)
    accepted = accept(first, token)
    assert accepted.status_code == 200
    assert accepted.json()["subject"]["email"] == "once@example.com"
    assert first.get("/auth/me").status_code == 200
    assert manager_session_count(manager_id) == 1
    assert client.get("/auth/me").status_code == 200

    second = TestClient(app, base_url=BASE_URL)
    reused = accept(second, token)
    assert reused.status_code == 410
    assert reused.json() == {"detail": "Invitation is no longer valid"}
    assert second.get("/auth/me").status_code == 401
    assert manager_session_count(manager_id) == 1
    assert client.get("/auth/me").status_code == 200


def test_concurrent_acceptance_activates_at_most_once(
    database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    admin_client = TestClient(app, base_url=BASE_URL)
    login_administrator(admin_client)
    assert create_manager(admin_client, email="race@example.com").status_code == 201
    manager_id = int(admin_client.get("/admin/managers").json()["managers"][0]["id"])
    token = mailbox.last_token

    clients = [TestClient(app, base_url=BASE_URL) for _ in range(2)]
    headers = [csrf_headers(prepared) for prepared in clients]
    barrier = threading.Barrier(2)
    outcomes: list[int] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def attempt(index: int) -> None:
        barrier.wait()
        try:
            response = accept(clients[index], token, headers=headers[index])
        except BaseException as exc:  # pragma: no cover - диагностика неожиданного сбоя
            with lock:
                errors.append(exc)
            return
        with lock:
            outcomes.append(response.status_code)

    threads = [threading.Thread(target=attempt, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert sorted(outcomes) == [200, 410]
    assert manager_session_count(manager_id) == 1


def test_password_errors_do_not_consume_invitation(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    login_administrator(client)
    assert create_manager(client, email="policy@example.com").status_code == 201
    manager_id = int(client.get("/admin/managers").json()["managers"][0]["id"])
    token = mailbox.last_token

    invitation_client = TestClient(app, base_url=BASE_URL)
    mismatched = accept(invitation_client, token, "correct1", "different1")
    assert mismatched.status_code == 422
    assert mismatched.json()["field"] == "password"
    weak = accept(invitation_client, token, "abcdefgh")
    assert weak.status_code == 422
    short = accept(invitation_client, token, "abc1")
    assert short.status_code == 422

    assert invitation_client.cookies.get(SESSION_COOKIE_NAME) is None
    assert manager_row(manager_id)["password_hash"] is None
    assert manager_session_count(manager_id) == 0
    assert preview(client, token).status_code == 200

    accepted = accept(invitation_client, token, "пароль123")
    assert accepted.status_code == 200
    assert accepted.json()["subject"] == {
        "type": "manager",
        "id": manager_id,
        "name": "Иван Петров",
        "email": "policy@example.com",
    }
    assert accepted.cookies.get(SESSION_COOKIE_NAME) is not None
    assert invitation_client.get("/auth/me").status_code == 200
    assert manager_row(manager_id)["password_hash"].startswith("$argon2id$")

    listing = client.get("/admin/managers").json()["managers"]
    assert listing[0]["status"] == "active"

    logout = invitation_client.post("/auth/logout", headers=csrf_headers(invitation_client))
    assert logout.status_code == 204
    assert invitation_client.get("/auth/me").status_code == 401

    later = TestClient(app, base_url=BASE_URL)
    assert login_manager(later, "POLICY@example.com", "пароль123").status_code == 200


def test_accept_requires_csrf_and_keeps_link_usable(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    login_administrator(client)
    assert create_manager(client, email="csrf@example.com").status_code == 201
    manager_id = int(client.get("/admin/managers").json()["managers"][0]["id"])
    token = mailbox.last_token

    invitation_client = TestClient(app, base_url=BASE_URL)
    bootstrap_csrf(invitation_client)
    missing_preview = invitation_client.post(
        "/invitations/preview",
        json={"token": token},
        headers={"Origin": BASE_URL},
    )
    assert missing_preview.status_code == 403
    missing = invitation_client.post(
        "/invitations/accept",
        json={
            "token": token,
            "password": "correct1",
            "password_confirmation": "correct1",
        },
        headers={"Origin": BASE_URL},
    )
    assert missing.status_code == 403
    assert manager_session_count(manager_id) == 0
    assert preview(client, token).status_code == 200

    assert accept(invitation_client, token).status_code == 200


def test_reissue_email_change_survives_smtp_failure_and_retry(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    login_administrator(client)
    assert create_manager(client, email="old@example.com").status_code == 201
    manager_id = int(client.get("/admin/managers").json()["managers"][0]["id"])
    old_token = mailbox.last_token

    mailbox.fail = True
    failed = reissue(client, manager_id, "new@example.com")
    assert failed.status_code == 502
    body = failed.json()
    assert body["manager"]["id"] == manager_id
    assert body["manager"]["email"] == "new@example.com"
    assert body["manager"]["status"] == "pending"
    assert body["delivery"] == {"status": "failed"}
    assert manager_row(manager_id)["email"] == "new@example.com"
    assert manager_row(manager_id)["password_hash"] is None
    assert manager_count() == 1

    assert preview(client, old_token).status_code == 410
    assert accept(TestClient(app, base_url=BASE_URL), old_token).status_code == 410
    rows = link_rows(manager_id)
    assert [row["revoked_at"] is not None for row in rows] == [True, False]

    mailbox.fail = False
    retried = reissue(client, manager_id)
    assert retried.status_code == 200
    assert retried.json()["manager"]["email"] == "new@example.com"
    assert mailbox.sent[-1][0] == "new@example.com"
    rows = link_rows(manager_id)
    assert [row["revoked_at"] is None for row in rows] == [False, False, True]
    assert len(mailbox.sent) == 2

    manager_client = TestClient(app, base_url=BASE_URL)
    assert accept(manager_client, mailbox.last_token).status_code == 200
    assert manager_session_count(manager_id) == 1
    assert client.get("/auth/me").status_code == 200


def test_reissue_requires_administrator(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    login_administrator(client)
    assert create_manager(client, email="admin-only@example.com").status_code == 201
    manager_id = int(client.get("/admin/managers").json()["managers"][0]["id"])
    token = mailbox.last_token

    anonymous = TestClient(app, base_url=BASE_URL)
    anonymous_response = anonymous.post(
        f"/admin/managers/{manager_id}/invitation",
        json={"email": "anonymous@example.com"},
        headers=csrf_headers(anonymous),
    )
    assert anonymous_response.status_code == 401

    add_active_manager("active-reissue@example.com")
    manager_client = TestClient(app, base_url=BASE_URL)
    login = login_manager(manager_client, "active-reissue@example.com", "correct1")
    assert login.status_code == 200
    manager_response = manager_client.post(
        f"/admin/managers/{manager_id}/invitation",
        json={"email": "manager@example.com"},
        headers=csrf_headers(manager_client),
    )
    assert manager_response.status_code == 403

    assert manager_row(manager_id)["email"] == "admin-only@example.com"
    assert preview(client, token).status_code == 200
    assert len(link_rows(manager_id)) == 1


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("LOGOS_SMTP_PORT", "abc"),
        ("LOGOS_SMTP_TIMEOUT", "abc"),
    ],
)
def test_smtp_configuration_error_keeps_pending_and_retry_succeeds(
    client: TestClient,
    database: Path,
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
) -> None:
    sent: list[Any] = []

    class FakeSmtp:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def ehlo(self) -> None:
            pass

        def send_message(self, message: Any) -> None:
            sent.append(message)

        def quit(self) -> None:
            pass

    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    add_administrator()
    login_administrator(client)
    monkeypatch.setenv(variable, value)

    failed = create_manager(client, email="config@example.com")
    assert failed.status_code == 502
    body = failed.json()
    assert body["delivery"] == {"status": "failed"}
    assert body["manager"]["status"] == "pending"
    manager_id = int(body["manager"]["id"])
    assert manager_row(manager_id)["password_hash"] is None
    assert manager_count() == 1
    assert sent == []

    monkeypatch.delenv(variable)
    retried = reissue(client, manager_id)
    assert retried.status_code == 200
    assert retried.json()["delivery"] == {"status": "sent"}
    assert len(sent) == 1
    assert sent[0]["To"] == "config@example.com"
    assert manager_count() == 1


def test_invitation_url_keeps_token_in_fragment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_PUBLIC_BASE_URL", "https://logos.example/")
    url = mail.invitation_url("tok/en+=")
    assert url == "https://logos.example/invitation#token=tok%2Fen%2B%3D"
    assert "/invitation/" not in url
    assert "?token" not in url


def test_validation_errors_are_field_scoped_and_do_not_echo_secrets(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_administrator()
    login_administrator(client)
    assert create_manager(client, email="validation@example.com").status_code == 201
    manager_id = int(client.get("/admin/managers").json()["managers"][0]["id"])
    token = mailbox.last_token

    secret = "never-echo-this-password-" + "a" * 1100
    oversized = accept(client, token, secret)
    assert oversized.status_code == 422
    assert oversized.json()["field"] == "password"
    assert secret not in oversized.text

    missing = client.post(
        "/invitations/accept",
        json={"token": token, "password_confirmation": "correct1"},
        headers=csrf_headers(client),
    )
    assert missing.status_code == 422
    assert missing.json()["field"] == "password"

    token_secret = "never-echo-this-token"
    malformed = client.post(
        "/invitations/preview",
        json={"token": {"raw": token_secret}},
        headers=csrf_headers(client),
    )
    assert malformed.status_code == 422
    assert malformed.json()["field"] == "token"
    assert token_secret not in malformed.text
    assert "input" not in malformed.json()

    assert manager_row(manager_id)["password_hash"] is None
    assert manager_session_count(manager_id) == 0
    assert preview(client, token).status_code == 200
