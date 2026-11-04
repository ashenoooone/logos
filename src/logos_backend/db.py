"""Доступ к базе данных для создания первого администратора и проверок готовности."""

from __future__ import annotations

from sqlalchemy import (
    URL,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    inspect,
    select,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from logos_backend.config import get_database_path

ADMINISTRATORS_TABLE = "administrators"
ADMINISTRATORS_COLUMNS = frozenset({"id", "login", "password_hash"})

metadata = MetaData()

administrators = Table(
    ADMINISTRATORS_TABLE,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("login", String, nullable=False),
    Column("password_hash", String, nullable=False),
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


def _create_engine() -> Engine:
    return create_engine(database_url(), poolclass=NullPool)


def _schema_ready(connection: Connection) -> bool:
    inspector = inspect(connection)
    if ADMINISTRATORS_TABLE not in inspector.get_table_names():
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
