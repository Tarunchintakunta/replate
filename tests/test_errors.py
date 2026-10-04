"""Failure cases must return a code and a useful message."""

from __future__ import annotations

import io

from PIL import Image

from tests.samples import image_bytes, native_pdf


def test_parallel_page_renders_stay_readable(client):
    """Thumbnails and page images used to race and return a torn PNG."""
    from concurrent.futures import ThreadPoolExecutor

    from app.services.document_service import get_service

    payload = native_pdf(
        [[("Page one stays", "helv", 22)], [("Welcome to Paris", "helv", 26)], [("Budget total", "helv", 22)]]
    )
    uploaded = client.post("/api/upload", files={"file": ("notes.pdf", payload, "application/pdf")})
    assert uploaded.status_code == 200
    doc_id = uploaded.json()["id"]
    service = get_service()

    def fetch(page: int) -> tuple[bytes, bytes]:
        image = service.page_image(doc_id, page, "current").read_bytes()
        thumb = service.thumbnail(doc_id, page).read_bytes()
        return image[:8], thumb[:3]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(fetch, [0, 1, 2, 0, 1, 2]))
    assert results
    for image_magic, thumb_magic in results:
        assert image_magic == b"\x89PNG\r\n\x1a\n"
        assert thumb_magic == b"\xff\xd8\xff"


def test_rejects_unknown_magic(client):
    response = client.post("/api/upload", files={"file": ("notes.png", b"GIF89a not really", "image/png")})
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_rejects_empty_upload(client):
    response = client.post("/api/upload", files={"file": ("empty.png", b"", "image/png")})
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_trusts_magic_bytes_over_extension(client):
    payload = image_bytes([("Hello there", (0, 0, 0), 48)], kind="jpg")
    response = client.post("/api/upload", files={"file": ("report.pdf", payload, "application/pdf")})
    assert response.status_code == 200
    assert response.json()["media_type"] == "jpeg"


def test_sanitizes_filename(client):
    payload = image_bytes([("Hello there", (0, 0, 0), 48)])
    response = client.post(
        "/api/upload",
        files={"file": ("../../secret.png", payload, "image/png")},
    )
    assert response.status_code == 200
    assert "/" not in response.json()["original_filename"]
    assert ".." not in response.json()["original_filename"]


def test_corrupted_pdf(client):
    response = client.post("/api/upload", files={"file": ("bad.pdf", b"%PDF-1.4\nthis is garbage", "application/pdf")})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CORRUPTED_PDF"


def test_no_text(client):
    buffer = io.BytesIO()
    Image.new("RGB", (400, 200), "white").save(buffer, format="PNG")
    uploaded = client.post("/api/upload", files={"file": ("blank.png", buffer.getvalue(), "image/png")})
    detected = client.post(f"/api/document/{uploaded.json()['id']}/detect-text")
    assert detected.status_code == 422
    assert detected.json()["error"]["code"] == "NO_TEXT_DETECTED"


def test_oversized_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("REWORDS_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("REWORDS_MAX_UPLOAD_BYTES", "800")
    monkeypatch.setenv("REWORDS_CLEANUP_HOURS", "100000")
    from app.config import reset_settings
    from app.main import create_app
    from app.services.document_service import reset_service
    from fastapi.testclient import TestClient

    reset_settings()
    reset_service()
    with TestClient(create_app()) as local:
        payload = image_bytes([("Too big", (0, 0, 0), 48)])
        response = local.post("/api/upload", files={"file": ("big.png", payload, "image/png")})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_too_many_pages(tmp_path, monkeypatch):
    monkeypatch.setenv("REWORDS_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("REWORDS_MAX_PDF_PAGES", "2")
    monkeypatch.setenv("REWORDS_CLEANUP_HOURS", "100000")
    from app.config import reset_settings
    from app.main import create_app
    from app.services.document_service import reset_service
    from fastapi.testclient import TestClient

    reset_settings()
    reset_service()
    payload = native_pdf([[("One", "helv", 18)], [("Two", "helv", 18)], [("Three", "helv", 18)]])
    with TestClient(create_app()) as local:
        response = local.post("/api/upload", files={"file": ("many.pdf", payload, "application/pdf")})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "TOO_MANY_PAGES"


def test_missing_document_and_bad_id(client):
    missing = client.get("/api/document/" + "a" * 32)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"
    bad = client.get("/api/document/not-a-valid-id")
    assert bad.status_code == 404


def test_invalid_replacement_and_export_format(client):
    payload = image_bytes([("Welcome to Paris", (0, 0, 0), 56)], kind="jpg")
    uploaded = client.post("/api/upload", files={"file": ("trip.jpg", payload, "image/jpeg")})
    doc_id = uploaded.json()["id"]
    detected = client.post(f"/api/document/{doc_id}/detect-text")
    region = detected.json()["document"]["regions"][0]
    blank = client.post(
        f"/api/document/{doc_id}/replace-text",
        json={"region_id": region["id"], "new_text": "   ", "mode": "fast"},
    )
    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "INVALID_REPLACEMENT_TEXT"
    wrong = client.post(f"/api/document/{doc_id}/export", json={"format": "pdf"})
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "EXPORT_FORMAT"
    early = client.post(f"/api/document/{doc_id}/undo")
    assert early.status_code == 400
    assert early.json()["error"]["code"] == "NOTHING_TO_UNDO"


def test_cleanup_removes_old_directories(tmp_path):
    from app.storage.local import LocalStorage

    storage = LocalStorage(tmp_path)
    doc_id = "a" * 32
    directory = storage.document_dir(doc_id)
    directory.mkdir()
    old = directory.stat().st_mtime - 48 * 3600
    import os

    os.utime(directory, (old, old))
    removed = storage.cleanup(24)
    assert removed == 1
    assert not directory.exists()
