#!/usr/bin/env python3
"""Measure the local pipeline and print JSON. Run with the project venv."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(ROOT / "models" / "paddlex"))
os.environ.setdefault("PADDLEX_HOME", str(ROOT / "models" / "paddlex"))
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ["REWORDS_STORAGE_DIR"] = str(ROOT / "storage" / "_bench")
os.environ["REWORDS_CLEANUP_HOURS"] = "100000"

from fastapi.testclient import TestClient  # noqa: E402

from app.config import reset_settings  # noqa: E402
from app.device import rss_mb  # noqa: E402
from app.main import create_app  # noqa: E402
from app.metrics import clear, snapshot  # noqa: E402
from app.services.document_service import reset_service  # noqa: E402
from tests.samples import image_bytes, native_pdf, scanned_pdf, textured_image  # noqa: E402


def main() -> None:
    reset_settings()
    reset_service()
    clear()
    client = TestClient(create_app())
    report: dict = {"rss_before_mb": rss_mb()}

    jpg = image_bytes([("Welcome to Paris", (10, 10, 10), 60)], kind="jpg")
    started = time.perf_counter()
    uploaded = client.post("/api/upload", files={"file": ("bench.jpg", jpg, "image/jpeg")}).json()
    detected = client.post(f"/api/document/{uploaded['id']}/detect-text")
    report["first_image_detect_ms"] = round((time.perf_counter() - started) * 1000, 1)
    report["first_detect_status"] = detected.status_code
    region = detected.json()["document"]["regions"][0]["id"]
    started = time.perf_counter()
    client.post(f"/api/document/{uploaded['id']}/detect-text")
    report["cached_image_detect_ms"] = round((time.perf_counter() - started) * 1000, 1)

    started = time.perf_counter()
    fast = client.post(
        f"/api/document/{uploaded['id']}/replace-text",
        json={"region_id": region, "new_text": "Welcome to Lyon", "mode": "fast"},
    )
    report["fast_replace_ms"] = round((time.perf_counter() - started) * 1000, 1)
    report["fast_mode"] = fast.json().get("mode_used")

    texture = client.post("/api/upload", files={"file": ("tex.png", textured_image(), "image/png")}).json()
    tex_doc = client.post(f"/api/document/{texture['id']}/detect-text").json()["document"]
    tex_region = next(item for item in tex_doc["regions"] if "Texture" in item["text"])
    started = time.perf_counter()
    ai = client.post(
        f"/api/document/{texture['id']}/replace-text",
        json={"region_id": tex_region["id"], "new_text": "Rebuilt line", "mode": "ai"},
    )
    report["ai_replace_ms"] = round((time.perf_counter() - started) * 1000, 1)
    report["ai_mode"] = ai.json().get("mode_used")
    report["ai_fallback"] = ai.json().get("fallback_reason")

    pdf_bytes = native_pdf(
        [[("Page one", "helv", 20)], [("Welcome to Paris", "helv", 24)], [("Budget total", "helv", 20)]]
    )
    started = time.perf_counter()
    pdf = client.post("/api/upload", files={"file": ("bench.pdf", pdf_bytes, "application/pdf")}).json()
    pdf_doc = client.post(f"/api/document/{pdf['id']}/detect-text").json()["document"]
    report["native_pdf_detect_ms"] = round((time.perf_counter() - started) * 1000, 1)
    target = next(item for item in pdf_doc["regions"] if "Paris" in item["text"])
    started = time.perf_counter()
    client.post(
        f"/api/document/{pdf['id']}/replace-text",
        json={"region_id": target["id"], "new_text": "Welcome to London", "mode": "auto"},
    )
    report["native_pdf_replace_ms"] = round((time.perf_counter() - started) * 1000, 1)

    scan = scanned_pdf(["Only on page one", "Secret on page two", "Marker on page three"])
    started = time.perf_counter()
    scan_doc = client.post("/api/upload", files={"file": ("scan.pdf", scan, "application/pdf")}).json()
    client.post(f"/api/document/{scan_doc['id']}/detect-text")
    report["scanned_3page_detect_ms"] = round((time.perf_counter() - started) * 1000, 1)
    report["rss_after_mb"] = rss_mb()
    report["samples"] = snapshot()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
