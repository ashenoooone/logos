"""Восстановление пароля менеджера: ограничение повтора, ссылка и смена пароля.

Ссылка восстановления одноразовая и действует ровно 1 час. В БД хранится
только дайджест токена. Повторный запрос разрешён не чаще раза в 60 секунд на
нормализованный email; счётчик отдельный от попыток входа и действует даже для
несуществующего адреса, поэтому его наблюдаемое поведение не раскрывает
наличие учётной записи. Для ожидающего менеджера ссылка не выпускается:
восстановление не заменяет приглашение и не активирует аккаунт.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from logos_backend import auth, clock, security
from logos_backend.db import (
    _create_engine,
    immediate_transaction,
    login_attempts,
    managers,
    one_time_links,
    password_reset_requests,
    sessions,
)
from logos_backend.security import hash_password, new_token, normalize_email, token_digest

PASSWORD_RESET_TTL_SECONDS = 60 * 60
PASSWORD_RESET_PURPOSE = "password_reset"
REQUEST_COOLDOWN_SECONDS = 60


@dataclass(frozen=True)
class CooldownReservation:
    """Результат атомарной попытки занять окно повтора для адреса.

    ``requested_at`` — зафиксированное время принятого запроса. Оно же служит
    поколением: фоновое задание выпускает ссылку только если это поколение
    всё ещё последнее для адреса.
    """

    accepted: bool
    retry_after_seconds: int
    requested_at: int | None = None


@dataclass(frozen=True)
class PasswordResetIssue:
    """Письмо восстановления, которое нужно отправить; токен живёт только здесь."""

    email: str
    token: str


@dataclass(frozen=True)
class PasswordResetPreview:
    email: str
    expires_at: int


@dataclass(frozen=True)
class CompletedPasswordReset:
    subject: auth.Subject
    session_token: str


class PasswordResetInvalidError(Exception):
    """Ссылка не найдена, использована, отозвана или просрочена."""


def _now(now: int | None) -> int:
    return clock.now_seconds() if now is None else now


def reserve_password_reset_request(
    email: str,
    now: int | None = None,
) -> CooldownReservation:
    """Атомарно занимает окно повтора для нормализованного адреса.

    Один UPSERT с условием не теряет запросы при конкуренции SQLite. Адрес не
    проверяется на существование: для известного, неизвестного и ожидающего
    email поведение и ответ одинаковы.
    """
    timestamp = _now(now)
    normalized = normalize_email(email)
    statement = (
        sqlite_insert(password_reset_requests)
        .values(email_normalized=normalized, requested_at=timestamp)
        .on_conflict_do_update(
            index_elements=[password_reset_requests.c.email_normalized],
            set_={"requested_at": timestamp},
            where=password_reset_requests.c.requested_at
            <= timestamp - REQUEST_COOLDOWN_SECONDS,
        )
        .returning(password_reset_requests.c.requested_at)
    )

    previous: int | None = None
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            reserved = connection.execute(statement).first()
            if reserved is not None:
                return CooldownReservation(
                    accepted=True,
                    retry_after_seconds=0,
                    requested_at=timestamp,
                )
            previous = int(
                connection.execute(
                    select(password_reset_requests.c.requested_at).where(
                        password_reset_requests.c.email_normalized == normalized
                    )
                ).scalar_one()
            )
    finally:
        engine.dispose()

    assert previous is not None
    retry_after = REQUEST_COOLDOWN_SECONDS - (timestamp - previous)
    return CooldownReservation(accepted=False, retry_after_seconds=max(retry_after, 1))


def issue_password_reset(
    email: str,
    reserved_at: int,
    now: int | None = None,
) -> PasswordResetIssue | None:
    """Выпускает ссылку, только если запрос всё ещё последний и менеджер активен.

    Вызывается вне HTTP-ответа. В одной пишущей транзакции проверяются
    поколение окна повтора и текущее состояние менеджера, поэтому задание,
    выполняющееся после более нового запроса, не отзывает новую ссылку, а
    ссылка не выпускается после смены адреса или потери активности.
    ``None`` означает, что выпускать нечего; вызывающая сторона не должна
    различать причины в ответе.
    """
    normalized = normalize_email(email)
    timestamp = _now(now)
    issue: PasswordResetIssue | None = None
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            current = connection.execute(
                select(password_reset_requests.c.requested_at).where(
                    password_reset_requests.c.email_normalized == normalized
                )
            ).scalar_one_or_none()
            if current is not None and int(current) == reserved_at:
                manager = (
                    connection.execute(
                        select(managers.c.id, managers.c.email).where(
                            managers.c.email_normalized == normalized,
                            managers.c.password_hash.is_not(None),
                        )
                    )
                    .mappings()
                    .first()
                )
                if manager is not None:
                    token = new_token()
                    connection.execute(
                        update(one_time_links)
                        .where(
                            and_(
                                one_time_links.c.manager_id == int(manager["id"]),
                                one_time_links.c.purpose == PASSWORD_RESET_PURPOSE,
                                one_time_links.c.consumed_at.is_(None),
                                one_time_links.c.revoked_at.is_(None),
                            )
                        )
                        .values(revoked_at=timestamp)
                    )
                    connection.execute(
                        insert(one_time_links).values(
                            token_hash=token_digest(token),
                            manager_id=int(manager["id"]),
                            purpose=PASSWORD_RESET_PURPOSE,
                            created_at=timestamp,
                            expires_at=timestamp + PASSWORD_RESET_TTL_SECONDS,
                        )
                    )
                    issue = PasswordResetIssue(email=str(manager["email"]), token=token)
    finally:
        engine.dispose()

    return issue


def preview_password_reset(token: str, now: int | None = None) -> PasswordResetPreview:
    """Читает адрес действующей ссылки; ничего не изменяет."""
    timestamp = _now(now)
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(managers.c.email, one_time_links.c.expires_at)
                    .select_from(
                        one_time_links.join(
                            managers,
                            one_time_links.c.manager_id == managers.c.id,
                        )
                    )
                    .where(
                        and_(
                            one_time_links.c.token_hash == token_digest(token),
                            one_time_links.c.purpose == PASSWORD_RESET_PURPOSE,
                            one_time_links.c.consumed_at.is_(None),
                            one_time_links.c.revoked_at.is_(None),
                            one_time_links.c.expires_at > timestamp,
                            managers.c.password_hash.is_not(None),
                        )
                    )
                )
                .mappings()
                .first()
            )
    finally:
        engine.dispose()

    if row is None:
        raise PasswordResetInvalidError("password reset link is no longer valid")
    return PasswordResetPreview(
        email=str(row["email"]),
        expires_at=int(row["expires_at"]),
    )


def complete_password_reset(
    token: str,
    password: str,
    confirmation: str,
    now: int | None = None,
) -> CompletedPasswordReset:
    """Атомарно гасит ссылку, меняет пароль, отзывает сессии и создаёт новую.

    Политика пароля и точный повтор проверяются до погашения ссылки, поэтому
    ошибочный ввод не делает действующую ссылку непригодной. Все прежние
    сессии менеджера удаляются, блокировка входа снимается, новая браузерная
    сессия создаётся в той же транзакции.
    """
    security.validate_password_confirmation(password, confirmation)
    timestamp = _now(now)
    preview_password_reset(token, timestamp)
    password_hash = hash_password(password)

    completed: CompletedPasswordReset | None = None
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            consumed = (
                connection.execute(
                    update(one_time_links)
                    .where(
                        and_(
                            one_time_links.c.token_hash == token_digest(token),
                            one_time_links.c.purpose == PASSWORD_RESET_PURPOSE,
                            one_time_links.c.consumed_at.is_(None),
                            one_time_links.c.revoked_at.is_(None),
                            one_time_links.c.expires_at > timestamp,
                        )
                    )
                    .values(consumed_at=timestamp)
                    .returning(one_time_links.c.manager_id)
                )
                .first()
            )
            if consumed is None:
                raise PasswordResetInvalidError("password reset link is no longer valid")
            manager_id = int(consumed[0])

            manager = (
                connection.execute(
                    select(
                        managers.c.name,
                        managers.c.email,
                        managers.c.email_normalized,
                    ).where(
                        and_(
                            managers.c.id == manager_id,
                            managers.c.password_hash.is_not(None),
                        )
                    )
                )
                .mappings()
                .first()
            )
            if manager is None:
                raise PasswordResetInvalidError("password reset link is no longer valid")

            connection.execute(
                update(managers)
                .where(
                    and_(
                        managers.c.id == manager_id,
                        managers.c.password_hash.is_not(None),
                    )
                )
                .values(password_hash=password_hash)
            )
            connection.execute(delete(sessions).where(sessions.c.manager_id == manager_id))
            connection.execute(
                delete(login_attempts).where(
                    and_(
                        login_attempts.c.scope == auth.MANAGER_SCOPE,
                        login_attempts.c.identifier == str(manager["email_normalized"]),
                    )
                )
            )

            subject = auth.Subject(
                kind=auth.MANAGER,
                id=manager_id,
                name=str(manager["name"]),
                email=str(manager["email"]),
            )
            session_token = auth.create_session_record(connection, subject, timestamp)
            completed = CompletedPasswordReset(
                subject=subject,
                session_token=session_token,
            )
    finally:
        engine.dispose()

    assert completed is not None
    return completed
