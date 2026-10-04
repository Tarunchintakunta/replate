"""Raster replacement: mask, inpaint, draw new text."""

from __future__ import annotations

import logging

import cv2
import numpy as np

from app.errors import AppError
from app.image.masking import background_complexity, build_text_mask
from app.inpainting.lama_provider import LamaInpainting, probe_lama
from app.inpainting.opencv_provider import OpenCVInpainting
from app.inpainting.selector import select_mode
from app.metrics import Timer, record
from app.models.domain import TextRegion
from app.rendering.fonts import resolve_font
from app.rendering.glyph_bank import GlyphBank
from app.config import get_settings
from app.inpainting import text_edit_provider as text_edit
from app.rendering.print_style import _restore_line, change_mask, preserve_line
from app.rendering.text_renderer import TextRenderer, paste_rgba
from app.rendering.visual_match import measure_appearance, refine

logger = logging.getLogger(__name__)
_FAST = OpenCVInpainting()
_AI = LamaInpainting()
_RENDERER = TextRenderer()


def replace_raster_text(
    working_bgr: np.ndarray,
    reference_bgr: np.ndarray,
    region: TextRegion,
    new_text: str,
    requested_mode: str,
    page_regions: list[TextRegion] | None = None,
) -> tuple[np.ndarray, str, str | None, str, float | None]:
    siblings = page_regions or []
    bank = _page_bank(reference_bgr, siblings)
    timer = Timer()
    polygon = np.asarray(region.polygon, dtype=np.float32)
    mask, _tight = build_text_mask(working_bgr, polygon)
    complexity = background_complexity(reference_bgr, mask)
    mode, fallback = select_mode(requested_mode, complexity)
    used = {"mode": mode, "fallback": fallback}

    def inpaint(image: np.ndarray, erase: np.ndarray) -> np.ndarray:
        # Erasing single letters needs paper grain, not a smear. LaMa runs on the
        # line crop only, so it is used unless FAST was asked for explicitly.
        if requested_mode != "fast" and used["mode"] == "fast" and used["fallback"] is None and probe_lama()[0]:
            used["mode"] = "ai"
        if used["mode"] == "ai":
            try:
                return _AI.inpaint(image, erase)
            except AppError as exc:
                logger.warning("LaMa failed, falling back to OpenCV: %s", exc.message)
                used["mode"], used["fallback"] = "fast", exc.message
        return _FAST.inpaint(image, erase)

    if region.source == "ocr":
        try:
            preserved = preserve_line(
                working_bgr,
                reference_bgr,
                polygon,
                region.source_text or region.text,
                new_text,
                bank,
                inpaint=inpaint,
                font_path=resolve_font(region.style.family, region.style.bold),
                align=region.style.align,
            )
        except AppError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Page-letter rebuild failed; using the line redraw")
            preserved = None
        if preserved is not None and not preserved.synthesized and not (preserved.rescaled and text_edit.key_present()):
            record("raster_replace", timer.ms(), mode=used["mode"], complexity=round(complexity, 3), requested=requested_mode, draw="glyphs")
            return preserved.image, used["mode"], used["fallback"], "glyphs", None

    # Letters the page never printed, or a line that does not cut into letters:
    # a neural text edit redraws only the changed letters, when it is allowed.
    ai_note = None
    if region.source == "ocr" and get_settings().text_edit != "off":
        if not text_edit.key_present():
            ai_note = "AI text edit was not used: no OPENAI_API_KEY or FAL_KEY in .env."
        else:
            source = region.source_text or region.text
            restored = _restore_line(working_bgr, reference_bgr, polygon)
            area = change_mask(reference_bgr, polygon, source, new_text)
            if area is None:
                area = text_edit.line_mask(working_bgr.shape[:2], polygon, source, new_text)
            try:
                result = text_edit.edit_line(restored, polygon, area, source, new_text, _read_text)
            except AppError as exc:
                ai_note = f"AI text edit was not used: {exc.message}"
            else:
                record("raster_replace", timer.ms(), mode="ai_text", requested=requested_mode, draw="ai_text", candidates=result.candidates)
                note = f"Redrawn by the AI text editor ({text_edit.engine()}); only the changed letters were replaced. OCR reads: {result.read_as!r}."
                return result.image, "ai_text", note, "ai_text", None

    if region.source == "ocr":
        if preserved is not None:
            draw = "synthesized"
            record(
                "raster_replace",
                timer.ms(),
                mode=used["mode"],
                complexity=round(complexity, 3),
                requested=requested_mode,
                draw=draw,
                synthesized=preserved.synthesized,
            )
            note = " ".join(part for part in (used["fallback"], ai_note) if part) or None
            if preserved.synthesized:
                shown = ", ".join(preserved.synthesized)
                extra = f"Not on the page: {shown}. Drawn from the closest matching font in this line's print."
                note = f"{note} {extra}" if note else extra
            logger.info("Synthesized %s; %s", preserved.synthesized, note)
            return preserved.image, used["mode"], note, draw, None

    # The line could not be cut into letters. Redraw it whole.
    missing = bank.missing_chars(new_text)
    use_glyphs = missing == ""
    if not use_glyphs and resolve_font(region.style.family, region.style.bold) is None:
        raise AppError(
            "MISSING_FONTS",
            "Bundled fonts were not found in the fonts/ directory, so replacement text cannot be drawn.",
            500,
        )
    try:
        if mode == "ai":
            try:
                cleaned = _AI.inpaint(working_bgr, mask)
            except AppError as exc:
                logger.warning("LaMa failed, falling back to OpenCV: %s", exc.message)
                cleaned = _FAST.inpaint(working_bgr, mask)
                mode = "fast"
                fallback = exc.message
        else:
            cleaned = _FAST.inpaint(working_bgr, mask)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Inpainting failed")
        raise AppError("INPAINT_FAILED", "The original text could not be removed.", 500) from exc
    appearance = measure_appearance(
        reference_bgr,
        polygon,
        align=region.style.align,
        line_gap_ratio=_neighbor_line_gap(region, siblings),
    )
    draw_source = "glyphs" if use_glyphs else "font"
    score = 0.0
    try:
        if appearance is None:
            rendered, _warning = _RENDERER.render(cleaned, new_text, polygon, region.style)
            draw_source = "font"
        else:
            rendered, report = _fit(cleaned, reference_bgr, polygon, region, new_text, bank, appearance, use_glyphs)
            score = report.total
            draw_source = "glyphs" if use_glyphs else "font"
            if use_glyphs and not report.accepted and resolve_font(region.style.family, region.style.bold) is not None:
                logger.info(
                    "Page-letter copy scored %s%% and was redrawn with the bundled face",
                    report.percent,
                )
                rendered, report = _fit(
                    cleaned, reference_bgr, polygon, region, new_text, bank, appearance, False
                )
                score = report.total
                draw_source = "font"
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Text render failed")
        raise AppError("RENDER_FAILED", "Replacement text could not be drawn.", 500) from exc
    record(
        "raster_replace",
        timer.ms(),
        mode=mode,
        complexity=round(complexity, 3),
        requested=requested_mode,
        draw=draw_source,
        match=round(score, 3),
    )
    fallback = " ".join(part for part in (fallback, ai_note) if part) or None
    return rendered, mode, fallback, draw_source, score


def _fit(cleaned, reference, polygon, region, new_text, bank, appearance, use_glyphs):
    def draw(params):
        if use_glyphs:
            height = max(8, int(round(appearance.ink_height * params.scale)))
            return bank.render(
                new_text,
                height,
                gap_ratio=max(0.0, appearance.gap_ratio * params.tracking),
                space_ratio=max(0.05, appearance.space_ratio * params.word_space),
                line_gap_ratio=appearance.line_gap_ratio,
                color_rgb=appearance.color_rgb,
            )
        layer, _warning = _RENDERER.build_layer(
            new_text,
            polygon,
            region.style,
            scale=params.scale,
            tracking=params.tracking,
        )
        return layer

    def paste(image, layer):
        return paste_rgba(image, layer, polygon, region.style.align)

    return refine(draw, appearance, reference, cleaned, polygon, paste)


def page_glyph_alphabet(image_bgr: np.ndarray, regions: list[TextRegion]) -> str:
    return _page_bank(image_bgr, regions).alphabet()


def _page_bank(reference_bgr: np.ndarray, regions: list[TextRegion]) -> GlyphBank:
    bank = GlyphBank()
    for item in regions:
        if item.source != "ocr":
            continue
        bank.add_region(
            reference_bgr,
            np.asarray(item.polygon, dtype=np.float32),
            item.source_text or item.text,
            item.confidence,
        )
    return bank


def _neighbor_line_gap(region: TextRegion, regions: list[TextRegion]) -> float:
    ordered = sorted((item for item in regions if item.page == region.page), key=lambda item: item.bbox.y)
    gaps: list[float] = []
    for above, below in zip(ordered, ordered[1:]):
        if above.bbox.height <= 0:
            continue
        gap = below.bbox.y - (above.bbox.y + above.bbox.height)
        if 0.05 * above.bbox.height < gap < 1.6 * above.bbox.height:
            gaps.append(gap / above.bbox.height)
    if not gaps:
        return 0.35
    return float(np.median(gaps))


def _read_text(page: np.ndarray, polygon: np.ndarray, area: np.ndarray) -> str:
    """OCR around the edited letters, left to right."""
    from app.ocr.paddle_provider import PaddleOCRProvider

    ys, xs = np.where(area > 0)
    points = np.asarray(polygon, np.float32).reshape(-1, 2)
    h = float(points[:, 1].max() - points[:, 1].min())
    x0 = int(max(0, min(xs.min(), points[:, 0].min()) - h))
    x1 = int(min(page.shape[1], max(xs.max(), points[:, 0].max()) + h))
    y0 = int(max(0, min(ys.min(), points[:, 1].min()) - 0.3 * h))
    y1 = int(min(page.shape[0], max(ys.max(), points[:, 1].max()) + 0.3 * h))
    found = PaddleOCRProvider().detect(page[y0:y1, x0:x1])
    # Only text sitting on the edited line; neighbours above or below are not part of it.
    outline = (points - [x0, y0]).astype(np.float32).reshape(-1, 1, 2)
    found = [
        item
        for item in found
        if cv2.pointPolygonTest(outline, tuple(float(v) for v in np.mean(item.polygon, axis=0)), False) >= 0
    ]
    found.sort(key=lambda item: float(np.mean([p[0] for p in item.polygon])))
    return " ".join(item.text for item in found)


