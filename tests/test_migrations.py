"""Поведение миграций на временных базах SQLite."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, inspect, select
from sqlalchemy.exc import IntegrityError

from logos_backend.db import (
    ADMINISTRATORS_TABLE,
    AlreadyInitializedError,
    DatabaseNotReadyError,
    StorageError,
    administrators,
    create_first_admin,
    database_url,
    is_database_ready,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    return config


def use_database(monkeypatch: pytest.MonkeyPatch, path: Path) -> Path:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(path))
    return path


def stored_administrators() -> list[tuple[int, str, str]]:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            rows = connection.execute(select(administrators)).all()
    finally:
        engine.dispose()
    return [(row.id, row.login, row.password_hash) for row in rows]


def test_upgrade_from_empty_database_creates_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = use_database(monkeypatch, tmp_path / "logos.sqlite3")

    command.upgrade(alembic_config(), "head")

    assert database.is_file()
    engine = create_engine(database_url())
    try:
        inspector = inspect(engine)
        assert ADMINISTRATORS_TABLE in inspector.get_table_names()
        columns = {column["name"]: column for column in inspector.get_columns(ADMINISTRATORS_TABLE)}
    finally:
        engine.dispose()
    assert set(columns) == {"id", "login", "password_hash"}
    assert columns["id"]["nullable"] is False
    assert columns["login"]["nullable"] is False
    assert columns["password_hash"]["nullable"] is False


def test_repeated_upgrade_preserves_existing_administrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_database(monkeypatch, tmp_path / "logos.sqlite3")
    config = alembic_config()
    command.upgrade(config, "head")
    create_first_admin("root", "argon2id-hash")

    command.upgrade(config, "head")

    assert stored_administrators() == [(1, "root", "argon2id-hash")]


def test_upgrade_creates_parent_directories_for_special_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = use_database(monkeypatch, tmp_path / "data base" / "logos #1?&.sqlite3")

    command.upgrade(alembic_config(), "head")

    assert database.is_file()
    assert is_database_ready() is True


def test_upgrade_uses_default_path_relative_to_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LOGOS_DATABASE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    command.upgrade(alembic_config(), "head")

    assert (tmp_path / "data" / "logos.sqlite3").is_file()


def test_create_first_admin_on_unmigrated_database_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = use_database(monkeypatch, tmp_path / "logos.sqlite3")
    database.touch()

    with pytest.raises(DatabaseNotReadyError):
        create_first_admin("root", "hash")


def test_create_first_admin_without_database_directory_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_database(monkeypatch, tmp_path / "missing" / "logos.sqlite3")

    with pytest.raises(DatabaseNotReadyError):
        create_first_admin("root", "hash")


def test_second_create_does_not_change_existing_administrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_database(monkeypatch, tmp_path / "logos.sqlite3")
    command.upgrade(alembic_config(), "head")
    create_first_admin("root", "first-hash")

    with pytest.raises(AlreadyInitializedError) as error:
        create_first_admin("other", "second-hash")

    assert "first-hash" not in str(error.value)
    assert "second-hash" not in str(error.value)
    assert stored_administrators() == [(1, "root", "first-hash")]


def test_partial_schema_is_not_treated_as_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = use_database(monkeypatch, tmp_path / "logos.sqlite3")
    engine = create_engine(database_url())
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE administrators (id INTEGER)")
    finally:
        engine.dispose()

    assert database.is_file()
    assert is_database_ready() is False
    with pytest.raises(DatabaseNotReadyError):
        create_first_admin("root", "hash")


def test_database_enforces_single_administrator_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_database(monkeypatch, tmp_path / "logos.sqlite3")
    command.upgrade(alembic_config(), "head")
    create_first_admin("root", "hash")

    engine = create_engine(database_url())
    try:
        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(
                insert(administrators).values(id=2, login="second", password_hash="hash")
            )
    finally:
        engine.dispose()
    assert stored_administrators() == [(1, "root", "hash")]


def test_concurrent_creates_leave_exactly_one_administrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_database(monkeypatch, tmp_path / "logos.sqlite3")
    command.upgrade(alembic_config(), "head")

    results: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(4)

    def attempt(index: int) -> None:
        barrier.wait()
        try:
            create_first_admin(f"login-{index}", f"hash-{index}")
        except AlreadyInitializedError:
            outcome = "exists"
        except StorageError:
            outcome = "storage"
        else:
            outcome = "created"
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 4
    assert results.count("created") == 1
    assert results.count("exists") == 3
    assert len(stored_administrators()) == 1
