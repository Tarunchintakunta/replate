"""PDF processor boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np

from app.models.domain import PageInfo, TextRegion


class PDFProcessor(Protocol):
    def inspect(self, path: Path, dpi: int, max_side: int) -> list[PageInfo]: ...

    def extract_regions(self, path: Path, page: PageInfo) -> list[TextRegion]: ...

    def render_page(self, path: Path, page: PageInfo) -> np.ndarray: ...

    def replace_native_text(
        self,
        path: Path,
        page_index: int,
        region: TextRegion,
        new_text: str,
        font_file: Path,
        other_regions: list[TextRegion],
    ) -> None: ...

    def export_mixed(self, work_pdf: Path, overrides: dict[int, Path], dest: Path) -> None: ...
