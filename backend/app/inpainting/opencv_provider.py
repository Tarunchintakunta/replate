"""OpenCV TELEA inpainting. Always available. Weak on strong texture."""

from __future__ import annotations

import cv2
import numpy as np

from app.metrics import Timer, record


class OpenCVInpainting:
    name = "fast"

    def available(self) -> tuple[bool, str]:
        return True, "OpenCV TELEA"

    def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        timer = Timer()
        painted = mask
        if painted.ndim == 3:
            painted = painted[:, :, 0]
        painted = np.where(painted > 0, 255, 0).astype(np.uint8)
        if int(painted.sum()) == 0:
            return image_bgr.copy()
        area = float(painted.sum()) / 255.0
        radius = int(np.clip(3 + area**0.5 / 40.0, 3, 12))
        result = cv2.inpaint(image_bgr, painted, radius, cv2.INPAINT_TELEA)
        record("inpaint_fast", timer.ms(), radius=radius, pixels=int(area))
        return result
