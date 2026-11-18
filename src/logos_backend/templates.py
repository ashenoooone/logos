"""Шаблоны ответов (#11).

Шаблоны общие на компанию: все менеджеры видят и используют любой шаблон.
Менеджер создаёт свои шаблоны и меняет/удаляет только их; чужие доступны
только для подстановки. Шаблон не отправляется сам — текст попадает в поле
ввода (решает фронтенд). Переменные ``{клиент}``, ``{номер}``, ``{дата}``
подставляет менеджер в предпросмотре, поэтому в БД хранится исходный текст.
"""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.engine import Connection

from logos_backend import clock
from logos_backend.db import _create_engine, managers, reply_templates

MAX_NAME_LENGTH = 100
MAX_TEXT_LENGTH = 4096


class InvalidTemplateError(Exception):
    """Пустое имя или пустой/слишком длинный текст."""


class TemplateNotFoundError(Exception):
    """Шаблона нет."""


class TemplateForbiddenError(Exception):
    """Менеджер меняет или удаляет чужой шаблон."""


def _clean(name: str, text: str) -> tuple[str, str]:
    clean_name = name.strip()
    clean_text = text.strip()
    if not clean_name or len(clean_name) > MAX_NAME_LENGTH:
        raise InvalidTemplateError("name")
    if not clean_text or len(clean_text) > MAX_TEXT_LENGTH:
        raise InvalidTemplateError("text")
    return clean_name, clean_text


def list_templates(manager_id: int) -> list[dict[str, object]]:
    """Все шаблоны компании по алфавиту; ``own`` — создан этим менеджером."""
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(
                    reply_templates.c.id,
                    reply_templates.c.name,
                    reply_templates.c.text,
                    reply_templates.c.manager_id,
                    managers.c.name,
                )
                .select_from(
                    reply_templates.outerjoin(
                        managers, managers.c.id == reply_templates.c.manager_id
                    )
                )
                .order_by(reply_templates.c.name, reply_templates.c.id)
            ).all()
    finally:
        engine.dispose()
    return [
        {
            "id": template_id,
            "name": name,
            "text": text,
            "own": author_id == manager_id,
            "author": author_name,
        }
        for template_id, name, text, author_id, author_name in rows
    ]


def create_template(manager_id: int, name: str, text: str) -> list[dict[str, object]]:
    clean_name, clean_text = _clean(name, text)
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                reply_templates.insert().values(
                    name=clean_name,
                    text=clean_text,
                    manager_id=manager_id,
                    created_at=clock.now_seconds(),
                )
            )
    finally:
        engine.dispose()
    return list_templates(manager_id)


def _owned(connection: Connection, template_id: int, manager_id: int) -> bool:
    author = connection.execute(
        select(reply_templates.c.manager_id).where(reply_templates.c.id == template_id)
    ).first()
    if author is None:
        raise TemplateNotFoundError
    if author[0] != manager_id:
        raise TemplateForbiddenError
    return True


def update_template(
    template_id: int, manager_id: int, name: str, text: str
) -> list[dict[str, object]]:
    clean_name, clean_text = _clean(name, text)
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            _owned(connection, template_id, manager_id)
            connection.execute(
                update(reply_templates)
                .where(reply_templates.c.id == template_id)
                .values(name=clean_name, text=clean_text)
            )
    finally:
        engine.dispose()
    return list_templates(manager_id)


def remove_template(template_id: int, manager_id: int) -> list[dict[str, object]]:
    """Удаляет шаблон; уже отправленные сообщения хранят свой текст и не меняются."""
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            _owned(connection, template_id, manager_id)
            connection.execute(delete(reply_templates).where(reply_templates.c.id == template_id))
    finally:
        engine.dispose()
    return list_templates(manager_id)
