"""Заметки о клиентах (#14).

Заметка живёт в карточке клиента, а не в переписке. У неё автор, дата и
видимость: «Вся команда» (по умолчанию) или «Только я». Автор видит свои
заметки всегда, чужие приватные — нет. Изменять и удалять может автор, а
администратор — любую заметку. Правка проверяет ``version``: если заметку
успели изменить, сохранение отклоняется и возвращает актуальную версию.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Connection, RowMapping

from logos_backend import auth, clock
from logos_backend.db import (
    _create_engine,
    client_notes,
    conversations,
    immediate_transaction,
    managers,
)

MAX_NOTE_LENGTH = 2000

TEAM = "team"


class InvalidNoteError(Exception):
    """Пустой или слишком длинный текст."""


class ConversationNotFoundError(Exception):
    """Диалога нет."""


class NoteNotFoundError(Exception):
    """Заметки нет или она не видна субъекту."""


class NoteForbiddenError(Exception):
    """Менеджер пытается изменить чужую заметку."""


class NoteChangedError(Exception):
    """Заметку изменили после того, как её открыли; содержит актуальную версию."""

    def __init__(self, note: dict[str, object]) -> None:
        super().__init__("Note was changed")
        self.note = note


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _clean(text: str) -> str:
    clean = text.strip()
    if not clean or len(clean) > MAX_NOTE_LENGTH:
        raise InvalidNoteError
    return clean


def _payload(row: RowMapping, subject: auth.Subject) -> dict[str, object]:
    own = (
        subject.kind == auth.MANAGER
        and row["manager_id"] is not None
        and int(row["manager_id"]) == subject.id
    )
    return {
        "id": row["id"],
        "text": row["text"],
        "visibility": row["visibility"],
        "author": row["author"],
        "own": own,
        "editable": own or subject.kind == auth.ADMINISTRATOR,
        "version": row["version"],
        "created_at": _iso(int(row["created_at"])),
        "updated_at": _iso(int(row["updated_at"])),
    }


def _rows(
    connection: Connection, conversation_id: int, subject: auth.Subject
) -> list[dict[str, object]]:
    """Видимые субъекту заметки диалога, новые сверху."""
    statement = (
        select(*client_notes.c, managers.c.name.label("author"))
        .select_from(
            client_notes.outerjoin(managers, managers.c.id == client_notes.c.manager_id)
        )
        .where(client_notes.c.conversation_id == conversation_id)
        .order_by(client_notes.c.created_at.desc(), client_notes.c.id.desc())
    )
    if subject.kind != auth.ADMINISTRATOR:
        # ponytail: видимость фильтруется в SQL без отдельной таблицы доступа.
        statement = statement.where(
            or_(client_notes.c.visibility == TEAM, client_notes.c.manager_id == subject.id)
        )
    return [_payload(row, subject) for row in connection.execute(statement).mappings().all()]


def _conversation_exists(connection: Connection, conversation_id: int) -> bool:
    return (
        connection.execute(
            select(conversations.c.id).where(conversations.c.id == conversation_id)
        ).first()
        is not None
    )


def list_notes(conversation_id: int, subject: auth.Subject) -> list[dict[str, object]]:
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            if not _conversation_exists(connection, conversation_id):
                raise ConversationNotFoundError
            return _rows(connection, conversation_id, subject)
    finally:
        engine.dispose()


def create_note(
    conversation_id: int, text: str, visibility: str, manager_id: int
) -> list[dict[str, object]]:
    """Создаёт заметку менеджера; ``visibility`` — «Вся команда» или «Только я»."""
    clean = _clean(text)
    now = clock.now_seconds()
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            if not _conversation_exists(connection, conversation_id):
                raise ConversationNotFoundError
            connection.execute(
                insert(client_notes).values(
                    conversation_id=conversation_id,
                    manager_id=manager_id,
                    text=clean,
                    visibility=visibility,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            subject = auth.Subject(kind=auth.MANAGER, id=manager_id)
            return _rows(connection, conversation_id, subject)
    finally:
        engine.dispose()


def _find(connection: Connection, note_id: int) -> RowMapping | None:
    return (
        connection.execute(
            select(*client_notes.c, managers.c.name.label("author"))
            .select_from(
                client_notes.outerjoin(managers, managers.c.id == client_notes.c.manager_id)
            )
            .where(client_notes.c.id == note_id)
        )
        .mappings()
        .first()
    )


def _check(note: RowMapping, subject: auth.Subject) -> None:
    if subject.kind == auth.ADMINISTRATOR:
        return
    author = note["manager_id"]
    if author is None or int(author) != subject.id:
        raise NoteForbiddenError


def update_note(
    conversation_id: int,
    note_id: int,
    text: str,
    visibility: str,
    version: int,
    subject: auth.Subject,
) -> list[dict[str, object]]:
    """Меняет текст и видимость; при чужой правке отдаёт актуальную версию."""
    clean = _clean(text)
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            note = _find(connection, note_id)
            if note is None or int(note["conversation_id"]) != conversation_id:
                raise NoteNotFoundError
            _check(note, subject)
            if int(note["version"]) != version:
                raise NoteChangedError(_payload(note, subject))
            connection.execute(
                update(client_notes)
                .where(client_notes.c.id == note_id)
                .values(
                    text=clean,
                    visibility=visibility,
                    version=version + 1,
                    updated_at=clock.now_seconds(),
                )
            )
            return _rows(connection, conversation_id, subject)
    finally:
        engine.dispose()


def delete_note(
    conversation_id: int, note_id: int, subject: auth.Subject
) -> list[dict[str, object]]:
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            note = _find(connection, note_id)
            if note is None or int(note["conversation_id"]) != conversation_id:
                raise NoteNotFoundError
            _check(note, subject)
            connection.execute(delete(client_notes).where(client_notes.c.id == note_id))
            return _rows(connection, conversation_id, subject)
    finally:
        engine.dispose()
