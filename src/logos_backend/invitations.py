"""Приглашения менеджеров: создание, повторная отправка и установка пароля.

Ссылка приглашения одноразовая и действует 72 часа. В БД хранится только
дайджест токена. Отправка письма выполняется вне транзакции: SMTP и SQLite не
образуют атомарной операции, поэтому сбой SMTP оставляет ожидающего менеджера
и позволяет администратору явно повторить отправку.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError

from logos_backend import auth, clock, security
from logos_backend.db import (
    _create_engine,
    managers,
    one_time_links,
)
from logos_backend.security import hash_password, new_token, normalize_email, token_digest

INVITATION_TTL_SECONDS = 72 * 60 * 60
INVITATION_PURPOSE = "invitation"

PENDING = "pending"
ACTIVE = "active"


@dataclass(frozen=True)
class ManagerSummary:
    id: int
    name: str
    email: str
    status: str
    created_at: int


@dataclass(frozen=True)
class InvitationIssue:
    """Ожидающий менеджер и токен только что выпущенной ссылки (в БД — дайджест)."""

    manager: ManagerSummary
    token: str


@dataclass(frozen=True)
class InvitationPreview:
    name: str
    email: str
    expires_at: int


@dataclass(frozen=True)
class AcceptedInvitation:
    subject: auth.Subject
    session_token: str


class InvalidManagerNameError(ValueError):
    """Имя менеджера пустое или состоит из пробелов."""


class EmailAlreadyExistsError(Exception):
    """Нормализованный email уже занят другой учётной записью менеджера."""


class ManagerNotFoundError(Exception):
    """Менеджер с указанным идентификатором отсутствует."""


class ManagerNotPendingError(Exception):
    """Приглашение можно менять только до задания пароля."""


class InvitationInvalidError(Exception):
    """Ссылка не найдена, использована, отозвана или просрочена."""


def _now(now: int | None) -> int:
    return clock.now_seconds() if now is None else now


def _summary(row: RowMapping) -> ManagerSummary:
    password_hash = row["password_hash"]
    return ManagerSummary(
        id=int(row["id"]),
        name=str(row["name"]),
        email=str(row["email"]),
        status=PENDING if password_hash is None else ACTIVE,
        created_at=int(row["created_at"]),
    )


def list_managers() -> list[ManagerSummary]:
    """Возвращает всех менеджеров в порядке создания."""
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            rows = (
                connection.execute(
                    select(
                        managers.c.id,
                        managers.c.name,
                        managers.c.email,
                        managers.c.password_hash,
                        managers.c.created_at,
                    ).order_by(managers.c.created_at, managers.c.id)
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()
    return [_summary(row) for row in rows]


def create_pending_manager_with_invitation(
    name: str,
    email: str,
    now: int | None = None,
) -> InvitationIssue:
    """Создаёт ожидающего менеджера и одноразовую ссылку в одной транзакции."""
    trimmed_name = name.strip()
    if not trimmed_name:
        raise InvalidManagerNameError("manager name must not be blank")
    trimmed_email = email.strip()
    security.validate_email_address(trimmed_email)
    normalized = normalize_email(trimmed_email)

    timestamp = _now(now)
    token = new_token()
    engine = _create_engine()
    try:
        try:
            with engine.begin() as connection:
                row = (
                    connection.execute(
                        insert(managers)
                        .values(
                            name=trimmed_name,
                            email=trimmed_email,
                            email_normalized=normalized,
                            password_hash=None,
                            created_at=timestamp,
                        )
                        .returning(
                            managers.c.id,
                            managers.c.name,
                            managers.c.email,
                            managers.c.password_hash,
                            managers.c.created_at,
                        )
                    )
                    .mappings()
                    .one()
                )
                connection.execute(
                    insert(one_time_links).values(
                        token_hash=token_digest(token),
                        manager_id=int(row["id"]),
                        purpose=INVITATION_PURPOSE,
                        created_at=timestamp,
                        expires_at=timestamp + INVITATION_TTL_SECONDS,
                    )
                )
        except IntegrityError as exc:
            raise EmailAlreadyExistsError(
                "A manager with this email already exists."
            ) from exc
    finally:
        engine.dispose()

    return InvitationIssue(manager=_summary(row), token=token)


def reissue_invitation(
    manager_id: int,
    email: str | None = None,
    now: int | None = None,
) -> InvitationIssue:
    """Исправляет email ожидающего менеджера и выпускает новую ссылку.

    Старая действующая ссылка отзывается. Активному менеджеру операция
    недоступна. Возвращаемое письмо адресуется уже сохранённой версии email.
    """
    new_email: str | None = None
    normalized: str | None = None
    if email is not None:
        new_email = email.strip()
        security.validate_email_address(new_email)
        normalized = normalize_email(new_email)

    timestamp = _now(now)
    token = new_token()
    issue: InvitationIssue | None = None
    engine = _create_engine()
    try:
        try:
            with engine.begin() as connection:
                row = (
                    connection.execute(
                        select(
                            managers.c.id,
                            managers.c.name,
                            managers.c.email,
                            managers.c.email_normalized,
                            managers.c.password_hash,
                            managers.c.created_at,
                        ).where(managers.c.id == manager_id)
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    raise ManagerNotFoundError("manager not found")
                if row["password_hash"] is not None:
                    raise ManagerNotPendingError("manager has already accepted the invitation")

                current_email = str(row["email"])
                if new_email is not None:
                    assert normalized is not None
                    updated = (
                        connection.execute(
                            update(managers)
                            .where(
                                and_(
                                    managers.c.id == manager_id,
                                    managers.c.password_hash.is_(None),
                                )
                            )
                            .values(email=new_email, email_normalized=normalized)
                            .returning(managers.c.email)
                        )
                        .mappings()
                        .first()
                    )
                    if updated is None:
                        raise ManagerNotPendingError("manager has already accepted the invitation")
                    current_email = str(updated["email"])

                connection.execute(
                    update(one_time_links)
                    .where(
                        and_(
                            one_time_links.c.manager_id == manager_id,
                            one_time_links.c.purpose == INVITATION_PURPOSE,
                            one_time_links.c.consumed_at.is_(None),
                            one_time_links.c.revoked_at.is_(None),
                        )
                    )
                    .values(revoked_at=timestamp)
                )
                connection.execute(
                    insert(one_time_links).values(
                        token_hash=token_digest(token),
                        manager_id=manager_id,
                        purpose=INVITATION_PURPOSE,
                        created_at=timestamp,
                        expires_at=timestamp + INVITATION_TTL_SECONDS,
                    )
                )

                still_pending = connection.execute(
                    select(managers.c.password_hash).where(managers.c.id == manager_id)
                ).scalar_one()
                if still_pending is not None:
                    raise ManagerNotPendingError("manager has already accepted the invitation")

                issue = InvitationIssue(
                    manager=ManagerSummary(
                        id=manager_id,
                        name=str(row["name"]),
                        email=current_email,
                        status=PENDING,
                        created_at=int(row["created_at"]),
                    ),
                    token=token,
                )
        except IntegrityError as exc:
            raise EmailAlreadyExistsError(
                "A manager with this email already exists."
            ) from exc
    finally:
        engine.dispose()

    assert issue is not None
    return issue


def preview_invitation(token: str, now: int | None = None) -> InvitationPreview:
    """Читает данные действующего приглашения; ничего не изменяет."""
    timestamp = _now(now)
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        managers.c.name,
                        managers.c.email,
                        one_time_links.c.expires_at,
                    )
                    .select_from(
                        one_time_links.join(
                            managers,
                            one_time_links.c.manager_id == managers.c.id,
                        )
                    )
                    .where(
                        and_(
                            one_time_links.c.token_hash == token_digest(token),
                            one_time_links.c.purpose == INVITATION_PURPOSE,
                            one_time_links.c.consumed_at.is_(None),
                            one_time_links.c.revoked_at.is_(None),
                            one_time_links.c.expires_at > timestamp,
                            managers.c.password_hash.is_(None),
                        )
                    )
                )
                .mappings()
                .first()
            )
    finally:
        engine.dispose()

    if row is None:
        raise InvitationInvalidError("invitation is no longer valid")
    return InvitationPreview(
        name=str(row["name"]),
        email=str(row["email"]),
        expires_at=int(row["expires_at"]),
    )


def accept_invitation(
    token: str,
    password: str,
    confirmation: str,
    now: int | None = None,
) -> AcceptedInvitation:
    """Атомарно гасит ссылку, активирует менеджера и создаёт браузерную сессию."""
    security.validate_password_confirmation(password, confirmation)
    timestamp = _now(now)

    preview_invitation(token, timestamp)
    password_hash = hash_password(password)

    accepted: AcceptedInvitation | None = None
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            consumed = (
                connection.execute(
                    update(one_time_links)
                    .where(
                        and_(
                            one_time_links.c.token_hash == token_digest(token),
                            one_time_links.c.purpose == INVITATION_PURPOSE,
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
                raise InvitationInvalidError("invitation is no longer valid")

            manager_id = int(consumed[0])
            activated = (
                connection.execute(
                    update(managers)
                    .where(
                        and_(
                            managers.c.id == manager_id,
                            managers.c.password_hash.is_(None),
                        )
                    )
                    .values(password_hash=password_hash)
                    .returning(managers.c.name, managers.c.email)
                )
                .mappings()
                .first()
            )
            if activated is None:
                raise InvitationInvalidError("invitation is no longer valid")

            subject = auth.Subject(
                kind=auth.MANAGER,
                id=manager_id,
                name=str(activated["name"]),
                email=str(activated["email"]),
            )
            session_token = auth.create_session_record(connection, subject, timestamp)
            accepted = AcceptedInvitation(subject=subject, session_token=session_token)
    finally:
        engine.dispose()

    assert accepted is not None
    return accepted
