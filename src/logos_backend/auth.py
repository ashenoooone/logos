"""Серверные сессии, вход и учёт неудачных попыток.

Модуль намеренно не зависит от FastAPI: HTTP-слой вызывает эти функции и
преобразует исключения в согласованные ответы.
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from typing import NoReturn

from sqlalchemy import and_, case, delete, insert, literal, null, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from logos_backend import clock
from logos_backend.db import (
    _create_engine,
    administrators,
    immediate_transaction,
    login_attempts,
    manager_otp_codes,
    manager_otp_requests,
    managers,
    sessions,
)
from logos_backend.security import (
    consume_dummy_verification,
    hash_password,
    new_token,
    normalize_email,
    token_digest,
    verify_password,
)

ADMINISTRATOR = "administrator"
MANAGER = "manager"

ADMINISTRATOR_SCOPE = ADMINISTRATOR
MANAGER_SCOPE = MANAGER

MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60


@dataclass(frozen=True)
class AdministratorRecord:
    id: int
    login: str
    password_hash: str



@dataclass(frozen=True)
class Subject:
    """Аутентифицированный субъект; администратор не получает выдуманных имени и email."""

    kind: str
    id: int
    login: str | None = None
    name: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class AttemptState:
    failed_count: int
    locked_until: int | None


@dataclass(frozen=True)
class LoginSession:
    """Результат входа: субъект и токен сессии, уже записанной в БД."""

    subject: Subject
    token: str


class InvalidCredentialsError(Exception):
    def __init__(self, attempts_remaining: int) -> None:
        super().__init__("Invalid credentials")
        self.attempts_remaining = attempts_remaining


class AccountLockedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many login attempts")
        self.retry_after_seconds = retry_after_seconds


def _now(now: int | None) -> int:
    return clock.now_seconds() if now is None else now

OTP_TTL_SECONDS = 600
OTP_MAX_ATTEMPTS = 5
OTP_REQUEST_COOLDOWN_SECONDS = 60


class OtpInvalidError(Exception):
    """Код недействителен, истёк или исчерпал число попыток."""


class OtpRateLimitedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


def request_manager_otp(email: str, now: int | None = None) -> str:
    """Занимает окно запроса; usable код выпускается только активному менеджеру."""
    timestamp = _now(now)
    normalized = normalize_email(email)
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            existing = connection.execute(
                select(manager_otp_requests.c.requested_at).where(
                    manager_otp_requests.c.email_normalized == normalized
                )
            ).scalar_one_or_none()
            if existing is not None and timestamp < int(existing) + OTP_REQUEST_COOLDOWN_SECONDS:
                raise OtpRateLimitedError(int(existing) + OTP_REQUEST_COOLDOWN_SECONDS - timestamp)
            connection.execute(
                sqlite_insert(manager_otp_requests)
                .values(email_normalized=normalized, requested_at=timestamp)
                .on_conflict_do_update(
                    index_elements=[manager_otp_requests.c.email_normalized],
                    set_={"requested_at": timestamp},
                )
            )
            manager_id = connection.execute(
                select(managers.c.id).where(
                    managers.c.email_normalized == normalized,
                    managers.c.password_hash.is_not(None),
                )
            ).scalar_one_or_none()
            code_hash = hash_password(code)
            if manager_id is not None:
                connection.execute(
                    sqlite_insert(manager_otp_codes)
                    .values(
                        manager_id=int(manager_id), code_hash=code_hash, created_at=timestamp,
                        expires_at=timestamp + OTP_TTL_SECONDS, attempts=0,
                        last_requested_at=timestamp,
                    )
                    .on_conflict_do_update(
                        index_elements=[manager_otp_codes.c["manager_id"]],
                        set_={
                            "code_hash": code_hash, "created_at": timestamp,
                            "expires_at": timestamp + OTP_TTL_SECONDS, "attempts": 0,
                            "last_requested_at": timestamp,
                        },
                    )
                )
    finally:
        engine.dispose()
    return code


def verify_manager_otp(
    email: str,
    code: str,
    previous_session_token: str | None = None,
    now: int | None = None,
) -> LoginSession:
    """Проверяет код и выдаёт сессию без возможности конкурентного повторного входа."""
    timestamp = _now(now)
    normalized = normalize_email(email)
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            row = connection.execute(
                select(
                    managers.c.id, managers.c.name, managers.c.email,
                    manager_otp_codes.c.code_hash, manager_otp_codes.c.expires_at,
                    manager_otp_codes.c.attempts,
                )
                .join(manager_otp_codes, manager_otp_codes.c["manager_id"] == managers.c.id)
                .where(
                    managers.c.email_normalized == normalized,
                    managers.c.password_hash.is_not(None),
                )
            ).mappings().first()
        valid = False
        verification_done = False
        if (
            row is not None
            and int(row["expires_at"]) > timestamp
            and int(row["attempts"]) < OTP_MAX_ATTEMPTS
        ):
            valid = verify_password(str(row["code_hash"]), code)
            verification_done = True
        if not verification_done:
            consume_dummy_verification(code)
        result: LoginSession | None = None
        failure = False
        with immediate_transaction(engine) as connection:
            if row is None:
                current = None
            else:
                manager_id = int(row["id"])
                current = connection.execute(
                    select(
                        manager_otp_codes.c.code_hash, manager_otp_codes.c.expires_at,
                        manager_otp_codes.c.attempts,
                    ).where(manager_otp_codes.c["manager_id"] == manager_id)
                ).mappings().first()
            if (
                row is None
                or current is None
                or int(current["expires_at"]) <= timestamp
                or int(current["attempts"]) >= OTP_MAX_ATTEMPTS
                or str(current["code_hash"]) != str(row["code_hash"])
            ):
                failure = True
            elif not valid:
                connection.execute(
                    manager_otp_codes.update()
                    .where(manager_otp_codes.c["manager_id"] == int(row["id"]))
                    .values(attempts=manager_otp_codes.c.attempts + 1)
                )
                failure = True
            else:
                connection.execute(
                    manager_otp_codes.delete().where(
                        manager_otp_codes.c["manager_id"] == int(row["id"])
                    )
                )
                subject = Subject(
                    kind=MANAGER,
                    id=int(row["id"]),
                    name=str(row["name"]),
                    email=str(row["email"]),
                )
                _revoke_session_in_transaction(connection, previous_session_token)
                token = create_session_record(connection, subject, timestamp)
                result = LoginSession(subject=subject, token=token)
        if failure or result is None:
            raise OtpInvalidError()
        return result
    finally:
        engine.dispose()


def get_attempt_state(scope: str, identifier: str) -> AttemptState:
    """Читает счётчик попыток; отсутствие строки означает ноль попыток."""
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(login_attempts.c.failed_count, login_attempts.c.locked_until).where(
                        login_attempts.c.scope == scope,
                        login_attempts.c.identifier == identifier,
                    )
                )
                .mappings()
                .first()
            )
    finally:
        engine.dispose()

    if row is None:
        return AttemptState(failed_count=0, locked_until=None)
    locked_until = row["locked_until"]
    return AttemptState(
        failed_count=int(row["failed_count"]),
        locked_until=int(locked_until) if locked_until is not None else None,
    )


def lock_remaining_seconds(state: AttemptState, now: int) -> int:
    if state.locked_until is None or state.locked_until <= now:
        return 0
    return state.locked_until - now


def register_failed_attempt(scope: str, identifier: str, now: int | None = None) -> AttemptState:
    """Атомарно увеличивает счётчик неудач для идентификатора в его пространстве.

    Один UPSERT с CASE не теряет инкременты при конкурентных запросах SQLite и не
    зависит от IP. Активная блокировка не продлевается; после её окончания счёт
    начинается заново.
    """
    timestamp = _now(now)
    table = login_attempts
    active_lock = and_(table.c.locked_until.is_not(None), table.c.locked_until > timestamp)
    expired_lock = and_(table.c.locked_until.is_not(None), table.c.locked_until <= timestamp)
    new_count = case(
        (active_lock, table.c.failed_count),
        (expired_lock, literal(1)),
        else_=table.c.failed_count + 1,
    )
    new_locked_until = case(
        (active_lock, table.c.locked_until),
        (expired_lock, null()),
        (table.c.failed_count + 1 >= MAX_FAILED_ATTEMPTS, literal(timestamp + LOCK_SECONDS)),
        else_=null(),
    )
    statement = (
        sqlite_insert(table)
        .values(
            scope=scope,
            identifier=identifier,
            failed_count=1,
            locked_until=None,
            updated_at=timestamp,
        )
        .on_conflict_do_update(
            index_elements=[table.c.scope, table.c.identifier],
            set_={
                "failed_count": new_count,
                "locked_until": new_locked_until,
                "updated_at": timestamp,
            },
        )
    )

    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(statement)
            row = (
                connection.execute(
                    select(table.c.failed_count, table.c.locked_until).where(
                        table.c.scope == scope,
                        table.c.identifier == identifier,
                    )
                )
                .mappings()
                .one()
            )
    finally:
        engine.dispose()

    locked_until = row["locked_until"]
    return AttemptState(
        failed_count=int(row["failed_count"]),
        locked_until=int(locked_until) if locked_until is not None else None,
    )


def _clear_attempts(connection: Connection, scope: str, identifier: str) -> None:
    connection.execute(
        delete(login_attempts).where(
            login_attempts.c.scope == scope,
            login_attempts.c.identifier == identifier,
        )
    )


def _revoke_session_in_transaction(connection: Connection, token: str | None) -> None:
    if token is None:
        return
    connection.execute(delete(sessions).where(sessions.c.token_hash == token_digest(token)))


def _ensure_not_locked(scope: str, identifier: str, now: int) -> None:
    remaining = lock_remaining_seconds(get_attempt_state(scope, identifier), now)
    if remaining > 0:
        raise AccountLockedError(remaining)


def _record_failure(scope: str, identifier: str, now: int) -> NoReturn:
    state = register_failed_attempt(scope, identifier, now)
    remaining = lock_remaining_seconds(state, now)
    if remaining > 0:
        raise AccountLockedError(remaining)
    raise InvalidCredentialsError(MAX_FAILED_ATTEMPTS - state.failed_count)


def find_administrator() -> AdministratorRecord | None:
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        administrators.c.id,
                        administrators.c.login,
                        administrators.c.password_hash,
                    )
                )
                .mappings()
                .first()
            )
    finally:
        engine.dispose()

    if row is None:
        return None
    return AdministratorRecord(
        id=int(row["id"]),
        login=str(row["login"]),
        password_hash=str(row["password_hash"]),
    )




def login_administrator(
    login: str,
    password: str,
    now: int | None = None,
    previous_session_token: str | None = None,
) -> LoginSession:
    """Вход администратора по точному CLI-логину; политика сложности не применяется.

    Argon2 выполняется до пишущей транзакции и не держит её блокировку. Сессия
    выдаётся только если в той же транзакции сохранённый хеш и логин всё ещё
    совпадают с проверенными: параллельное изменение учётных данных не даёт
    войти со старым паролем.
    """
    timestamp = _now(now)
    _ensure_not_locked(ADMINISTRATOR_SCOPE, login, timestamp)

    administrator = find_administrator()
    verified_hash: str | None = None
    if administrator is not None and administrator.login == login:
        verified_hash = administrator.password_hash
        valid = verify_password(verified_hash, password)
    else:
        consume_dummy_verification(password)
        valid = False

    if not valid or administrator is None or verified_hash is None:
        _record_failure(ADMINISTRATOR_SCOPE, login, timestamp)

    issued: LoginSession | None = None
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            row = (
                connection.execute(
                    select(
                        administrators.c.id,
                        administrators.c.login,
                        administrators.c.password_hash,
                    ).where(administrators.c.id == administrator.id)
                )
                .mappings()
                .first()
            )
            if (
                row is not None
                and str(row["password_hash"]) == verified_hash
                and str(row["login"]) == login
            ):
                subject = Subject(
                    kind=ADMINISTRATOR,
                    id=int(row["id"]),
                    login=str(row["login"]),
                )
                _clear_attempts(connection, ADMINISTRATOR_SCOPE, login)
                _revoke_session_in_transaction(connection, previous_session_token)
                token = create_session_record(connection, subject, timestamp)
                issued = LoginSession(subject=subject, token=token)
    finally:
        engine.dispose()

    if issued is None:
        # Учётные данные изменились между проверкой и выдачей сессии: для
        # клиента это обычный неверный вход, сессия не создаётся.
        _record_failure(ADMINISTRATOR_SCOPE, login, timestamp)
    return issued




def create_session_record(
    connection: Connection,
    subject: Subject,
    now: int | None = None,
) -> str:
    """Вставляет сессию в уже открытую транзакцию и возвращает открытый токен."""
    timestamp = _now(now)
    token = new_token()
    connection.execute(
        insert(sessions).values(
            token_hash=token_digest(token),
            administrator_id=subject.id if subject.kind == ADMINISTRATOR else None,
            manager_id=subject.id if subject.kind == MANAGER else None,
            created_at=timestamp,
            expires_at=timestamp + SESSION_TTL_SECONDS,
        )
    )
    return token


def session_subject(token: str, now: int | None = None) -> Subject | None:
    """Возвращает владельца действующей сессии или ``None``."""
    timestamp = _now(now)
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        sessions.c.administrator_id,
                        sessions.c.manager_id,
                        sessions.c.expires_at,
                        administrators.c.login,
                        managers.c.name,
                        managers.c.email,
                    )
                    .select_from(sessions)
                    .outerjoin(
                        administrators,
                        sessions.c.administrator_id == administrators.c.id,
                    )
                    .outerjoin(managers, sessions.c.manager_id == managers.c.id)
                    .where(sessions.c.token_hash == token_digest(token))
                )
                .mappings()
                .first()
            )
    finally:
        engine.dispose()

    if row is None or int(row["expires_at"]) <= timestamp:
        return None

    administrator_id = row["administrator_id"]
    if administrator_id is not None:
        login = row["login"]
        return Subject(
            kind=ADMINISTRATOR,
            id=int(administrator_id),
            login=str(login) if login is not None else None,
        )

    manager_id = row["manager_id"]
    if manager_id is None:
        return None
    name = row["name"]
    email = row["email"]
    if name is None or email is None:
        return None
    return Subject(
        kind=MANAGER,
        id=int(manager_id),
        name=str(name),
        email=str(email),
    )


def revoke_session(token: str) -> None:
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                delete(sessions).where(sessions.c.token_hash == token_digest(token))
            )
    finally:
        engine.dispose()
