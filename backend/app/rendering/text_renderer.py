"""Draw replacement text into a cleaned image.

Placement follows the detected quad (rotation included) without stretching
the glyphs to the old string's width. Alignment keeps the left, center, or
right anchor of the original region.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.models.domain import StyleHint
from app.rendering.fonts import resolve_font


class TextRenderer:
    name = "pillow"

    def render(
        self,
        image_bgr: np.ndarray,
        text: str,
        polygon: list[list[float]] | np.ndarray,
        style: StyleHint,
    ) -> tuple[np.ndarray, str | None]:
        layer, warning = self.build_layer(text, polygon, style)
        return paste_rgba(image_bgr, layer, polygon, style.align), warning

    def build_layer(
        self,
        text: str,
        polygon: list[list[float]] | np.ndarray,
        style: StyleHint,
        *,
        scale: float = 1.0,
        tracking: float = 1.0,
    ) -> tuple[np.ndarray, str | None]:
        warning = None
        font_path = resolve_font(style.family, style.bold)
        quad = _order_quad(np.asarray(polygon, dtype=np.float32))
        target_h = max(8.0, (_length(quad[3] - quad[0]) + _length(quad[2] - quad[1])) / 2.0)
        old_w = max(8.0, (_length(quad[1] - quad[0]) + _length(quad[2] - quad[3])) / 2.0)
        max_w = max(old_w * 1.45, target_h) * max(scale, 0.5)
        if font_path is None:
            warning = "MISSING_FONTS"
            return _draw_default(text, style.color_rgb), warning
        size = _fit_size(text, font_path, target_h * 0.92 * scale, max_w)
        if abs(tracking - 1.0) < 0.05:
            layer = _draw(text, font_path, size, style.color_rgb)
        else:
            layer = _draw_tracked(text, font_path, size, style.color_rgb, tracking)
        return layer, warning


def paste_rgba(
    image_bgr: np.ndarray,
    rgba: np.ndarray,
    polygon: list[list[float]] | np.ndarray,
    align: str,
) -> np.ndarray:
    """Warp an RGBA patch into the detected quad and composite it."""
    quad = _order_quad(np.asarray(polygon, dtype=np.float32))
    layer_h, layer_w = rgba.shape[:2]
    dest = _place_quad(quad, float(layer_w), float(layer_h), align)
    height, width = image_bgr.shape[:2]
    source = np.float32([[0, 0], [layer_w, 0], [layer_w, layer_h], [0, layer_h]])
    matrix = cv2.getPerspectiveTransform(source, dest)
    warped = cv2.warpPerspective(
        rgba,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return _composite(image_bgr, warped)


def _draw(text: str, font_path: object, size: int, color_rgb: list[int]) -> np.ndarray:
    font = ImageFont.truetype(str(font_path), size=max(6, size))
    left, top, right, bottom = font.getbbox(text)
    width = max(1, right - left)
    height = max(1, bottom - top)
    pad = 2
    image = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    red, green, blue = [int(np.clip(channel, 0, 255)) for channel in color_rgb[:3]]
    draw.text((pad - left, pad - top), text, font=font, fill=(red, green, blue, 255))
    return np.array(image)


def _draw_tracked(text: str, font_path: object, size: int, color_rgb: list[int], tracking: float) -> np.ndarray:
    font = ImageFont.truetype(str(font_path), size=max(6, size))
    extra = int(round((tracking - 1.0) * max(size, 1) * 0.18))
    widths: list[int] = []
    for char in text:
        left, _top, right, _bottom = font.getbbox(char)
        widths.append(max(1, right - left))
    left, top, _right, bottom = font.getbbox(text)
    height = max(1, bottom - top)
    width = sum(widths) + extra * max(0, len(text) - 1) + 4
    image = Image.new("RGBA", (max(1, width), height + 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    red, green, blue = [int(np.clip(channel, 0, 255)) for channel in color_rgb[:3]]
    cursor = 2 - left
    for char, char_width in zip(text, widths):
        draw.text((cursor, 2 - top), char, font=font, fill=(red, green, blue, 255))
        cursor += char_width + extra
    return np.array(image)


def _draw_default(text: str, color_rgb: list[int]) -> np.ndarray:
    font = ImageFont.load_default()
    image = Image.new("RGBA", (max(8, len(text) * 8), 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    red, green, blue = [int(np.clip(channel, 0, 255)) for channel in color_rgb[:3]]
    draw.text((0, 0), text, font=font, fill=(red, green, blue, 255))
    return np.array(image)


def _fit_size(text: str, font_path: object, target_h: float, max_w: float) -> int:
    low, high = 6, max(8, int(target_h * 1.6))
    best = 8
    while low <= high:
        mid = (low + high) // 2
        width, height = _measure(text, font_path, mid)
        if height <= target_h and width <= max_w:
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    return best


def _measure(text: str, font_path: object, size: int) -> tuple[int, int]:
    font = ImageFont.truetype(str(font_path), size=size)
    left, top, right, bottom = font.getbbox(text)
    return max(1, right - left), max(1, bottom - top)


def _order_quad(points: np.ndarray) -> np.ndarray:
    pts = points.reshape(-1, 2).astype(np.float32)
    if len(pts) != 4:
        rect = cv2.minAreaRect(pts)
        pts = cv2.boxPoints(rect)
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)
    ordered = np.stack(
        [
            pts[int(np.argmin(sums))],
            pts[int(np.argmin(diffs))],
            pts[int(np.argmax(sums))],
            pts[int(np.argmax(diffs))],
        ]
    )
    return ordered.astype(np.float32)


def _place_quad(quad: np.ndarray, text_w: float, text_h: float, align: str) -> np.ndarray:
    direction = quad[1] - quad[0]
    norm = _length(direction)
    direction = direction / norm if norm > 1e-3 else np.array([1.0, 0.0], np.float32)
    down = quad[3] - quad[0]
    down_norm = _length(down)
    down = down / down_norm if down_norm > 1e-3 else np.array([0.0, 1.0], np.float32)
    width_vec = direction * text_w
    height_vec = down * text_h
    if align == "center":
        center = quad.mean(axis=0)
        top_left = center - width_vec / 2 - height_vec / 2
    elif align == "right":
        right_mid = (quad[1] + quad[2]) / 2
        top_left = right_mid - width_vec - height_vec / 2
    else:
        left_mid = (quad[0] + quad[3]) / 2
        top_left = left_mid - height_vec / 2
    top_right = top_left + width_vec
    bottom_right = top_right + height_vec
    bottom_left = top_left + height_vec
    return np.stack([top_left, top_right, bottom_right, bottom_left]).astype(np.float32)


def _composite(image_bgr: np.ndarray, rgba: np.ndarray) -> np.ndarray:
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    layer = rgba[:, :, :3][:, :, ::-1].astype(np.float32)
    base = image_bgr.astype(np.float32)
    mixed = layer * alpha + base * (1.0 - alpha)
    return np.clip(mixed, 0, 255).astype(np.uint8)


def _length(vector: np.ndarray) -> float:
    return float(np.linalg.norm(vector))
