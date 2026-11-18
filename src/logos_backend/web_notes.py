"""HTTP-слой заметок о клиентах (#14).

Читать может любой вошедший: заметку «Вся команда» видят все менеджеры и
администратор, «Только я» — только автор (администратор видит всё для модерации).
Создаёт заметки менеджер; правит и удаляет автор, администратор — любую.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt

from logos_backend import auth, notes
from logos_backend.web_account import Manager
from logos_backend.web_auth import require_csrf, require_subject

router = APIRouter()

Subject = Annotated[auth.Subject, Depends(require_subject)]


class NoteBody(BaseModel):
    text: str = Field(max_length=notes.MAX_NOTE_LENGTH + 100)  # пробелы по краям обрезаются
    visibility: Literal["team", "private"] = "team"


class UpdateNoteBody(NoteBody):
    """``version`` — версия открытой заметки; устаревшая получает ``409``."""

    version: StrictInt = Field(ge=1)


def _json(content: dict[str, object], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=content, headers={"Cache-Control": "no-store"}
    )


def _not_found(what: str = "Note") -> JSONResponse:
    return _json({"detail": f"{what} not found"}, status_code=404)


@router.get("/conversations/{conversation_id}/notes")
def list_notes(conversation_id: int, subject: Subject) -> JSONResponse:
    try:
        return _json({"notes": notes.list_notes(conversation_id, subject)})
    except notes.ConversationNotFoundError:
        return _not_found("Conversation")


@router.post("/conversations/{conversation_id}/notes", dependencies=[Depends(require_csrf)])
def create_note(conversation_id: int, payload: NoteBody, subject: Manager) -> JSONResponse:
    try:
        created = notes.create_note(
            conversation_id, payload.text, payload.visibility, subject.id
        )
        return _json({"notes": created}, status_code=201)
    except notes.InvalidNoteError:
        return _json({"detail": "Note text must not be blank", "field": "text"}, status_code=422)
    except notes.ConversationNotFoundError:
        return _not_found("Conversation")


@router.put(
    "/conversations/{conversation_id}/notes/{note_id}", dependencies=[Depends(require_csrf)]
)
def update_note(
    conversation_id: int, note_id: int, payload: UpdateNoteBody, subject: Subject
) -> JSONResponse:
    try:
        return _json(
            {
                "notes": notes.update_note(
                    conversation_id,
                    note_id,
                    payload.text,
                    payload.visibility,
                    payload.version,
                    subject,
                )
            }
        )
    except notes.InvalidNoteError:
        return _json({"detail": "Note text must not be blank", "field": "text"}, status_code=422)
    except notes.NoteNotFoundError:
        return _not_found()
    except notes.NoteForbiddenError:
        return _json({"detail": "Only own notes can be changed"}, status_code=403)
    except notes.NoteChangedError as exc:
        return _json(
            {"detail": "Note was changed by another manager", "note": exc.note},
            status_code=409,
        )


@router.delete(
    "/conversations/{conversation_id}/notes/{note_id}", dependencies=[Depends(require_csrf)]
)
def delete_note(conversation_id: int, note_id: int, subject: Subject) -> JSONResponse:
    try:
        return _json({"notes": notes.delete_note(conversation_id, note_id, subject)})
    except notes.NoteNotFoundError:
        return _not_found()
    except notes.NoteForbiddenError:
        return _json({"detail": "Only own notes can be deleted"}, status_code=403)
