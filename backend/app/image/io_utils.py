"""Image decode/encode that respects EXIF orientation."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.errors import AppError

Image.MAX_IMAGE_PIXELS = 40_000_000


def load_bgr(path: Path) -> np.ndarray:
    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            rgb = image.convert("RGB")
            array = np.array(rgb)
    except Image.DecompressionBombError as exc:
        raise AppError(
            "IMAGE_TOO_LARGE",
            "This image expands to more pixels than the safety limit.",
            413,
        ) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise AppError("CORRUPTED_IMAGE", "The image could not be opened.", 400) from exc
    return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)


def save_png(path: Path, image_bgr: np.ndarray) -> None:
    _save_atomic(path, image_bgr, "PNG")


def save_jpeg(path: Path, image_bgr: np.ndarray, quality: int = 92) -> None:
    _save_atomic(path, image_bgr, "JPEG", quality=quality)


def _save_atomic(path: Path, image_bgr: np.ndarray, kind: str, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    temporary = path.with_name(f".{path.name}.partial")
    image = Image.fromarray(rgb)
    if kind == "JPEG":
        image.save(temporary, format="JPEG", quality=quality, optimize=True)
    else:
        image.save(temporary, format="PNG")
    temporary.replace(path)
