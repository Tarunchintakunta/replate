"""PaddleOCR adapter.

The rest of the app never sees PaddleOCR's result objects. Swap this module
for another provider without changing the API or the frontend.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import cv2
import numpy as np

from app.config import get_settings
from app.device import paddle_device
from app.errors import AppError
from app.inference_lane import run_inference
from app.metrics import Timer, record
from app.ocr.base import RawDetection

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# Largest input that ran reliably on the macOS CPU build (Tesco receipt is 1.58 MP).
_MAX_OCR_PIXELS = 1_600_000
_engine: Any = None
_load_ms: float | None = None
_load_error: str | None = None


class PaddleOCRProvider:
    name = "paddleocr"

    def detect(self, image_bgr: np.ndarray) -> list[RawDetection]:
        if not isinstance(image_bgr, np.ndarray):
            raise AppError("OCR_FAILURE", "Text detection received a file path instead of an image.", 500)
        image = np.ascontiguousarray(image_bgr)
        return run_inference(lambda: self._detect(image))

    def _detect(self, image_bgr: np.ndarray) -> list[RawDetection]:
        # Paddle's CPU conv (im2col) segfaults on macOS for multi-megapixel inputs.
        # OCR runs on a downscaled copy; polygons are mapped back to full size.
        scale = min(1.0, (_MAX_OCR_PIXELS / max(1, image_bgr.shape[0] * image_bgr.shape[1])) ** 0.5)
        if scale < 1.0:
            small = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            found = self._predict(small)
            for item in found:
                item.polygon = [[x / scale, y / scale] for x, y in item.polygon]
            return found
        return self._predict(image_bgr)

    def _predict(self, image_bgr: np.ndarray) -> list[RawDetection]:
        engine = _get_engine()
        timer = Timer()
        last_error: Exception | None = None
        result = None
        for attempt in range(2):
            try:
                result = engine.predict(image_bgr)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001 - surface OCR failures to the client
                last_error = exc
                logger.exception("PaddleOCR predict failed on attempt %s", attempt + 1)
        if last_error is not None:
            raise AppError(
                "OCR_FAILURE",
                "Text detection failed while running PaddleOCR.",
                500,
            ) from last_error
        detections = _parse_result(result)
        record("ocr_predict", timer.ms(), regions=len(detections), engine=self.name)
        return detections


def ocr_status() -> dict[str, Any]:
    return {
        "engine": "paddleocr",
        "device": paddle_device() if _engine is not None else "not_loaded",
        "loaded": _engine is not None,
        "load_ms": _load_ms,
        "error": _load_error,
        "lang": get_settings().ocr_lang,
    }


def _get_engine() -> Any:
    global _engine, _load_ms, _load_error
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        timer = Timer()
        try:
            from paddleocr import PaddleOCR
        except Exception as exc:  # noqa: BLE001
            _load_error = str(exc)
            raise AppError(
                "OCR_FAILURE",
                "PaddleOCR is not installed. Install backend/requirements.txt and run scripts/download_models.py.",
                500,
            ) from exc
        settings = get_settings()
        device = paddle_device()
        attempts: list[dict[str, Any]] = [
            {
                "lang": settings.ocr_lang,
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": True,
                "device": device,
            },
            {
                "lang": settings.ocr_lang,
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": True,
            },
            {"lang": settings.ocr_lang},
        ]
        last_error: Exception | None = None
        engine = None
        for kwargs in attempts:
            try:
                engine = PaddleOCR(**kwargs)
                logger.info("Loaded PaddleOCR with %s", kwargs)
                break
            except TypeError as exc:
                last_error = exc
                logger.info("PaddleOCR rejected kwargs %s: %s", kwargs, exc)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.exception("PaddleOCR failed to load")
                break
        if engine is None:
            _load_error = str(last_error)
            raise AppError(
                "OCR_FAILURE",
                "PaddleOCR failed to load.",
                500,
            )
        _engine = engine
        _load_ms = timer.ms()
        _load_error = None
        record("ocr_model_load", _load_ms, device=device)
        return _engine


def _parse_result(result: Any) -> list[RawDetection]:
    detections: list[RawDetection] = []
    if result is None:
        return detections
    items = result if isinstance(result, (list, tuple)) else [result]
    for item in items:
        payload = _as_payload(item)
        texts = list(payload.get("rec_texts") or [])
        scores = list(payload.get("rec_scores") or [])
        polys = payload.get("rec_polys")
        if polys is None:
            polys = payload.get("dt_polys")
        boxes = payload.get("rec_boxes")
        for index, text in enumerate(texts):
            polygon = _polygon_at(polys, boxes, index)
            if polygon is None:
                continue
            score = float(scores[index]) if index < len(scores) else 0.0
            detections.append(
                RawDetection(text=str(text), confidence=score, polygon=polygon)
            )
    return detections


def _as_payload(item: Any) -> dict[str, Any]:
    data: Any
    if isinstance(item, dict):
        data = item
    elif hasattr(item, "json"):
        raw = item.json
        data = raw() if callable(raw) else raw
    else:
        try:
            return {
                "rec_texts": item["rec_texts"],
                "rec_scores": item["rec_scores"],
                "rec_polys": item.get("rec_polys", item["dt_polys"]) if hasattr(item, "get") else item["rec_polys"],
                "rec_boxes": item["rec_boxes"] if "rec_boxes" in item else None,
            }
        except Exception:  # noqa: BLE001
            data = {}
    if isinstance(data, dict) and isinstance(data.get("res"), dict):
        inner = data["res"]
        if any(key in inner for key in ("rec_texts", "rec_polys", "dt_polys")):
            return inner
    return data if isinstance(data, dict) else {}


def _polygon_at(polys: Any, boxes: Any, index: int) -> list[list[float]] | None:
    if polys is not None:
        try:
            poly = polys[index]
        except Exception:  # noqa: BLE001
            poly = None
        if poly is not None:
            points = [[float(point[0]), float(point[1])] for point in list(poly)]
            if len(points) >= 4:
                return points[:4]
    if boxes is None:
        return None
    try:
        box = list(boxes[index])
    except Exception:  # noqa: BLE001
        return None
    if len(box) < 4:
        return None
    x0, y0, x1, y1 = [float(value) for value in box[:4]]
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
