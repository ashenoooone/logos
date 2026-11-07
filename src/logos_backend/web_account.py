"""HTTP-слой профиля менеджера: имя, email, пароль.

Изменения профиля доступны только сессии менеджера. Подтверждение email —
публичное: ссылку из письма можно открыть в браузере без сессии, токен
приходит только в JSON-теле.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from logos_backend import account, auth, mail
from logos_backend.security import InvalidEmailError, PasswordPolicyError
from logos_backend.web_auth import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
    SESSION_COOKIE_NAME,
    _subject_payload,
    require_csrf,
    require_subject,
)
from logos_backend.web_managers import MAX_MANAGER_NAME_LENGTH

router = APIRouter(prefix="/account", dependencies=[Depends(require_csrf)])


class NameBody(BaseModel):
    name: str = Field(max_length=MAX_MANAGER_NAME_LENGTH)


class EmailBody(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_LENGTH)


class TokenBody(BaseModel):
    token: str


class PasswordBody(BaseModel):
    current_password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    new_password_confirmation: str = Field(max_length=MAX_PASSWORD_LENGTH)
    sign_out_other_devices: bool = True


def require_manager(
    subject: Annotated[auth.Subject, Depends(require_subject)],
) -> auth.Subject:
    if subject.kind != auth.MANAGER:
        raise HTTPException(status_code=403, detail="Forbidden")
    return subject


Manager = Annotated[auth.Subject, Depends(require_manager)]


def _json(content: dict[str, object], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=content, headers={"Cache-Control": "no-store"}
    )


def _field_error(field: str, detail: str) -> JSONResponse:
    return _json({"detail": detail, "field": field}, status_code=422)


@router.post("/name")
def change_name(payload: NameBody, subject: Manager) -> JSONResponse:
    try:
        updated = account.rename(subject.id, payload.name)
    except account.InvalidNameError:
        return _field_error("name", "Name must not be blank")
    return _json({"subject": _subject_payload(updated)})


@router.post("/email")
def request_email_change(payload: EmailBody, subject: Manager) -> JSONResponse:
    """Отправляет ссылку на новый адрес; до подтверждения вход по старому."""
    try:
        issue = account.request_email_change(subject.id, payload.email)
    except InvalidEmailError:
        return _field_error("email", "Invalid email address")
    except account.EmailUnchangedError:
        return _field_error("email", "Email is unchanged")
    except account.EmailTakenError:
        return _field_error("email", "Email is already taken")
    try:
        mail.send_email_change(issue.email, issue.token)
    except mail.MailDeliveryError:
        return _json({"detail": "Confirmation email could not be delivered"}, status_code=502)
    return _json({"pending_email": issue.email}, status_code=202)


@router.post("/email/confirm")
def confirm_email_change(payload: TokenBody) -> JSONResponse:
    try:
        confirmed = account.confirm_email_change(payload.token)
    except account.EmailChangeInvalidError:
        return _json({"detail": "Email confirmation link is no longer valid"}, status_code=410)
    except account.EmailTakenError:
        return _json({"detail": "Email is already taken"}, status_code=409)
    return _json({"manager_id": confirmed.manager_id, "email": confirmed.email})


@router.post("/password")
def change_password(payload: PasswordBody, subject: Manager, request: Request) -> JSONResponse:
    """Меняет пароль; с ``sign_out_other_devices`` отзывает все сессии, кроме текущей."""
    try:
        account.change_password(
            subject.id,
            request.cookies.get(SESSION_COOKIE_NAME, ""),
            payload.current_password,
            payload.new_password,
            payload.new_password_confirmation,
            payload.sign_out_other_devices,
        )
    except account.CurrentPasswordRequiredError:
        return _field_error("current_password", "Current password is required")
    except PasswordPolicyError as exc:
        field = (
            "new_password_confirmation"
            if str(exc) == "passwords do not match"
            else "new_password"
        )
        return _field_error(field, str(exc))
    except account.CurrentPasswordInvalidError:
        return _field_error("current_password", "Current password is incorrect")
    return _json({}, status_code=200)
