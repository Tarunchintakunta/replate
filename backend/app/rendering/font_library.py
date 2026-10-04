"""Identify the closest open font for a line from letters already on the page.

The page letters are compared against every font in models/font-library
(Google Fonts via Fontsource, regular and bold) on shape, width-to-height
ratio and stroke weight. A letter the page does not have is then drawn in the
winning face. The exact font file is not recovered; the closest shape is.

The index is built once (scripts/build_font_index.py) and cached as an .npz.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings

logger = logging.getLogger(__name__)

CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
CELL = 32
_RENDER = 96


def library_dir() -> Path:
    return get_settings().models_dir / "font-library"


def glyph_features(mask: np.ndarray) -> tuple[np.ndarray, float, float] | None:
    """Tight binary letter -> (CELL x CELL soft shape, width/height, stroke/height)."""
    binary = (mask > 0).astype(np.uint8)
    ys, xs = np.where(binary > 0)
    if xs.size < 6:
        return None
    binary = binary[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = binary.shape
    # Dot-matrix and worn print: close small gaps so the shape, not the dots, is compared.
    k = max(1, int(round(h / 40)))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    area = int(binary.sum())
    edge = int((binary - cv2.erode(binary, np.ones((3, 3), np.uint8))).sum())
    stroke = 2.0 * area / max(edge, 1) / h
    cell = cv2.resize(binary.astype(np.float32), (CELL, CELL), interpolation=cv2.INTER_AREA)
    cell = cv2.GaussianBlur(cell, (0, 0), 0.6)
    return cell, w / h, stroke


def render_glyph(path: str | Path, char: str, size: int) -> tuple[np.ndarray, int] | None:
    """Anti-aliased alpha for one character, cropped to ink, and its top relative to the baseline."""
    canvas = Image.new("L", (size * 3, size * 3), 0)
    baseline = size * 2
    try:
        face = ImageFont.truetype(str(path), size)
        ImageDraw.Draw(canvas).text((size, baseline), char, font=face, fill=255, anchor="ls")
    except (OSError, ValueError):  # broken hinting or missing glyph table
        return None
    alpha = np.asarray(canvas, np.float32) / 255.0
    ys, xs = np.where(alpha > 0.1)
    if xs.size < 4:
        return None
    return alpha[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], int(ys.min()) - baseline


def build_index(out: Path | None = None, workers: int = 8) -> Path:
    from concurrent.futures import ProcessPoolExecutor

    folder = library_dir()
    fonts = sorted(str(p) for p in folder.glob("*.ttf"))
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(_index_font, fonts, chunksize=16))
    keep = [(f, r) for f, r in zip(fonts, rows) if r is not None]
    cells = np.stack([r[0] for _f, r in keep]).astype(np.float16)  # fonts x chars x CELL x CELL
    shape = np.stack([r[1] for _f, r in keep]).astype(np.float32)  # fonts x chars x (aspect, stroke, height/cap)
    target = out or folder / "index.npz"
    np.savez_compressed(target, fonts=np.array([Path(f).name for f, _r in keep]), cells=cells, shape=shape)
    return target


def _index_font(path: str):
    cells = np.zeros((len(CHARS), CELL, CELL), np.float32)
    shape = np.full((len(CHARS), 3), np.nan, np.float32)
    cap = render_glyph(path, "H", _RENDER)
    if cap is None:
        return None
    cap_h = cap[0].shape[0]
    found = 0
    for index, char in enumerate(CHARS):
        glyph = render_glyph(path, char, _RENDER)
        if glyph is None:
            continue
        features = glyph_features(glyph[0] > 0.5)
        if features is None:
            continue
        cells[index], aspect, stroke = features
        shape[index] = (aspect, stroke, glyph[0].shape[0] / max(cap_h, 1))
        found += 1
    return (cells, shape) if found >= 40 else None


@lru_cache(maxsize=1)
def _index():
    path = library_dir() / "index.npz"
    if not path.is_file():
        return None
    data = np.load(path)
    return data["fonts"], data["cells"].astype(np.float32), data["shape"]


def available() -> bool:
    return _index() is not None


@lru_cache(maxsize=1)
def _categories() -> dict[str, str]:
    import json

    path = library_dir() / "catalog.json"
    if not path.is_file():
        return {}
    return {item["id"]: item.get("category", "") for item in json.loads(path.read_text())}


def _category_prior(fonts: np.ndarray) -> np.ndarray:
    """Printed text is rarely a script face; a close script match must win clearly."""
    categories = _categories()
    return np.array([0.88 if categories.get(str(name).split("__")[0]) == "handwriting" else 1.0 for name in fonts])


def best_font(samples: dict[str, np.ndarray], top: int = 1) -> list[tuple[Path, float]]:
    """samples: char -> tight binary mask cut from the page. Returns (font path, score 0..1)."""
    index = _index()
    if index is None or not samples:
        return []
    fonts, cells, shape = index
    used = [(CHARS.index(c), glyph_features(m)) for c, m in samples.items() if c in CHARS]
    used = [(i, f) for i, f in used if f is not None]
    if not used:
        return []
    idx = np.array([i for i, _f in used])
    page_cells = np.stack([f[0] for _i, f in used])
    page_aspect = np.array([f[1] for _i, f in used])
    page_stroke = np.array([f[2] for _i, f in used])
    cand = cells[:, idx]  # fonts x n x CELL x CELL
    inter = np.minimum(cand, page_cells[None]).sum(axis=(2, 3))
    union = np.maximum(cand, page_cells[None]).sum(axis=(2, 3))
    iou = inter / np.maximum(union, 1e-6)
    aspect = np.exp(-3.0 * np.abs(np.log(np.maximum(shape[:, idx, 0], 1e-3) / page_aspect[None])))
    stroke = np.exp(-4.0 * np.abs(np.log(np.maximum(shape[:, idx, 1], 1e-3) / np.maximum(page_stroke[None], 1e-3))))
    score = iou * aspect * (0.5 + 0.5 * stroke)
    score = np.where(np.isnan(score), 0.0, score).mean(axis=1) * _category_prior(fonts)
    order = np.argsort(-score)[:top]
    folder = library_dir()
    return [(folder / str(fonts[i]), float(score[i])) for i in order]
