"""HTTP-слой тегов (#8): менеджер ставит/снимает теги, администратор ведёт справочник."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt

from logos_backend import auth, tags
from logos_backend.web_account import Manager
from logos_backend.web_auth import require_administrator, require_csrf

router = APIRouter()

Administrator = Annotated[auth.Subject, Depends(require_administrator)]


class AttachBody(BaseModel):
    tag_id: StrictInt | None = None
    name: str | None = Field(default=None, max_length=tags.MAX_TAG_LENGTH + 100)


class NameBody(BaseModel):
    name: str = Field(max_length=tags.MAX_TAG_LENGTH + 100)  # пробелы по краям обрезаются


def _json(content: dict[str, object], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=content, headers={"Cache-Control": "no-store"}
    )


def _invalid_name() -> JSONResponse:
    return _json({"detail": "Invalid tag name", "field": "name"}, status_code=422)


def _exists() -> JSONResponse:
    return _json({"detail": "Tag already exists", "field": "name"}, status_code=409)


def _not_found(what: str = "Tag") -> JSONResponse:
    return _json({"detail": f"{what} not found"}, status_code=404)


@router.get("/tags")
def list_tags(subject: Manager) -> JSONResponse:
    return _json({"tags": tags.list_tags(subject.id)})


@router.delete("/tags/{tag_id}", dependencies=[Depends(require_csrf)])
def delete_own_tag(tag_id: int, subject: Manager) -> JSONResponse:
    try:
        tags.remove(tag_id, subject.id)
    except tags.TagNotFoundError:
        return _not_found()
    except tags.TagForbiddenError:
        return _json({"detail": "Only own tags can be deleted"}, status_code=403)
    return _json({"status": "ok"})


@router.post("/conversations/{conversation_id}/tags", dependencies=[Depends(require_csrf)])
def attach(conversation_id: int, payload: AttachBody, subject: Manager) -> JSONResponse:
    has_id = payload.tag_id is not None
    has_name = payload.name is not None
    if has_id == has_name:
        return _json({"detail": "Exactly one of tag_id or name is required"}, status_code=422)
    try:
        if has_id:
            assert payload.tag_id is not None
            return _json({"tags": tags.attach_by_id(conversation_id, payload.tag_id, subject.id)})
        assert payload.name is not None
        return _json({"tags": tags.attach_by_name(conversation_id, payload.name, subject.id)})
    except tags.InvalidTagNameError:
        return _invalid_name()
    except tags.TagExistsError:
        return _exists()
    except tags.TagNotFoundError:
        return _not_found()
    except tags.TagForbiddenError:
        return _json({"detail": "Cannot attach invisible tag"}, status_code=403)
    except tags.ConversationNotFoundError:
        return _not_found("Conversation")


@router.delete(
    "/conversations/{conversation_id}/tags/{tag_id}", dependencies=[Depends(require_csrf)]
)
def detach(conversation_id: int, tag_id: int, subject: Manager) -> JSONResponse:
    try:
        return _json({"tags": tags.detach(conversation_id, tag_id)})
    except tags.ConversationNotFoundError:
        return _not_found("Conversation")


@router.get("/admin/tags")
def admin_list(subject: Administrator) -> JSONResponse:
    return _json({"tags": tags.list_tags(None)})


@router.post("/admin/tags", dependencies=[Depends(require_csrf)])
def admin_create(payload: NameBody, subject: Administrator) -> JSONResponse:
    try:
        tags.create_standard(payload.name)
    except tags.InvalidTagNameError:
        return _invalid_name()
    except tags.TagExistsError:
        return _exists()
    return _json({"tags": tags.list_tags(None)})


@router.patch("/admin/tags/{tag_id}", dependencies=[Depends(require_csrf)])
def admin_rename(tag_id: int, payload: NameBody, subject: Administrator) -> JSONResponse:
    try:
        tags.rename(tag_id, payload.name)
    except tags.InvalidTagNameError:
        return _invalid_name()
    except tags.TagExistsError:
        return _exists()
    except tags.TagNotFoundError:
        return _not_found()
    return _json({"tags": tags.list_tags(None)})


@router.delete("/admin/tags/{tag_id}", dependencies=[Depends(require_csrf)])
def admin_delete(tag_id: int, subject: Administrator) -> JSONResponse:
    try:
        tags.remove(tag_id, None)
    except tags.TagNotFoundError:
        return _not_found()
    return _json({"tags": tags.list_tags(None)})
