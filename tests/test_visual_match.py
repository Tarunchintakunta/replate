"""Replacement is accepted only after the render is measured against the original line."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.errors import AppError
from app.image.editing import replace_raster_text
from app.image.masking import build_text_mask
from app.models.domain import BBox, TextRegion
from app.rendering.glyph_bank import GlyphBank
from app.rendering.visual_match import measure_appearance, refine

FONT = Path(__file__).resolve().parents[1] / "fonts" / "LiberationSans-Regular.ttf"


def _scene(text: str, *, shadow: tuple[int, int, tuple[int, int, int]] | None = None, stroke: int = 0):
    face = ImageFont.truetype(str(FONT), 64)
    left, top, right, bottom = face.getbbox(text)
    width, height = right - left + 80, bottom - top + 80
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    origin = (40 - left, 40 - top)
    if shadow:
        draw.text((origin[0] + shadow[0], origin[1] + shadow[1]), text, font=face, fill=shadow[2])
    if stroke:
        draw.text(origin, text, font=face, fill=(0, 0, 0), stroke_width=stroke, stroke_fill=(200, 40, 40))
    else:
        draw.text(origin, text, font=face, fill=(0, 0, 0))
    array = np.array(image)[:, :, ::-1].copy()
    polygon = np.array([[8, 8], [width - 8, 8], [width - 8, height - 8], [8, height - 8]], np.float32)
    return array, polygon


def _region(text: str, polygon: np.ndarray, confidence: float) -> TextRegion:
    x0, y0 = float(polygon[:, 0].min()), float(polygon[:, 1].min())
    x1, y1 = float(polygon[:, 0].max()), float(polygon[:, 1].max())
    region = TextRegion(
        id="line",
        page=0,
        text=text,
        source_text=text,
        bbox=BBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0),
        polygon=polygon.tolist(),
        confidence=0.99,
        source="ocr",
    )
    region.style.font_confidence = confidence
    region.style.family = "sans"
    region.style.font_label = "Liberation Sans"
    return region


def _stroke(gray: np.ndarray) -> float:
    ink = (gray < 128).astype(np.uint8)
    edge = ink - cv2.erode(ink, np.ones((3, 3), np.uint8))
    return 2.0 * int(ink.sum()) / max(int(edge.sum()), 1)


def test_page_letters_are_copied_when_the_bundled_face_is_a_poor_match():
    image, polygon = _scene("THE CAT SAT")
    region = _region("THE CAT SAT", polygon, 0.2)
    edited, _mode, _fallback, draw_source, _score = replace_raster_text(
        image, image, region, "THE SAT CAT", "fast", [region]
    )
    assert draw_source == "glyphs"
    assert not np.array_equal(edited, image)
    # "THE " is unchanged, so its pixels are the original ones.
    split = int(image.shape[1] * 0.3)
    assert float(np.abs(edited[:, :split].astype(np.int16) - image[:, :split]).mean()) < 1.0


def test_missing_letters_are_drawn_in_the_line_print_and_reported():
    image, polygon = _scene("THE CAT SAT")
    region = _region("THE CAT SAT", polygon, 0.2)
    edited, _mode, note, draw_source, _score = replace_raster_text(
        image, image, region, "QUIZ NIGHT", "fast", [region]
    )
    assert draw_source == "synthesized"
    assert note and "Q" in note and "Not on the page" in note
    before = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    after = cv2.cvtColor(edited, cv2.COLOR_BGR2GRAY)
    assert (after < 128).sum() > 0.5 * (before < 128).sum()
    # Same print: stroke width and ink gray stay with the line.
    assert abs(_stroke(after) - _stroke(before)) / _stroke(before) < 0.25
    assert abs(float(np.median(after[after < 128])) - float(np.median(before[before < 128]))) < 14


def test_plain_text_is_not_given_a_shadow_and_a_real_shadow_is_found():
    plain, plain_polygon = _scene("SHADOW")
    plain_look = measure_appearance(plain, plain_polygon)
    assert plain_look is not None
    assert plain_look.shadow is None
    assert plain_look.outline_px == 0

    shadowed, shadow_polygon = _scene("SHADOW", shadow=(5, 4, (170, 170, 170)))
    _mask, tight = build_text_mask(shadowed, shadow_polygon)
    from app.rendering.visual_match import _effects

    found = _effects(shadowed, tight, shadow_polygon)
    assert found[0] is not None
    assert found[0][0] == 5
    assert found[0][1] == 4


def test_outline_is_not_called_a_shadow():
    image, polygon = _scene("OUTLINE", stroke=3)
    _mask, tight = build_text_mask(image, polygon)
    from app.rendering.visual_match import _effects

    shadow, outline_px, color = _effects(image, tight, polygon)
    assert shadow is None
    assert outline_px > 0
    assert color is not None and color[0] > color[2]


def test_a_poor_spacing_pass_is_adjusted():
    image, polygon = _scene("THE CAT SAT")
    appearance = measure_appearance(image, polygon)
    assert appearance is not None
    seen: list[float] = []

    def draw(params):
        seen.append(params.tracking)
        layer = np.zeros((appearance.ink_height, 220, 4), np.uint8)
        for left in (4, 70, 150):
            layer[4:-4, left : left + 18, 3] = 255
        return layer

    def paste(base, layer):
        from app.rendering.text_renderer import paste_rgba

        return paste_rgba(base, layer, polygon, "left")

    _image, report = refine(draw, appearance, image, image, polygon, paste)
    assert len(seen) >= 2
    assert seen[1] < seen[0] or seen[1] > seen[0]
    assert report.passes >= 1


def test_copied_letters_keep_line_spacing():
    image, polygon = _scene("AB CD")
    bank = GlyphBank()
    bank.add_region(image, polygon, "AB CD", 0.99)
    single = bank.render("AB", 40)
    stacked = bank.render("AB\nCD", 40, line_gap_ratio=0.5)
    assert single is not None and stacked is not None
    assert stacked.shape[0] > single.shape[0] * 2
