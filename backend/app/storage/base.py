"""Storage boundary. Local disk today, object storage later."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class StorageProvider(Protocol):
    def document_dir(self, doc_id: str) -> Path: ...

    def path(self, doc_id: str, relative: str) -> Path: ...

    def write_bytes(self, doc_id: str, relative: str, data: bytes) -> Path: ...

    def delete_document(self, doc_id: str) -> None: ...

    def cleanup(self, max_age_hours: int) -> int: ...
