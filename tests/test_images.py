"""Image detection and replacement using real OCR."""

from __future__ import annotations

import cv2
import numpy as np

from app.image.masking import background_complexity
from app.ocr.paddle_provider import PaddleOCRProvider
from tests.samples import image_bytes, textured_image


def _upload(client, payload: bytes, name: str = "sample.png"):
    media = "image/jpeg" if name.endswith(".jpg") else "image/png"
    response = client.post("/api/upload", files={"file": (name, payload, media)})
    assert response.status_code == 200, response.text
    return response.json()


def _detect(client, doc_id: str) -> dict:
    response = client.post(f"/api/document/{doc_id}/detect-text")
    assert response.status_code == 200, response.text
    return response.json()["document"]


def _replace(client, doc_id: str, region_id: str, text: str, mode: str = "fast") -> dict:
    response = client.post(
        f"/api/document/{doc_id}/replace-text",
        json={"region_id": region_id, "new_text": text, "mode": mode},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _ocr_png(data: bytes) -> list[str]:
    array = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return [item.text for item in PaddleOCRProvider().detect(array)]


def _find(document: dict, needle: str, page: int | None = None) -> dict:
    for region in document["regions"]:
        if page is not None and region["page"] != page:
            continue
        if needle.lower() in region["text"].lower():
            return region
    raise AssertionError(f"{needle!r} not in {[region['text'] for region in document['regions']]}")


def test_complexity_distinguishes_flat_and_texture():
    flat = np.full((200, 400, 3), 240, np.uint8)
    mask = np.zeros((200, 400), np.uint8)
    mask[70:130, 40:220] = 255
    assert background_complexity(flat, mask) < 0.42
    noisy = np.random.default_rng(0).integers(0, 255, (200, 400, 3), dtype=np.uint8)
    assert background_complexity(noisy, mask) >= 0.42


def test_simple_jpg_replace_and_export(client, tmp_path):
    uploaded = _upload(
        client,
        image_bytes([("Welcome to Paris", (20, 30, 80), 64)], kind="jpg"),
        "trip.jpg",
    )
    document = _detect(client, uploaded["id"])
    region = _find(document, "Paris")
    original = (tmp_path / "storage" / uploaded["id"]).rglob("original.jpg")
    original_path = next(original)
    original_bytes = original_path.read_bytes()
    result = _replace(client, uploaded["id"], region["id"], "Welcome to London", "fast")
    assert result["mode_used"] == "fast"
    assert original_path.read_bytes() == original_bytes
    exported = client.post(f"/api/document/{uploaded['id']}/export", json={"format": "jpg"})
    assert exported.status_code == 200
    download = client.get(f"/api/document/{uploaded['id']}/download")
    assert download.status_code == 200
    assert download.content[:2] == b"\xff\xd8"
    texts = " ".join(_ocr_png(download.content))
    assert "London" in texts
    assert "Paris" not in texts


def test_multiple_regions_and_colors(client):
    payload = image_bytes(
        [
            ("Red fox", (180, 20, 20), 54),
            ("Blue bird", (20, 40, 170), 54),
        ],
        size=(1000, 360),
    )
    uploaded = _upload(client, payload)
    document = _detect(client, uploaded["id"])
    red = _find(document, "Red")
    blue = _find(document, "Blue")
    assert red["style"]["color_rgb"][0] > red["style"]["color_rgb"][2]
    assert blue["style"]["color_rgb"][2] > blue["style"]["color_rgb"][0]
    _replace(client, uploaded["id"], red["id"], "Green fox")
    second = _replace(client, uploaded["id"], blue["id"], "Gold bird")
    assert len(second["document"]["edits"]) == 2
    assert second["document"]["pages"][0]["version"] == 2


def test_dark_background_estimates_light_text(client):
    payload = image_bytes(
        [("Night market", (245, 245, 245), 60)],
        background=(15, 15, 18),
    )
    document = _detect(client, _upload(client, payload)["id"])
    region = _find(document, "Night")
    assert sum(region["style"]["color_rgb"]) / 3 > 160


def test_large_and_small_text(client):
    payload = image_bytes(
        [("LARGE TITLE", (0, 0, 0), 72), ("small caption", (0, 0, 0), 22)],
        size=(1100, 320),
    )
    document = _detect(client, _upload(client, payload)["id"])
    texts = " ".join(region["text"] for region in document["regions"])
    assert "LARGE" in texts
    assert "small" in texts.lower() or "caption" in texts.lower()


def test_rotated_text_round_trip(client):
    payload = image_bytes([("Rotated heading", (0, 0, 0), 48)], size=(1000, 420), rotate=12)
    uploaded = _upload(client, payload)
    document = _detect(client, uploaded["id"])
    region = _find(document, "Rotated")
    assert abs(region["rotation"]) > 4
    _replace(client, uploaded["id"], region["id"], "Level heading", "fast")
    png = client.get(f"/api/document/{uploaded['id']}/pages/0/image?variant=current").content
    texts = " ".join(_ocr_png(png))
    assert "Level" in texts or "heading" in texts.lower()


def test_textured_background_uses_ai_and_preserves_corners(client):
    uploaded = _upload(client, textured_image("Texture line"))
    document = _detect(client, uploaded["id"])
    region = _find(document, "Texture")
    before = client.get(f"/api/document/{uploaded['id']}/pages/0/image?variant=original").content
    result = _replace(client, uploaded["id"], region["id"], "Rebuilt line", "auto")
    assert result["mode_used"] == "ai", result["fallback_reason"]
    after = client.get(f"/api/document/{uploaded['id']}/pages/0/image?variant=current").content
    texts = " ".join(_ocr_png(after))
    # A second OCR pass on a noisy background can fuse glyphs. The old word must be gone.
    assert "Texture" not in texts
    assert "Rebuil" in texts.replace(" ", "")
    before_arr = cv2.imdecode(np.frombuffer(before, np.uint8), cv2.IMREAD_COLOR)
    after_arr = cv2.imdecode(np.frombuffer(after, np.uint8), cv2.IMREAD_COLOR)
    # Corners sit well outside the line and should stay put.
    assert np.abs(before_arr[:20, :20].astype(int) - after_arr[:20, :20].astype(int)).max() <= 2


def test_multiple_replacements_undo_redo(client):
    payload = image_bytes(
        [("First line", (0, 0, 0), 48), ("Second line", (0, 0, 0), 48)],
        size=(900, 320),
    )
    uploaded = _upload(client, payload)
    document = _detect(client, uploaded["id"])
    first = _find(document, "First")
    second = _find(document, "Second")
    _replace(client, uploaded["id"], first["id"], "Alpha line")
    _replace(client, uploaded["id"], second["id"], "Beta line")
    current = client.get(f"/api/document/{uploaded['id']}/pages/0/image?variant=current").content
    texts = " ".join(_ocr_png(current))
    assert "Alpha" in texts and "Beta" in texts
    undone = client.post(f"/api/document/{uploaded['id']}/undo")
    assert undone.status_code == 200
    assert undone.json()["can_redo"] is True
    mid = client.get(f"/api/document/{uploaded['id']}/pages/0/image?variant=current").content
    mid_texts = " ".join(_ocr_png(mid))
    assert "Beta" not in mid_texts
    assert "Second" in mid_texts
    redone = client.post(f"/api/document/{uploaded['id']}/redo")
    assert redone.status_code == 200
    again = client.get(f"/api/document/{uploaded['id']}/pages/0/image?variant=current").content
    assert "Beta" in " ".join(_ocr_png(again))
    reset = client.post(f"/api/document/{uploaded['id']}/reset")
    assert reset.status_code == 200
    assert reset.json()["can_undo"] is False
    restored = client.get(f"/api/document/{uploaded['id']}/pages/0/image?variant=current").content
    restored_texts = " ".join(_ocr_png(restored))
    assert "First" in restored_texts and "Second" in restored_texts


def test_ai_request_falls_back_when_weights_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("REWORDS_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("REWORDS_MODELS_DIR", str(tmp_path / "empty-models"))
    monkeypatch.setenv("REWORDS_CLEANUP_HOURS", "100000")
    from app.config import reset_settings
    from app.main import create_app
    from app.services.document_service import reset_service
    from fastapi.testclient import TestClient

    reset_settings()
    reset_service()
    payload = image_bytes([("Welcome to Paris", (0, 0, 0), 56)])
    with TestClient(create_app()) as local:
        uploaded = local.post("/api/upload", files={"file": ("a.png", payload, "image/png")})
        doc_id = uploaded.json()["id"]
        detected = local.post(f"/api/document/{doc_id}/detect-text")
        region = detected.json()["document"]["regions"][0]
        replaced = local.post(
            f"/api/document/{doc_id}/replace-text",
            json={"region_id": region["id"], "new_text": "Welcome to London", "mode": "ai"},
        )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["mode_used"] == "fast"
    assert replaced.json()["fallback_reason"]
