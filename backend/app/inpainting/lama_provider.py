"""LaMa inpainting via a TorchScript checkpoint.

The checkpoint is loaded once. If the file is missing, the checksum does not
match, or torch cannot load it, callers fall back to OpenCV.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from typing import Any

import cv2
import numpy as np

from app.config import get_settings
from app.device import rss_mb, torch_device
from app.errors import AppError
from app.inference_lane import run_inference
from app.metrics import Timer, record

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model: Any = None
_device: str = "cpu"
_load_ms: float | None = None
_error: str | None = None
_checksum_ok = False


class LamaInpainting:
    name = "ai"

    def available(self) -> tuple[bool, str]:
        ok, detail = probe_lama()
        return ok, detail

    def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return run_inference(lambda: self._inpaint(image_bgr, mask))

    def _inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        model, device = _load_model()
        timer = Timer()
        result = image_bgr.copy()
        painted = mask[:, :, 0] if mask.ndim == 3 else mask
        ys, xs = np.where(painted > 0)
        if len(xs) == 0:
            return result
        margin = 48
        y0 = max(0, int(ys.min()) - margin)
        x0 = max(0, int(xs.min()) - margin)
        y1 = min(image_bgr.shape[0], int(ys.max()) + margin + 1)
        x1 = min(image_bgr.shape[1], int(xs.max()) + margin + 1)
        crop = image_bgr[y0:y1, x0:x1]
        crop_mask = painted[y0:y1, x0:x1]
        filled = _run(model, device, crop, crop_mask)
        # The model also nudges pixels it was not asked to fill. Keep only the
        # masked area (softly), so no rectangle seam shows around the edit.
        weight = cv2.GaussianBlur((crop_mask > 0).astype(np.float32), (0, 0), 1.0)
        weight = np.maximum(weight, (crop_mask > 0).astype(np.float32))[..., None]
        result[y0:y1, x0:x1] = np.clip(filled * weight + crop * (1 - weight), 0, 255).astype(np.uint8)
        record("inpaint_ai", timer.ms(), crop_w=x1 - x0, crop_h=y1 - y0, device=device)
        return result


def probe_lama() -> tuple[bool, str]:
    """Readiness check. The checksum is verified once per process."""
    global _checksum_ok
    if _error:
        return False, _error
    settings = get_settings()
    path = settings.lama_path
    if not path.is_file():
        return False, f"LaMa weights not found at {path}. Run python scripts/download_models.py."
    if not _checksum_ok:
        expected = _expected_checksum(settings.models_dir / "checksums.json", settings.lama_relpath)
        if expected is None:
            return False, "models/checksums.json has no checksum for the LaMa weights."
        digest = _sha256(path)
        if digest != expected:
            return False, "LaMa checksum does not match models/checksums.json. Refusing to load it."
        _checksum_ok = True
    return True, "LaMa TorchScript ready"


def lama_status() -> dict[str, Any]:
    ok, detail = probe_lama()
    return {
        "engine": "lama",
        "ready": ok,
        "loaded": _model is not None,
        "device": _device if _model is not None else torch_device(),
        "load_ms": _load_ms,
        "detail": detail,
        "rss_mb": rss_mb(),
    }


def _load_model() -> tuple[Any, str]:
    global _model, _device, _load_ms, _error, _checked
    if _model is not None:
        return _model, _device
    with _lock:
        if _model is not None:
            return _model, _device
        ok, detail = probe_lama()
        if not ok:
            _error = detail
            raise AppError("MODEL_UNAVAILABLE", detail, 503)
        try:
            import torch
        except Exception as exc:  # noqa: BLE001
            _error = f"PyTorch is not installed, so LaMa cannot run ({exc})."
            raise AppError("MODEL_UNAVAILABLE", _error, 503) from exc
        timer = Timer()
        device = torch_device()
        path = get_settings().lama_path
        try:
            # TorchScript is not pickle, but it can still embed operators.
            # We only load this path after the pinned SHA-256 matches.
            model = torch.jit.load(str(path), map_location=device)
            model.eval()
        except Exception as exc:  # noqa: BLE001
            _error = f"LaMa weights failed to load: {exc}"
            logger.exception("LaMa load failed")
            raise AppError("MODEL_UNAVAILABLE", _error, 503) from exc
        _model = model
        _device = device
        _load_ms = timer.ms()
        _error = None
        record("lama_model_load", _load_ms, device=device, rss_mb=rss_mb())
        logger.info("Loaded LaMa on %s in %.0f ms", device, _load_ms)
        return _model, _device


def _run(model: Any, device: str, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    import torch

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    original_h, original_w = rgb.shape[:2]
    image_t = _prepare_image(rgb)
    mask_t = _prepare_mask(mask)
    image_t = torch.from_numpy(image_t).unsqueeze(0).to(device)
    mask_t = torch.from_numpy(mask_t).unsqueeze(0).to(device)
    mask_t = (mask_t > 0).float()
    with torch.inference_mode():
        output = model(image_t, mask_t)
    array = output[0].permute(1, 2, 0).detach().cpu().numpy()
    array = np.clip(array * 255.0, 0, 255).astype(np.uint8)
    array = array[:original_h, :original_w]
    return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)


def _prepare_image(rgb: np.ndarray) -> np.ndarray:
    array = np.transpose(rgb, (2, 0, 1)).astype(np.float32) / 255.0
    return _pad_modulo(array, 8)


def _prepare_mask(mask: np.ndarray) -> np.ndarray:
    array = (mask > 0).astype(np.float32)[None, ...]
    return _pad_modulo(array, 8)


def _pad_modulo(array: np.ndarray, modulo: int) -> np.ndarray:
    _channels, height, width = array.shape
    out_h = height if height % modulo == 0 else height + (modulo - height % modulo)
    out_w = width if width % modulo == 0 else width + (modulo - width % modulo)
    return np.pad(array, ((0, 0), (0, out_h - height), (0, out_w - width)), mode="symmetric")


def _expected_checksum(path: Any, key: str) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get(key)
    return str(value) if value else None


def _sha256(path: Any) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
