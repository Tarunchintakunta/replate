"""Normalized document model shared by every pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BBox(BaseModel):
    x: float
    y: float
    width: float
    height: float

    def as_rect(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


class StyleHint(BaseModel):
    """Visual estimate. This is not an identified typeface."""

    family: Literal["sans", "serif", "mono", "condensed", "receipt"] = "sans"
    bold: bool = False
    font_label: str = ""
    font_confidence: float | None = None
    font_size_px: float = 16
    color_rgb: list[int] = Field(default_factory=lambda: [0, 0, 0])
    align: Literal["left", "center", "right"] = "left"
    pdf_font_size: float | None = None
    pdf_color: list[float] | None = None
    source_font_name: str | None = None


class TextRegion(BaseModel):
    id: str
    page: int
    text: str
    bbox: BBox
    polygon: list[list[float]]
    confidence: float
    rotation: float = 0
    source: Literal["ocr", "pdf_text"]
    source_text: str = ""
    pdf_bbox: BBox | None = None
    style: StyleHint = Field(default_factory=StyleHint)


class PageInfo(BaseModel):
    index: int
    kind: Literal["image", "native", "scanned"]
    width_px: int
    height_px: int
    width_pt: float | None = None
    height_pt: float | None = None
    pixel_scale: float = 1.0
    version: int = 0


class EditRecord(BaseModel):
    region_id: str
    page: int
    before: str
    after: str
    mode_requested: str
    mode_used: str
    draw_source: Literal["glyphs", "synthesized", "ai_text", "font", "pdf_text"] = "font"
    match_score: float | None = None
    fallback_reason: str | None = None


class DocumentState(BaseModel):
    id: str
    original_filename: str
    media_type: Literal["png", "jpeg", "pdf"]
    file_kind: Literal["image", "pdf"]
    created_at: str
    page_count: int
    pages: list[PageInfo]
    regions: list[TextRegion] = Field(default_factory=list)
    detected: bool = False
    edits: list[EditRecord] = Field(default_factory=list)
    history_index: int = 0
    snapshot_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    page_glyphs: dict[str, str] = Field(default_factory=dict)
    render_dpi: int = 144

    @property
    def can_undo(self) -> bool:
        return self.history_index > 0

    @property
    def can_redo(self) -> bool:
        return self.history_index < self.snapshot_count - 1
