"""OCR provider interface. Implementations must return polygons, not a UI format."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class RawDetection:
    text: str
    confidence: float
    polygon: list[list[float]]


class OCRProvider(Protocol):
    name: str

    def detect(self, image_bgr: np.ndarray) -> list[RawDetection]: ...
