"""HTTP routes. The frontend talks only to these endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.device import paddle_device, rss_mb, torch_device
from app.inpainting.lama_provider import lama_status
from app.inpainting.text_edit_provider import status as text_edit_status
from app.metrics import snapshot as metric_snapshot
from app.models.domain import DocumentState
from app.ocr.paddle_provider import ocr_status
from app.services.document_service import _read_upload, get_service

router = APIRouter()


class ReplaceRequest(BaseModel):
    region_id: str = Field(min_length=1, max_length=64)
    new_text: str = Field(min_length=1, max_length=400)
    mode: Literal["fast", "ai", "auto"] = "auto"

    @field_validator("new_text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Replacement text is empty.")
        return value


class ExportRequest(BaseModel):
    format: Literal["png", "jpg", "pdf"]


class DetectRequest(BaseModel):
    document_id: str = Field(min_length=32, max_length=32)


def _document_payload(state: DocumentState) -> dict:
    payload = state.model_dump()
    payload["can_undo"] = state.can_undo
    payload["can_redo"] = state.can_redo
    return payload


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "device": {"torch": torch_device(), "paddle": paddle_device()},
        "ocr": ocr_status(),
        "inpaint_ai": lama_status(),
        "text_edit": {**text_edit_status(), "enabled": get_settings().text_edit != "off"},
        "rss_mb": rss_mb(),
    }


@router.get("/metrics")
def metrics() -> dict:
    return {"samples": metric_snapshot()}


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    settings = get_settings()
    data = _read_upload(file.file, settings.max_upload_bytes)
    if not data:
        from app.errors import AppError

        raise AppError("UNSUPPORTED_FILE_TYPE", "The upload was empty.", 415)
    state = get_service().create_from_bytes(file.filename or "upload", data)
    return _document_payload(state)


@router.post("/ocr")
def ocr(body: DetectRequest) -> dict:
    state, timings = get_service().detect_text(body.document_id)
    return {"document": _document_payload(state), "timings_ms": timings}


@router.get("/document/{doc_id}")
def get_document(doc_id: str) -> dict:
    return _document_payload(get_service().get(doc_id))


@router.post("/document/{doc_id}/detect-text")
def detect_text(doc_id: str) -> dict:
    state, timings = get_service().detect_text(doc_id)
    return {"document": _document_payload(state), "timings_ms": timings}


@router.post("/document/{doc_id}/replace-text")
def replace_text(doc_id: str, body: ReplaceRequest) -> dict:
    state, mode_used, fallback, timings = get_service().replace_text(
        doc_id, body.region_id, body.new_text, body.mode
    )
    return {
        "document": _document_payload(state),
        "mode_requested": body.mode,
        "mode_used": mode_used,
        "draw_source": state.edits[-1].draw_source if state.edits else "font",
        "match_score": state.edits[-1].match_score if state.edits else None,
        "fallback_reason": fallback,
        "timings_ms": timings,
    }


@router.post("/document/{doc_id}/undo")
def undo(doc_id: str) -> dict:
    return _document_payload(get_service().undo(doc_id))


@router.post("/document/{doc_id}/redo")
def redo(doc_id: str) -> dict:
    return _document_payload(get_service().redo(doc_id))


@router.post("/document/{doc_id}/reset")
def reset(doc_id: str) -> dict:
    return _document_payload(get_service().reset(doc_id))


@router.get("/document/{doc_id}/pages/{page}/image")
def page_image(doc_id: str, page: int, variant: Literal["current", "original"] = "current", v: int = 0) -> FileResponse:
    del v
    path = get_service().page_image(doc_id, page, variant)
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/document/{doc_id}/pages/{page}/thumbnail")
def page_thumbnail(doc_id: str, page: int, v: int = 0) -> FileResponse:
    del v
    path = get_service().thumbnail(doc_id, page)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/document/{doc_id}/preview")
def preview(doc_id: str) -> dict:
    return get_service().preview(doc_id)


@router.post("/document/{doc_id}/export")
def export_document(doc_id: str, body: ExportRequest) -> dict:
    return get_service().export(doc_id, body.format)


@router.get("/document/{doc_id}/download")
def download(doc_id: str) -> FileResponse:
    path, filename, media = get_service().download(doc_id)
    return FileResponse(path, media_type=media, filename=filename)
