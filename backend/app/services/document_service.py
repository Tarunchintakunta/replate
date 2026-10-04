"""Upload, detect, edit, history, and export.

Original bytes are never overwritten. Edits land in work files and snapshots.
"""

from __future__ import annotations

import io
import logging
import re
import shutil
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import Settings, get_settings
from app.errors import AppError
from app.image.editing import page_glyph_alphabet, replace_raster_text
from app.image.io_utils import load_bgr, save_jpeg, save_png
from app.image.style import estimate_style
from app.metrics import Timer, record
from app.models.domain import DocumentState, EditRecord, PageInfo, TextRegion
from app.ocr.normalize import normalize_detections
from app.ocr.paddle_provider import PaddleOCRProvider
from app.pdf.pymupdf_processor import PyMuPDFProcessor
from app.rendering.fonts import resolve_font
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)

_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")
_service: "DocumentService | None" = None
_service_lock = threading.Lock()


def get_service() -> "DocumentService":
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = DocumentService(get_settings())
    return _service


def reset_service() -> None:
    global _service
    _service = None


class DocumentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = LocalStorage(settings.storage_dir)
        self.pdf = PyMuPDFProcessor()
        self.ocr = PaddleOCRProvider()
        # RLock so a request that already holds the document lock can render a page.
        self._locks: dict[str, threading.RLock] = defaultdict(threading.RLock)

    def create_from_bytes(self, filename: str, data: bytes) -> DocumentState:
        if len(data) > self.settings.max_upload_bytes:
            raise AppError(
                "FILE_TOO_LARGE",
                f"This file is larger than the {self.settings.max_upload_bytes // (1024 * 1024)} MB limit.",
                413,
            )
        media_type = _sniff(data)
        if media_type is None:
            raise AppError(
                "UNSUPPORTED_FILE_TYPE",
                "Upload a PNG, JPEG, or PDF. The file contents do not match a supported type.",
                415,
            )
        doc_id = uuid.uuid4().hex
        safe_name = _safe_filename(filename, media_type)
        self.storage.document_dir(doc_id).mkdir(parents=True, exist_ok=True)
        try:
            if media_type == "pdf":
                state = self._create_pdf(doc_id, safe_name, data)
            else:
                state = self._create_image(doc_id, safe_name, media_type, data)
        except Exception:
            self.storage.delete_document(doc_id)
            raise
        self._save_meta(state)
        logger.info("Stored document %s (%s, %s bytes)", doc_id, media_type, len(data))
        return state

    def get(self, doc_id: str) -> DocumentState:
        return self._load(doc_id)

    def detect_text(self, doc_id: str) -> tuple[DocumentState, dict[str, float]]:
        with self._locks[doc_id]:
            timer = Timer()
            state = self._load(doc_id)
            self._restore_pristine(state)
            warnings: list[str] = []
            failures: list[str] = []
            regions: list[TextRegion] = []
            if state.file_kind == "image":
                image = load_bgr(self.storage.path(doc_id, "pages/page_0.png"))
                regions.extend(self._ocr_page(state, state.pages[0], image, failures, warnings))
            else:
                original = self.storage.path(doc_id, "original.pdf")
                for page in state.pages:
                    if page.kind == "native":
                        extracted = self.pdf.extract_regions(original, page)
                        if not extracted:
                            warnings.append(f"No extractable text on page {page.index + 1}.")
                        regions.extend(extracted)
                    else:
                        image = load_bgr(self._original_pdf_raster(state, page))
                        regions.extend(self._ocr_page(state, page, image, failures, warnings))
            if not regions:
                if failures:
                    raise AppError("OCR_FAILURE", failures[0], 500, detail=failures)
                raise AppError(
                    "NO_TEXT_DETECTED",
                    "No text was found. Try a sharper image or a PDF with a real text layer.",
                    422,
                )
            state.regions = regions
            state.page_glyphs = self._glyph_index(state, regions)
            state.detected = True
            state.edits = []
            state.warnings = warnings
            state.history_index = 0
            state.snapshot_count = 0
            self._clear_snapshots(doc_id)
            self._save_meta(state)
            self._write_snapshot(state, 0)
            state.history_index = 0
            state.snapshot_count = 1
            self._save_meta(state)
            elapsed = timer.ms()
            record("detect_text", elapsed, pages=state.page_count, regions=len(regions))
            return state, {"total": elapsed}

    def replace_text(
        self,
        doc_id: str,
        region_id: str,
        new_text: str,
        mode: str,
    ) -> tuple[DocumentState, str, str | None, dict[str, float]]:
        cleaned = new_text.strip()
        if not cleaned:
            raise AppError("INVALID_REPLACEMENT_TEXT", "Replacement text is empty.", 422)
        if len(cleaned) > 400:
            raise AppError("INVALID_REPLACEMENT_TEXT", "Replacement text is limited to 400 characters.", 422)
        with self._locks[doc_id]:
            timer = Timer()
            state = self._load(doc_id)
            if not state.detected:
                raise AppError("TEXT_NOT_DETECTED", "Detect text before replacing it.", 400)
            region = next((item for item in state.regions if item.id == region_id), None)
            if region is None:
                raise AppError("REGION_NOT_FOUND", "That text region is not on this document.", 404)
            page = state.pages[region.page]
            self._truncate_future(state)
            if page.kind == "native":
                mode_used, fallback, draw_source, match_score = self._replace_native(state, region, cleaned)
            else:
                mode_used, fallback, draw_source, match_score = self._replace_raster(state, page, region, cleaned, mode)
            before = region.text
            region.text = cleaned
            page.version += 1
            state.edits.append(
                EditRecord(
                    region_id=region.id,
                    page=region.page,
                    before=before,
                    after=cleaned,
                    mode_requested=mode if page.kind != "native" else "pdf_text",
                    mode_used=mode_used,
                    draw_source=draw_source,  # type: ignore[arg-type]
                    match_score=match_score,
                    fallback_reason=fallback,
                )
            )
            if fallback and draw_source != "ai_text" and fallback not in state.warnings:
                state.warnings.append(fallback)
            new_index = state.history_index + 1
            self._write_snapshot(state, new_index)
            state.history_index = new_index
            state.snapshot_count = new_index + 1
            self._save_meta(state)
            elapsed = timer.ms()
            record("replace_text", elapsed, mode=mode_used, page_kind=page.kind)
            return state, mode_used, fallback, {"total": elapsed}

    def undo(self, doc_id: str) -> DocumentState:
        with self._locks[doc_id]:
            state = self._load(doc_id)
            if not state.can_undo:
                raise AppError("NOTHING_TO_UNDO", "There is nothing to undo.", 400)
            return self._restore(doc_id, state.history_index - 1, state.snapshot_count)

    def redo(self, doc_id: str) -> DocumentState:
        with self._locks[doc_id]:
            state = self._load(doc_id)
            if not state.can_redo:
                raise AppError("NOTHING_TO_REDO", "There is nothing to redo.", 400)
            return self._restore(doc_id, state.history_index + 1, state.snapshot_count)

    def reset(self, doc_id: str) -> DocumentState:
        with self._locks[doc_id]:
            state = self._load(doc_id)
            if state.snapshot_count < 1:
                raise AppError("NOTHING_TO_UNDO", "There are no edits to reset.", 400)
            restored = self._restore(doc_id, 0, 1)
            self._truncate_snapshots_after(doc_id, 0)
            restored.snapshot_count = 1
            restored.history_index = 0
            self._save_meta(restored)
            return restored

    def page_image(self, doc_id: str, page_index: int, variant: str) -> Path:
        state = self._load(doc_id)
        page = self._page(state, page_index)
        if variant == "original":
            return self._ensure_original_preview(state, page)
        return self._ensure_current_preview(state, page)

    def thumbnail(self, doc_id: str, page_index: int) -> Path:
        with self._locks[doc_id]:
            state = self._load(doc_id)
            page = self._page(state, page_index)
            target = self.storage.path(doc_id, f"cache/thumb_p{page.index}_v{page.version}.jpg")
            if target.exists():
                return target
            source = self._ensure_current_preview(state, page)
            image = Image.open(source).convert("RGB")
            image.thumbnail((180, 240))
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, format="JPEG", quality=80)
            return target

    def preview(self, doc_id: str) -> dict:
        state = self._load(doc_id)
        pages = []
        for page in state.pages:
            changed = page.version > 0 or self.storage.path(doc_id, f"overrides/page_{page.index}.png").exists()
            pages.append(
                {
                    "index": page.index,
                    "kind": page.kind,
                    "changed": changed,
                    "width_px": page.width_px,
                    "height_px": page.height_px,
                    "current_url": f"/api/document/{doc_id}/pages/{page.index}/image?variant=current&v={page.version}",
                    "original_url": f"/api/document/{doc_id}/pages/{page.index}/image?variant=original&v=0",
                    "thumbnail_url": f"/api/document/{doc_id}/pages/{page.index}/thumbnail?v={page.version}",
                }
            )
        return {"document_id": doc_id, "pages": pages}

    def export(self, doc_id: str, export_format: str) -> dict:
        with self._locks[doc_id]:
            state = self._load(doc_id)
            stem = Path(state.original_filename).stem or "document"
            export_dir = self.storage.path(doc_id, "exports")
            export_dir.mkdir(parents=True, exist_ok=True)
            try:
                if state.file_kind == "image":
                    if export_format not in {"png", "jpg"}:
                        raise AppError(
                            "EXPORT_FORMAT",
                            "This upload is an image. Export it as PNG or JPG.",
                            400,
                        )
                    image = load_bgr(self._ensure_current_preview(state, state.pages[0]))
                    filename = f"{stem}-edited.{export_format}"
                    target = export_dir / "output.png" if export_format == "png" else export_dir / "output.jpg"
                    if export_format == "png":
                        save_png(target, image)
                        media = "image/png"
                    else:
                        save_jpeg(target, image)
                        media = "image/jpeg"
                else:
                    if export_format != "pdf":
                        raise AppError(
                            "EXPORT_FORMAT",
                            "This upload is a PDF. Export it as PDF so every page stays in order.",
                            400,
                        )
                    filename = f"{stem}-edited.pdf"
                    target = export_dir / "output.pdf"
                    overrides = {}
                    for page in state.pages:
                        override = self.storage.path(doc_id, f"overrides/page_{page.index}.png")
                        if override.exists():
                            overrides[page.index] = override
                    self.pdf.export_mixed(self.storage.path(doc_id, "work.pdf"), overrides, target)
                    media = "application/pdf"
            except AppError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("Export failed")
                raise AppError("EXPORT_FAILED", "The edited file could not be exported.", 500) from exc
            (export_dir / "latest.txt").write_text(f"{filename}\n{target.name}\n{media}\n", encoding="utf-8")
            return {
                "document_id": doc_id,
                "filename": filename,
                "media_type": media,
                "download_url": f"/api/document/{doc_id}/download",
            }

    def download(self, doc_id: str) -> tuple[Path, str, str]:
        self._load(doc_id)
        latest = self.storage.path(doc_id, "exports/latest.txt")
        if not latest.exists():
            raise AppError("EXPORT_FAILED", "Export the document before downloading it.", 400)
        filename, stored, media = latest.read_text(encoding="utf-8").splitlines()[:3]
        path = self.storage.path(doc_id, f"exports/{stored}")
        if not path.exists():
            raise AppError("EXPORT_FAILED", "The exported file is missing. Export it again.", 404)
        return path, filename, media

    def _create_pdf(self, doc_id: str, filename: str, data: bytes) -> DocumentState:
        original = self.storage.write_bytes(doc_id, "original.pdf", data)
        work = self.storage.path(doc_id, "work.pdf")
        shutil.copy2(original, work)
        max_side = 2400
        pages = self.pdf.inspect(original, self.settings.render_dpi, max_side)
        if len(pages) > self.settings.max_pdf_pages:
            raise AppError(
                "TOO_MANY_PAGES",
                f"This PDF has {len(pages)} pages. The limit is {self.settings.max_pdf_pages}.",
                413,
            )
        if any(page.width_px * page.height_px > self.settings.max_page_pixels for page in pages):
            raise AppError("IMAGE_TOO_LARGE", "A PDF page is larger than the safety limit.", 413)
        return self._new_state(doc_id, filename, "pdf", "pdf", pages)

    def _create_image(self, doc_id: str, filename: str, media_type: str, data: bytes) -> DocumentState:
        extension = "png" if media_type == "png" else "jpg"
        original = self.storage.write_bytes(doc_id, f"original.{extension}", data)
        try:
            image = load_bgr(original)
        except AppError:
            raise
        height, width = image.shape[:2]
        if width * height > self.settings.max_page_pixels:
            raise AppError("IMAGE_TOO_LARGE", "This image is larger than the safety limit.", 413)
        save_png(self.storage.path(doc_id, "original_pages/page_0.png"), image)
        save_png(self.storage.path(doc_id, "pages/page_0.png"), image)
        page = PageInfo(index=0, kind="image", width_px=width, height_px=height, pixel_scale=1.0)
        return self._new_state(doc_id, filename, media_type, "image", [page])  # type: ignore[arg-type]

    def _new_state(
        self,
        doc_id: str,
        filename: str,
        media_type: str,
        file_kind: str,
        pages: list[PageInfo],
    ) -> DocumentState:
        return DocumentState(
            id=doc_id,
            original_filename=filename,
            media_type=media_type,  # type: ignore[arg-type]
            file_kind=file_kind,  # type: ignore[arg-type]
            created_at=datetime.now(timezone.utc).isoformat(),
            page_count=len(pages),
            pages=pages,
            render_dpi=self.settings.render_dpi,
        )

    def _ocr_page(
        self,
        state: DocumentState,
        page: PageInfo,
        image: np.ndarray,
        failures: list[str],
        warnings: list[str],
    ) -> list[TextRegion]:
        try:
            raw = self.ocr.detect(image)
        except AppError as exc:
            detail = exc.detail or exc.message
            failures.append(str(detail))
            warnings.append(f"Page {page.index + 1}: {exc.message} {detail}")
            return []
        found = normalize_detections(raw, page=page.index, page_width=float(page.width_px))
        if not found:
            warnings.append(f"No text on page {page.index + 1}.")
            return []
        styled: list[TextRegion] = []
        for region in found:
            polygon = np.asarray(region.polygon, dtype=np.float32)
            from app.image.masking import build_text_mask

            _mask, tight = build_text_mask(image, polygon)
            region.style = estimate_style(
                image,
                polygon,
                tight,
                text=region.text,
                page_width=float(page.width_px),
                base=region.style,
            )
            if page.kind == "scanned" and page.pixel_scale:
                region.pdf_bbox = _scale_bbox(region.bbox, 1.0 / page.pixel_scale)
            if not region.source_text:
                region.source_text = region.text
            styled.append(region)
        return styled

    def _glyph_index(self, state: DocumentState, regions: list[TextRegion]) -> dict[str, str]:
        index: dict[str, str] = {}
        for page in state.pages:
            if page.kind == "native":
                continue
            try:
                image = load_bgr(self._original_raster(state, page))
            except Exception:
                logger.exception("Could not read page %s while collecting page letters", page.index)
                continue
            on_page = [item for item in regions if item.page == page.index and item.source == "ocr"]
            if not on_page:
                continue
            try:
                index[str(page.index)] = page_glyph_alphabet(image, on_page)
            except Exception:
                logger.exception("Could not collect page letters on page %s", page.index)
        return index

    def _replace_native(self, state: DocumentState, region: TextRegion, new_text: str) -> tuple[str, str | None, str, float | None]:
        font = resolve_font(region.style.family, region.style.bold)
        if font is None:
            raise AppError(
                "MISSING_FONTS",
                "Bundled fonts were not found in the fonts/ directory, so PDF text cannot be rewritten.",
                500,
            )
        others = [item for item in state.regions if item.page == region.page]
        self.pdf.replace_native_text(
            self.storage.path(state.id, "work.pdf"),
            region.page,
            region,
            new_text,
            font,
            others,
        )
        self._drop_page_cache(state.id, region.page)
        return "pdf_text", None, "pdf_text", None

    def _replace_raster(
        self,
        state: DocumentState,
        page: PageInfo,
        region: TextRegion,
        new_text: str,
        mode: str,
    ) -> tuple[str, str | None]:
        working = load_bgr(self._current_raster(state, page))
        reference = load_bgr(self._original_raster(state, page))
        others = [item for item in state.regions if item.page == region.page]
        edited, mode_used, fallback, draw_source, match_score = replace_raster_text(
            working, reference, region, new_text, mode, others
        )
        if page.kind == "image":
            save_png(self.storage.path(state.id, "pages/page_0.png"), edited)
        else:
            save_png(self.storage.path(state.id, f"overrides/page_{page.index}.png"), edited)
        self._drop_page_cache(state.id, page.index)
        return mode_used, fallback, draw_source, match_score

    def _current_raster(self, state: DocumentState, page: PageInfo) -> Path:
        if page.kind == "image":
            return self.storage.path(state.id, "pages/page_0.png")
        override = self.storage.path(state.id, f"overrides/page_{page.index}.png")
        if override.exists():
            return override
        return self._original_pdf_raster(state, page)

    def _original_raster(self, state: DocumentState, page: PageInfo) -> Path:
        if page.kind == "image":
            return self.storage.path(state.id, "original_pages/page_0.png")
        return self._original_pdf_raster(state, page)

    def _original_pdf_raster(self, state: DocumentState, page: PageInfo) -> Path:
        target = self.storage.path(state.id, f"cache/original_p{page.index}.png")
        with self._locks[state.id]:
            if not target.exists():
                image = self.pdf.render_page(self.storage.path(state.id, "original.pdf"), page)
                save_png(target, image)
            return target

    def _ensure_original_preview(self, state: DocumentState, page: PageInfo) -> Path:
        return self._original_raster(state, page)

    def _ensure_current_preview(self, state: DocumentState, page: PageInfo) -> Path:
        if page.kind == "image":
            return self.storage.path(state.id, "pages/page_0.png")
        if page.kind == "scanned":
            override = self.storage.path(state.id, f"overrides/page_{page.index}.png")
            if override.exists():
                return override
            return self._original_pdf_raster(state, page)
        target = self.storage.path(state.id, f"cache/work_p{page.index}_v{page.version}.png")
        with self._locks[state.id]:
            if not target.exists():
                image = self.pdf.render_page(self.storage.path(state.id, "work.pdf"), page)
                save_png(target, image)
            return target

    def _restore_pristine(self, state: DocumentState) -> None:
        doc_id = state.id
        if state.file_kind == "image":
            source = self.storage.path(doc_id, "original_pages/page_0.png")
            dest = self.storage.path(doc_id, "pages/page_0.png")
            if source.exists():
                shutil.copy2(source, dest)
        else:
            shutil.copy2(self.storage.path(doc_id, "original.pdf"), self.storage.path(doc_id, "work.pdf"))
            overrides = self.storage.path(doc_id, "overrides")
            if overrides.exists():
                shutil.rmtree(overrides)
        for page in state.pages:
            page.version = 0
        self._drop_page_cache(doc_id, None)

    def _write_snapshot(self, state: DocumentState, index: int) -> None:
        snap = self.storage.path(state.id, f"snapshots/{index}")
        if snap.exists():
            shutil.rmtree(snap)
        snap.mkdir(parents=True)
        copy = state.model_copy(deep=True)
        copy.history_index = index
        copy.snapshot_count = index + 1
        (snap / "state.json").write_text(copy.model_dump_json(), encoding="utf-8")
        work = self.storage.path(state.id, "work.pdf")
        if work.exists():
            shutil.copy2(work, snap / "work.pdf")
        self._copy_tree(self.storage.path(state.id, "pages"), snap / "pages")
        self._copy_tree(self.storage.path(state.id, "overrides"), snap / "overrides")

    def _restore(self, doc_id: str, index: int, keep_count: int) -> DocumentState:
        snap = self.storage.path(doc_id, f"snapshots/{index}")
        state_path = snap / "state.json"
        if not state_path.exists():
            raise AppError("NOTHING_TO_UNDO", "That edit snapshot is missing.", 500)
        restored = DocumentState.model_validate_json(state_path.read_text(encoding="utf-8"))
        restored.history_index = index
        restored.snapshot_count = keep_count
        if (snap / "work.pdf").exists():
            shutil.copy2(snap / "work.pdf", self.storage.path(doc_id, "work.pdf"))
        self._replace_tree(snap / "pages", self.storage.path(doc_id, "pages"))
        self._replace_tree(snap / "overrides", self.storage.path(doc_id, "overrides"))
        self._drop_page_cache(doc_id, None)
        self._save_meta(restored)
        return restored

    def _truncate_future(self, state: DocumentState) -> None:
        for index in range(state.history_index + 1, state.snapshot_count):
            snap = self.storage.path(state.id, f"snapshots/{index}")
            if snap.exists():
                shutil.rmtree(snap)
        state.snapshot_count = state.history_index + 1

    def _truncate_snapshots_after(self, doc_id: str, index: int) -> None:
        root = self.storage.path(doc_id, "snapshots")
        if not root.exists():
            return
        for child in root.iterdir():
            if child.is_dir() and child.name.isdigit() and int(child.name) > index:
                shutil.rmtree(child)

    def _clear_snapshots(self, doc_id: str) -> None:
        root = self.storage.path(doc_id, "snapshots")
        if root.exists():
            shutil.rmtree(root)

    def _drop_page_cache(self, doc_id: str, page_index: int | None) -> None:
        cache = self.storage.path(doc_id, "cache")
        if not cache.exists():
            return
        for child in cache.iterdir():
            if not child.is_file():
                continue
            if child.name.startswith("original_"):
                continue
            if page_index is None or _cache_belongs_to_page(child.name, page_index):
                child.unlink(missing_ok=True)

    def _copy_tree(self, src: Path, dest: Path) -> None:
        if src.exists():
            shutil.copytree(src, dest)

    def _replace_tree(self, src: Path, dest: Path) -> None:
        if dest.exists():
            shutil.rmtree(dest)
        if src.exists():
            shutil.copytree(src, dest)

    def _page(self, state: DocumentState, index: int) -> PageInfo:
        if index < 0 or index >= len(state.pages):
            raise AppError("DOCUMENT_NOT_FOUND", "That page does not exist.", 404)
        return state.pages[index]

    def _load(self, doc_id: str) -> DocumentState:
        path = self.storage.path(doc_id, "meta.json")
        if not path.exists():
            raise AppError("DOCUMENT_NOT_FOUND", "Document not found.", 404)
        return DocumentState.model_validate_json(path.read_text(encoding="utf-8"))

    def _save_meta(self, state: DocumentState) -> None:
        target = self.storage.path(state.id, "meta.json")
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"%PDF"):
        return "pdf"
    return None


def _safe_filename(name: str, media_type: str) -> str:
    base = Path(name or "").name
    cleaned = _FILENAME.sub("_", base).strip("._ ")
    if not cleaned:
        extension = {"png": "png", "jpeg": "jpg", "pdf": "pdf"}[media_type]
        cleaned = f"document.{extension}"
    return cleaned[:120]


def _cache_belongs_to_page(name: str, page_index: int) -> bool:
    return name.startswith(f"work_p{page_index}_v") or name.startswith(f"thumb_p{page_index}_v")


def _scale_bbox(bbox, scale: float):
    from app.models.domain import BBox

    return BBox(x=bbox.x * scale, y=bbox.y * scale, width=bbox.width * scale, height=bbox.height * scale)


def _read_upload(file_obj: io.BufferedIOBase, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file_obj.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise AppError(
                "FILE_TOO_LARGE",
                f"This file is larger than the {limit // (1024 * 1024)} MB limit.",
                413,
            )
        chunks.append(chunk)
    return b"".join(chunks)
