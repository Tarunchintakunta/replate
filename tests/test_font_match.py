"""The closest bundled face is chosen from the ink, not from a fixed sans default."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.image.masking import build_text_mask
from app.image.style import estimate_style

FONT_DIR = Path(__file__).resolve().parents[1] / "fonts"


def _line(text: str, font_file: str, size: int = 52) -> tuple[np.ndarray, np.ndarray]:
    face = ImageFont.truetype(str(FONT_DIR / font_file), size)
    left, top, right, bottom = face.getbbox(text)
    width, height = right - left + 24, bottom - top + 24
    image = Image.new("RGB", (width, height), (255, 255, 255))
    ImageDraw.Draw(image).text((12 - left, 12 - top), text, font=face, fill=(0, 0, 0))
    array = np.array(image)[:, :, ::-1].copy()
    polygon = np.array([[2, 2], [width - 2, 2], [width - 2, height - 2], [2, height - 2]], np.float32)
    return array, polygon


def test_regular_sans_is_not_called_bold_or_condensed():
    image, polygon = _line("HELLO WORLD", "LiberationSans-Regular.ttf")
    _mask, tight = build_text_mask(image, polygon)
    style = estimate_style(image, polygon, tight, text="HELLO WORLD", page_width=float(image.shape[1]))
    assert style.family == "sans"
    assert style.bold is False
    assert style.font_label == "Liberation Sans"
    assert style.font_confidence is not None and style.font_confidence >= 0.45


def test_condensed_bold_is_selected_for_condensed_bold_ink():
    image, polygon = _line("REDUCED PRICE", "BarlowCondensed-Bold.ttf", size=48)
    _mask, tight = build_text_mask(image, polygon)
    style = estimate_style(image, polygon, tight, text="REDUCED PRICE", page_width=float(image.shape[1]))
    assert style.family == "condensed"
    assert style.bold is True
    assert "Condensed" in style.font_label
    assert style.font_confidence is not None and style.font_confidence >= 0.45


def test_low_confidence_replacement_is_still_drawn():
    from app.image.editing import replace_raster_text
    from app.models.domain import BBox, TextRegion

    image = np.full((90, 280, 3), 255, np.uint8)
    region = TextRegion(
        id="p0r000",
        page=0,
        text="EVERY LITTLE HELPS",
        bbox=BBox(x=10, y=20, width=200, height=40),
        polygon=[[10, 20], [210, 20], [210, 60], [10, 60]],
        confidence=0.9,
        source="ocr",
    )
    region.style.family = "condensed"
    region.style.bold = True
    region.style.font_label = "Barlow Condensed Bold"
    region.style.font_confidence = 0.27
    edited, _mode, _fallback, _draw, _score = replace_raster_text(
        image, image, region, "EVERY LITTLE COUNTS", "fast"
    )
    assert not np.array_equal(edited, image)
