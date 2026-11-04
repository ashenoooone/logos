"""Поведенческие тесты B3: восстановление пароля менеджера."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from logos_backend import auth, clock, mail, recovery, security
from logos_backend.app import app
from logos_backend.db import (
    create_first_admin,
    database_url,
    login_attempts,
    managers,
    one_time_links,
    password_reset_requests,
    sessions,
)
from logos_backend.web_auth import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
)
from logos_backend.web_auth import (
    router as auth_router,
)
from logos_backend.web_recovery import REQUEST_ACCEPTED_DETAIL, STALE_LINK_DETAIL
from logos_backend.web_recovery import router as recovery_router

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
    """Заменяет только сетевые SMTP-вызовы, не трогая БД и HTTP-слой."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.unavailable = False
        self.fail_send = False

    def check(self) -> None:
        if self.unavailable:
            raise mail.MailDeliveryError("SMTP is unavailable")

    def send(self, recipient: str, token: str) -> None:
        if self.fail_send:
            raise mail.MailDeliveryError("recipient is undeliverable")
        self.sent.append((recipient, token))

    @property
    def last_token(self) -> str:
        return self.sent[-1][1]


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
    monkeypatch.setattr(mail, "check_delivery_available", box.check)
    monkeypatch.setattr(mail, "send_password_reset", box.send)
    return box


@pytest.fixture()
def client(database: Path) -> TestClient:
    return TestClient(app, base_url=BASE_URL)


def bootstrap_csrf(test_client: TestClient) -> str:
    response = test_client.get("/auth/csrf")
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def csrf_headers(test_client: TestClient) -> dict[str, str]:
    token = test_client.cookies.get(CSRF_COOKIE_NAME)
    if token is None:
        token = bootstrap_csrf(test_client)
    return {CSRF_HEADER_NAME: token, "Origin": BASE_URL}


def add_administrator(login: str = "root", password: str = "correct1") -> None:
    create_first_admin(login=login, password_hash=security.hash_password(password))


def login_administrator(test_client: TestClient) -> Any:
    return test_client.post(
        "/auth/admin/login",
        json={"login": "root", "password": "correct1", "remember": False},
        headers=csrf_headers(test_client),
    )


def login_manager(test_client: TestClient, email: str, password: str) -> Any:
    return test_client.post(
        "/auth/manager/login",
        json={"email": email, "password": password, "remember": False},
        headers=csrf_headers(test_client),
    )


def add_manager(email: str, password: str | None, name: str = "Manager") -> int:
    """Пишет менеджера напрямую в БД, минуя продуктовые сценарии."""
    password_hash = security.hash_password(password) if password is not None else None
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            row = (
                connection.execute(
                    insert(managers)
                    .values(
                        name=name,
                        email=email.strip(),
                        email_normalized=security.normalize_email(email),
                        password_hash=password_hash,
                        created_at=clock.now_seconds(),
                    )
                    .returning(managers.c.id)
                )
                .scalar_one()
            )
    finally:
        engine.dispose()
    return int(row)


def add_active_manager(email: str = "active@example.com", password: str = "correct1") -> int:
    return add_manager(email, password, name="Active Manager")


def add_pending_manager(
    email: str = "pending@example.com",
    invitation_token: str = "invitation-token",
) -> int:
    manager_id = add_manager(email, None, name="Pending Manager")
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(one_time_links).values(
                    token_hash=security.token_digest(invitation_token),
                    manager_id=manager_id,
                    purpose="invitation",
                    created_at=clock.now_seconds(),
                    expires_at=clock.now_seconds() + 72 * 60 * 60,
                )
            )
    finally:
        engine.dispose()
    return manager_id


def request_reset(
    test_client: TestClient,
    email: str,
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    return test_client.post(
        "/password-reset/request",
        json={"email": email},
        headers=csrf_headers(test_client) if headers is None else headers,
    )


def preview_reset(
    test_client: TestClient,
    token: str,
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    return test_client.post(
        "/password-reset/preview",
        json={"token": token},
        headers=csrf_headers(test_client) if headers is None else headers,
    )


def complete_reset(
    test_client: TestClient,
    token: str,
    password: str = "newpass1",
    confirmation: str | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    return test_client.post(
        "/password-reset/complete",
        json={
            "token": token,
            "password": password,
            "password_confirmation": password if confirmation is None else confirmation,
        },
        headers=csrf_headers(test_client) if headers is None else headers,
    )


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


def manager_session_count(manager_id: int) -> int:
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


def reset_links(manager_id: int) -> list[Any]:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return list(
                connection.execute(
                    select(one_time_links)
                    .where(
                        one_time_links.c.manager_id == manager_id,
                        one_time_links.c.purpose == recovery.PASSWORD_RESET_PURPOSE,
                    )
                    .order_by(one_time_links.c.id)
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()


def attempt_state(email: str) -> Any:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return (
                connection.execute(
                    select(login_attempts).where(
                        login_attempts.c.scope == "manager",
                        login_attempts.c.identifier == security.normalize_email(email),
                    )
                )
                .mappings()
                .first()
            )
    finally:
        engine.dispose()


def test_request_is_neutral_for_unknown_active_and_pending(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_active_manager("Active@Example.com")
    pending_id = add_pending_manager("Pending@Example.com", invitation_token="pending-invite")

    active = request_reset(client, "active@example.com")
    unknown = request_reset(client, "nobody@example.com")
    pending = request_reset(client, "PENDING@example.com")

    for response in (active, unknown, pending):
        assert response.status_code == 202
        assert response.json() == {"detail": REQUEST_ACCEPTED_DETAIL}
        assert "token" not in response.json()

    assert reset_links(pending_id) == []
    assert manager_row(pending_id)["password_hash"] is None
    invitation = client.post(
        "/invitations/preview",
        json={"token": "pending-invite"},
        headers=csrf_headers(client),
    )
    assert invitation.status_code == 200
    assert invitation.json()["email"] == "Pending@Example.com"
    pending_login = login_manager(
        TestClient(app, base_url=BASE_URL),
        "pending@example.com",
        "correct1",
    )
    assert pending_login.status_code == 401
    assert [recipient for recipient, _ in mailbox.sent] == ["Active@Example.com"]
    assert mailbox.last_token not in active.text


def test_cooldown_is_identical_and_boundary_is_exactly_sixty_seconds(
    client: TestClient,
    database: Path,
    mailbox: Mailbox,
    fake_clock: FakeClock,
) -> None:
    manager_id = add_active_manager("active@example.com")
    started_at = fake_clock.now

    assert request_reset(client, "active@example.com").status_code == 202
    first_token = mailbox.last_token

    fake_clock.advance(59)
    cooling = request_reset(client, "active@example.com")
    assert cooling.status_code == 429
    assert cooling.json()["retry_after_seconds"] == 1
    assert cooling.headers["Retry-After"] == "1"
    assert len(mailbox.sent) == 1

    fake_clock.advance(1)
    assert fake_clock.now == started_at + 60
    allowed = request_reset(client, "active@example.com")
    assert allowed.status_code == 202
    assert len(mailbox.sent) == 2
    second_token = mailbox.last_token
    assert second_token != first_token
    assert preview_reset(client, first_token).status_code == 410
    assert preview_reset(client, second_token).status_code == 200

    links = reset_links(manager_id)
    assert len(links) == 2
    assert links[0]["revoked_at"] is not None
    assert links[1]["revoked_at"] is None

    unknown_started = fake_clock.now
    assert request_reset(client, "nobody@example.com").status_code == 202
    fake_clock.advance(59)
    unknown_cooling = request_reset(client, "nobody@example.com")
    assert unknown_cooling.status_code == 429
    assert unknown_cooling.json()["retry_after_seconds"] == 1
    assert len(mailbox.sent) == 2

    fake_clock.now = unknown_started + 60
    assert request_reset(client, "nobody@example.com").status_code == 202
    assert len(mailbox.sent) == 2

    assert reset_links(add_pending_manager("waiting@example.com", "waiting-invite")) == []
    assert request_reset(client, "waiting@example.com").status_code == 202
    waiting_cooling = request_reset(client, "waiting@example.com")
    assert waiting_cooling.status_code == 429
    assert waiting_cooling.json()["detail"] == "Too many password recovery requests"


def test_concurrent_requests_have_one_cooldown_winner(
    database: Path, mailbox: Mailbox
) -> None:
    manager_id = add_active_manager("race@example.com")
    clients = [TestClient(app, base_url=BASE_URL) for _ in range(2)]
    headers = [csrf_headers(prepared) for prepared in clients]
    barrier = threading.Barrier(2)
    outcomes: list[int] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def attempt(index: int) -> None:
        barrier.wait()
        try:
            response = request_reset(clients[index], "race@example.com", headers=headers[index])
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
    assert sorted(outcomes) == [202, 429]
    assert len(mailbox.sent) == 1
    assert len(reset_links(manager_id)) == 1


def test_smtp_unavailable_is_the_same_error_for_every_address(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    active_id = add_active_manager("active@example.com")
    pending_id = add_pending_manager("pending@example.com")
    mailbox.unavailable = True

    responses = [
        request_reset(client, address)
        for address in ("active@example.com", "pending@example.com", "nobody@example.com")
    ]

    assert [response.status_code for response in responses] == [502, 502, 502]
    assert [response.json() for response in responses] == [
        {"detail": "Password recovery email could not be delivered"}
    ] * 3
    assert mailbox.sent == []
    assert reset_links(active_id) == []
    assert reset_links(pending_id) == []
    assert manager_row(pending_id)["password_hash"] is None


def test_address_specific_delivery_failure_stays_neutral(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_active_manager("undeliverable@example.com")
    mailbox.fail_send = True

    known = request_reset(client, "undeliverable@example.com")
    unknown = request_reset(client, "nobody@example.com")

    assert known.status_code == 202
    assert known.json() == unknown.json() == {"detail": REQUEST_ACCEPTED_DETAIL}
    assert "token" not in known.json()
    assert mailbox.sent == []


def test_reset_routes_require_csrf_and_allowed_origin(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    manager_id = add_active_manager("csrf@example.com")
    token = "csrf-token"
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(one_time_links).values(
                    token_hash=security.token_digest(token),
                    manager_id=manager_id,
                    purpose=recovery.PASSWORD_RESET_PURPOSE,
                    created_at=clock.now_seconds(),
                    expires_at=clock.now_seconds() + recovery.PASSWORD_RESET_TTL_SECONDS,
                )
            )
    finally:
        engine.dispose()

    bootstrap_csrf(client)
    missing = request_reset(client, "csrf@example.com", headers={"Origin": BASE_URL})
    assert missing.status_code == 403
    assert preview_reset(client, token, headers={"Origin": BASE_URL}).status_code == 403
    assert complete_reset(client, token, headers={"Origin": BASE_URL}).status_code == 403
    csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token is not None
    foreign_origin = preview_reset(
        client,
        token,
        headers={CSRF_HEADER_NAME: csrf_token, "Origin": "http://evil.test"},
    )
    assert foreign_origin.status_code == 403
    assert client.get("/password-reset/request").status_code == 405
    assert mailbox.sent == []
    assert manager_row(manager_id)["password_hash"] is not None
    assert manager_session_count(manager_id) == 0


def test_expiry_boundary_is_exactly_one_hour(
    client: TestClient,
    database: Path,
    mailbox: Mailbox,
    fake_clock: FakeClock,
) -> None:
    manager_id = add_active_manager("boundary@example.com", "oldpass1")
    started_at = fake_clock.now
    assert request_reset(client, "boundary@example.com").status_code == 202
    token = mailbox.last_token
    links = reset_links(manager_id)
    assert links[0]["expires_at"] == started_at + recovery.PASSWORD_RESET_TTL_SECONDS
    stored_hash = manager_row(manager_id)["password_hash"]

    fake_clock.advance(recovery.PASSWORD_RESET_TTL_SECONDS - 1)
    assert preview_reset(client, token).status_code == 200

    fake_clock.advance(1)
    assert preview_reset(client, token).json() == {"detail": STALE_LINK_DETAIL}
    fresh = TestClient(app, base_url=BASE_URL)
    assert complete_reset(fresh, token, "newpass1").status_code == 410
    assert manager_row(manager_id)["password_hash"] == stored_hash
    assert manager_session_count(manager_id) == 0
    unchanged_login = login_manager(
        TestClient(app, base_url=BASE_URL),
        "boundary@example.com",
        "oldpass1",
    )
    assert unchanged_login.status_code == 200


def test_completion_revokes_every_old_session_and_authenticates_new_one(
    database: Path, mailbox: Mailbox
) -> None:
    manager_id = add_active_manager("sessions@example.com", "oldpass1")
    add_administrator()
    admin_client = TestClient(app, base_url=BASE_URL)
    assert login_administrator(admin_client).status_code == 200

    first_device = TestClient(app, base_url=BASE_URL)
    second_device = TestClient(app, base_url=BASE_URL)
    assert login_manager(first_device, "sessions@example.com", "oldpass1").status_code == 200
    assert login_manager(second_device, "sessions@example.com", "oldpass1").status_code == 200
    assert manager_session_count(manager_id) == 2

    recovery_device = TestClient(app, base_url=BASE_URL)
    assert request_reset(recovery_device, "sessions@example.com").status_code == 202
    completed = complete_reset(recovery_device, mailbox.last_token, "newpass1")

    assert completed.status_code == 200
    assert completed.json()["subject"] == {
        "type": "manager",
        "id": manager_id,
        "name": "Active Manager",
        "email": "sessions@example.com",
    }
    assert completed.cookies.get(SESSION_COOKIE_NAME) is not None
    assert recovery_device.get("/auth/me").status_code == 200
    assert first_device.get("/auth/me").status_code == 401
    assert second_device.get("/auth/me").status_code == 401
    assert manager_session_count(manager_id) == 1

    other = TestClient(app, base_url=BASE_URL)
    assert login_manager(other, "sessions@example.com", "oldpass1").status_code == 401
    newer = TestClient(app, base_url=BASE_URL)
    assert login_manager(newer, "sessions@example.com", "newpass1").status_code == 200

    assert admin_client.get("/auth/me").status_code == 200
    fresh_admin = TestClient(app, base_url=BASE_URL)
    assert login_administrator(fresh_admin).status_code == 200


def test_completion_clears_login_lock(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_active_manager("locked@example.com", "oldpass1")
    attacker = TestClient(app, base_url=BASE_URL)
    response: Any = None
    for _ in range(5):
        response = login_manager(attacker, "locked@example.com", "wrongpass")
    assert response.status_code == 423
    assert attempt_state("locked@example.com") is not None

    assert request_reset(client, "locked@example.com").status_code == 202
    unlocked = complete_reset(
        TestClient(app, base_url=BASE_URL),
        mailbox.last_token,
        "newpass1",
    )
    assert unlocked.status_code == 200

    assert attempt_state("locked@example.com") is None
    fresh = TestClient(app, base_url=BASE_URL)
    assert login_manager(fresh, "locked@example.com", "newpass1").status_code == 200


def test_password_errors_do_not_consume_reset_link(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    manager_id = add_active_manager("policy@example.com", "oldpass1")
    assert request_reset(client, "policy@example.com").status_code == 202
    token = mailbox.last_token
    before = manager_row(manager_id)["password_hash"]

    mismatch = complete_reset(client, token, "newpass1", "different1")
    assert mismatch.status_code == 422
    assert mismatch.json()["field"] == "password"

    weak = complete_reset(client, token, "abcdefgh")
    assert weak.status_code == 422
    assert weak.json()["field"] == "password"

    short = complete_reset(client, token, "abc1")
    assert short.status_code == 422
    assert short.json()["field"] == "password"

    assert manager_row(manager_id)["password_hash"] == before
    assert manager_session_count(manager_id) == 0
    assert preview_reset(client, token).status_code == 200

    assert complete_reset(client, token, "пароль123").status_code == 200
    assert preview_reset(client, token).status_code == 410


def test_token_is_single_use_and_unknown_or_used_tokens_share_the_same_response(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    manager_id = add_active_manager("once@example.com", "oldpass1")
    assert request_reset(client, "once@example.com").status_code == 202
    token = mailbox.last_token

    first = TestClient(app, base_url=BASE_URL)
    assert complete_reset(first, token, "newpass1").status_code == 200
    assert first.get("/auth/me").status_code == 200
    assert manager_session_count(manager_id) == 1

    reused = complete_reset(TestClient(app, base_url=BASE_URL), token, "another1")
    unknown = preview_reset(TestClient(app, base_url=BASE_URL), "unknown-token")
    assert reused.status_code == 410
    assert unknown.status_code == 410
    assert reused.json() == unknown.json() == {"detail": STALE_LINK_DETAIL}
    assert "email" not in reused.json()
    assert manager_session_count(manager_id) == 1


def test_concurrent_completion_succeeds_at_most_once(
    database: Path, mailbox: Mailbox
) -> None:
    manager_id = add_active_manager("race-complete@example.com", "oldpass1")
    bootstrap = TestClient(app, base_url=BASE_URL)
    assert request_reset(bootstrap, "race-complete@example.com").status_code == 202
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
            response = complete_reset(
                clients[index],
                token,
                "newpass1",
                headers=headers[index],
            )
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
    raced_login = login_manager(
        TestClient(app, base_url=BASE_URL),
        "race-complete@example.com",
        "newpass1",
    )
    assert raced_login.status_code == 200


def test_validation_errors_do_not_echo_token_or_password(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    add_active_manager("echo@example.com", "oldpass1")
    assert request_reset(client, "echo@example.com").status_code == 202
    token = mailbox.last_token

    secret = "never-echo-this-password-" + "a" * 1100
    oversized = complete_reset(client, token, secret)
    assert oversized.status_code == 422
    assert oversized.json()["field"] == "password"
    assert secret not in oversized.text

    token_secret = "never-echo-this-token"
    malformed = client.post(
        "/password-reset/preview",
        json={"token": {"raw": token_secret}},
        headers=csrf_headers(client),
    )
    assert malformed.status_code == 422
    assert malformed.json()["field"] == "token"
    assert token_secret not in malformed.text
    assert "input" not in malformed.json()

    missing = client.post(
        "/password-reset/complete",
        json={"token": token, "password_confirmation": "newpass1"},
        headers=csrf_headers(client),
    )
    assert missing.status_code == 422
    assert missing.json()["field"] == "password"
    assert preview_reset(client, token).status_code == 200


def test_new_request_invalidates_previous_token(
    client: TestClient,
    database: Path,
    mailbox: Mailbox,
    fake_clock: FakeClock,
) -> None:
    manager_id = add_active_manager("rotate@example.com", "oldpass1")
    assert request_reset(client, "rotate@example.com").status_code == 202
    first_token = mailbox.last_token

    fake_clock.advance(recovery.REQUEST_COOLDOWN_SECONDS)
    assert request_reset(client, "rotate@example.com").status_code == 202
    second_token = mailbox.last_token
    assert second_token != first_token

    assert preview_reset(client, first_token).status_code == 410
    assert preview_reset(client, second_token).status_code == 200
    links = reset_links(manager_id)
    assert [link["revoked_at"] is not None for link in links] == [True, False]


def test_password_reset_url_keeps_token_in_fragment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_PUBLIC_BASE_URL", "https://logos.example/")
    url = mail.password_reset_url("tok/en+=")
    assert url == "https://logos.example/password-reset#token=tok%2Fen%2B%3D"
    assert "?token" not in url
    assert "/password-reset/" not in url


def test_cooldown_is_scoped_to_normalized_email(
    client: TestClient, database: Path, mailbox: Mailbox
) -> None:
    assert request_reset(client, "nobody@example.com").status_code == 202
    assert request_reset(client, "other@example.com").status_code == 202
    assert len(mailbox.sent) == 0

    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            rows = connection.execute(select(password_reset_requests)).all()
    finally:
        engine.dispose()
    assert sorted(row.email_normalized for row in rows) == [
        "nobody@example.com",
        "other@example.com",
    ]


def reset_requested_at(email: str) -> int:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return int(
                connection.execute(
                    select(password_reset_requests.c.requested_at).where(
                        password_reset_requests.c.email_normalized
                        == security.normalize_email(email)
                    )
                ).scalar_one()
            )
    finally:
        engine.dispose()


def link_states(manager_id: int) -> list[tuple[int, int | None, int | None]]:
    return [
        (int(link["id"]), link["revoked_at"], link["consumed_at"])
        for link in reset_links(manager_id)
    ]


class ResponseBoundaryMiddleware:
    """Отмечает момент, когда ответ уже начал уходить клиенту."""

    def __init__(self, app: Any, started: threading.Event) -> None:
        self.app = app
        self.started = started

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_boundary(message: Any) -> None:
            if message["type"] == "http.response.start":
                self.started.set()
            await send(message)

        await self.app(scope, receive, send_with_boundary)


def test_account_specific_reset_work_starts_after_response(
    database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_active_manager("after-response@example.com", "oldpass1")
    started = threading.Event()
    observed: list[tuple[str, bool]] = []
    delivered: list[str] = []
    original_issue = recovery.issue_password_reset

    def check() -> None:
        observed.append(("check", started.is_set()))

    def issue(email: str, reserved_at: int, now: int | None = None) -> Any:
        observed.append(("issue", started.is_set()))
        return original_issue(email, reserved_at, now)

    def send(recipient: str, token: str) -> None:
        observed.append(("send", started.is_set()))
        delivered.append(token)

    monkeypatch.setattr(mail, "check_delivery_available", check)
    monkeypatch.setattr(mail, "send_password_reset", send)
    monkeypatch.setattr(recovery, "issue_password_reset", issue)

    boundary_app = FastAPI()
    boundary_app.include_router(auth_router)
    boundary_app.include_router(recovery_router)
    boundary_app.add_middleware(ResponseBoundaryMiddleware, started=started)
    boundary_client = TestClient(boundary_app, base_url=BASE_URL)

    headers = csrf_headers(boundary_client)
    started.clear()  # bootstrap CSRF-запрос тоже проходит через middleware
    response = request_reset(boundary_client, "after-response@example.com", headers=headers)

    assert response.status_code == 202
    assert observed[0] == ("check", False)
    assert all(flag for _, flag in observed[1:])
    assert [name for name, _ in observed] == ["check", "issue", "send"]
    assert len(delivered) == 1
    assert response.json() == {"detail": REQUEST_ACCEPTED_DETAIL}
    assert delivered[0] not in response.text

    assert preview_reset(TestClient(app, base_url=BASE_URL), delivered[0]).status_code == 200


def test_late_background_issue_cannot_revoke_newer_link(
    client: TestClient,
    database: Path,
    mailbox: Mailbox,
    fake_clock: FakeClock,
) -> None:
    manager_id = add_active_manager("late@example.com", "oldpass1")
    assert request_reset(client, "late@example.com").status_code == 202
    first_generation = reset_requested_at("late@example.com")
    first_token = mailbox.last_token

    fake_clock.advance(recovery.REQUEST_COOLDOWN_SECONDS)
    assert request_reset(client, "late@example.com").status_code == 202
    second_token = mailbox.last_token
    assert first_token != second_token
    before = link_states(manager_id)

    assert recovery.issue_password_reset("late@example.com", first_generation) is None

    assert preview_reset(client, second_token).status_code == 200
    assert link_states(manager_id) == before


def test_stale_login_does_not_survive_concurrent_reset(
    database: Path, mailbox: Mailbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager_id = add_active_manager("race-login@example.com", "oldpass1")
    old_device = TestClient(app, base_url=BASE_URL)
    assert login_manager(old_device, "race-login@example.com", "oldpass1").status_code == 200
    assert request_reset(old_device, "race-login@example.com").status_code == 202
    reset_token = mailbox.last_token

    verified = threading.Event()
    reset_committed = threading.Event()
    paused = threading.Event()
    real_verify = security.verify_password

    def verify(password_hash: str, password: str) -> bool:
        result = real_verify(password_hash, password)
        if result and not paused.is_set():
            paused.set()
            verified.set()
            assert reset_committed.wait(30)
        return result

    monkeypatch.setattr(auth, "verify_password", verify)

    stale_client = TestClient(app, base_url=BASE_URL)
    headers = csrf_headers(stale_client)
    outcome: dict[str, Any] = {}

    def stale_login() -> None:
        outcome["response"] = stale_client.post(
            "/auth/manager/login",
            json={
                "email": "race-login@example.com",
                "password": "oldpass1",
                "remember": False,
            },
            headers=headers,
        )

    thread = threading.Thread(target=stale_login)
    thread.start()
    assert verified.wait(30)

    reset_client = TestClient(app, base_url=BASE_URL)
    completed = complete_reset(reset_client, reset_token, "newpass1")
    assert completed.status_code == 200
    reset_committed.set()
    thread.join(30)
    assert not thread.is_alive()

    stale = outcome["response"]
    assert stale.status_code == 401
    assert stale.json() == {"detail": "Invalid credentials", "attempts_remaining": 4}
    assert stale.cookies.get(SESSION_COOKIE_NAME) is None
    assert old_device.get("/auth/me").status_code == 401
    assert reset_client.get("/auth/me").status_code == 200
    assert manager_session_count(manager_id) == 1

    after_race = TestClient(app, base_url=BASE_URL)
    assert login_manager(after_race, "race-login@example.com", "oldpass1").status_code == 401
    fresh = TestClient(app, base_url=BASE_URL)
    assert login_manager(fresh, "race-login@example.com", "newpass1").status_code == 200


def test_reset_preserves_other_manager_and_administrator_sessions(
    database: Path, mailbox: Mailbox
) -> None:
    manager_id = add_active_manager("first@example.com", "oldpass1")
    other_id = add_active_manager("second@example.com", "otherpass1")
    add_administrator()

    first_device = TestClient(app, base_url=BASE_URL)
    second_device = TestClient(app, base_url=BASE_URL)
    admin_client = TestClient(app, base_url=BASE_URL)
    assert login_manager(first_device, "first@example.com", "oldpass1").status_code == 200
    assert login_manager(second_device, "second@example.com", "otherpass1").status_code == 200
    assert login_administrator(admin_client).status_code == 200

    reset_device = TestClient(app, base_url=BASE_URL)
    assert request_reset(reset_device, "first@example.com").status_code == 202
    completed = complete_reset(reset_device, mailbox.last_token, "newpass1")
    assert completed.status_code == 200

    assert first_device.get("/auth/me").status_code == 401
    assert second_device.get("/auth/me").status_code == 200
    assert admin_client.get("/auth/me").status_code == 200
    assert manager_session_count(manager_id) == 1
    assert manager_session_count(other_id) == 1


def test_reset_session_cookie_is_browser_session_cookie(
    database: Path, mailbox: Mailbox
) -> None:
    add_active_manager("cookie@example.com", "oldpass1")
    secure_client = TestClient(app, base_url="https://testserver")
    csrf = secure_client.get("/auth/csrf").json()["csrf_token"]
    headers = {CSRF_HEADER_NAME: str(csrf), "Origin": "https://testserver"}

    assert request_reset(secure_client, "cookie@example.com", headers=headers).status_code == 202
    completed = complete_reset(
        secure_client,
        mailbox.last_token,
        "newpass1",
        headers=headers,
    )

    assert completed.status_code == 200
    header = completed.headers["set-cookie"].lower()
    assert header.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "secure" in header
    assert "path=/" in header
    assert "max-age" not in header
    assert "expires" not in header
