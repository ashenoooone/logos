"""Теги диалогов (#8).

Решения ADR-0007: имя уникально в компании без учёта регистра, внешние пробелы
обрезаются; теги на диалогах видны всем менеджерам; менеджер создаёт теги и
удаляет только свои, без переименования; стандартные теги (``manager_id`` NULL)
создаёт, меняет и удаляет администратор. Удаление снимает тег с диалогов (CASCADE).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from logos_backend import clock
from logos_backend.db import _create_engine, conversation_tags, conversations, managers, tags

MAX_TAG_LENGTH = 50


class InvalidTagNameError(Exception):
    """Пустое или слишком длинное имя."""


class TagExistsError(Exception):
    """Тег с таким именем (без учёта регистра) уже есть."""


class TagNotFoundError(Exception):
    """Тега нет."""


class TagForbiddenError(Exception):
    """Менеджер удаляет чужой или стандартный тег."""


class ConversationNotFoundError(Exception):
    """Диалога нет."""


def _clean(name: str) -> tuple[str, str]:
    clean = name.strip()
    if not clean or len(clean) > MAX_TAG_LENGTH:
        raise InvalidTagNameError
    return clean, clean.casefold()


def conversation_tag_map(connection: Connection) -> dict[int, list[dict[str, object]]]:
    """Теги всех диалогов: ``{conversation_id: [{id, name}]}`` по алфавиту."""
    rows = connection.execute(
        select(conversation_tags.c.conversation_id, tags.c.id, tags.c.name)
        .join(tags, tags.c.id == conversation_tags.c.tag_id)
        .order_by(tags.c.name_normalized)
    ).all()
    result: dict[int, list[dict[str, object]]] = {}
    for conversation_id, tag_id, name in rows:
        result.setdefault(int(conversation_id), []).append({"id": tag_id, "name": name})
    return result


def list_tags(manager_id: int | None) -> list[dict[str, object]]:
    """Все теги с числом диалогов; ``own`` — создан этим менеджером."""
    count = (
        select(func.count())
        .select_from(conversation_tags)
        .where(conversation_tags.c.tag_id == tags.c.id)
        .scalar_subquery()
    )
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(tags.c.id, tags.c.name, tags.c.manager_id, managers.c.name, count)
                .select_from(tags.outerjoin(managers, managers.c.id == tags.c.manager_id))
                .order_by(tags.c.name_normalized)
            ).all()
    finally:
        engine.dispose()
    return [
        {
            "id": tag_id,
            "name": name,
            "standard": author_id is None,
            "own": author_id is not None and author_id == manager_id,
            "author": author_name,
            "conversation_count": int(used),
        }
        for tag_id, name, author_id, author_name, used in rows
    ]


def _tags_of(connection: Connection, conversation_id: int) -> list[dict[str, object]]:
    return conversation_tag_map(connection).get(conversation_id, [])


def attach(conversation_id: int, name: str, manager_id: int) -> list[dict[str, object]]:
    """Ставит тег на диалог: существующий без учёта регистра или новый от менеджера."""
    clean, normalized = _clean(name)
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            exists = connection.execute(
                select(conversations.c.id).where(conversations.c.id == conversation_id)
            ).first()
            if exists is None:
                raise ConversationNotFoundError
            connection.execute(
                insert(tags)
                .values(
                    name=clean,
                    name_normalized=normalized,
                    manager_id=manager_id,
                    created_at=clock.now_seconds(),
                )
                .on_conflict_do_nothing(index_elements=[tags.c.name_normalized])
            )
            tag_id = connection.execute(
                select(tags.c.id).where(tags.c.name_normalized == normalized)
            ).scalar_one()
            connection.execute(
                insert(conversation_tags)
                .values(conversation_id=conversation_id, tag_id=tag_id)
                .on_conflict_do_nothing()
            )
            return _tags_of(connection, conversation_id)
    finally:
        engine.dispose()


def detach(conversation_id: int, tag_id: int) -> list[dict[str, object]]:
    """Снимает тег с диалога; сам тег остаётся."""
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            exists = connection.execute(
                select(conversations.c.id).where(conversations.c.id == conversation_id)
            ).first()
            if exists is None:
                raise ConversationNotFoundError
            connection.execute(
                delete(conversation_tags).where(
                    conversation_tags.c.conversation_id == conversation_id,
                    conversation_tags.c.tag_id == tag_id,
                )
            )
            return _tags_of(connection, conversation_id)
    finally:
        engine.dispose()


def create_standard(name: str) -> None:
    clean, normalized = _clean(name)
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(tags).values(
                    name=clean,
                    name_normalized=normalized,
                    manager_id=None,
                    created_at=clock.now_seconds(),
                )
            )
    except IntegrityError as exc:
        raise TagExistsError from exc
    finally:
        engine.dispose()


def rename(tag_id: int, name: str) -> None:
    """Переименование — только администратор (менеджер свои теги не переименовывает)."""
    clean, normalized = _clean(name)
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            changed = connection.execute(
                update(tags)
                .where(tags.c.id == tag_id)
                .values(name=clean, name_normalized=normalized)
            ).rowcount
    except IntegrityError as exc:
        raise TagExistsError from exc
    finally:
        engine.dispose()
    if changed != 1:
        raise TagNotFoundError


def remove(tag_id: int, manager_id: int | None) -> None:
    """Удаляет тег и снимает его со всех диалогов.

    ``manager_id`` None — администратор, удаляет любой тег; менеджер — только свой.
    """
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            author: Any = connection.execute(
                select(tags.c.manager_id).where(tags.c.id == tag_id)
            ).first()
            if author is None:
                raise TagNotFoundError
            if manager_id is not None and author[0] != manager_id:
                raise TagForbiddenError
            connection.execute(delete(tags).where(tags.c.id == tag_id))
    finally:
        engine.dispose()
