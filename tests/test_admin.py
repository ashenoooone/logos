"""Поведенческие тесты закрытой консольной команды создания первого администратора."""

from __future__ import annotations

import getpass
import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from logos_backend import cli

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class _FakeTerminal:
    def isatty(self) -> bool:
        return True

    def readline(self) -> str:  # pragma: no cover - CLI никогда сюда не доходит
        raise AssertionError("the CLI must not read stdin directly")


class _NotATerminal:
    def isatty(self) -> bool:
        return False


def _migrate(database: Path) -> None:
    environment = os.environ.copy()
    environment["LOGOS_DATABASE_PATH"] = str(database)
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert database.exists()


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    template = tmp_path_factory.mktemp("admin-cli") / "template.sqlite3"
    _migrate(template)
    return template


@pytest.fixture()
def database_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "logos.sqlite3"
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(path))
    return path


@pytest.fixture()
def migrated_database(
    migrated_template: Path,
    database_path: Path,
) -> Path:
    shutil.copyfile(migrated_template, database_path)
    return database_path


def _rows(database: Path) -> list[tuple[int, str, str]]:
    with closing(sqlite3.connect(database)) as connection:
        return connection.execute(
            "SELECT id, login, password_hash FROM administrators ORDER BY id"
        ).fetchall()


def _table_names(database: Path) -> list[str]:
    if not database.exists():
        return []
    with closing(sqlite3.connect(database)) as connection:
        return [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]


def _run_cli(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    passwords: Iterable[str] = (),
    *,
    interactive: bool = True,
    interrupt: BaseException | None = None,
) -> int:
    monkeypatch.setattr(
        sys,
        "stdin",
        _FakeTerminal() if interactive else _NotATerminal(),
    )

    pending = iter(passwords)

    def fake_getpass(prompt: str = "Password: ") -> str:
        if interrupt is not None:
            raise interrupt
        try:
            return next(pending)
        except StopIteration:  # pragma: no cover - страховка от неожиданного запроса пароля
            raise AssertionError(f"unexpected password prompt: {prompt!r}") from None

    monkeypatch.setattr(getpass, "getpass", fake_getpass)
    return cli.main(argv)


def test_creates_administrator_with_argon2id_hash(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run_cli(
        monkeypatch,
        ["create-admin", "--login", "root"],
        ["correct horse", "correct horse"],
    )

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "root" in captured.out

    rows = _rows(migrated_database)
    assert len(rows) == 1
    administrator_id, login, password_hash = rows[0]
    assert administrator_id == 1
    assert login == "root"
    assert password_hash.startswith("$argon2id$")

    hasher = PasswordHasher()
    assert hasher.verify(password_hash, "correct horse") is True
    with pytest.raises(VerifyMismatchError):
        hasher.verify(password_hash, "wrong horse")

    assert b"correct horse" not in migrated_database.read_bytes()


def test_login_is_stored_unchanged(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run_cli(
        monkeypatch,
        ["create-admin", "--login", "  Root  "],
        ["secret", "secret"],
    )

    assert code == 0, capsys.readouterr().err
    assert _rows(migrated_database)[0][1] == "  Root  "


def test_repeated_same_login_keeps_original_hash(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        _run_cli(
            monkeypatch,
            ["create-admin", "--login", "root"],
            ["first-password", "first-password"],
        )
        == 0
    )
    original = _rows(migrated_database)
    capsys.readouterr()

    code = _run_cli(
        monkeypatch,
        ["create-admin", "--login", "root"],
        ["second-password", "second-password"],
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "already exists" in captured.err
    assert "second-password" not in captured.err
    assert _rows(migrated_database) == original

    hasher = PasswordHasher()
    assert hasher.verify(original[0][2], "first-password") is True
    with pytest.raises(VerifyMismatchError):
        hasher.verify(original[0][2], "second-password")


def test_repeated_different_login_keeps_original_identity(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        _run_cli(
            monkeypatch,
            ["create-admin", "--login", "root"],
            ["first-password", "first-password"],
        )
        == 0
    )
    original = _rows(migrated_database)
    capsys.readouterr()

    code = _run_cli(
        monkeypatch,
        ["create-admin", "--login", "other"],
        ["other-password", "other-password"],
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "already exists" in captured.err
    assert "other-password" not in captured.err
    assert _rows(migrated_database) == original


def test_mismatched_passwords_write_nothing(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run_cli(
        monkeypatch,
        ["create-admin", "--login", "root"],
        ["first", "second"],
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "do not match" in captured.err
    assert _rows(migrated_database) == []


def test_empty_password_writes_nothing(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run_cli(
        monkeypatch,
        ["create-admin", "--login", "root"],
        ["", ""],
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "must not be empty" in captured.err
    assert _rows(migrated_database) == []


def test_non_interactive_stdin_is_rejected_without_prompting(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run_cli(
        monkeypatch,
        ["create-admin", "--login", "root"],
        interactive=False,
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "terminal" in captured.err
    assert "Traceback" not in captured.err
    assert _rows(migrated_database) == []


@pytest.mark.parametrize("interrupt", [EOFError(), KeyboardInterrupt()])
def test_cancelled_password_input_is_reported(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    interrupt: BaseException,
) -> None:
    code = _run_cli(
        monkeypatch,
        ["create-admin", "--login", "root"],
        interrupt=interrupt,
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "cancelled" in captured.err
    assert "Traceback" not in captured.err
    assert _rows(migrated_database) == []


@pytest.mark.parametrize("login", ["", "   ", "\t\n"])
def test_empty_login_is_a_usage_error(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    login: str,
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        _run_cli(
            monkeypatch,
            ["create-admin", "--login", login],
            ["secret", "secret"],
        )

    assert excinfo.value.code == 2
    assert _rows(migrated_database) == []


def test_missing_login_is_a_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as excinfo:
        _run_cli(monkeypatch, ["create-admin"], ["secret", "secret"])

    assert excinfo.value.code == 2


def test_unmigrated_database_points_to_migrations(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run_cli(
        monkeypatch,
        ["create-admin", "--login", "root"],
        ["secret", "secret"],
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "alembic upgrade head" in captured.err
    assert "secret" not in captured.err
    assert "Traceback" not in captured.err
    assert "administrators" not in _table_names(database_path)


def test_echo_enabled_password_prompt_writes_nothing(
    migrated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # getpass falls back to echo-enabled reading when it cannot disable echo;
    # the CLI must abort that fallback before any password is read.
    monkeypatch.setattr(sys, "stdin", _FakeTerminal())
    # fallback_getpass есть в рантайме, но отсутствует в typeshed,
    # поэтому берём его напрямую из пространства имён модуля.
    fallback_getpass = vars(getpass)["fallback_getpass"]
    monkeypatch.setattr(getpass, "getpass", fallback_getpass)

    code = cli.main(["create-admin", "--login", "root"])

    captured = capsys.readouterr()
    assert code == 1
    assert "cannot disable terminal echo" in captured.err
    assert "Traceback" not in captured.err
    assert _rows(migrated_database) == []
