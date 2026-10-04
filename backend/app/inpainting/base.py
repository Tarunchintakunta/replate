"""Inpainting boundary. FAST is OpenCV. AI is LaMa, when the weights load."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class InpaintingProvider(Protocol):
    name: str

    def available(self) -> tuple[bool, str]: ...

    def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray: ...
