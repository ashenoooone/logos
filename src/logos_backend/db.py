"""Схема SQLite, доступ к ней и проверки готовности.

Здесь описаны Core-таблицы, создание первого администратора, проверка
мигрированной схемы и общий помощник пишущей транзакции.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import (
    URL,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    insert,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from logos_backend.config import get_database_path

ADMINISTRATORS_TABLE = "administrators"
ADMINISTRATORS_COLUMNS = frozenset({"id", "login", "password_hash"})

MANAGERS_TABLE = "managers"
SESSIONS_TABLE = "sessions"
ONE_TIME_LINKS_TABLE = "one_time_links"
LOGIN_ATTEMPTS_TABLE = "login_attempts"
PASSWORD_RESET_REQUESTS_TABLE = "password_reset_requests"
EMAIL_CHANGES_TABLE = "email_changes"
CHANNELS_TABLE = "channels"

REQUIRED_TABLES = frozenset(
    {
        ADMINISTRATORS_TABLE,
        MANAGERS_TABLE,
        SESSIONS_TABLE,
        ONE_TIME_LINKS_TABLE,
        LOGIN_ATTEMPTS_TABLE,
        PASSWORD_RESET_REQUESTS_TABLE,
        EMAIL_CHANGES_TABLE,
        CHANNELS_TABLE,
    }
)

metadata = MetaData()

administrators = Table(
    ADMINISTRATORS_TABLE,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("login", String, nullable=False),
    Column("password_hash", String, nullable=False),
)

managers = Table(
    MANAGERS_TABLE,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False),
    Column("email_normalized", String, nullable=False, unique=True),
    Column("password_hash", String, nullable=True),
    Column("created_at", Integer, nullable=False),
    CheckConstraint("length(trim(name)) > 0", name="ck_managers_name_not_blank"),
    CheckConstraint("length(trim(email)) > 0", name="ck_managers_email_not_blank"),
)

login_attempts = Table(
    LOGIN_ATTEMPTS_TABLE,
    metadata,
    Column("scope", String, primary_key=True),
    Column("identifier", String, primary_key=True),
    Column("failed_count", Integer, nullable=False),
    Column("locked_until", Integer, nullable=True),
    Column("updated_at", Integer, nullable=False),
    CheckConstraint(
        "scope IN ('administrator', 'manager')",
        name="ck_login_attempts_scope",
    ),
    CheckConstraint("failed_count >= 0", name="ck_login_attempts_count"),
)

sessions = Table(
    SESSIONS_TABLE,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("token_hash", String, nullable=False, unique=True),
    Column(
        "administrator_id",
        Integer,
        ForeignKey("administrators.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column(
        "manager_id",
        Integer,
        ForeignKey("managers.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column("created_at", Integer, nullable=False),
    Column("expires_at", Integer, nullable=False),
    CheckConstraint(
        "(administrator_id IS NOT NULL AND manager_id IS NULL) "
        "OR (administrator_id IS NULL AND manager_id IS NOT NULL)",
        name="ck_sessions_single_owner",
    ),
    CheckConstraint("expires_at > created_at", name="ck_sessions_expiry"),
)

one_time_links = Table(
    ONE_TIME_LINKS_TABLE,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("token_hash", String, nullable=False, unique=True),
    Column(
        "manager_id",
        Integer,
        ForeignKey("managers.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("purpose", String, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("expires_at", Integer, nullable=False),
    Column("consumed_at", Integer, nullable=True),
    Column("revoked_at", Integer, nullable=True),
    CheckConstraint(
        "purpose IN ('invitation', 'password_reset')",
        name="ck_one_time_links_purpose",
    ),
    CheckConstraint("expires_at > created_at", name="ck_one_time_links_expiry"),
)

password_reset_requests = Table(
    PASSWORD_RESET_REQUESTS_TABLE,
    metadata,
    Column("email_normalized", String, primary_key=True),
    Column("requested_at", Integer, nullable=False),
)

# Одна неподтверждённая смена email на менеджера; подтверждение удаляет строку.
email_changes = Table(
    EMAIL_CHANGES_TABLE,
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "manager_id",
        Integer,
        ForeignKey("managers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("token_hash", String, nullable=False, unique=True),
    Column("new_email", String, nullable=False),
    Column("new_email_normalized", String, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("expires_at", Integer, nullable=False),
    CheckConstraint("expires_at > created_at", name="ck_email_changes_expiry"),
)

# Один Telegram-бот на установку (ADR-0007): строка с id=1. Отключение очищает
# токен, но строку не удаляет — переписка из #6 будет ссылаться на канал.
channels = Table(
    CHANNELS_TABLE,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("bot_username", String, nullable=False),
    Column("token", String, nullable=True),
    Column("status", String, nullable=False),
    Column("error", String, nullable=True),
    Column("update_offset", Integer, nullable=False),
    Column("connected_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    CheckConstraint("id = 1", name="ck_channels_single"),
    CheckConstraint(
        "status IN ('connected', 'error', 'disconnected')", name="ck_channels_status"
    ),
)

Index(
    "uq_one_time_links_active",
    one_time_links.c.manager_id,
    one_time_links.c.purpose,
    unique=True,
    sqlite_where=text("consumed_at IS NULL AND revoked_at IS NULL"),
)


class DatabaseNotReadyError(Exception):
    """База данных недоступна или её схема не мигрирована."""


class AlreadyInitializedError(Exception):
    """Первый администратор уже существует."""


class StorageError(Exception):
    """Администратора не удалось сохранить по причине, отличной от указанных выше."""


def database_url() -> URL:
    """Строит URL SQLite с безопасным экранированием настроенного пути к файлу."""
    return URL.create("sqlite", database=str(get_database_path().absolute()))


def _enable_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def _create_engine() -> Engine:
    engine = create_engine(
        database_url(),
        poolclass=NullPool,
        connect_args={"timeout": 30},
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    return engine


@contextmanager
def immediate_transaction(engine: Engine) -> Iterator[Connection]:
    """Пишущая транзакция SQLite с блокировкой записи до чтения.

    ``BEGIN IMMEDIATE`` берёт блокировку записи сразу, поэтому другой писатель
    не сможет зафиксировать изменение между проверкой прочитанной строки и
    записью решения. Нужна там, где проверка и запись обязаны быть атомарны.
    Исключение внутри блока откатывает транзакцию.
    """
    connection = engine.connect()
    try:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()


def _schema_ready(connection: Connection) -> bool:
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    if not table_names.issuperset(REQUIRED_TABLES):
        return False
    columns = {column["name"] for column in inspector.get_columns(ADMINISTRATORS_TABLE)}
    return columns >= ADMINISTRATORS_COLUMNS


def is_database_ready() -> bool:
    """Возвращает, существует ли требуемая сервису мигрированная схема."""
    engine = _create_engine()
    try:
        with engine.connect() as connection:
            return _schema_ready(connection)
    except (SQLAlchemyError, OSError):
        return False
    finally:
        engine.dispose()


def create_first_admin(login: str, password_hash: str) -> None:
    """Сохраняет единственного первого администратора или завершается ошибкой, не меняя данные."""
    engine = _create_engine()
    try:
        try:
            with engine.connect() as connection:
                ready = _schema_ready(connection)
        except (SQLAlchemyError, OSError) as exc:
            raise DatabaseNotReadyError("Database is not ready. Apply migrations first.") from exc

        if not ready:
            raise DatabaseNotReadyError("Database is not ready. Apply migrations first.")

        try:
            with engine.begin() as connection:
                connection.execute(
                    insert(administrators).values(id=1, login=login, password_hash=password_hash)
                )
        except IntegrityError as exc:
            if _administrator_exists(engine):
                raise AlreadyInitializedError("The first administrator already exists.") from exc
            raise StorageError("Could not store the administrator.") from exc
        except SQLAlchemyError as exc:
            raise StorageError("Could not store the administrator.") from exc
    finally:
        engine.dispose()


def _administrator_exists(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            return connection.execute(select(administrators.c.id)).first() is not None
    except SQLAlchemyError:
        return False
