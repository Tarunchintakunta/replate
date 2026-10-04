"""Pick FAST or LaMa from the request and the background."""

from __future__ import annotations

from app.inpainting.lama_provider import probe_lama
from app.inpainting.opencv_provider import OpenCVInpainting

_FAST = OpenCVInpainting()
_COMPLEXITY_THRESHOLD = 0.42


def select_mode(requested: str, complexity: float) -> tuple[str, str | None]:
    ai_ok, ai_detail = probe_lama()
    if requested == "fast":
        return "fast", None
    if requested == "auto" and complexity < _COMPLEXITY_THRESHOLD:
        return "fast", None
    if ai_ok:
        return "ai", None
    if requested == "auto":
        reason = f"Background looks textured, but LaMa is unavailable ({ai_detail}). Used FAST."
    else:
        reason = f"AI inpainting was requested, but LaMa is unavailable ({ai_detail}). Used FAST."
    return "fast", reason


def opencv_provider() -> OpenCVInpainting:
    return _FAST
