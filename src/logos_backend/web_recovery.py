"""Публичное восстановление пароля менеджера.

Токен приходит только в JSON-теле POST: он не появляется в пути, query,
``Referer`` или access-логах. Все изменяющие запросы требуют разрешённый
``Origin`` и CSRF-заголовок. Ответ на запрос ссылки одинаков для известного,
неизвестного и ожидающего адреса; ограничение повтора действует на сам адрес.
Выпуск ссылки и отправка письма выполняются фоновой задачей после ответа,
поэтому ``202`` не подтверждает доставку.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from logos_backend import mail, recovery
from logos_backend.security import InvalidEmailError, PasswordPolicyError, validate_email_address
from logos_backend.web_auth import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
    _set_session_cookie,
    _subject_payload,
    require_csrf,
)

router = APIRouter()

logger = logging.getLogger(__name__)

REQUEST_ACCEPTED_DETAIL = "If the account exists, password recovery instructions will be sent"
STALE_LINK_DETAIL = "Password reset link is no longer valid"


class PasswordResetRequestBody(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_LENGTH)


class PasswordResetTokenBody(BaseModel):
    token: str


class PasswordResetCompleteBody(BaseModel):
    token: str
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    password_confirmation: str = Field(max_length=MAX_PASSWORD_LENGTH)


def _isoformat(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _field_error(field: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": detail, "field": field},
        headers={"Cache-Control": "no-store"},
    )


def _accepted() -> JSONResponse:
    return JSONResponse(
        status_code=202,
        content={"detail": REQUEST_ACCEPTED_DETAIL},
        headers={"Cache-Control": "no-store"},
    )


def _too_many(retry_after_seconds: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many password recovery requests",
            "retry_after_seconds": retry_after_seconds,
        },
        headers={
            "Cache-Control": "no-store",
            "Retry-After": str(retry_after_seconds),
        },
    )


def _mail_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": "Password recovery email could not be delivered"},
        headers={"Cache-Control": "no-store"},
    )


def _stale_link() -> JSONResponse:
    return JSONResponse(
        status_code=410,
        content={"detail": STALE_LINK_DETAIL},
        headers={"Cache-Control": "no-store"},
    )


def _deliver_password_reset(email: str, reserved_at: int) -> None:
    """Выпускает ссылку и отправляет письмо уже после HTTP-ответа.

    Задача живёт только в памяти процесса: при падении или перезапуске между
    ответом и её выполнением письмо не отправится. Это осознанный компромисс
    локального SMTP-транспорта, а не обещание доставки; очереди и повторов нет.
    Ошибка доставки не раскрывает адрес, токен или пароль и только фиксируется
    классом исключения.
    """
    issue = recovery.issue_password_reset(email, reserved_at)
    if issue is None:
        return
    try:
        mail.send_password_reset(issue.email, issue.token)
    except mail.MailDeliveryError as exc:
        logger.warning("Password reset email delivery failed: %s", type(exc).__name__)


@router.post("/password-reset/request", dependencies=[Depends(require_csrf)])
def request_password_reset(
    payload: PasswordResetRequestBody,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Запрашивает ссылку; ответ не раскрывает состояние учётной записи.

    Все валидные адреса проходят один путь до ответа: проверка синтаксиса,
    атомарное окно повтора и общая проверка доступности SMTP. Выпуск ссылки и
    отправка письма выполняются фоновой задачей после отправки ответа, поэтому
    время ответа не зависит от существования аккаунта. Недоступный SMTP даёт
    общий ``502`` до планирования, как и раньше, и расходует окно повтора.
    """
    try:
        validate_email_address(payload.email)
    except InvalidEmailError:
        return _field_error("email", "Invalid email address")

    reservation = recovery.reserve_password_reset_request(payload.email)
    if not reservation.accepted:
        return _too_many(reservation.retry_after_seconds)

    try:
        mail.check_delivery_available()
    except mail.MailDeliveryError:
        return _mail_unavailable()

    assert reservation.requested_at is not None
    background_tasks.add_task(
        _deliver_password_reset,
        payload.email,
        reservation.requested_at,
    )
    return _accepted()


@router.post("/password-reset/preview", dependencies=[Depends(require_csrf)])
def preview_password_reset(payload: PasswordResetTokenBody) -> JSONResponse:
    """Читает адрес действующей ссылки; для недействительной ссылки email не выдаётся."""
    try:
        preview = recovery.preview_password_reset(payload.token)
    except recovery.PasswordResetInvalidError:
        return _stale_link()
    return JSONResponse(
        content={
            "email": preview.email,
            "expires_at": _isoformat(preview.expires_at),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/password-reset/complete", dependencies=[Depends(require_csrf)])
def complete_password_reset(
    payload: PasswordResetCompleteBody,
    request: Request,
) -> JSONResponse:
    """Меняет пароль, отзывает все прежние сессии и сразу открывает новую."""
    try:
        completed = recovery.complete_password_reset(
            payload.token,
            payload.password,
            payload.password_confirmation,
        )
    except PasswordPolicyError as exc:
        return _field_error("password", str(exc))
    except recovery.PasswordResetInvalidError:
        return _stale_link()

    response = JSONResponse(
        content={"subject": _subject_payload(completed.subject)},
        headers={"Cache-Control": "no-store"},
    )
    _set_session_cookie(response, request, completed.session_token, remember=False)
    return response
