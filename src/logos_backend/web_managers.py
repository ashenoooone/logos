"""Административные операции с менеджерами и публичное принятие приглашения."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from logos_backend import auth, invitations, mail
from logos_backend.security import InvalidEmailError, PasswordPolicyError
from logos_backend.web_auth import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
    SESSION_COOKIE_NAME,
    _set_session_cookie,
    _subject_payload,
    require_administrator,
    require_csrf,
)

MAX_MANAGER_NAME_LENGTH = 200

router = APIRouter()


class ManagerCreateRequest(BaseModel):
    name: str = Field(max_length=MAX_MANAGER_NAME_LENGTH)
    email: str = Field(max_length=MAX_EMAIL_LENGTH)


class InvitationReissueRequest(BaseModel):
    email: str | None = Field(default=None, max_length=MAX_EMAIL_LENGTH)


class InvitationPreviewRequest(BaseModel):
    token: str


class InvitationAcceptRequest(BaseModel):
    token: str
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    password_confirmation: str = Field(max_length=MAX_PASSWORD_LENGTH)


def _isoformat(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _manager_payload(manager: invitations.ManagerSummary) -> dict[str, object]:
    return {
        "id": manager.id,
        "name": manager.name,
        "email": manager.email,
        "role": auth.MANAGER,
        "status": manager.status,
        "created_at": _isoformat(manager.created_at),
    }


def _field_error(field: str, detail: str, status_code: int = 422) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "field": field},
        headers={"Cache-Control": "no-store"},
    )


def _delivery_sent(manager: invitations.ManagerSummary, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "manager": _manager_payload(manager),
            "delivery": {"status": "sent"},
        },
        headers={"Cache-Control": "no-store"},
    )


def _delivery_failed(manager: invitations.ManagerSummary) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={
            "detail": "Invitation email could not be delivered",
            "manager": _manager_payload(manager),
            "delivery": {"status": "failed"},
        },
        headers={"Cache-Control": "no-store"},
    )


def _stale_invitation() -> JSONResponse:
    return JSONResponse(
        status_code=410,
        content={"detail": "Invitation is no longer valid"},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/admin/managers")
def list_managers(
    subject: Annotated[auth.Subject, Depends(require_administrator)],
) -> JSONResponse:
    """Список менеджеров; роль всегда «менеджер», администратор в него не входит."""
    return JSONResponse(
        content={
            "managers": [
                _manager_payload(manager) for manager in invitations.list_managers()
            ]
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/admin/managers", dependencies=[Depends(require_csrf)])
def create_manager(
    payload: ManagerCreateRequest,
    subject: Annotated[auth.Subject, Depends(require_administrator)],
) -> JSONResponse:
    """Создаёт ожидающего менеджера и отправляет приглашение.

    Роль из тела запроса не читается: создаётся только менеджер. Сбой SMTP
    оставляет запись и возвращает явную ошибку доставки для повторной попытки.
    """
    try:
        issue = invitations.create_pending_manager_with_invitation(payload.name, payload.email)
    except invitations.InvalidManagerNameError:
        return _field_error("name", "Name must not be blank")
    except InvalidEmailError:
        return _field_error("email", "Invalid email address")
    except invitations.EmailAlreadyExistsError:
        return _field_error("email", "A manager with this email already exists")

    try:
        mail.send_invitation(issue.manager.email, issue.manager.name, issue.token)
    except mail.MailDeliveryError:
        return _delivery_failed(issue.manager)
    return _delivery_sent(issue.manager, status_code=201)


@router.post("/admin/managers/{manager_id}/invitation", dependencies=[Depends(require_csrf)])
def reissue_invitation(
    manager_id: int,
    payload: InvitationReissueRequest,
    subject: Annotated[auth.Subject, Depends(require_administrator)],
) -> JSONResponse:
    """Исправляет email ожидающего менеджера и отправляет новую ссылку."""
    try:
        issue = invitations.reissue_invitation(manager_id, payload.email)
    except InvalidEmailError:
        return _field_error("email", "Invalid email address")
    except invitations.EmailAlreadyExistsError:
        return _field_error("email", "A manager with this email already exists")
    except invitations.ManagerNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"detail": "Manager not found"},
            headers={"Cache-Control": "no-store"},
        )
    except invitations.ManagerNotPendingError:
        return JSONResponse(
            status_code=409,
            content={"detail": "Manager has already accepted the invitation"},
            headers={"Cache-Control": "no-store"},
        )

    try:
        mail.send_invitation(issue.manager.email, issue.manager.name, issue.token)
    except mail.MailDeliveryError:
        return _delivery_failed(issue.manager)
    return _delivery_sent(issue.manager, status_code=200)


@router.post("/invitations/preview", dependencies=[Depends(require_csrf)])
def invitation_preview(payload: InvitationPreviewRequest) -> JSONResponse:
    """Публичное чтение приглашения; email неизменяем и берётся из БД.

    Токен приходит только в теле: он не попадает в путь запроса и,
    следовательно, в access-логи.
    """
    try:
        preview = invitations.preview_invitation(payload.token)
    except invitations.InvitationInvalidError:
        return _stale_invitation()
    return JSONResponse(
        content={
            "name": preview.name,
            "email": preview.email,
            "expires_at": _isoformat(preview.expires_at),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/invitations/accept", dependencies=[Depends(require_csrf)])
def accept_invitation(
    payload: InvitationAcceptRequest,
    request: Request,
) -> JSONResponse:
    """Задаёт пароль, активирует менеджера и сразу открывает браузерную сессию."""
    try:
        accepted = invitations.accept_invitation(
            payload.token,
            payload.password,
            payload.password_confirmation,
        )
    except PasswordPolicyError as exc:
        return _field_error("password", str(exc))
    except invitations.InvitationInvalidError:
        return _stale_invitation()

    previous_token = request.cookies.get(SESSION_COOKIE_NAME)
    if previous_token:
        auth.revoke_session(previous_token)

    response = JSONResponse(
        content={"subject": _subject_payload(accepted.subject)},
        headers={"Cache-Control": "no-store"},
    )
    _set_session_cookie(response, request, accepted.session_token, remember=False)
    return response
