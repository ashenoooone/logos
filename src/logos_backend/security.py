"""Нормализация email, политика пароля и криптографические примитивы."""

from __future__ import annotations

import hashlib
import secrets
from contextlib import suppress

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from email_validator import EmailNotValidError, validate_email

MIN_PASSWORD_LENGTH = 8
TOKEN_BYTES = 32

_DUMMY_PASSWORD = "logos-dummy-password-for-timing-only"
_PASSWORD_HASHER = PasswordHasher(type=Type.ID)
DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash(_DUMMY_PASSWORD)


class PasswordPolicyError(ValueError):
    """Пароль не удовлетворяет согласованной политике или повтор не совпадает."""


class InvalidEmailError(ValueError):
    """Адрес не является синтаксически корректным email."""


def normalize_email(email: str) -> str:
    """Обрезает внешние пробелы и приводит адрес к регистронезависимому виду.

    Точки и ``+``-алиасы не объединяются: провайдер-зависимая нормализация запрещена.
    """
    return email.strip().casefold()


def validate_email_address(email: str) -> None:
    """Проверяет синтаксис адреса без проверки доставляемости домена."""
    candidate = email.strip()
    if not candidate or len(candidate) > 254:
        raise InvalidEmailError("email is not valid")
    try:
        validate_email(candidate, check_deliverability=False)
    except EmailNotValidError as exc:
        raise InvalidEmailError("email is not valid") from exc


def validate_password(password: str) -> None:
    """Проверяет новый пароль по ADR-0006; существующие пароли так не оцениваются."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError("password must contain at least 8 characters")
    if not any(character.isalpha() for character in password):
        raise PasswordPolicyError("password must contain a letter")
    if not any(character.isdecimal() for character in password):
        raise PasswordPolicyError("password must contain a decimal digit")


def validate_password_confirmation(password: str, confirmation: str) -> None:
    """Требует точного совпадения повтора и проверяет политику без strip/нормализации."""
    if password != confirmation:
        raise PasswordPolicyError("passwords do not match")
    validate_password(password)


def hash_password(password: str) -> str:
    """Возвращает Argon2id-хеш пароля с параметрами библиотеки по умолчанию."""
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Проверяет пароль; повреждённый или чужой хеш считается несовпадением."""
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except InvalidHashError:
        # Повреждённый хеш в БД — несовпадение, но проверка по фиктивному хешу
        # сохраняет стоимость Argon2 и не выдаёт состояние хранилища по времени.
        with suppress(VerificationError):
            _PASSWORD_HASHER.verify(DUMMY_PASSWORD_HASH, password)
        return False
    except VerificationError:
        return False


def consume_dummy_verification(password: str) -> None:
    """Выполняет проверку по фиктивному хешу для выравнивания времени неизвестных учёток."""
    verify_password(DUMMY_PASSWORD_HASH, password)


def new_token() -> str:
    """Возвращает непредсказуемый opaque-токен для cookie или одноразовой ссылки."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_digest(token: str) -> str:
    """Возвращает SHA-256-дайджест токена, который только и хранится в БД."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
