"""Поведенческие тесты B1: схема, вход, сессии, блокировка и CSRF."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, inspect, select
from sqlalchemy.exc import IntegrityError

from logos_backend import auth, clock, mail, security
from logos_backend.app import MAX_REQUEST_BODY_BYTES, app
from logos_backend.db import (
    administrators,
    create_first_admin,
    database_url,
    login_attempts,
    manager_otp_requests,
    managers,
    sessions,
)
from logos_backend.web_auth import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    MAX_EMAIL_LENGTH,
    MAX_LOGIN_LENGTH,
    MAX_PASSWORD_LENGTH,
    SESSION_COOKIE_NAME,
    require_administrator,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
def client(database: Path) -> TestClient:
    return TestClient(app, base_url="http://testserver")


def bootstrap_csrf(client: TestClient) -> str:
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    assert isinstance(token, str)
    return token


def csrf_headers(token: str, origin: str = "http://testserver") -> dict[str, str]:
    return {CSRF_HEADER_NAME: token, "Origin": origin}


def administrator_login(
    client: TestClient,
    login: str,
    password: str,
    *,
    remember: bool = False,
    origin: str = "http://testserver",
) -> Any:
    token = bootstrap_csrf(client)
    return client.post(
        "/auth/admin/login",
        json={"login": login, "password": password, "remember": remember},
        headers=csrf_headers(token, origin),
    )


def manager_login(
    client: TestClient,
    email: str,
    code: str,
    *,
    remember: bool = False,
    origin: str = "http://testserver",
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    token = bootstrap_csrf(client)
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                manager_otp_requests.delete().where(
                    manager_otp_requests.c.email_normalized == security.normalize_email(email)
                )
            )
    finally:
        engine.dispose()
    captured: list[str] = []
    monkeypatch.setattr(mail, "send_manager_otp", lambda recipient, code: captured.append(code))
    monkeypatch.setattr(mail, "check_delivery_available", lambda: None)
    headers = csrf_headers(token, origin)
    requested = client.post("/auth/manager/otp/request", json={"email": email}, headers=headers)
    if requested.status_code != 202:
        return requested
    return client.post(
        "/auth/manager/otp/verify",
        json={"email": email, "code": captured[-1], "remember": remember},
        headers=headers,
    )


def add_administrator(login: str, password: str) -> None:
    create_first_admin(login=login, password_hash=security.hash_password(password))


def insert_manager(
    email: str,
    name: str,
    password_hash: str | None,
    created_at: int = 1_700_000_000,
) -> Any:
    """Пишет менеджера напрямую в БД; уникальность email проверяет сама схема.

    Продуктовый путь создания менеджера — только приглашение, поэтому тесты
    входа и сессий не должны зависеть от отдельной публичной функции создания.
    """
    trimmed_email = email.strip()
    normalized = security.normalize_email(trimmed_email)
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            row = (
                connection.execute(
                    insert(managers)
                    .values(
                        name=name,
                        email=trimmed_email,
                        email_normalized=normalized,
                        password_hash=password_hash,
                        created_at=created_at,
                    )
                    .returning(
                        managers.c.id,
                        managers.c.name,
                        managers.c.email,
                        managers.c.email_normalized,
                    )
                )
                .mappings()
                .one()
            )
    finally:
        engine.dispose()
    return SimpleNamespace(
        id=int(row["id"]),
        name=str(row["name"]),
        email=str(row["email"]),
        email_normalized=str(row["email_normalized"]),
    )


def add_manager(
    email: str,
    password: str | None = "correct1",
    name: str = "Manager",
) -> Any:
    password_hash = security.hash_password(password) if password is not None else None
    return insert_manager(email, name, password_hash)


def stored_administrators() -> list[tuple[int, str, str]]:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            rows = connection.execute(select(administrators)).all()
    finally:
        engine.dispose()
    return [(int(row.id), str(row.login), str(row.password_hash)) for row in rows]


def session_token_hashes() -> list[str]:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            rows = connection.execute(select(sessions.c.token_hash)).all()
    finally:
        engine.dispose()
    return [str(row[0]) for row in rows]


def manager_count() -> int:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return len(connection.execute(select(managers.c.id)).all())
    finally:
        engine.dispose()


def login_attempt_count() -> int:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            return len(connection.execute(select(login_attempts.c.identifier)).all())
    finally:
        engine.dispose()


def test_migration_preserves_existing_administrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    config = alembic_config()
    command.upgrade(config, "0001")

    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(administrators).values(
                    id=1,
                    login="root",
                    password_hash="argon2id-hash",
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    assert stored_administrators() == [(1, "root", "argon2id-hash")]
    engine = create_engine(database_url())
    try:
        table_names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert {"managers", "sessions", "one_time_links", "login_attempts"} <= table_names

    command.downgrade(config, "0001")

    assert stored_administrators() == [(1, "root", "argon2id-hash")]
    engine = create_engine(database_url())
    try:
        downgraded_tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert downgraded_tables.isdisjoint({"managers", "sessions", "one_time_links"})


def test_normalized_email_is_unique_including_concurrent_creation(database: Path) -> None:
    created = add_manager("  User@Example.com  ")

    assert created.email == "User@Example.com"
    assert created.email_normalized == "user@example.com"

    with pytest.raises(IntegrityError):
        insert_manager("user@example.COM", "Second", "hash")

    barrier = threading.Barrier(4)
    outcomes: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def attempt(index: int) -> None:
        barrier.wait()
        try:
            insert_manager("race@example.com", f"Racer {index}", "hash")
        except IntegrityError:
            outcome = "conflict"
        except BaseException as exc:  # pragma: no cover - диагностика неожиданного сбоя
            with lock:
                errors.append(exc)
            return
        else:
            outcome = "created"
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=attempt, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert outcomes.count("created") == 1
    assert outcomes.count("conflict") == 3
    assert manager_count() == 2



def test_administrator_login_uses_exact_cli_login_and_accepts_existing_password(
    client: TestClient, database: Path
) -> None:
    add_administrator("  Root  ", "short")

    wrong_case = administrator_login(client, "Root", "short")
    assert wrong_case.status_code == 401

    response = administrator_login(client, "  Root  ", "short")

    assert response.status_code == 200
    assert response.json() == {"subject": {"type": "administrator"}}

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json() == {"subject": {"type": "administrator"}}
    assert "email" not in me.json()["subject"]
    assert "name" not in me.json()["subject"]



def test_login_lock_boundary_is_fifteen_minutes(
    client: TestClient, database: Path, fake_clock: FakeClock
) -> None:
    add_administrator("root", "correct1")

    for _ in range(5):
        response = administrator_login(client, "root", "wrongpass1")
    assert response.status_code == 423
    assert response.json()["retry_after_seconds"] == auth.LOCK_SECONDS

    during_lock = administrator_login(client, "root", "correct1")
    assert during_lock.status_code == 423
    assert during_lock.json()["retry_after_seconds"] == auth.LOCK_SECONDS

    fake_clock.advance(auth.LOCK_SECONDS - 1)
    boundary = administrator_login(client, "root", "correct1")
    assert boundary.status_code == 423
    assert boundary.json()["retry_after_seconds"] == 1

    fake_clock.advance(1)
    unlocked = administrator_login(client, "root", "correct1")
    assert unlocked.status_code == 200



def test_malformed_stored_hash_fails_generically_and_counts_attempt(
    client: TestClient, database: Path
) -> None:
    create_first_admin(login="root", password_hash="not-an-argon2-hash")

    response = administrator_login(client, "root", "correct1")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials", "attempts_remaining": 4}
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    state = auth.get_attempt_state(auth.ADMINISTRATOR_SCOPE, "root")
    assert state.failed_count == 1
    assert state.locked_until is None


def test_oversized_request_body_is_rejected_before_parsing_and_writes(
    client: TestClient, database: Path
) -> None:
    add_manager("known@example.com", "correct1")

    known = client.post(
        "/auth/manager/otp/verify",
        content=b'{"email":"known@example.com","code":"' + b"a" * MAX_REQUEST_BODY_BYTES + b'"}',
        headers={"Content-Type": "application/json"},
    )
    unknown = client.post(
        "/auth/manager/otp/verify",
        content=b'{"email":"missing@example.com","code":"' + b"a" * MAX_REQUEST_BODY_BYTES + b'"}',
        headers={"Content-Type": "application/json"},
    )

    assert known.status_code == unknown.status_code == 413
    assert known.content == unknown.content

    chunks = iter(
        (
            b'{"email":"known@example.com","code":"',
            b"a" * MAX_REQUEST_BODY_BYTES,
            b'"}',
        )
    )
    streamed = client.post(
        "/auth/manager/otp/verify",
        content=chunks,
        headers={"Content-Type": "application/json"},
    )
    assert streamed.status_code == 413

    assert login_attempt_count() == 0
    assert manager_count() == 1
    assert session_token_hashes() == []

def test_oversized_credentials_are_rejected_before_authentication(
    client: TestClient, database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_administrator("root", "correct1")
    overlong_password = "a" * (MAX_PASSWORD_LENGTH + 1)

    known = administrator_login(client, "root", overlong_password)
    unknown = administrator_login(client, "nobody", overlong_password)

    assert known.status_code == unknown.status_code == 422
    assert known.json() == unknown.json()

    overlong_login = administrator_login(client, "a" * (MAX_LOGIN_LENGTH + 1), "correct1")
    assert overlong_login.status_code == 422

    overlong_email = "a" * (MAX_EMAIL_LENGTH + 1 - len("@example.com")) + "@example.com"
    assert len(overlong_email) == MAX_EMAIL_LENGTH + 1
    assert (
        manager_login(client, overlong_email, "correct1", monkeypatch=monkeypatch).status_code
        == 422
    )

    assert login_attempt_count() == 0
    assert session_token_hashes() == []
    stored = stored_administrators()
    assert len(stored) == 1
    assert stored[0][1] == "root"


def test_normal_unicode_password_authenticates(
    client: TestClient, database: Path
) -> None:
    add_administrator("root", "пароль123")

    response = administrator_login(client, "root", "пароль123")

    assert response.status_code == 200
    assert response.json() == {"subject": {"type": "administrator"}}


def test_session_cookie_flags_and_thirty_day_server_limit(
    database: Path, fake_clock: FakeClock
) -> None:
    add_administrator("root", "correct1")
    secure_client = TestClient(app, base_url="https://testserver")

    session_cookie = administrator_login(
        secure_client,
        "root",
        "correct1",
        origin="https://testserver",
    )

    assert session_cookie.status_code == 200
    header = session_cookie.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "secure" in header
    assert "max-age" not in header
    assert "expires" not in header

    remembered = administrator_login(
        TestClient(app, base_url="https://testserver"),
        "root",
        "correct1",
        remember=True,
        origin="https://testserver",
    )
    remember_header = remembered.headers["set-cookie"].lower()
    assert f"max-age={auth.SESSION_TTL_SECONDS}" in remember_header
    assert "secure" in remember_header

    plain_client = TestClient(app, base_url="http://testserver")
    plain = administrator_login(plain_client, "root", "correct1")
    assert "secure" not in plain.headers["set-cookie"].lower()

    session_client = TestClient(app, base_url="http://testserver")
    administrator_login(session_client, "root", "correct1")
    fake_clock.advance(auth.SESSION_TTL_SECONDS - 1)
    assert session_client.get("/auth/me").status_code == 200

    fake_clock.advance(1)
    assert session_client.get("/auth/me").status_code == 401


def test_logout_revokes_current_session_and_stores_only_digest(
    client: TestClient, database: Path, fake_clock: FakeClock
) -> None:
    add_administrator("root", "correct1")
    administrator_login(client, "root", "correct1")

    raw_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert raw_token is not None
    digest = security.token_digest(raw_token)
    assert session_token_hashes() == [digest]
    assert raw_token not in session_token_hashes()

    token = bootstrap_csrf(client)
    response = client.post("/auth/logout", headers=csrf_headers(token))

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert client.get("/auth/me").status_code == 401
    assert session_token_hashes() == []


def test_successful_login_rotates_session_token(
    client: TestClient, database: Path, fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    add_manager("rotate@example.com", "correct1")

    manager_login(client, "rotate@example.com", "correct1", monkeypatch=monkeypatch)
    first_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert first_token is not None

    manager_login(client, "rotate@example.com", "correct1", monkeypatch=monkeypatch)
    second_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert second_token is not None

    assert first_token != second_token
    assert auth.session_subject(first_token, fake_clock.now) is None
    assert auth.session_subject(second_token, fake_clock.now) is not None
    assert len(session_token_hashes()) == 1


def test_csrf_bootstrap_and_unsafe_request_protection(
    client: TestClient, database: Path
) -> None:
    add_administrator("root", "correct1")

    no_origin = client.post(
        "/auth/admin/login",
        json={"login": "root", "password": "correct1"},
    )
    assert no_origin.status_code == 403
    assert no_origin.json() == {"detail": "Request origin is not allowed"}

    token = bootstrap_csrf(client)
    assert client.cookies.get(CSRF_COOKIE_NAME) == token

    bootstrap_response = client.get("/auth/csrf")
    assert "httponly" not in bootstrap_response.headers["set-cookie"].lower()

    wrong_origin = client.post(
        "/auth/admin/login",
        json={"login": "root", "password": "correct1"},
        headers={"X-CSRF-Token": token, "Origin": "http://evil.test"},
    )
    assert wrong_origin.status_code == 403
    assert wrong_origin.json() == {"detail": "Request origin is not allowed"}

    missing_token = client.post(
        "/auth/admin/login",
        json={"login": "root", "password": "correct1"},
        headers={"Origin": "http://testserver"},
    )
    assert missing_token.status_code == 403
    assert missing_token.json() == {"detail": "CSRF verification failed"}

    wrong_token = client.post(
        "/auth/admin/login",
        json={"login": "root", "password": "correct1"},
        headers={"X-CSRF-Token": "wrong", "Origin": "http://testserver"},
    )
    assert wrong_token.status_code == 403

    success = client.post(
        "/auth/admin/login",
        json={"login": "root", "password": "correct1"},
        headers=csrf_headers(token),
    )
    assert success.status_code == 200

    logout_without_token = client.post("/auth/logout", headers={"Origin": "http://testserver"})
    assert logout_without_token.status_code == 403
    assert client.get("/auth/me").status_code == 200


def build_admin_only_app() -> FastAPI:
    test_app = FastAPI()

    @test_app.get("/admin-only")
    def admin_only(
        subject: Annotated[auth.Subject, Depends(require_administrator)],
    ) -> dict[str, str]:
        return {"type": subject.kind}

    return test_app


def test_administrator_authorization_dependency(
    client: TestClient, database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_administrator("root", "correct1")
    add_manager("manager@example.com", "correct1")

    admin_only = TestClient(build_admin_only_app(), base_url="http://testserver")
    assert admin_only.get("/admin-only").status_code == 401

    administrator_login(client, "root", "correct1")
    admin_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert admin_token is not None
    admin_only.cookies.set(SESSION_COOKIE_NAME, admin_token)
    assert admin_only.get("/admin-only").status_code == 200

    manager_client = TestClient(app, base_url="http://testserver")
    manager_login(manager_client, "manager@example.com", "correct1", monkeypatch=monkeypatch)
    manager_token = manager_client.cookies.get(SESSION_COOKIE_NAME)
    assert manager_token is not None
    manager_only = TestClient(build_admin_only_app(), base_url="http://testserver")
    manager_only.cookies.set(SESSION_COOKIE_NAME, manager_token)
    response = manager_only.get("/admin-only")
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_database_enforces_session_ownership_and_unique_digest(
    database: Path, fake_clock: FakeClock
) -> None:
    add_administrator("root", "correct1")
    manager = add_manager("owner@example.com")

    engine = create_engine(database_url())
    try:
        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(
                insert(sessions).values(
                    token_hash="both-owners",
                    administrator_id=1,
                    manager_id=manager.id,
                    created_at=fake_clock.now,
                    expires_at=fake_clock.now + 100,
                )
            )

        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(
                insert(sessions).values(
                    token_hash="no-owner",
                    administrator_id=None,
                    manager_id=None,
                    created_at=fake_clock.now,
                    expires_at=fake_clock.now + 100,
                )
            )

        with engine.begin() as connection:
            connection.execute(
                insert(sessions).values(
                    token_hash="duplicate",
                    administrator_id=1,
                    manager_id=None,
                    created_at=fake_clock.now,
                    expires_at=fake_clock.now + 100,
                )
            )
        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(
                insert(sessions).values(
                    token_hash="duplicate",
                    administrator_id=None,
                    manager_id=manager.id,
                    created_at=fake_clock.now,
                    expires_at=fake_clock.now + 100,
                )
            )
    finally:
        engine.dispose()


def test_concurrent_failed_attempts_are_counted_atomically(
    database: Path, fake_clock: FakeClock
) -> None:
    barrier = threading.Barrier(5)
    errors: list[BaseException] = []
    lock = threading.Lock()

    def attempt() -> None:
        barrier.wait()
        try:
            auth.register_failed_attempt(
                auth.MANAGER_SCOPE,
                "shared@example.com",
                now=fake_clock.now,
            )
        except BaseException as exc:  # pragma: no cover - диагностика неожиданного сбоя
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    state = auth.get_attempt_state(auth.MANAGER_SCOPE, "shared@example.com")
    assert state.failed_count == auth.MAX_FAILED_ATTEMPTS
    assert state.locked_until == fake_clock.now + auth.LOCK_SECONDS


def test_email_normalization_and_password_policy() -> None:
    assert security.normalize_email(" User@Example.COM ") == "user@example.com"
    assert security.normalize_email("user+tag@example.com") != security.normalize_email(
        "usertag@example.com"
    )
    assert security.normalize_email("u.ser@example.com") != security.normalize_email(
        "user@example.com"
    )

    security.validate_password_confirmation("пароль1x", "пароль1x")
    with pytest.raises(security.PasswordPolicyError):
        security.validate_password("abcdefgh")
    with pytest.raises(security.PasswordPolicyError):
        security.validate_password("12345678")
    with pytest.raises(security.PasswordPolicyError):
        security.validate_password("abc1")
    with pytest.raises(security.PasswordPolicyError):
        security.validate_password_confirmation("correct1", "correct2")

    password_hash = security.hash_password("correct1")
    assert password_hash.startswith("$argon2id$")
    assert security.verify_password(password_hash, "correct1") is True
    assert security.verify_password(password_hash, "correct1 ") is False
