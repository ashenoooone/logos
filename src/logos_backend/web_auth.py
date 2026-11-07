"""HTTP-слой аутентификации: cookie-сессии, CSRF и проверка прав.

Эндпоинты намеренно узкие: вход администратора/менеджера, текущий субъект,
выход и выдача CSRF-токена. Административные операции появятся в следующих
этапах и должны использовать :func:`require_administrator`.
"""

from __future__ import annotations

import secrets
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from logos_backend import auth, mail
from logos_backend.config import get_allowed_origins
from logos_backend.security import InvalidEmailError, new_token, validate_email_address

SESSION_COOKIE_NAME = "logos_session"
CSRF_COOKIE_NAME = "logos_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Защитные верхние границы публичного ввода. Лимиты не ужесточают политику
# пароля и не укорачивают уже допустимые CLI-пароли: 1024 символа с запасом
# покрывают практические значения, но не дают сохранить мегабайтный
# идентификатор в первичном ключе login_attempts. Email ограничен RFC 5321.
MAX_LOGIN_LENGTH = 1024
MAX_PASSWORD_LENGTH = 1024
MAX_EMAIL_LENGTH = 254

router = APIRouter(prefix="/auth")



class AdministratorLoginRequest(BaseModel):
    login: str = Field(max_length=MAX_LOGIN_LENGTH)
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    remember: bool = False


class ManagerOtpRequest(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_LENGTH)


class ManagerOtpVerify(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_LENGTH)
    code: str = Field(pattern=r"^[0-9]{6}$")
    remember: bool = False


def _canonical_origin(value: str) -> str | None:
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def _request_origin(request: Request) -> str | None:
    host = request.headers.get("host") or request.url.netloc
    return _canonical_origin(f"{request.url.scheme}://{host}")


def _origin_is_allowed(request: Request) -> bool:
    supplied = request.headers.get("origin")
    if supplied is None:
        return False
    supplied_origin = _canonical_origin(supplied)
    if supplied_origin is None:
        return False

    allowed = {_request_origin(request)}
    allowed.update(_canonical_origin(origin) for origin in get_allowed_origins())
    allowed.discard(None)
    return supplied_origin in allowed


def require_csrf(request: Request) -> None:
    """Требует явный разрешённый Origin и совпадающий double-submit токен.

    Применяется ко всем небезопасным запросам, включая вход: анонимный клиент
    сначала получает токен через ``GET /auth/csrf``.
    """
    if not _origin_is_allowed(request):
        raise HTTPException(status_code=403, detail="Request origin is not allowed")

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    supplied_token = request.headers.get(CSRF_HEADER_NAME)
    if (
        not cookie_token
        or not supplied_token
        or not secrets.compare_digest(
            cookie_token.encode("utf-8"),
            supplied_token.encode("utf-8"),
        )
    ):
        raise HTTPException(status_code=403, detail="CSRF verification failed")


def require_subject(request: Request) -> auth.Subject:
    """Зависимость FastAPI: действующая сессия или 401."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    subject = auth.session_subject(token)
    if subject is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return subject


def require_administrator(
    subject: Annotated[auth.Subject, Depends(require_subject)],
) -> auth.Subject:
    """Зависимость FastAPI: только администратор; роль берётся из сессии, не из запроса."""
    if subject.kind != auth.ADMINISTRATOR:
        raise HTTPException(status_code=403, detail="Forbidden")
    return subject


def _is_secure(request: Request) -> bool:
    return request.url.scheme == "https"


def _set_session_cookie(
    response: Response,
    request: Request,
    token: str,
    remember: bool,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=auth.SESSION_TTL_SECONDS if remember else None,
        httponly=True,
        samesite="lax",
        secure=_is_secure(request),
        path="/",
    )


def _clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_is_secure(request),
    )


def _set_csrf_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        samesite="lax",
        secure=_is_secure(request),
        path="/",
    )


def _subject_payload(subject: auth.Subject) -> dict[str, object]:
    if subject.kind == auth.ADMINISTRATOR:
        return {"type": "administrator"}
    return {
        "type": "manager",
        "id": subject.id,
        "name": subject.name,
        "email": subject.email,
    }


def _invalid_credentials(attempts_remaining: int) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "detail": "Invalid credentials",
            "attempts_remaining": attempts_remaining,
        },
        headers={"Cache-Control": "no-store"},
    )


def _locked(retry_after_seconds: int) -> JSONResponse:
    return JSONResponse(
        status_code=423,
        content={
            "detail": "Too many login attempts",
            "attempts_remaining": 0,
            "retry_after_seconds": retry_after_seconds,
        },
        headers={
            "Cache-Control": "no-store",
            "Retry-After": str(retry_after_seconds),
        },
    )


def _authenticated(
    request: Request,
    session: auth.LoginSession,
    remember: bool,
) -> JSONResponse:
    response = JSONResponse(
        content={"subject": _subject_payload(session.subject)},
        headers={"Cache-Control": "no-store"},
    )
    _set_session_cookie(response, request, session.token, remember)
    return response


@router.get("/csrf")
def csrf_bootstrap(request: Request) -> JSONResponse:
    """Выдаёт читаемый CSRF-токен; повторный вызов сохраняет действующий."""
    existing = request.cookies.get(CSRF_COOKIE_NAME)
    token = existing if existing and len(existing) >= 32 else new_token()
    response = JSONResponse(
        content={"csrf_token": token},
        headers={"Cache-Control": "no-store"},
    )
    _set_csrf_cookie(response, request, token)
    return response


@router.post("/admin/login", dependencies=[Depends(require_csrf)])
def administrator_login(
    payload: AdministratorLoginRequest,
    request: Request,
) -> JSONResponse:
    try:
        session = auth.login_administrator(
            payload.login,
            payload.password,
            previous_session_token=request.cookies.get(SESSION_COOKIE_NAME),
        )
    except auth.AccountLockedError as exc:
        return _locked(exc.retry_after_seconds)
    except auth.InvalidCredentialsError as exc:
        return _invalid_credentials(exc.attempts_remaining)
    return _authenticated(request, session, payload.remember)



@router.post("/manager/otp/request", dependencies=[Depends(require_csrf)])
def request_manager_otp(payload: ManagerOtpRequest) -> JSONResponse:
    try:
        validate_email_address(payload.email)
        mail.check_delivery_available()
    except InvalidEmailError:
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid email address", "field": "email"},
            headers={"Cache-Control": "no-store"},
        )
    except mail.MailDeliveryError:
        return JSONResponse(
            status_code=503,
            content={"detail": "Email delivery is temporarily unavailable"},
            headers={"Cache-Control": "no-store"},
        )
    try:
        code = auth.request_manager_otp(payload.email)
    except auth.OtpRateLimitedError as exc:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many code requests",
                "retry_after_seconds": exc.retry_after_seconds,
            },
            headers={"Cache-Control": "no-store", "Retry-After": str(exc.retry_after_seconds)},
        )
    try:
        mail.send_manager_otp(payload.email.strip(), code)
    except mail.MailDeliveryError:
        return JSONResponse(
            status_code=503,
            content={"detail": "Email delivery is temporarily unavailable"},
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(
        status_code=202,
        content={"detail": "If the account exists, a sign-in code will be sent"},
        headers={"Cache-Control": "no-store"},
    )


@router.post("/manager/otp/verify", dependencies=[Depends(require_csrf)])
def verify_manager_otp(payload: ManagerOtpVerify, request: Request) -> JSONResponse:

    try:
        validate_email_address(payload.email)
        session = auth.verify_manager_otp(
            payload.email, payload.code,
            previous_session_token=request.cookies.get(SESSION_COOKIE_NAME),
        )
    except InvalidEmailError:
        return JSONResponse(
            status_code=422, content={"detail": "Invalid email address", "field": "email"},
            headers={"Cache-Control": "no-store"},
        )
    except auth.OtpInvalidError:
        return JSONResponse(
            status_code=401, content={"detail": "Invalid or expired sign-in code"},
            headers={"Cache-Control": "no-store"},
        )
    return _authenticated(request, session, payload.remember)


@router.get("/me")
def current_subject(
    subject: Annotated[auth.Subject, Depends(require_subject)],
) -> JSONResponse:
    return JSONResponse(
        content={"subject": _subject_payload(subject)},
        headers={"Cache-Control": "no-store"},
    )


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        auth.revoke_session(token)
    response = Response(status_code=204)
    _clear_session_cookie(response, request)
    response.headers["Cache-Control"] = "no-store"
    return response
