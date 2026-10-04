"""Programmatic fixtures. Tests do not depend on checked-in images."""

from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parents[1] / "fonts"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size=size)


def image_bytes(
    lines: list[tuple[str, tuple[int, int, int], int]],
    *,
    size: tuple[int, int] = (1100, 420),
    background: tuple[int, int, int] = (255, 255, 255),
    kind: str = "png",
    font_file: str = "LiberationSans-Regular.ttf",
    rotate: float | None = None,
) -> bytes:
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    y = 48
    for text, color, text_size in lines:
        face = font(font_file, text_size)
        if rotate:
            layer = Image.new("RGBA", (size[0], text_size + 24), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((10, 4), text, font=face, fill=color + (255,))
            layer = layer.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)
            image.paste(layer, (40, y), layer)
            y += layer.size[1] + 12
        else:
            draw.text((48, y), text, font=face, fill=color)
            y += text_size + 28
    buffer = io.BytesIO()
    if kind == "jpg":
        image.save(buffer, format="JPEG", quality=95)
    else:
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def textured_image(text: str = "Texture line") -> bytes:
    import numpy as np

    rng = np.random.default_rng(7)
    noise = rng.integers(0, 180, (360, 980, 3), dtype=np.uint16)
    yy, xx = np.mgrid[0:360, 0:980]
    stripes = (((xx // 10) % 2) * 90 + ((yy // 8) % 2) * 50).astype(np.uint16)
    image_arr = np.clip(noise + stripes[:, :, None], 0, 255).astype(np.uint8)
    image = Image.fromarray(image_arr)
    draw = ImageDraw.Draw(image)
    draw.text((70, 140), text, font=font("LiberationSans-Bold.ttf", 64), fill=(250, 250, 250))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def native_pdf(pages: list[list[tuple[str, str, float]]]) -> bytes:
    """pages: list of lines (text, fontname, size)."""
    document = fitz.open()
    for lines in pages:
        page = document.new_page()
        y = 120
        for text, fontname, size in lines:
            page.insert_text((72, y), text, fontname=fontname, fontsize=size, color=(0.1, 0.1, 0.2))
            y += size + 22
    return _save(document)


def pdf_with_table_and_image() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 90), "Report header", fontname="helv", fontsize=20)
    page.draw_rect(fitz.Rect(72, 140, 360, 240), color=(0, 0, 0), width=1)
    page.draw_line((216, 140), (216, 240), color=(0, 0, 0), width=1)
    page.insert_text((84, 190), "Left cell", fontname="cour", fontsize=14)
    page.insert_text((230, 190), "Right cell", fontname="hebo", fontsize=14)
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 48, 48), 1)
    pixmap.set_rect(pixmap.irect, (180, 60, 40, 255))
    page.insert_image(fitz.Rect(420, 140, 500, 220), pixmap=pixmap)
    return _save(document)


def scanned_pdf(lines: list[str]) -> bytes:
    document = fitz.open()
    for text in lines:
        raster = image_bytes([(text, (0, 0, 0), 64)], size=(1000, 1400), background=(255, 255, 255))
        page = document.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=raster)
    return _save(document)


def mixed_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 120), "Native introduction", fontname="helv", fontsize=22)
    raster = image_bytes([("Scanned middle page", (0, 0, 0), 60)], size=(1000, 1400))
    scanned = document.new_page(width=595, height=842)
    scanned.insert_image(scanned.rect, stream=raster)
    last = document.new_page()
    last.insert_text((72, 120), "Closing native page", fontname="tiro", fontsize=22)
    last.draw_rect(fitz.Rect(72, 180, 320, 260), color=(0, 0, 0), width=1)
    last.insert_text((84, 225), "Table cell", fontname="cour", fontsize=14)
    return _save(document)


def _save(document: fitz.Document) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()
