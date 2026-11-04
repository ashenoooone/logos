"""«Входящие» (#6): приём сообщений Telegram, диалоги, прочитанность, ответы.

Решения ADR-0007: только личные чаты с ботом; текст, фото и документы, прочие
типы — «неподдерживаемое сообщение»; прочитанность общая на компанию;
«доставлено» = успешный ответ Bot API, иначе «Не доставлено» и ручной повтор.
Вложения лежат файлами в ``attachments/`` рядом с SQLite.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import IntegrityError

from logos_backend import channels, clock, tags
from logos_backend.config import get_database_path
from logos_backend.db import (
    _create_engine,
    conversations,
    immediate_transaction,
    inbox_preferences,
    messages,
    saved_filters,
)

logger = logging.getLogger(__name__)

# Bot API: getFile скачивает до 20 МБ. Тот же предел для файлов ответа, хотя
# sendDocument принимает до 50 МБ: файл целиком держится в памяти запроса.
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_LENGTH = 4096  # sendMessage: 1-4096 символов
MAX_CAPTION_LENGTH = 1024  # подпись к документу: 0-1024 символа

IN = "in"
OUT = "out"
SENDING = "sending"
DELIVERED = "delivered"
FAILED = "failed"

SORTS = ("newest", "oldest", "unread")  # ADR-0007; по умолчанию newest


class ConversationNotFoundError(Exception):
    """Диалога нет."""


class NotRetryableError(Exception):
    """Повторить можно только недоставленный ответ."""


def attachments_dir() -> Path:
    return get_database_path().absolute().parent / "attachments"


def _save_file(content: bytes) -> str:
    directory = attachments_dir()
    directory.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex
    (directory / name).write_bytes(content)
    return name


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _client_name(chat: dict[str, Any]) -> str:
    full = " ".join(str(chat.get(key) or "").strip() for key in ("first_name", "last_name"))
    if full.strip():
        return full.strip()
    if chat.get("username"):
        return f"@{chat['username']}"
    return f"Клиент {chat.get('id')}"


def _parse(message: dict[str, Any]) -> tuple[str, str | None, str | None, int | None]:
    """Тип, file_id, имя и размер файла входящего сообщения."""
    photo = message.get("photo")
    if isinstance(photo, list) and photo and isinstance(photo[-1], dict):
        largest = photo[-1]  # Bot API отдаёт размеры по возрастанию
        return "photo", str(largest.get("file_id")), "photo.jpg", largest.get("file_size")
    document = message.get("document")
    if isinstance(document, dict):
        name = str(document.get("file_name") or "file")
        return "document", str(document.get("file_id")), name, document.get("file_size")
    if isinstance(message.get("text"), str):
        return "text", None, None, None
    return "unsupported", None, None, None


def _known(chat_id: int, message_id: int) -> bool:
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            return (
                connection.execute(
                    select(messages.c.id)
                    .join(conversations, conversations.c.id == messages.c.conversation_id)
                    .where(
                        conversations.c.chat_id == chat_id,
                        messages.c.direction == IN,
                        messages.c.telegram_message_id == message_id,
                    )
                ).first()
                is not None
            )
    finally:
        engine.dispose()


def _touch_conversation(connection: Connection, chat_id: int, name: str | None, at: int) -> int:
    """Создаёт диалог или поднимает его время последнего сообщения; возвращает id."""
    values: dict[str, Any] = {"chat_id": chat_id, "name": name or "", "created_at": at}
    changes: dict[str, Any] = {
        "last_message_at": func.max(conversations.c.last_message_at, at),
    }
    if name:
        changes["name"] = name
    return int(
        connection.execute(
            insert(conversations)
            .values(**values, last_message_at=at)
            .on_conflict_do_update(index_elements=[conversations.c.chat_id], set_=changes)
            .returning(conversations.c.id)
        ).scalar_one()
    )


def store_update(token: str, update_: dict[str, Any]) -> None:
    """Сохраняет входящее сообщение из обновления ``getUpdates``; прочее игнорирует."""
    message = update_.get("message")
    if not isinstance(message, dict):
        return
    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("type") != "private":
        return
    chat_id, message_id = int(chat["id"]), int(message["message_id"])
    if _known(chat_id, message_id):
        return

    kind, file_id, file_name, file_size = _parse(message)
    file_path = None
    if file_id is not None:
        try:
            content = channels.download_file(token, file_id, MAX_FILE_BYTES)
        except (channels.TelegramUnavailableError, channels.InvalidTokenError):
            # ponytail: файл не скачался — показываем «файл недоступен» без
            # повторной попытки; повтор нужен, если такие сбои станут частыми.
            logger.warning("Could not download a Telegram attachment")
            content = None
        if content is not None:
            file_path = _save_file(content)
            file_size = len(content)

    at = int(message.get("date") or clock.now_seconds())
    text = message.get("text") if kind == "text" else message.get("caption")
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            conversation_id = _touch_conversation(connection, chat_id, _client_name(chat), at)
            connection.execute(
                insert(messages).values(
                    conversation_id=conversation_id,
                    direction=IN,
                    telegram_message_id=message_id,
                    kind=kind,
                    text=text if isinstance(text, str) else None,
                    file_name=file_name,
                    file_size=file_size,
                    file_path=file_path,
                    created_at=at,
                )
            )
    except IntegrityError:
        if file_path:  # параллельный дубль уже сохранён
            (attachments_dir() / file_path).unlink(missing_ok=True)
    finally:
        engine.dispose()


def _message_payload(row: RowMapping) -> dict[str, object]:
    file = None
    if row["file_name"] is not None:
        file = {
            "name": row["file_name"],
            "size": row["file_size"],
            "available": row["file_path"] is not None,
        }
    return {
        "id": row["id"],
        "direction": row["direction"],
        "kind": row["kind"],
        "text": row["text"],
        "file": file,
        "status": row["status"],
        "created_at": _iso(int(row["created_at"])),
    }


def _unread_filter() -> Any:
    return and_(messages.c.direction == IN, messages.c.read_at.is_(None))


def list_conversations() -> dict[str, object]:
    """Все диалоги, свежие сверху, с последним сообщением и числом непрочитанных."""
    inner = messages.alias("inner")  # иначе подзапросы скоррелируют с внешним messages
    last_id = (
        select(func.max(inner.c.id))
        .where(inner.c.conversation_id == conversations.c.id)
        .scalar_subquery()
    )
    unread = (
        select(func.count())
        .select_from(inner)
        .where(
            inner.c.conversation_id == conversations.c.id,
            inner.c.direction == IN,
            inner.c.read_at.is_(None),
        )
        .scalar_subquery()
    )
    statement = (
        select(
            conversations.c.id.label("conversation_id"),
            conversations.c.name,
            conversations.c.last_message_at,
            unread.label("unread_count"),
            *[column for column in messages.c if column.name != "conversation_id"],
        )
        .select_from(conversations.outerjoin(messages, messages.c.id == last_id))
        .order_by(conversations.c.last_message_at.desc(), conversations.c.id.desc())
    )
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
            last_incoming_id, incoming_total = connection.execute(
                select(func.max(messages.c.id), func.count()).where(messages.c.direction == IN)
            ).one()
            tag_map = tags.conversation_tag_map(connection)
    finally:
        engine.dispose()
    items = [
        {
            "id": row["conversation_id"],
            "provider": "telegram",
            "name": row["name"],
            "last_message_at": _iso(int(row["last_message_at"])),
            "unread_count": int(row["unread_count"]),
            "last_message": _message_payload(row) if row["id"] is not None else None,
            "tags": tag_map.get(int(row["conversation_id"]), []),
        }
        for row in rows
    ]
    return {
        "conversations": items,
        "unread_total": sum(int(row["unread_count"]) for row in rows),
        "last_incoming_id": last_incoming_id,
        # Счётчик всех входящих: разница даёт «N новых сообщений» (#7).
        "incoming_total": int(incoming_total),
    }


def get_conversation(conversation_id: int) -> dict[str, object]:
    """Диалог со всей перепиской по порядку."""
    # ponytail: вся переписка одним ответом; постраничность — когда диалоги станут длинными.
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            conversation = (
                connection.execute(
                    select(conversations).where(conversations.c.id == conversation_id)
                )
                .mappings()
                .first()
            )
            rows = (
                connection.execute(
                    select(messages)
                    .where(messages.c.conversation_id == conversation_id)
                    .order_by(messages.c.id)
                )
                .mappings()
                .all()
            )
            conversation_tags = tags.conversation_tag_map(connection).get(conversation_id, [])
    finally:
        engine.dispose()
    if conversation is None:
        raise ConversationNotFoundError
    return {
        "conversation": {
            "id": conversation["id"],
            "provider": "telegram",
            "name": conversation["name"],
            "tags": conversation_tags,
        },
        "messages": [_message_payload(row) for row in rows],
    }


def mark_read(conversation_id: int) -> None:
    """Помечает входящие диалога прочитанными — для всех менеджеров сразу."""
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            exists = connection.execute(
                select(conversations.c.id).where(conversations.c.id == conversation_id)
            ).first()
            if exists is None:
                raise ConversationNotFoundError
            connection.execute(
                update(messages)
                .where(messages.c.conversation_id == conversation_id, _unread_filter())
                .values(read_at=clock.now_seconds())
            )
    finally:
        engine.dispose()


def _load_message(message_id: int) -> RowMapping | None:
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            return (
                connection.execute(
                    select(messages, conversations.c.chat_id)
                    .join(conversations, conversations.c.id == messages.c.conversation_id)
                    .where(messages.c.id == message_id)
                )
                .mappings()
                .first()
            )
    finally:
        engine.dispose()


def _send(row: RowMapping) -> int:
    """Отправляет ответ в Telegram; возвращает message_id или поднимает ошибку."""
    token = channels.current_token()
    if token is None:
        raise channels.TelegramUnavailableError
    if row["file_path"] is not None:
        content = (attachments_dir() / row["file_path"]).read_bytes()
        result = channels._call(
            token,
            "sendDocument",
            {"chat_id": row["chat_id"], "caption": row["text"] or ""},
            channels.FILE_TIMEOUT_SECONDS,
            file=("document", str(row["file_name"]), content),
        )
    else:
        result = channels._call(
            token,
            "sendMessage",
            {"chat_id": row["chat_id"], "text": row["text"]},
            channels.REQUEST_TIMEOUT_SECONDS,
        )
    if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
        raise channels.TelegramUnavailableError
    return int(result["message_id"])


def _deliver(message_id: int) -> dict[str, object]:
    row = _load_message(message_id)
    assert row is not None
    values: dict[str, Any]
    try:
        values = {"status": DELIVERED, "telegram_message_id": _send(row)}
    except (
        channels.TelegramUnavailableError,
        channels.TelegramConflictError,
        channels.InvalidTokenError,
        OSError,
    ):
        # Таймаут тоже сюда: результат неизвестен, повтор — вручную (ADR-0007).
        values = {"status": FAILED}
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            saved = (
                connection.execute(
                    update(messages)
                    .where(messages.c.id == message_id)
                    .values(**values)
                    .returning(*messages.c)
                )
                .mappings()
                .one()
            )
    finally:
        engine.dispose()
    return _message_payload(saved)


def reply(
    conversation_id: int, text: str, file: tuple[str, bytes] | None = None
) -> dict[str, object]:
    """Сохраняет ответ (текст не теряется при сбое) и сразу отправляет его."""
    file_path = _save_file(file[1]) if file else None
    now = clock.now_seconds()
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            chat_id = connection.execute(
                select(conversations.c.chat_id).where(conversations.c.id == conversation_id)
            ).scalar()
            if chat_id is None:
                raise ConversationNotFoundError
            _touch_conversation(connection, int(chat_id), None, now)
            message_id = connection.execute(
                insert(messages)
                .values(
                    conversation_id=conversation_id,
                    direction=OUT,
                    kind="document" if file else "text",
                    text=text or None,
                    file_name=file[0] if file else None,
                    file_size=len(file[1]) if file else None,
                    file_path=file_path,
                    status=SENDING,
                    created_at=now,
                )
                .returning(messages.c.id)
            ).scalar_one()
    except ConversationNotFoundError:
        if file_path:
            (attachments_dir() / file_path).unlink(missing_ok=True)
        raise
    finally:
        engine.dispose()
    return _deliver(int(message_id))


def retry(message_id: int) -> dict[str, object]:
    """Повторно отправляет недоставленный ответ; двойной повтор отсекает блокировка."""
    engine = _create_engine()
    try:
        with immediate_transaction(engine) as connection:
            claimed = connection.execute(
                update(messages)
                .where(
                    messages.c.id == message_id,
                    messages.c.direction == OUT,
                    messages.c.status == FAILED,
                )
                .values(status=SENDING)
            ).rowcount
    finally:
        engine.dispose()
    if claimed != 1:
        raise NotRetryableError
    return _deliver(message_id)


def attachment(message_id: int) -> tuple[Path, str, str] | None:
    """Путь, имя и тип сохранённого файла сообщения."""
    row = _load_message(message_id)
    if row is None or row["file_path"] is None:
        return None
    return attachments_dir() / str(row["file_path"]), str(row["file_name"]), str(row["kind"])


def get_preferences(manager_id: int) -> dict[str, object]:
    """Сортировка и сохранённые наборы фильтров менеджера (#7)."""
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            sort = connection.execute(
                select(inbox_preferences.c.sort).where(
                    inbox_preferences.c.manager_id == manager_id
                )
            ).scalar()
            rows = connection.execute(
                select(saved_filters.c.id, saved_filters.c.name, saved_filters.c.filters)
                .where(saved_filters.c.manager_id == manager_id)
                .order_by(saved_filters.c.id)
            ).all()
    finally:
        engine.dispose()
    return {
        "sort": sort or SORTS[0],
        "saved_filters": [
            {"id": row_id, "name": name, "filters": json.loads(filters)}
            for row_id, name, filters in rows
        ],
    }


def set_sort(manager_id: int, sort: str) -> None:
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(inbox_preferences)
                .values(manager_id=manager_id, sort=sort)
                .on_conflict_do_update(
                    index_elements=[inbox_preferences.c.manager_id], set_={"sort": sort}
                )
            )
    finally:
        engine.dispose()


def save_filter(manager_id: int, name: str, filters: dict[str, object]) -> None:
    """Сохраняет набор фильтров; то же название перезаписывает набор."""
    encoded = json.dumps(filters, ensure_ascii=False)
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                insert(saved_filters)
                .values(
                    manager_id=manager_id,
                    name=name,
                    filters=encoded,
                    created_at=clock.now_seconds(),
                )
                .on_conflict_do_update(
                    index_elements=[saved_filters.c.manager_id, saved_filters.c.name],
                    set_={"filters": encoded},
                )
            )
    finally:
        engine.dispose()


def delete_filter(manager_id: int, filter_id: int) -> None:
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                saved_filters.delete().where(
                    saved_filters.c.id == filter_id, saved_filters.c.manager_id == manager_id
                )
            )
    finally:
        engine.dispose()
