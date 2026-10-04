"""PyMuPDF implementation.

Native pages stay vector: the span is redacted and new text is inserted.
Scanned pages are rendered for OCR and are not rewritten here.
"""

from __future__ import annotations

import logging
import math
import uuid
from pathlib import Path

import fitz
import numpy as np

from app.errors import AppError
from app.models.domain import BBox, PageInfo, StyleHint, TextRegion
from app.ocr.normalize import infer_alignment
from app.rendering.fonts import font_key, family_from_pdf, installed_font

logger = logging.getLogger(__name__)

_MAX_SQUEEZE = 0.15  # a justified word gap may shrink by this fraction of the font size


class PyMuPDFProcessor:
    def open(self, path: Path) -> fitz.Document:
        try:
            document = fitz.open(path)
        except Exception as exc:  # noqa: BLE001
            raise AppError("CORRUPTED_PDF", "This PDF could not be opened. It may be damaged.", 400) from exc
        if document.needs_pass:
            document.close()
            raise AppError(
                "PDF_ENCRYPTED",
                "This PDF is encrypted. Remove the password and upload it again.",
                400,
            )
        if document.page_count < 1:
            document.close()
            raise AppError("CORRUPTED_PDF", "This PDF has no pages.", 400)
        return document

    def inspect(self, path: Path, dpi: int, max_side: int) -> list[PageInfo]:
        document = self.open(path)
        try:
            pages: list[PageInfo] = []
            for index, page in enumerate(document):
                kind = _classify_page(page)
                scale = _pixel_scale(page.rect, dpi, max_side)
                pages.append(
                    PageInfo(
                        index=index,
                        kind=kind,  # type: ignore[arg-type]
                        width_px=max(1, int(round(page.rect.width * scale))),
                        height_px=max(1, int(round(page.rect.height * scale))),
                        width_pt=float(page.rect.width),
                        height_pt=float(page.rect.height),
                        pixel_scale=scale,
                    )
                )
            return pages
        finally:
            document.close()

    def extract_regions(self, path: Path, page_info: PageInfo) -> list[TextRegion]:
        document = self.open(path)
        try:
            page = document[page_info.index]
            payload = page.get_text("dict")
            regions: list[TextRegion] = []
            scale = page_info.pixel_scale
            for block in payload.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    direction = line.get("dir") or (1, 0)
                    rotation = math.degrees(math.atan2(direction[1], direction[0]))
                    for span in line.get("spans", []):
                        text = str(span.get("text", "")).strip()
                        if not text:
                            continue
                        x0, y0, x1, y1 = [float(value) for value in span["bbox"]]
                        if x1 - x0 < 1 or y1 - y0 < 1:
                            continue
                        pdf_bbox = BBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0)
                        pixel_bbox = BBox(
                            x=x0 * scale,
                            y=y0 * scale,
                            width=(x1 - x0) * scale,
                            height=(y1 - y0) * scale,
                        )
                        family, bold = family_from_pdf(int(span.get("flags") or 0), str(span.get("font") or ""))
                        color = _color_to_rgb(int(span.get("color") or 0))
                        size = float(span.get("size") or pixel_bbox.height)
                        regions.append(
                            TextRegion(
                                id=f"p{page_info.index}r{len(regions):03d}",
                                page=page_info.index,
                                text=text,
                                bbox=pixel_bbox,
                                polygon=[
                                    [pixel_bbox.x, pixel_bbox.y],
                                    [pixel_bbox.x + pixel_bbox.width, pixel_bbox.y],
                                    [pixel_bbox.x + pixel_bbox.width, pixel_bbox.y + pixel_bbox.height],
                                    [pixel_bbox.x, pixel_bbox.y + pixel_bbox.height],
                                ],
                                confidence=1.0,
                                rotation=rotation,
                                source="pdf_text",
                                pdf_bbox=pdf_bbox,
                                style=StyleHint(
                                    family=family,  # type: ignore[arg-type]
                                    bold=bold,
                                    font_size_px=max(8.0, size * scale),
                                    color_rgb=color,
                                    align=infer_alignment(pixel_bbox, page_info.width_px),  # type: ignore[arg-type]
                                    pdf_font_size=size,
                                    pdf_color=[channel / 255.0 for channel in color],
                                    source_font_name=str(span.get("font") or ""),
                                ),
                            )
                        )
            return regions
        finally:
            document.close()

    def render_page(self, path: Path, page_info: PageInfo) -> np.ndarray:
        document = self.open(path)
        try:
            page = document[page_info.index]
            matrix = fitz.Matrix(page_info.pixel_scale, page_info.pixel_scale)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
            if pixmap.n == 4:
                array = array[:, :, :3]
            # PyMuPDF pixmap is RGB.
            return array[:, :, ::-1].copy()
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AppError("RENDER_FAILED", "A PDF page could not be rendered.", 500) from exc
        finally:
            document.close()

    def replace_native_text(
        self,
        path: Path,
        page_index: int,
        region: TextRegion,
        new_text: str,
        font_file: Path,
        other_regions: list[TextRegion],
    ) -> None:
        if region.pdf_bbox is None:
            raise AppError("RENDER_FAILED", "This text region has no PDF coordinates.", 500)
        document = self.open(path)
        try:
            page = document[page_index]
            rect = fitz.Rect(*region.pdf_bbox.as_rect())
            trace, chars = _trace_style(page, rect)
            face = _matching_face(document, page, trace, new_text) if trace else None
            if trace and face and trace["type"] in (1, 2):
                trace["linewidth"] = _fit_stroke_width(document, page_index, region, trace, chars, face)
            # Text that runs straight on after this span on the same line moves with it.
            chain = _followers(region, other_regions)
            later = [(other, *_trace_style(page, fitz.Rect(*other.pdf_bbox.as_rect()))) for other in chain]
            if chain or _has_left_neighbour(region, other_regions):
                region_for_draw = region.model_copy(update={"style": region.style.model_copy(update={"align": "left"})})
            else:
                region_for_draw = region
            # Remove only the old glyphs; whatever was drawn beneath them stays as it was.
            for item in [region, *chain]:
                box = fitz.Rect(*item.pdf_bbox.as_rect())
                page.add_redact_annot(fitz.Rect(box.x0 - 0.4, box.y0 - 0.3, box.x1 + 0.4, box.y1 + 0.3) & page.rect, fill=False)
            page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE,
                graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                text=fitz.PDF_REDACT_TEXT_REMOVE,
            )
            if face is None:  # no trace or no usable face: closest bundled family
                face = (fitz.Font(fontfile=str(font_file)), {"fontfile": str(font_file)})
            available = _available_width(page, chain[-1] if chain else region, other_regions)
            if chain:  # room left after the line's last span, plus what its word gaps can give up
                last = later[-1][2]
                if last and _on_right_margin(page, last[-1][3][2], last[-1][3][2] - region.pdf_bbox.x):
                    available = chain[-1].pdf_bbox.width  # justified: the paragraph margin is the limit
                available += region.pdf_bbox.width - chain[-1].pdf_bbox.width
                available += 0.95 * sum(_squeezable(t, other_chars) for _o, t, other_chars in later if t)
            alias, moved, extent = _draw_like(page, region_for_draw, trace, chars, face, new_text, available)
            _tidy_font(document, page, alias, trace["font"] if trace else None)
            _set_extent(region, *extent)
            for other, other_trace, other_chars in later:
                if other_trace is None:
                    continue
                text = "".join(chr(c[0]) for c in other_chars)
                other_face = _matching_face(document, page, other_trace, text) or face
                other_alias, _, other_extent = _draw_like(page, other, other_trace, other_chars, other_face, text, float("inf"), move=moved)
                _tidy_font(document, page, other_alias, other_trace["font"])
                _set_extent(other, *other_extent)
            temporary = path.with_suffix(".saving.pdf")
            document.save(temporary, garbage=4, deflate=True)
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Native PDF text replacement failed")
            raise AppError("EXPORT_FAILED", "The PDF text could not be replaced.", 500) from exc
        finally:
            document.close()
        temporary.replace(path)

    def export_mixed(self, work_pdf: Path, overrides: dict[int, Path], dest: Path) -> None:
        source = self.open(work_pdf)
        output = fitz.open()
        try:
            for index in range(source.page_count):
                override = overrides.get(index)
                if override is not None and override.is_file():
                    rect = source[index].rect
                    page = output.new_page(width=rect.width, height=rect.height)
                    page.insert_image(page.rect, filename=str(override))
                else:
                    output.insert_pdf(source, from_page=index, to_page=index)
            dest.parent.mkdir(parents=True, exist_ok=True)
            output.save(dest, garbage=4, deflate=True)
        except Exception as exc:  # noqa: BLE001
            raise AppError("EXPORT_FAILED", "The PDF export failed.", 500) from exc
        finally:
            output.close()
            source.close()


def _trace_style(page: fitz.Page, rect: fitz.Rect) -> tuple[dict | None, list]:
    """The drawing state (font, size, colour, render mode, stroke, opacity, direction) and glyphs inside rect.

    Fill-and-stroke text arrives as two traces over the same glyphs: one fill (type 0), one stroke (type 1).
    """
    style, chars, seen = None, [], set()
    for trace in page.get_texttrace():
        inside = [c for c in trace["chars"] if rect.contains(fitz.Point((c[3][0] + c[3][2]) / 2, (c[3][1] + c[3][3]) / 2))]
        if not inside:
            continue
        if style is None:
            style = dict(trace)
        elif {trace["type"], style["type"]} == {0, 1} and trace["font"] == style["font"] and "stroke" not in style:
            stroke = trace if trace["type"] == 1 else style
            fill = style if trace["type"] == 1 else trace
            style = dict(fill, type=2, stroke=stroke["color"], linewidth=stroke["linewidth"])
        for char in inside:
            key = (char[0], round(char[2][0], 1), round(char[2][1], 1))
            if key not in seen:
                seen.add(key)
                chars.append(char)
    while chars and not chr(chars[0][0]).strip():
        chars.pop(0)
    while chars and not chr(chars[-1][0]).strip():
        chars.pop()
    return (style if chars else None), chars


def _matching_face(document: fitz.Document, page: fitz.Page, trace: dict, new_text: str):
    """(fitz.Font, insert_font kwargs) for the span's own face: installed copy, then a complete embedded copy, then the closest library face."""
    needed = {ord(c) for c in new_text if c.strip()}
    path = installed_font(trace["font"])
    if path is not None:
        font = fitz.Font(fontfile=str(path))
        if all(font.has_glyph(c) for c in needed):
            return font, {"fontfile": str(path)}
    for xref, _ext, _type, basefont, *_rest in page.get_fonts():
        if font_key(basefont) != font_key(trace["font"]):
            continue
        buffer = document.extract_font(xref)[3]
        if buffer:
            font = fitz.Font(fontbuffer=buffer)
            if all(font.has_glyph(c) for c in needed):  # subsets usually fail here
                return font, {"fontbuffer": buffer}
    path = _closest_library_face(page, trace)
    return (fitz.Font(fontfile=str(path)), {"fontfile": str(path)}) if path else None


def _closest_library_face(page: fitz.Page, trace: dict) -> Path | None:
    """Compare the face's glyphs as drawn on this page against the open font library."""
    from app.rendering.font_library import best_font

    samples: dict[str, np.ndarray] = {}
    for other in page.get_texttrace():
        if other["font"] != trace["font"]:
            continue
        for code, _gid, _origin, box in other["chars"]:
            char = chr(code)
            if char in samples or not char.isalnum():
                continue
            clip = fitz.Rect(box) & page.rect
            if clip.is_empty:
                continue
            pix = page.get_pixmap(matrix=fitz.Matrix(96 / max(clip.height, 1), 96 / max(clip.height, 1)), clip=clip, colorspace=fitz.csGRAY, alpha=False)
            gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)
            samples[char] = gray < 128
    found = best_font(samples)
    return found[0][0] if found else None


def _tidy_font(document: fitz.Document, page: fitz.Page, alias: str, original_name: str | None) -> None:
    """Keep copied text and the font name the same as before the edit.

    MuPDF's ToUnicode maps the space and hyphen glyphs to NBSP and soft hyphen,
    so a copy of the edited line would not match the original line's text.
    """
    for xref, _ext, _type, _name, refname, *_rest in page.get_fonts():
        if refname != alias:
            continue
        kind, value = document.xref_get_key(xref, "ToUnicode")
        if kind == "xref":
            cmap_xref = int(value.split()[0])
            cmap = document.xref_stream(cmap_xref).replace(b" <00a0>", b" <0020>").replace(b" <00ad>", b" <002d>")
            document.update_stream(cmap_xref, cmap)
        if original_name:
            name = "/" + "".join(c if c.isalnum() or c in "-_" else "" for c in original_name.split("+")[-1])
            document.xref_set_key(xref, "BaseFont", name)
            kind, value = document.xref_get_key(xref, "DescendantFonts")
            if kind == "array":
                document.xref_set_key(int(value.strip("[] ").split()[0]), "BaseFont", name)


def _fit_stroke_width(document: fitz.Document, page_index: int, region: TextRegion, trace: dict, chars: list, face) -> float:
    """MuPDF's trace reports a placeholder stroke width; redraw the old text at candidate widths and keep the closest."""
    old = "".join(chr(c[0]) for c in chars)
    clip = fitz.Rect(chars[0][3])
    for char in chars:
        clip |= fitz.Rect(char[3])
    clip = fitz.Rect(clip.x0 - 0.3 * trace["size"], clip.y0 - 0.3 * trace["size"], clip.x1 + 0.3 * trace["size"], clip.y1 + 0.3 * trace["size"])
    zoom = fitz.Matrix(4, 4)

    def look(pg: fitz.Page) -> np.ndarray:
        pix = pg.get_pixmap(matrix=zoom, clip=clip, alpha=False)
        return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n).astype(np.int16)

    target = look(document[page_index])
    best = (float("inf"), float(trace["linewidth"]))
    for rel in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.1, 0.12, 0.15):
        scratch = fitz.open()
        scratch.insert_pdf(document, from_page=page_index, to_page=page_index)
        page = scratch[0]
        page.add_redact_annot(fitz.Rect(*region.pdf_bbox.as_rect()) + (-0.4, -0.3, 0.4, 0.3), fill=False)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE, text=fitz.PDF_REDACT_TEXT_REMOVE)
        _draw_like(page, region, dict(trace, linewidth=rel * trace["size"]), chars, face, old, float("inf"), decorations=False)
        error = float(np.abs(look(page) - target).mean())
        scratch.close()
        best = min(best, (error, rel * trace["size"]))
    return best[1]


def _followers(region: TextRegion, others: list[TextRegion]) -> list[TextRegion]:
    """Spans that continue this span's line without a tab-sized gap."""
    box, size = region.pdf_bbox, float(region.style.pdf_font_size or 12)
    end, chain = box.x + box.width, []
    line = [o for o in others if o.id != region.id and o.page == region.page and o.pdf_bbox is not None
            and _vertical_overlap(o.pdf_bbox, box) > 0.5 * min(o.pdf_bbox.height, box.height) and o.pdf_bbox.x >= end - 1]
    for other in sorted(line, key=lambda o: o.pdf_bbox.x):
        if other.pdf_bbox.x - end > 0.6 * size:
            break
        chain.append(other)
        end = other.pdf_bbox.x + other.pdf_bbox.width
    return chain


def _has_left_neighbour(region: TextRegion, others: list[TextRegion]) -> bool:
    box, size = region.pdf_bbox, float(region.style.pdf_font_size or 12)
    return any(
        o.id != region.id and o.page == region.page and o.pdf_bbox is not None
        and _vertical_overlap(o.pdf_bbox, box) > 0.5 * min(o.pdf_bbox.height, box.height)
        and 0 <= box.x - (o.pdf_bbox.x + o.pdf_bbox.width) < 0.6 * size
        for o in others
    )


def _squeezable(trace: dict, chars: list) -> float:
    """How much narrower a justified span can get: each word gap down to a tight space."""
    tight = float(trace["spacewidth"]) - _MAX_SQUEEZE * float(trace["size"])
    return sum(
        max(0.0, chars[i + 1][2][0] - chars[i][2][0] - tight)
        for i in range(len(chars) - 1)
        if chr(chars[i][0]) == " "
    )


def _set_extent(region: TextRegion, x0: float, x1: float) -> None:
    """Record where the redrawn span now sits, so the next edit finds all of it."""
    if region.pdf_bbox is None or x1 <= x0:
        return
    scale = region.bbox.width / max(region.pdf_bbox.width, 1e-6)
    region.pdf_bbox.x, region.pdf_bbox.width = x0, x1 - x0
    region.bbox.x, region.bbox.width = x0 * scale, (x1 - x0) * scale
    top, bottom = region.bbox.y, region.bbox.y + region.bbox.height
    region.polygon = [[x0 * scale, top], [x1 * scale, top], [x1 * scale, bottom], [x0 * scale, bottom]]


def _draw_like(page: fitz.Page, region: TextRegion, trace: dict | None, chars: list, face, new_text: str, available: float, decorations: bool = True, move: float = 0.0) -> tuple[str, float, tuple[float, float]]:
    """Draw new_text in the span's measured style.

    Returns the font alias, how far the line end moved, and the new left/right x (horizontal lines).
    """
    font, source = face
    alias = f"F{uuid.uuid4().hex[:8]}"
    page.insert_font(fontname=alias, **source)
    if trace is None or not chars:  # nothing measurable: keep the region's recorded size/colour
        size = float(region.style.pdf_font_size or 12)
        color = tuple(region.style.pdf_color or (0, 0, 0))
        trace = {"size": size, "color": color, "type": 0, "linewidth": 0.05 * size, "opacity": 1.0, "dir": (1.0, 0.0)}
        rect = fitz.Rect(*region.pdf_bbox.as_rect())
        origin = fitz.Point(rect.x0, rect.y1 + font.descender * size)
        old, along, tracking, word = "", [], 0.0, 0.0
    else:
        size = float(trace["size"])
        dx, dy = trace["dir"]
        origin = fitz.Point(chars[0][2])
        old = "".join(chr(c[0]) for c in chars)
        along = [(c[2][0] - origin.x) * dx + (c[2][1] - origin.y) * dy for c in chars]
        # Letter and word spacing = measured pen advance minus the face's own advance.
        gaps = [(old[i], along[i + 1] - along[i] - font.glyph_advance(chars[i][0]) * size) for i in range(len(chars) - 1)]
        letters = [g for c, g in gaps if c != " "]
        spaces = [g for c, g in gaps if c == " "]
        tracking = float(np.median(letters)) if letters else 0.0
        word = float(np.median(spaces)) - tracking if spaces else 0.0
    keep = 0  # unchanged leading characters stay exactly where they were
    while keep < min(len(old), len(new_text)) and old[keep] == new_text[keep]:
        keep += 1

    def layout(sz: float, tr: float, wd: float, fixed: int) -> list[float]:
        xs, pen = [], 0.0
        for i, char in enumerate(new_text):
            if i < fixed:
                pen = along[i]
            xs.append(pen)
            pen += font.glyph_advance(ord(char)) * sz + tr + (wd if char == " " else 0.0)
        return xs + [pen - tr - (wd if new_text[-1:] == " " else 0.0)]

    old_width = along[-1] + font.glyph_advance(chars[-1][0]) * size if along else region.pdf_bbox.width
    if move:  # a following span slides along its own baseline; its right end stays if justified
        dx, dy = trace["dir"]
        origin = fitz.Point(origin.x + move * dx, origin.y + move * dy)
    available = max(available, old_width) + 0.25  # the old text always fits its own slot
    xs = layout(size, tracking, word, keep)
    # Too long for the slot: tighten spacing first, then scale the whole line uniformly.
    if xs[-1] > available and tracking > 0:
        tracking = max(0.0, tracking - (xs[-1] - available) / max(len(new_text) - 1, 1))
        keep, xs = 0, layout(size, tracking, word, 0)
    while size > 4 and xs[-1] > available:
        size *= 0.97
        keep, xs = 0, layout(size, tracking, word * size / float(trace["size"]), 0)
    shift = 0.0
    justified = " " in new_text and bool(chars) and size == float(trace["size"]) and _on_right_margin(page, chars[-1][3][2], old_width)
    if justified and (keep < len(new_text) or move):
        # Re-justify like a word processor: spread the difference over every gap of the line,
        # so no single gap looks wider than its neighbours. Only the first word stays fixed.
        fixed = min(keep, new_text.find(" ") + 1)
        natural = layout(size, tracking, 0.0, fixed)
        gaps = new_text[max(fixed - 1, 0):].rstrip().count(" ")  # spaces whose width still moves later letters
        stretch = (old_width - move - natural[-1]) / gaps if gaps else 0.0
        if -_MAX_SQUEEZE * size <= stretch < 0.6 * size:  # ponytail: no paragraph reflow; a far shorter line stays ragged
            keep, xs = fixed, layout(size, tracking, stretch, fixed)
    elif keep < len(new_text) and old_width < 0.7 * page.rect.width and region.style.align == "center":
        shift = (old_width - xs[-1]) / 2
    elif keep < len(new_text) and region.style.align == "right":
        shift = old_width - xs[-1]
    angle = math.degrees(math.atan2(trace["dir"][1], trace["dir"][0]))
    kwargs = {
        "fontname": alias,
        "fontsize": size,
        "color": tuple(trace.get("stroke") or trace["color"]),
        "fill": tuple(trace["color"]) if trace["type"] == 2 else None,
        "render_mode": int(trace["type"]),
        "border_width": float(trace["linewidth"]) / max(size, 1e-3),
        "fill_opacity": float(trace["opacity"]),
        "stroke_opacity": float(trace["opacity"]),
    }
    if abs(angle) > 0.01:
        radians = math.radians(-angle)  # trace direction is in y-down page space; morph is not
        kwargs["morph"] = (origin, fitz.Matrix(math.cos(radians), math.sin(radians), -math.sin(radians), math.cos(radians), 0, 0))
    for char, x in zip(new_text, xs):  # spaces too: they keep word boundaries for copy and later edits
        page.insert_text(fitz.Point(origin.x + shift + x, origin.y), char, **kwargs)
    if decorations and abs(angle) <= 0.01 and not move:
        _refit_decorations(page, origin, size, old_width, origin.x + shift, origin.x + shift + xs[-1])
    extent = (origin.x + shift + xs[0], origin.x + shift + xs[-1]) if abs(angle) <= 0.01 else (0.0, 0.0)
    return alias, shift + xs[-1] - old_width + move, extent


def _on_right_margin(page: fitz.Page, right: float, width: float) -> bool:
    """A long line that ends where other lines of the page end belongs to a justified paragraph."""
    if width < 0.45 * page.rect.width:
        return False
    ends: dict[tuple[int, int], float] = {}
    for *box, _word, block, line, _n in page.get_text("words"):  # word boxes exclude trailing spaces
        ends[(block, line)] = max(ends.get((block, line), 0.0), box[2])
    return sum(abs(end - right) < 1.0 for end in ends.values()) >= 2


def _refit_decorations(page: fitz.Page, origin: fitz.Point, size: float, old_width: float, x0: float, x1: float) -> None:
    """Underline / strike-through lines drawn under the old text follow the new text's length."""
    found = []
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if (
            r.height < 0.2 * size
            and origin.y - 0.45 * size < r.y0 < origin.y + 0.4 * size
            and abs(r.x0 - origin.x) < 0.6 * size
            and abs(r.x1 - (origin.x + old_width)) < 0.6 * size
        ):
            found.append(drawing)
    if not found or (abs(x0 - origin.x) < 0.05 and abs(x1 - origin.x - old_width) < 0.05):
        return
    for drawing in found:
        pad = (drawing.get("width") or 0.5) + 0.2
        r = drawing["rect"]
        page.add_redact_annot(fitz.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad), fill=False)
    page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_NONE,
        graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
        text=fitz.PDF_REDACT_TEXT_NONE,
    )
    for drawing in found:
        r = drawing["rect"]
        left, right = x0 + (r.x0 - origin.x), x1 + (r.x1 - origin.x - old_width)
        if drawing.get("fill") is not None and r.height > 0:
            page.draw_rect(fitz.Rect(left, r.y0, right, r.y1), color=None, fill=drawing["fill"], fill_opacity=drawing.get("fill_opacity") or 1)
        else:
            y = (r.y0 + r.y1) / 2
            page.draw_line((left, y), (right, y), color=drawing.get("color"), width=drawing.get("width") or 1,
                           stroke_opacity=drawing.get("stroke_opacity") or 1, lineCap=max(drawing.get("lineCap") or (0,)))


def _classify_page(page: fitz.Page) -> str:
    text_chars = 0
    payload = page.get_text("dict")
    for block in payload.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text_chars += len(str(span.get("text", "")).strip())
    page_area = max(page.rect.width * page.rect.height, 1.0)
    largest = 0.0
    for info in page.get_image_info():
        box = info.get("bbox")
        if not box:
            continue
        area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
        largest = max(largest, area)
    coverage = largest / page_area
    if coverage >= 0.82:
        return "scanned"
    if text_chars >= 8:
        return "native"
    return "scanned"


def _pixel_scale(rect: fitz.Rect, dpi: int, max_side: int) -> float:
    scale = max(dpi, 72) / 72.0
    longest = max(rect.width, rect.height) * scale
    if longest > max_side:
        scale *= max_side / longest
    return scale


def _color_to_rgb(value: int) -> list[int]:
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255]


def _sample_background(page: fitz.Page, rect: fitz.Rect) -> tuple[float, float, float]:
    pad = 3.0
    clip = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad) & page.rect
    if clip.is_empty or clip.width < 1 or clip.height < 1:
        return (1, 1, 1)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
    array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
    scale = 2.0
    x0 = int(np.clip((rect.x0 - clip.x0) * scale, 0, pixmap.width))
    y0 = int(np.clip((rect.y0 - clip.y0) * scale, 0, pixmap.height))
    x1 = int(np.clip((rect.x1 - clip.x0) * scale, 0, pixmap.width))
    y1 = int(np.clip((rect.y1 - clip.y0) * scale, 0, pixmap.height))
    keep = np.ones((pixmap.height, pixmap.width), dtype=bool)
    keep[y0:y1, x0:x1] = False
    pixels = array[keep]
    if len(pixels) < 5:
        pixels = array.reshape(-1, array.shape[-1])
    median = np.median(pixels, axis=0)
    red, green, blue = [float(median[channel]) / 255.0 for channel in range(3)]
    return (red, green, blue)


def _available_width(page: fitz.Page, region: TextRegion, others: list[TextRegion]) -> float:
    assert region.pdf_bbox is not None
    blockers: list[float] = []
    for other in others:
        if other.id == region.id or other.page != region.page or other.pdf_bbox is None:
            continue
        overlap = _vertical_overlap(region.pdf_bbox, other.pdf_bbox)
        if overlap > 0.45 * min(region.pdf_bbox.height, other.pdf_bbox.height) and other.pdf_bbox.x > region.pdf_bbox.x + 1:
            blockers.append(other.pdf_bbox.x)
    right_limit = min(blockers) - 3 if blockers else page.rect.width - 36
    return max(region.pdf_bbox.width, right_limit - region.pdf_bbox.x)


def _vertical_overlap(a: BBox, b: BBox) -> float:
    top = max(a.y, b.y)
    bottom = min(a.y + a.height, b.y + b.height)
    return max(0.0, bottom - top)
