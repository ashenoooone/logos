"""Отправка писем по SMTP без очереди и автоматических повторов.

Модуль выполняет ровно одну попытку передачи письма SMTP-серверу. Токены
одноразовых ссылок передаются только в письмах: они не пишутся в лог и не
попадают в HTTP-ответы. Таймаут ограничивает время сетевого вызова.
"""

from __future__ import annotations

import smtplib
import ssl
from contextlib import suppress
from email.message import EmailMessage
from urllib.parse import quote

from logos_backend.config import SmtpSettings, get_public_base_url, get_smtp_settings

ALLOWED_TLS_MODES = frozenset({"none", "starttls", "ssl"})


class MailDeliveryError(Exception):
    """Письмо не удалось передать SMTP-серверу."""


def invitation_url(token: str) -> str:
    """Ссылка на фронтенд-страницу установки пароля.

    Токен передаётся во фрагменте URL: браузер не отправляет фрагмент на
    сервер, поэтому токен не попадает в access-логи ни фронтенда, ни backend.
    """
    return f"{get_public_base_url().rstrip('/')}/invitation#token={quote(token, safe='')}"


def password_reset_url(token: str) -> str:
    """Ссылка на фронтенд-страницу восстановления; токен только во фрагменте."""
    return f"{get_public_base_url().rstrip('/')}/password-reset#token={quote(token, safe='')}"


def email_change_url(token: str) -> str:
    """Ссылка подтверждения нового email; токен только во фрагменте."""
    return f"{get_public_base_url().rstrip('/')}/email-confirmation#token={quote(token, safe='')}"


def _settings() -> SmtpSettings:
    try:
        settings = get_smtp_settings()
    except ValueError as exc:
        # Неверный порт или таймаут в окружении — ошибка конфигурации, а не
        # повод для 500: вызывающая сторона должна получить MailDeliveryError.
        raise MailDeliveryError("Could not deliver email") from exc
    if settings.tls not in ALLOWED_TLS_MODES:
        raise MailDeliveryError("Unsupported SMTP TLS mode")
    return settings


def _open_client(settings: SmtpSettings) -> smtplib.SMTP:
    context = ssl.create_default_context()
    client: smtplib.SMTP | smtplib.SMTP_SSL
    if settings.tls == "ssl":
        client = smtplib.SMTP_SSL(
            settings.host,
            settings.port,
            timeout=settings.timeout_seconds,
            context=context,
        )
    else:
        client = smtplib.SMTP(
            settings.host,
            settings.port,
            timeout=settings.timeout_seconds,
        )
    client.ehlo()
    if settings.tls == "starttls":
        client.starttls(context=context)
        client.ehlo()
    if settings.username is not None:
        client.login(settings.username, settings.password or "")
    return client


def _close_client(client: smtplib.SMTP) -> None:
    with suppress(smtplib.SMTPException, OSError):
        client.quit()


def check_delivery_available() -> None:
    """Проверяет доступность SMTP-транспорта без отправки письма.

    Проверка не зависит от получателя: она одинаково выполняется для
    известного, неизвестного и ожидающего адреса. Ошибка конфигурации или
    соединения — ``MailDeliveryError``.
    """
    settings = _settings()
    try:
        client = _open_client(settings)
        try:
            return
        finally:
            _close_client(client)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise MailDeliveryError("Could not deliver email") from exc


def _deliver(message: EmailMessage) -> None:
    settings = _settings()
    try:
        client = _open_client(settings)
        try:
            client.send_message(message)
        finally:
            _close_client(client)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise MailDeliveryError("Could not deliver email") from exc


def _build_message(
    recipient: str,
    subject: str,
    body: str,
    sender: str,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    return message


def send_invitation(recipient: str, name: str, token: str) -> None:
    """Отправляет одно письмо приглашения; любая ошибка — ``MailDeliveryError``."""
    sender = _settings().sender
    message = _build_message(
        recipient,
        "Приглашение в Logos",
        (
            f"Здравствуйте, {name}!\n\n"
            "Вас пригласили в Logos. Чтобы задать пароль, перейдите по ссылке:\n"
            f"{invitation_url(token)}\n\n"
            "Ссылка действует 72 часа и может быть использована один раз.\n"
            "Если вы не ожидали приглашение, проигнорируйте это письмо.\n"
        ),
        sender,
    )
    _deliver(message)


def send_password_reset(recipient: str, token: str) -> None:
    """Отправляет письмо восстановления; любая ошибка — ``MailDeliveryError``."""
    sender = _settings().sender
    message = _build_message(
        recipient,
        "Восстановление пароля в Logos",
        (
            "Чтобы восстановить пароль в Logos, перейдите по ссылке:\n"
            f"{password_reset_url(token)}\n\n"
            "Ссылка действует 1 час и может быть использована один раз.\n"
            "Если вы не запрашивали восстановление, проигнорируйте это письмо.\n"
        ),
        sender,
    )
    _deliver(message)


def send_email_change(recipient: str, token: str) -> None:
    """Отправляет на новый адрес ссылку подтверждения; ошибка — ``MailDeliveryError``."""
    sender = _settings().sender
    message = _build_message(
        recipient,
        "Подтверждение email в Logos",
        (
            "Чтобы использовать этот адрес для входа в Logos, перейдите по ссылке:\n"
            f"{email_change_url(token)}\n\n"
            "Ссылка действует 24 часа и может быть использована один раз.\n"
            "До подтверждения вход выполняется по прежнему адресу.\n"
            "Если вы не меняли email, проигнорируйте это письмо.\n"
        ),
        sender,
    )
    _deliver(message)
