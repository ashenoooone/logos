"""Закрытая консольная команда создания первого администратора."""

from __future__ import annotations

import argparse
import getpass
import sys
import warnings

from argon2 import PasswordHasher

from logos_backend.db import (
    AlreadyInitializedError,
    DatabaseNotReadyError,
    create_first_admin,
)

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

_MIGRATION_HINT = "error: database is not ready; run 'alembic upgrade head' first."
_SECURE_INPUT_ERROR = "error: cannot disable terminal echo; password input aborted."


def _login_argument(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("login must not be empty")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logos-backend",
        description="Administrative commands for the Logos backend.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin = subparsers.add_parser(
        "create-admin",
        help="Create the first administrator (interactive password prompt).",
    )
    create_admin.add_argument(
        "--login",
        required=True,
        type=_login_argument,
        help="login of the first administrator; stored unchanged",
    )
    return parser


def _stdin_is_terminal() -> bool:
    stdin = sys.stdin
    return stdin is not None and stdin.isatty()


def _read_password() -> str | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Password: ")
            confirmation = getpass.getpass("Repeat password: ")
    except getpass.GetPassWarning:
        print(_SECURE_INPUT_ERROR, file=sys.stderr)
        return None
    except (EOFError, KeyboardInterrupt):
        print("error: password input cancelled.", file=sys.stderr)
        return None

    if not password:
        print("error: password must not be empty.", file=sys.stderr)
        return None
    if password != confirmation:
        print("error: passwords do not match.", file=sys.stderr)
        return None
    return password


def _create_admin(login: str) -> int:
    if not _stdin_is_terminal():
        print(
            "error: a terminal is required to read the password.",
            file=sys.stderr,
        )
        return EXIT_FAILURE

    password = _read_password()
    if password is None:
        return EXIT_FAILURE

    try:
        password_hash = PasswordHasher().hash(password)
    except Exception:
        print("error: failed to hash the password.", file=sys.stderr)
        return EXIT_FAILURE

    try:
        create_first_admin(login=login, password_hash=password_hash)
    except AlreadyInitializedError:
        print("error: an administrator already exists.", file=sys.stderr)
        return EXIT_FAILURE
    except DatabaseNotReadyError:
        print(_MIGRATION_HINT, file=sys.stderr)
        return EXIT_FAILURE
    except Exception:
        print("error: failed to create the administrator.", file=sys.stderr)
        return EXIT_FAILURE

    print(f"Administrator '{login}' created.")
    return EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return _create_admin(args.login)
