"""Фейковые данные для демонстрации продукта; применяет миграция 0009.

Менеджеры, теги, диалоги с перепиской и демо-бот Telegram. Только на пустой
базе (нет ни менеджеров, ни диалогов), чтобы не смешать демо с настоящими
данными. Не для production: известные пароли.
"""

from __future__ import annotations

import json
import logging
import os

from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection

from logos_backend import channels, inbox
from logos_backend.db import (
    channels as channels_table,
)
from logos_backend.db import (
    conversation_tags,
    conversations,
    managers,
    messages,
    saved_filters,
    tags,
)
from logos_backend.security import hash_password, normalize_email

logger = logging.getLogger(__name__)

# Токен демо-бота только из окружения: репозиторий публичный.
DEMO_BOT_TOKEN = os.environ.get("LOGOS_DEMO_BOT_TOKEN", "")
MANAGER_PASSWORD = "demo1234"

MANAGERS = [
    ("Анна Смирнова", "anna@demo.logos"),
    ("Игорь Петров", "igor@demo.logos"),
    ("Мария Козлова", "maria@demo.logos"),
]
# None — стандартный тег; иначе индекс менеджера-владельца в MANAGERS.
TAGS: list[tuple[str, int | None]] = [
    ("VIP", None),
    ("Оплата", None),
    ("Доставка", None),
    ("Возврат", None),
    ("Новый клиент", None),
    ("Перезвонить", 0),
]

# Реплика: (минут назад, направление, текст, статус исходящего).
Line = tuple[int, str, str, str | None]
# Диалог: (имя клиента, теги, реплики, прочитаны ли входящие).
DIALOGS: list[tuple[str, list[str], list[Line], bool]] = [
    (
        "Екатерина Волкова",
        ["Новый клиент"],
        [
            (12, "in", "Здравствуйте! Подскажите, есть ли диван «Осло» в сером цвете?", None),
            (9, "in", "И сколько займёт доставка в Казань?", None),
        ],
        False,
    ),
    (
        "Дмитрий Орлов",
        ["VIP", "Оплата"],
        [
            (180, "in", "Добрый день, выставите, пожалуйста, счёт на юрлицо.", None),
            (172, "out", "Добрый день, Дмитрий! Пришлите реквизиты компании.", "delivered"),
            (165, "in", "Реквизиты во вложении.", None),
            (150, "out", "Спасибо, счёт отправим в течение часа.", "delivered"),
            (35, "in", "Оплатили, проверьте, пожалуйста.", None),
        ],
        False,
    ),
    (
        "Ольга Невская",
        ["Доставка"],
        [
            (60 * 26, "in", "Когда приедет мой заказ №10482?", None),
            (60 * 25, "out", "Ольга, заказ у курьера, привезём завтра 10–14.", "delivered"),
            (60 * 25 - 5, "in", "Отлично, спасибо!", None),
        ],
        True,
    ),
    (
        "Сергей Кузнецов",
        ["Возврат"],
        [
            (60 * 5, "in", "Пришёл стул с царапиной на спинке. Хочу вернуть.", None),
            (60 * 5 - 10, "out", "Сергей, извините! Пришлите фото повреждения.", "delivered"),
            (60 * 4, "in", "Фото не могу сделать сейчас, вечером пришлю.", None),
            (60 * 4 - 3, "out", "Хорошо, оформим возврат сразу после фото.", "failed"),
        ],
        True,
    ),
    (
        "@alex_design",
        ["VIP", "Перезвонить"],
        [
            (60 * 50, "in", "Нужна консультация по комплектации офиса на 20 мест.", None),
            (60 * 49, "out", "Александр, удобно созвониться завтра в 11:00?", "delivered"),
            (60 * 48, "in", "Да, давайте.", None),
        ],
        True,
    ),
    (
        "Наталья Белова",
        [],
        [
            (60 * 24 * 3, "in", "Работаете в выходные?", None),
            (60 * 24 * 3 - 20, "out", "Да, по субботам с 10 до 18.", "delivered"),
        ],
        True,
    ),
    (
        "Павел Морозов",
        ["Новый клиент", "Оплата"],
        [
            (3, "in", "Можно оплатить частями?", None),
        ],
        False,
    ),
]

DOCUMENT_TEXT = (
    "ООО «Орлов и партнёры»\nИНН 7701234567\nКПП 770101001\n"
    "Р/с 40702810900000012345 в АО «Демо-Банк»\n"
).encode()


def _not_empty(connection: Connection) -> bool:
    total = 0
    for table in (managers, conversations):
        total += connection.execute(select(func.count()).select_from(table)).scalar_one()
    return total > 0


def _connect_bot(connection: Connection, now: int) -> None:
    """Как ``channels.connect``, но в транзакции миграции; без сети — без бота."""
    if not DEMO_BOT_TOKEN:
        logger.warning("Demo bot skipped: LOGOS_DEMO_BOT_TOKEN is not set")
        return
    try:
        username = channels.check_token(DEMO_BOT_TOKEN)
        channels._call(
            DEMO_BOT_TOKEN,
            "deleteWebhook",
            {"drop_pending_updates": "true"},
            channels.REQUEST_TIMEOUT_SECONDS,
        )
    except (channels.InvalidTokenError, channels.TelegramUnavailableError):
        logger.warning("Demo bot not connected; connect it on /channels")
        return
    connection.execute(
        insert(channels_table)
        .prefix_with("OR IGNORE")
        .values(
            id=1,
            name=channels.DEFAULT_NAME,
            bot_username=username,
            token=DEMO_BOT_TOKEN,
            status=channels.CONNECTED,
            update_offset=0,
            connected_at=now,
            updated_at=now,
        )
    )


def seed(connection: Connection, now: int) -> None:
    if _not_empty(connection):
        logger.warning("Demo data skipped: database already has managers or conversations")
        return
    password_hash = hash_password(MANAGER_PASSWORD)
    manager_ids = [
        connection.execute(
            insert(managers)
            .values(
                name=name,
                email=email,
                email_normalized=normalize_email(email),
                password_hash=password_hash,
                created_at=now - 60 * 60 * 24 * 30,
            )
            .returning(managers.c.id)
        ).scalar_one()
        for name, email in MANAGERS
    ]
    tag_ids = {
        name: connection.execute(
            insert(tags)
            .values(
                name=name,
                name_normalized=name.casefold(),
                manager_id=None if owner is None else manager_ids[owner],
                created_at=now - 60 * 60 * 24 * 7,
            )
            .returning(tags.c.id)
        ).scalar_one()
        for name, owner in TAGS
    }

    # Сначала старые диалоги: id сообщений растут вместе со временем.
    ordered = sorted(enumerate(DIALOGS), key=lambda item: -item[1][2][0][0])
    for index, (name, dialog_tags, lines, read) in ordered:
        times = [now - minutes * 60 for minutes, *_ in lines]
        conversation_id = connection.execute(
            insert(conversations)
            .values(
                # Вне диапазона реальных id Telegram, чтобы не слиться с живым чатом.
                chat_id=9_000_000_000_000 + index,
                name=name,
                created_at=times[0],
                last_message_at=times[-1],
            )
            .returning(conversations.c.id)
        ).scalar_one()
        for number, ((_, direction, text, status), at) in enumerate(zip(lines, times, strict=True)):
            values: dict[str, object] = {
                "conversation_id": conversation_id,
                "direction": direction,
                "telegram_message_id": number + 1 if status != "failed" else None,
                "kind": "text",
                "text": text,
                "status": status,
                "created_at": at,
                "read_at": at + 60 if direction == "in" and read else None,
            }
            if text == "Реквизиты во вложении.":
                values.update(
                    kind="document",
                    file_name="Реквизиты.txt",
                    file_size=len(DOCUMENT_TEXT),
                    file_path=inbox._save_file(DOCUMENT_TEXT),
                )
            connection.execute(insert(messages).values(**values))
        for tag_name in dialog_tags:
            connection.execute(
                insert(conversation_tags).values(
                    conversation_id=conversation_id, tag_id=tag_ids[tag_name]
                )
            )

    connection.execute(
        insert(saved_filters).values(
            manager_id=manager_ids[0],
            name="VIP без ответа",
            filters=json.dumps(
                {"channel": [], "tag": [tag_ids["VIP"]], "status": ["unread"]},
                ensure_ascii=False,
            ),
            created_at=now,
        )
    )
    _connect_bot(connection, now)
