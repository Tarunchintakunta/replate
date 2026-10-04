"""Shared fixtures. Model caches point at the project models directory."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(ROOT / "models" / "paddlex"))
os.environ.setdefault("PADDLEX_HOME", str(ROOT / "models" / "paddlex"))
os.environ.setdefault("FLAGS_use_mkldnn", "0")
# Tests never call the paid text-edit API.
os.environ["REWORDS_TEXT_EDIT"] = "off"

from app.config import reset_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.document_service import reset_service  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REWORDS_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("REWORDS_CLEANUP_HOURS", "100000")
    reset_settings()
    reset_service()
    with TestClient(create_app()) as test_client:
        yield test_client
