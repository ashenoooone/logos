"""HTTP-слой шаблонов ответов (#11): только менеджеры.

Шаблоны общие на компанию. Ответ на изменение — полный список, как у тегов:
это избавляет фронтенд от повторного запроса.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from logos_backend import templates
from logos_backend.web_account import Manager
from logos_backend.web_auth import require_csrf

router = APIRouter()


class TemplateBody(BaseModel):
    name: str = Field(max_length=templates.MAX_NAME_LENGTH + 100)
    text: str = Field(max_length=templates.MAX_TEXT_LENGTH + 100)


def _json(content: dict[str, object], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=content, headers={"Cache-Control": "no-store"}
    )


def _invalid(field: str) -> JSONResponse:
    detail = "Invalid template name" if field == "name" else "Invalid template text"
    return _json({"detail": detail, "field": field}, status_code=422)


@router.get("/templates")
def list_templates(subject: Manager) -> JSONResponse:
    return _json({"templates": templates.list_templates(subject.id)})


@router.post("/templates", dependencies=[Depends(require_csrf)])
def create_template(payload: TemplateBody, subject: Manager) -> JSONResponse:
    try:
        created = templates.create_template(subject.id, payload.name, payload.text)
        return _json({"templates": created})
    except templates.InvalidTemplateError as exc:
        return _invalid(str(exc))


@router.patch("/templates/{template_id}", dependencies=[Depends(require_csrf)])
def update_template(template_id: int, payload: TemplateBody, subject: Manager) -> JSONResponse:
    try:
        return _json(
            {
                "templates": templates.update_template(
                    template_id, subject.id, payload.name, payload.text
                )
            }
        )
    except templates.InvalidTemplateError as exc:
        return _invalid(str(exc))
    except templates.TemplateNotFoundError:
        return _json({"detail": "Template not found"}, status_code=404)
    except templates.TemplateForbiddenError:
        return _json({"detail": "Only own templates can be changed"}, status_code=403)


@router.delete("/templates/{template_id}", dependencies=[Depends(require_csrf)])
def delete_template(template_id: int, subject: Manager) -> JSONResponse:
    try:
        return _json({"templates": templates.remove_template(template_id, subject.id)})
    except templates.TemplateNotFoundError:
        return _json({"detail": "Template not found"}, status_code=404)
    except templates.TemplateForbiddenError:
        return _json({"detail": "Only own templates can be deleted"}, status_code=403)
