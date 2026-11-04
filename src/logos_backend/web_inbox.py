"""HTTP-слой «Входящих» (#6): диалоги, переписка, ответы, вложения.

Доступно только менеджерам (ADR-0007: администратор «Входящие» не видит).
Файл ответа приходит сырым телом запроса (имя и подпись — в query), чтобы не
тянуть python-multipart ради одного поля.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from logos_backend import inbox
from logos_backend.web_account import Manager
from logos_backend.web_auth import require_csrf

MAX_FILE_NAME_LENGTH = 255

router = APIRouter()


class ReplyBody(BaseModel):
    text: str = Field(max_length=inbox.MAX_TEXT_LENGTH)


def _json(content: dict[str, object], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=content, headers={"Cache-Control": "no-store"}
    )


def _not_found() -> JSONResponse:
    return _json({"detail": "Conversation not found"}, status_code=404)


def _field_error(field: str, detail: str) -> JSONResponse:
    return _json({"detail": detail, "field": field}, status_code=422)


@router.get("/conversations")
def list_conversations(subject: Manager) -> JSONResponse:
    return _json(inbox.list_conversations())


@router.get("/conversations/{conversation_id}/messages")
def get_conversation(conversation_id: int, subject: Manager) -> JSONResponse:
    try:
        return _json(inbox.get_conversation(conversation_id))
    except inbox.ConversationNotFoundError:
        return _not_found()


@router.post("/conversations/{conversation_id}/read", dependencies=[Depends(require_csrf)])
def mark_read(conversation_id: int, subject: Manager) -> JSONResponse:
    try:
        inbox.mark_read(conversation_id)
    except inbox.ConversationNotFoundError:
        return _not_found()
    return _json({"status": "ok"})


@router.post("/conversations/{conversation_id}/messages", dependencies=[Depends(require_csrf)])
def reply(conversation_id: int, payload: ReplyBody, subject: Manager) -> JSONResponse:
    text = payload.text.strip()
    if not text:
        return _field_error("text", "Text must not be blank")
    try:
        return _json({"message": inbox.reply(conversation_id, text)})
    except inbox.ConversationNotFoundError:
        return _not_found()


@router.post("/conversations/{conversation_id}/files", dependencies=[Depends(require_csrf)])
async def reply_with_file(
    conversation_id: int,
    request: Request,
    subject: Manager,
    name: Annotated[str, Query(min_length=1, max_length=MAX_FILE_NAME_LENGTH)],
    text: Annotated[str, Query(max_length=inbox.MAX_CAPTION_LENGTH)] = "",
) -> JSONResponse:
    """Ответ с файлом; размер ограничен ``MAX_UPLOAD_BYTES`` в ``app``."""
    content = await request.body()
    if not content:
        return _field_error("file", "File must not be empty")
    try:
        message = await run_in_threadpool(
            inbox.reply, conversation_id, text.strip(), (name.strip() or "file", content)
        )
    except inbox.ConversationNotFoundError:
        return _not_found()
    return _json({"message": message})


@router.post("/messages/{message_id}/retry", dependencies=[Depends(require_csrf)])
def retry(message_id: int, subject: Manager) -> JSONResponse:
    try:
        return _json({"message": inbox.retry(message_id)})
    except inbox.NotRetryableError:
        return _json({"detail": "Message is not failed"}, status_code=409)


@router.get("/messages/{message_id}/attachment", response_model=None)
def get_attachment(message_id: int, subject: Manager) -> FileResponse | JSONResponse:
    """Отдаёт вложение после проверки сессии.

    Фото Telegram всегда JPEG и показываются в диалоге. Документ от клиента
    может оказаться HTML со скриптом, поэтому он отдаётся только на скачивание
    как ``application/octet-stream`` и под ``sandbox``.
    """
    found = inbox.attachment(message_id)
    if found is None or not found[0].is_file():
        return _json({"detail": "Attachment not found"}, status_code=404)
    path, name, kind = found
    photo = kind == "photo"
    return FileResponse(
        path,
        media_type="image/jpeg" if photo else "application/octet-stream",
        filename=name,
        content_disposition_type="inline" if photo else "attachment",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )
