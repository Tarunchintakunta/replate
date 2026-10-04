"""Build a text mask from pixels inside a detected region.

A filled rectangle leaves a visible box on anything that is not flat color.
The mask keeps pixels that differ from the local background, then expands
just enough to cover antialiased edges.
"""

from __future__ import annotations

import cv2
import numpy as np


def build_text_mask(image_bgr: np.ndarray, polygon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(inpaint_mask, tight_text_mask)`` as uint8 images."""
    height, width = image_bgr.shape[:2]
    poly = np.round(polygon).astype(np.int32)
    shape = np.zeros((height, width), np.uint8)
    if len(poly) >= 3:
        cv2.fillConvexPoly(shape, poly, 255)

    background = _background_color(image_bgr, shape)
    diff = np.linalg.norm(image_bgr.astype(np.float32) - background.reshape(1, 1, 3), axis=2)
    inside = diff[shape > 0]
    if inside.size == 0:
        return shape, shape
    threshold = max(18.0, float(np.percentile(inside, 45)))
    tight = ((diff >= threshold) & (shape > 0)).astype(np.uint8) * 255
    if tight.sum() < 0.04 * max(int(shape.sum()), 1):
        tight = shape.copy()

    ys = poly[:, 1] if len(poly) else np.array([0])
    text_height = max(8, int(ys.max() - ys.min())) if len(ys) else 8
    radius = int(np.clip(text_height / 22, 1, 4))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    expanded_shape = cv2.dilate(shape, kernel)
    painted = cv2.dilate(tight, kernel)
    painted = cv2.bitwise_and(painted, expanded_shape)
    return painted, tight


def background_complexity(image_bgr: np.ndarray, mask: np.ndarray) -> float:
    """0 is flat color, 1 is a busy texture. Used to choose FAST vs LaMa."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    outer = cv2.dilate(mask, kernel)
    ring = cv2.subtract(outer, mask)
    if int(ring.sum()) < 255 * 20:
        return 0.0
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    values = gray[ring > 0].astype(np.float32)
    std = float(values.std()) if values.size else 0.0
    edges = cv2.Canny(gray, 80, 160)
    edge_ratio = float((edges[ring > 0] > 0).mean()) if values.size else 0.0
    score = min(1.0, std / 38.0) * 0.7 + min(1.0, edge_ratio / 0.1) * 0.3
    return float(score)


def _background_color(image_bgr: np.ndarray, shape: np.ndarray) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    outer = cv2.dilate(shape, kernel, iterations=2)
    ring = cv2.subtract(outer, cv2.dilate(shape, kernel, iterations=1))
    pixels = image_bgr[ring > 0]
    if len(pixels) < 8:
        pixels = image_bgr[shape == 0]
    if len(pixels) == 0:
        return np.array([255, 255, 255], np.float32)
    return np.median(pixels, axis=0).astype(np.float32)
