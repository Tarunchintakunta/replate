"""Per-document directories on the local filesystem."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from app.errors import AppError

_DOC_ID = re.compile(r"^[a-f0-9]{32}$")


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def document_dir(self, doc_id: str) -> Path:
        self._check_id(doc_id)
        path = (self.root / doc_id).resolve()
        root = self.root.resolve()
        if not path.is_relative_to(root):
            raise AppError("INVALID_PATH", "Document path escaped the storage root.", 400)
        return path

    def path(self, doc_id: str, relative: str) -> Path:
        relative = relative.replace("\\", "/").lstrip("/")
        parts = Path(relative).parts
        if not relative or any(part in {"..", ""} for part in parts):
            raise AppError("INVALID_PATH", "That file path is not allowed.", 400)
        root = self.document_dir(doc_id)
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise AppError("INVALID_PATH", "That file path is not allowed.", 400)
        return target

    def write_bytes(self, doc_id: str, relative: str, data: bytes) -> Path:
        target = self.path(doc_id, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def delete_document(self, doc_id: str) -> None:
        directory = self.document_dir(doc_id)
        if directory.exists():
            shutil.rmtree(directory)

    def cleanup(self, max_age_hours: int) -> int:
        if max_age_hours <= 0:
            return 0
        cutoff = time.time() - max_age_hours * 3600
        removed = 0
        root = self.root.resolve()
        for child in root.iterdir():
            if not child.is_dir() or not _DOC_ID.match(child.name):
                continue
            try:
                if child.stat().st_mtime < cutoff:
                    shutil.rmtree(child)
                    removed += 1
            except OSError:
                continue
        return removed

    def _check_id(self, doc_id: str) -> None:
        if not _DOC_ID.match(doc_id or ""):
            raise AppError("DOCUMENT_NOT_FOUND", "Document not found.", 404)
