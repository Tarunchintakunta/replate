"""Turn raw detections into the app's normalized text regions."""

from __future__ import annotations

import math

from app.models.domain import BBox, StyleHint, TextRegion
from app.ocr.base import RawDetection


def bbox_from_polygon(polygon: list[list[float]]) -> BBox:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return BBox(x=float(min_x), y=float(min_y), width=float(max_x - min_x), height=float(max_y - min_y))


def rotation_degrees(polygon: list[list[float]]) -> float:
    if len(polygon) < 2:
        return 0.0
    dx = polygon[1][0] - polygon[0][0]
    dy = polygon[1][1] - polygon[0][1]
    if abs(dx) < 1e-3 and abs(dy) < 1e-3:
        return 0.0
    return float(math.degrees(math.atan2(dy, dx)))


def infer_alignment(bbox: BBox, page_width: float) -> str:
    if page_width <= 0:
        return "left"
    left = bbox.x
    right = page_width - (bbox.x + bbox.width)
    if left > page_width * 0.12 and abs(left - right) < page_width * 0.08:
        return "center"
    if left > right * 1.8 and left > page_width * 0.28:
        return "right"
    return "left"


def normalize_detections(
    detections: list[RawDetection],
    *,
    page: int,
    page_width: float,
    source: str = "ocr",
    min_confidence: float = 0.2,
) -> list[TextRegion]:
    regions: list[TextRegion] = []
    for detection in detections:
        text = detection.text.strip()
        if not text or detection.confidence < min_confidence:
            continue
        if len(detection.polygon) < 4:
            continue
        bbox = bbox_from_polygon(detection.polygon)
        if bbox.width < 2 or bbox.height < 2:
            continue
        regions.append(
            TextRegion(
                id=f"p{page}r{len(regions):03d}",
                page=page,
                text=text,
                bbox=bbox,
                polygon=[[float(x), float(y)] for x, y in detection.polygon[:4]],
                confidence=float(detection.confidence),
                rotation=rotation_degrees(detection.polygon),
                source="ocr" if source == "ocr" else "pdf_text",
                style=StyleHint(
                    font_size_px=max(8.0, bbox.height * 0.92),
                    align=infer_alignment(bbox, page_width),  # type: ignore[arg-type]
                ),
            )
        )
    return regions
