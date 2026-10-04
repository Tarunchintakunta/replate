"""Choose the bundled face that best matches ink already on the page.

The original font file is not recovered. Each candidate is drawn at the
same height as the detected line and scored against that line's mask.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings

# family, bold, filename, label shown in the UI
CANDIDATES: tuple[tuple[str, bool, str, str], ...] = (
    ("sans", False, "LiberationSans-Regular.ttf", "Liberation Sans"),
    ("sans", True, "LiberationSans-Bold.ttf", "Liberation Sans Bold"),
    ("serif", False, "LiberationSerif-Regular.ttf", "Liberation Serif"),
    ("serif", True, "LiberationSerif-Bold.ttf", "Liberation Serif Bold"),
    ("mono", False, "LiberationMono-Regular.ttf", "Liberation Mono"),
    ("mono", True, "LiberationMono-Bold.ttf", "Liberation Mono Bold"),
    ("condensed", False, "BarlowCondensed-Regular.ttf", "Barlow Condensed"),
    ("condensed", True, "BarlowCondensed-Bold.ttf", "Barlow Condensed Bold"),
    ("receipt", False, "ShareTechMono-Regular.ttf", "Share Tech Mono"),
)


# A redraw is kept only when the chosen face, at its own width, covers the ink.
# Stretching a face to the box made weak matches look acceptable and then drew
# letters that did not resemble the line.
MIN_FONT_MATCH = 0.45
# A tilted or noisy line scores lower after the ink is resampled. It may still
# be drawn, but only if the later visual check accepts the render. Below this
# the face is too far from the ink to try.
SOFT_FONT_MATCH = 0.34


def match_bundled_font(tight_mask: np.ndarray, text: str) -> tuple[str, bool, str, float] | None:
    cleaned = " ".join(text.split())
    if len(cleaned) < 3:
        return None
    crop = _ink_crop(tight_mask)
    if crop is None:
        return None
    height, width = crop.shape
    if height < 8 or width < 8:
        return None
    best: tuple[float, str, bool, str] | None = None
    for view in _orientations(crop):
        view_h, view_w = view.shape
        if view_h < 8 or view_w < 8:
            continue
        for family, bold, filename, label in CANDIDATES:
            path = get_settings().fonts_dir / filename
            if not path.is_file():
                continue
            rendered = _render_mask(cleaned, path, view_h)
            if rendered is None:
                continue
            score = _score(view, rendered)
            if best is None or score > best[0]:
                best = (score, family, bold, label)
    if best is None:
        return None
    return best[1], best[2], best[3], best[0]


def label_for(family: str, bold: bool) -> str:
    for candidate_family, candidate_bold, _filename, label in CANDIDATES:
        if candidate_family == family and candidate_bold == bold:
            return label
    return family


def _ink_crop(mask: np.ndarray) -> np.ndarray | None:
    ink = mask > 0
    ys, xs = np.where(ink)
    if len(xs) < 12:
        return None
    crop = ink[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    return _level(crop)


def _orientations(crop: np.ndarray) -> list[np.ndarray]:
    leveled = _level(crop)
    turned = np.rot90(leveled, 2)
    return [leveled, turned, np.fliplr(leveled), np.fliplr(turned)]


def _level(crop: np.ndarray) -> np.ndarray:
    """Rotate a tilted line so the font comparison sees upright letters."""
    ys, xs = np.where(crop)
    if len(xs) < 30:
        return crop
    center, size, angle = cv2.minAreaRect(np.stack([xs, ys], axis=1).astype(np.float32))
    width, height = size
    if width < height:
        angle += 90.0
    if abs(angle) < 2.0 or abs(abs(angle) - 180.0) < 2.0:
        return crop
    matrix = cv2.getRotationMatrix2D((float(center[0]), float(center[1])), angle, 1.0)
    crop_h, crop_w = crop.shape
    cosine, sine = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(crop_h * sine + crop_w * cosine) + 2
    new_h = int(crop_h * cosine + crop_w * sine) + 2
    matrix[0, 2] += new_w / 2.0 - center[0]
    matrix[1, 2] += new_h / 2.0 - center[1]
    rotated = cv2.warpAffine((crop.astype(np.uint8) * 255), matrix, (new_w, new_h), flags=cv2.INTER_NEAREST)
    binary = rotated > 128
    rows, cols = np.where(binary)
    if len(cols) < 12:
        return crop
    return binary[rows.min() : rows.max() + 1, cols.min() : cols.max() + 1]


def _render_mask(text: str, font_path, target_h: int) -> np.ndarray | None:
    low, high = 6, max(8, int(target_h * 2.4))
    best_size = None
    while low <= high:
        mid = (low + high) // 2
        _width, height = _measure(text, font_path, mid)
        if height <= target_h:
            best_size = mid
            low = mid + 1
        else:
            high = mid - 1
    if best_size is None:
        return None
    font = ImageFont.truetype(str(font_path), best_size)
    left, top, right, bottom = font.getbbox(text)
    width = max(1, right - left)
    height = max(1, bottom - top)
    image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(image).text((-left, -top), text, font=font, fill=255)
    mask = np.array(image) > 128
    if mask.shape[0] != target_h and mask.shape[0] > 0:
        scaled = cv2.resize(mask.astype(np.uint8) * 255, (mask.shape[1], target_h), interpolation=cv2.INTER_NEAREST)
        mask = scaled > 128
    return mask


def _measure(text: str, font_path, size: int) -> tuple[int, int]:
    font = ImageFont.truetype(str(font_path), size)
    left, top, right, bottom = font.getbbox(text)
    return max(1, right - left), max(1, bottom - top)


def _score(original: np.ndarray, rendered: np.ndarray) -> float:
    """Overlap when both masks keep their own width and are centered.

    This is the confidence that redrawing the same words in that face would
    land on the ink. Forcing both into one box is not used, because that hid
    a face that was the wrong width.
    """
    canvas_h = max(original.shape[0], rendered.shape[0])
    canvas_w = max(original.shape[1], rendered.shape[1]) + 4

    def place(mask: np.ndarray) -> np.ndarray:
        canvas = np.zeros((canvas_h, canvas_w), dtype=bool)
        top = (canvas_h - mask.shape[0]) // 2
        left = (canvas_w - mask.shape[1]) // 2
        canvas[top : top + mask.shape[0], left : left + mask.shape[1]] = mask
        return canvas

    left = place(original)
    right = place(rendered)
    union = int(np.logical_or(left, right).sum())
    if union == 0:
        return 0.0
    return float(np.logical_and(left, right).sum()) / float(union)
