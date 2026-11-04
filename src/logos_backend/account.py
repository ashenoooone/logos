"""Профиль менеджера: имя, смена email с подтверждением и смена пароля.

Новый email начинает работать только после перехода по одноразовой ссылке,
которая действует 24 часа (ADR-0007). До подтверждения вход — по старому
адресу. Неверный текущий пароль учитывается в тех же счётчиках, что и вход:
украденная сессия не даёт перебирать пароль без ограничений.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from logos_backend import auth, clock, security
from logos_backend.db import (
    _create_engine,
    email_changes,
    immediate_transaction,
    login_attempts,
    managers,
    sessions,
)
from logos_backend.security import hash_password, new_token, normalize_email, token_digest

EMAIL_CHANGE_TTL_SECONDS = 24 * 60 * 60


class InvalidNameError(ValueError):
    """Имя пустое или состоит из пробелов."""


class EmailTakenError(Exception):
    """Адрес уже занят другим менеджером."""


class EmailUnchangedError(Exception):
    """Новый адрес совпадает с текущим."""


class EmailChangeInvalidError(Exception):
    """Ссылка подтверждения не найдена, использована, заменена или просрочена."""


class CurrentPasswordRequiredError(Exception):
    """Текущий пароль не указан."""


@dataclass(frozen=True)
class EmailChangeIssue:
    email: str
    token: str


@dataclass(frozen=True)
class ConfirmedEmail:
    manager_id: int
    email: str


def _now(now: int | None) -> int:
    return clock.now_seconds() if now is None else now


def rename(manager_id: int, name: str) -> auth.Subject:
    trimmed = name.strip()
    if not trimmed:
        raise InvalidNameError("name must not be blank")
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            row = (
                connection.execute(
                    update(managers)
                    .where(managers.c.id == manager_id)
                    .values(name=trimmed)
                    .returning(managers.c.name, managers.c.email)
                )
                .mappings()
                .one()
            )
    finally:
        engine.dispose()
    return auth.Subject(
        kind=auth.MANAGER, id=manager_id, name=str(row["name"]), email=str(row["email"])
    )


def request_email_change(manager_id: int, email: str, now: int | None = None) -> EmailChangeIssue:
    """Сохраняет неподтверждённый адрес и выпускает ссылку; прежняя ссылка заменяется."""
    new_email = email.strip()
    security.validate_email_address(new_email)
    normalized = normalize_email(new_email)
    timestamp = _now(now)
    token = new_token()

    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            current = connection.execute(
                select(managers.c.email_normalized).where(managers.c.id == manager_id)
            ).scalar_one()
            if str(current) == normalized:
                raise EmailUnchangedError("email is unchanged")
            taken = connection.execute(
                select(managers.c.id).where(managers.c.email_normalized == normalized)
            ).first()
            if taken is not None:
                raise EmailTakenError("email is taken")
            connection.execute(
                delete(email_changes).where(email_changes.c.manager_id == manager_id)
            )
            connection.execute(
                insert(email_changes).values(
                    manager_id=manager_id,
                    token_hash=token_digest(token),
                    new_email=new_email,
                    new_email_normalized=normalized,
                    created_at=timestamp,
                    expires_at=timestamp + EMAIL_CHANGE_TTL_SECONDS,
                )
            )
    finally:
        engine.dispose()
    return EmailChangeIssue(email=new_email, token=token)


def confirm_email_change(token: str, now: int | None = None) -> ConfirmedEmail:
    """Гасит ссылку и делает новый адрес рабочим. Сессии не отзываются (ADR-0007)."""
    timestamp = _now(now)
    engine = _create_engine()
    try:
        try:
            with immediate_transaction(engine) as connection:
                row = (
                    connection.execute(
                        delete(email_changes)
                        .where(email_changes.c.token_hash == token_digest(token))
                        .returning(
                            email_changes.c.manager_id,
                            email_changes.c.new_email,
                            email_changes.c.new_email_normalized,
                            email_changes.c.expires_at,
                        )
                    )
                    .mappings()
                    .first()
                )
                if row is None or int(row["expires_at"]) <= timestamp:
                    raise EmailChangeInvalidError("email change link is no longer valid")
                connection.execute(
                    update(managers)
                    .where(managers.c.id == int(row["manager_id"]))
                    .values(
                        email=str(row["new_email"]),
                        email_normalized=str(row["new_email_normalized"]),
                    )
                )
        except IntegrityError as exc:
            # Адрес заняли между запросом и подтверждением; ссылка остаётся непогашенной.
            raise EmailTakenError("email is taken") from exc
    finally:
        engine.dispose()
    return ConfirmedEmail(manager_id=int(row["manager_id"]), email=str(row["new_email"]))


def change_password(
    manager_id: int,
    session_token: str,
    current_password: str,
    new_password: str,
    confirmation: str,
    sign_out_other_devices: bool,
    now: int | None = None,
) -> None:
    """Меняет пароль по верному текущему; текущая сессия всегда сохраняется.

    Неверный текущий пароль — ``auth.InvalidCredentialsError`` или
    ``auth.AccountLockedError``, как при входе по тому же email.
    """
    if not current_password:
        raise CurrentPasswordRequiredError("current password is required")
    security.validate_password_confirmation(new_password, confirmation)
    timestamp = _now(now)

    engine = _create_engine()
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(managers.c.email_normalized, managers.c.password_hash).where(
                        managers.c.id == manager_id
                    )
                )
                .mappings()
                .one()
            )
        identifier = str(row["email_normalized"])
        verified_hash = str(row["password_hash"])
        auth._ensure_not_locked(auth.MANAGER_SCOPE, identifier, timestamp)
        if not security.verify_password(verified_hash, current_password):
            auth._record_failure(auth.MANAGER_SCOPE, identifier, timestamp)

        password_hash = hash_password(new_password)
        with immediate_transaction(engine) as connection:
            updated = connection.execute(
                update(managers)
                .where(and_(managers.c.id == manager_id, managers.c.password_hash == verified_hash))
                .values(password_hash=password_hash)
                .returning(managers.c.id)
            ).first()
            if updated is not None:
                connection.execute(
                    delete(login_attempts).where(
                        login_attempts.c.scope == auth.MANAGER_SCOPE,
                        login_attempts.c.identifier == identifier,
                    )
                )
                if sign_out_other_devices:
                    connection.execute(
                        delete(sessions).where(
                            sessions.c.manager_id == manager_id,
                            sessions.c.token_hash != token_digest(session_token),
                        )
                    )
    finally:
        engine.dispose()

    if updated is None:
        # Пароль изменили параллельно: проверенный текущий уже не действует.
        auth._record_failure(auth.MANAGER_SCOPE, identifier, timestamp)
