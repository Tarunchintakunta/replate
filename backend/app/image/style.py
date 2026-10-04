"""Estimate size, weight, color, and alignment from a text region.

This does not identify the original typeface. It only picks values the
renderer can match with the bundled font library.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.models.domain import StyleHint
from app.ocr.normalize import infer_alignment
from app.rendering.font_match import label_for, match_bundled_font


def estimate_style(
    image_bgr: np.ndarray,
    polygon: np.ndarray,
    tight_mask: np.ndarray,
    *,
    text: str,
    page_width: float,
    base: StyleHint | None = None,
) -> StyleHint:
    style = base.model_copy(deep=True) if base else StyleHint()
    xs = polygon[:, 0]
    ys = polygon[:, 1]
    height = max(8.0, float(ys.max() - ys.min()))
    width = max(1.0, float(xs.max() - xs.min()))
    style.font_size_px = height * 0.92
    bbox_x = float(xs.min())
    from app.models.domain import BBox

    style.align = infer_alignment(BBox(x=bbox_x, y=float(ys.min()), width=width, height=height), page_width)  # type: ignore[assignment]
    color = _text_color(image_bgr, tight_mask, polygon)
    style.color_rgb = color
    matched = match_bundled_font(tight_mask, text)
    if matched is not None:
        style.family, style.bold, style.font_label, style.font_confidence = matched  # type: ignore[assignment]
        return style
    style.bold = _looks_bold(tight_mask, height)
    if style.family == "sans" and _looks_mono(text, width, height):
        style.family = "mono"
    style.font_label = label_for(style.family, style.bold)
    return style


def _text_color(image_bgr: np.ndarray, tight_mask: np.ndarray, polygon: np.ndarray) -> list[int]:
    pixels = image_bgr[tight_mask > 0]
    if len(pixels) < 8:
        return [0, 0, 0]
    sample = pixels
    if len(sample) > 4000:
        rng = np.random.default_rng(0)
        sample = sample[rng.choice(len(sample), 4000, replace=False)]
    data = np.float32(sample)
    clusters = 2 if len(data) >= 2 else 1
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0)
    _compact, labels, centers = cv2.kmeans(data, clusters, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    background = _ring_color(image_bgr, polygon)
    distances = np.linalg.norm(centers - background, axis=1)
    chosen = centers[int(np.argmax(distances))]
    blue, green, red = [int(np.clip(channel, 0, 255)) for channel in chosen]
    return [red, green, blue]


def _ring_color(image_bgr: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    height, width = image_bgr.shape[:2]
    shape = np.zeros((height, width), np.uint8)
    cv2.fillConvexPoly(shape, np.round(polygon).astype(np.int32), 255)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    ring = cv2.subtract(cv2.dilate(shape, kernel, iterations=2), cv2.dilate(shape, kernel))
    pixels = image_bgr[ring > 0]
    if len(pixels) == 0:
        return np.array([255, 255, 255], np.float32)
    return np.median(pixels, axis=0).astype(np.float32)


def _looks_bold(tight_mask: np.ndarray, height: float) -> bool:
    if int(tight_mask.sum()) < 255 * 10 or height <= 0:
        return False
    distance = cv2.distanceTransform(tight_mask, cv2.DIST_L2, 3)
    strokes = distance[tight_mask > 0]
    if strokes.size == 0:
        return False
    stroke_width = float(np.median(strokes)) * 2.0
    return stroke_width / height > 0.22


def _looks_mono(text: str, width: float, height: float) -> bool:
    letters = [char for char in text if not char.isspace()]
    if len(letters) < 4 or height <= 0:
        return False
    aspect = (width / len(letters)) / height
    return 0.45 <= aspect <= 0.72 and all(not char.islower() for char in letters if char.isalpha())
