"""Letters that do not change keep their original pixels. New letters take that print."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.image.editing import replace_raster_text
from app.models.domain import BBox, TextRegion

FONT = Path(__file__).resolve().parents[1] / "fonts" / "LiberationSans-Bold.ttf"


def _region(text: str, polygon: np.ndarray) -> TextRegion:
    x0, y0 = float(polygon[:, 0].min()), float(polygon[:, 1].min())
    x1, y1 = float(polygon[:, 0].max()), float(polygon[:, 1].max())
    region = TextRegion(
        id=text[:6],
        page=0,
        text=text,
        source_text=text,
        bbox=BBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0),
        polygon=polygon.tolist(),
        confidence=0.99,
        source="ocr",
    )
    region.style.font_confidence = 0.2
    region.style.bold = True
    return region


def _draw_tracked(draw: ImageDraw.ImageDraw, origin: tuple[int, int], text: str, face: ImageFont.FreeTypeFont, fill, stroke: int = 0) -> int:
    x, y = origin
    for char in text:
        if stroke:
            draw.text((x, y), char, font=face, fill=fill, stroke_width=stroke, stroke_fill=fill)
        else:
            draw.text((x, y), char, font=face, fill=fill)
        x += int(face.getlength(char)) + (14 if char == " " else 2)
    return x


def _page() -> tuple[np.ndarray, np.ndarray, int]:
    """Faded slogan on top, darker donor line underneath. Returns image, slogan polygon, split x of HELPS."""
    face = ImageFont.truetype(str(FONT), 46)
    slogan = "EVERY LITTLE HELPS"
    donor = "CASH COUNTS REDUCED"
    width, height = 980, 260
    paper = (196, 193, 184)
    image = Image.new("RGB", (width, height), paper)
    draw = ImageDraw.Draw(image)
    _draw_tracked(draw, (36, 156), donor, face, (25, 25, 25))
    fade = Image.new("L", (width, height), 0)
    split = _draw_tracked(ImageDraw.Draw(fade), (36, 28), slogan[: slogan.index("HELPS")], face, 255, stroke=1)
    _draw_tracked(ImageDraw.Draw(fade), (split, 28), "HELPS", face, 255, stroke=1)
    soft = cv2.GaussianBlur(np.array(fade), (0, 0), 0.8)
    cover = soft.astype(np.float32) / 255.0
    canvas = np.array(image).astype(np.float32)
    ink = np.array([130, 128, 122], np.float32)
    base = np.array(paper, np.float32)
    painted = base * (1.0 - cover[:, :, None] * 0.5) + ink * (cover[:, :, None] * 0.5)
    for row in range(40, 110, 7):
        painted[row] = painted[row] * 0.75 + base * 0.25
    crisp = np.array(image)
    painted[140:250] = crisp[140:250]
    array = np.clip(painted, 0, 255).astype(np.uint8)[:, :, ::-1].copy()
    polygon = np.array([[16, 16], [width - 16, 16], [width - 16, 132], [16, 132]], np.float32)
    return array, polygon, split


def _edge_energy(gray: np.ndarray, mask: np.ndarray) -> float:
    magnitude = np.abs(cv2.Laplacian(gray, cv2.CV_32F))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    ring = cv2.dilate(mask, kernel) - cv2.erode(mask, kernel)
    values = magnitude[ring > 0]
    if values.size < 10:
        return 0.0
    return float(values.mean())


def _ink_median(gray: np.ndarray, mask: np.ndarray) -> float:
    values = gray[mask > 0]
    return float(np.median(values)) if values.size else 0.0


def test_unchanged_letters_keep_their_pixels_and_new_letters_match_the_print():
    image, polygon, split = _page()
    region = _region("EVERY LITTLE HELPS", polygon)
    donor_poly = np.array([[20, 140], [780, 140], [780, 240], [20, 240]], np.float32)
    donor = _region("CASH COUNTS REDUCED", donor_poly)
    edited, _mode, _fallback, draw_source, _score = replace_raster_text(
        image, image, region, "EVERY LITTLE COUNTS", "fast", [region, donor]
    )
    assert draw_source == "glyphs"
    y0, y1 = 24, 130
    x0 = 20
    prefix_original = image[y0:y1, x0:split]
    prefix_edited = edited[y0:y1, x0:split]
    assert float(np.mean(np.abs(prefix_original.astype(np.int16) - prefix_edited.astype(np.int16)))) < 4.0

    gray_before = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray_after = cv2.cvtColor(edited, cv2.COLOR_BGR2GRAY)
    x1 = int(polygon[:, 0].max())
    before_span = gray_before[y0:y1, split:x1]
    after_span = gray_after[y0:y1, split:x1]
    _threshold, before_mask = cv2.threshold(before_span, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _threshold, after_mask = cv2.threshold(after_span, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    before_energy = _edge_energy(before_span, before_mask)
    after_energy = _edge_energy(after_span, after_mask)
    assert before_energy > 0
    assert 0.7 <= after_energy / before_energy <= 1.3
    assert abs(_ink_median(before_span, before_mask) - _ink_median(after_span, after_mask)) < 14
