#!/usr/bin/env python3
"""Browser acceptance test. The API and Vite dev server must already be running.

    python tests/e2e_acceptance.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from tests.samples import image_bytes, native_pdf, scanned_pdf  # noqa: E402

BASE = "http://127.0.0.1:8742"
OUT = Path("/opt/cursor/artifacts")
SHOTS = OUT / "screenshots"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    samples = OUT / "samples"
    samples.mkdir(parents=True, exist_ok=True)

    jpg = image_bytes([("Welcome to Paris", (20, 30, 90), 64)], size=(1100, 320), kind="jpg")
    (samples / "before-welcome.jpg").write_bytes(jpg)
    notes = native_pdf(
        [
            [("Page one stays", "helv", 22)],
            [("Welcome to Paris", "helv", 26), ("Footer two", "tiro", 14)],
            [("Budget total", "helv", 22), ("Footer three", "tiro", 14)],
        ]
    )
    scan = scanned_pdf(["Only on page one", "Secret on page two", "Marker on page three"])

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto(BASE, wait_until="networkidle")
        run_image(page, jpg, samples)
        run_pdf(page, notes, samples / "native-edited.pdf", native=True)
        run_pdf(page, scan, samples / "scanned-edited.pdf", native=False)
        browser.close()
    verify_native(samples / "native-edited.pdf")
    verify_scanned(samples / "scanned-edited.pdf")
    print("Acceptance passed")
    print(f"Screenshots: {SHOTS}")
    print(f"Samples: {samples}")


def run_image(page, payload: bytes, samples: Path) -> None:
    page.locator("[data-testid=file-input]").set_input_files(
        {"name": "welcome.jpg", "mimeType": "image/jpeg", "buffer": payload}
    )
    expect(page.get_by_text("Welcome to Paris").first).to_be_visible(timeout=120_000)
    page.locator("[data-testid=viewer]").screenshot(path=str(SHOTS / "01-jpg-highlighted.png"))
    page.locator("[data-testid^=region-]").filter(has_text="Paris").first.click()
    page.locator("[data-testid=viewer]").screenshot(path=str(SHOTS / "02-jpg-selected.png"))
    page.locator("[data-testid=replacement]").fill("Welcome to London")
    page.locator("[data-testid=apply]").click()
    expect(page.get_by_text("Welcome to London").first).to_be_visible(timeout=60_000)
    page.locator("[data-testid=viewer]").screenshot(path=str(SHOTS / "03-jpg-after-replace.png"))
    with page.expect_download(timeout=60_000) as download_info:
        page.locator("[data-testid=export-jpg]").click()
    download = download_info.value
    target = samples / "after-welcome.jpg"
    download.save_as(str(target))
    page.screenshot(path=str(SHOTS / "04-jpg-exported-ui.png"), full_page=True)


def run_pdf(page, payload: bytes, dest: Path, native: bool) -> None:
    page.get_by_role("button", name="New file").click()
    name = "notes.pdf" if native else "scan.pdf"
    page.locator("[data-testid=file-input]").set_input_files(
        {"name": name, "mimeType": "application/pdf", "buffer": payload}
    )
    expect(page.locator("[data-testid=page-thumb-2]")).to_be_visible(timeout=180_000)
    page.locator("[data-testid=page-thumb-1]").click()
    needle = "Paris" if native else "Secret"
    replacement = "Welcome to London" if native else "Changed on page two"
    expect(page.get_by_text(needle).first).to_be_visible(timeout=60_000)
    tag = "native" if native else "scanned"
    page.locator("[data-testid=viewer]").screenshot(path=str(SHOTS / f"05-{tag}-page2-highlighted.png"))
    page.locator("[data-testid^=region-]").filter(has_text=needle).first.click()
    page.locator("[data-testid=viewer]").screenshot(path=str(SHOTS / f"06-{tag}-page2-selected.png"))
    page.locator("[data-testid=replacement]").fill(replacement)
    page.locator("[data-testid=apply]").click()
    expect(page.get_by_text(replacement).first).to_be_visible(timeout=120_000)
    page.locator("[data-testid=viewer]").screenshot(path=str(SHOTS / f"07-{tag}-page2-after.png"))

    page.locator("[data-testid=page-thumb-2]").click()
    second_needle = "Budget" if native else "Marker"
    second_text = "Budget revised" if native else "Changed on page three"
    expect(page.get_by_text(second_needle).first).to_be_visible(timeout=60_000)
    page.locator("[data-testid^=region-]").filter(has_text=second_needle).first.click()
    page.locator("[data-testid=replacement]").fill(second_text)
    page.locator("[data-testid=apply]").click()
    expect(page.get_by_text(second_text).first).to_be_visible(timeout=120_000)
    page.locator("[data-testid=viewer]").screenshot(path=str(SHOTS / f"08-{tag}-page3-after.png"))
    with page.expect_download(timeout=120_000) as download_info:
        page.locator("[data-testid=export-pdf]").click()
    download_info.value.save_as(str(dest))
    page.screenshot(path=str(SHOTS / f"09-{tag}-exported-ui.png"), full_page=True)


def verify_native(path: Path) -> None:
    document = fitz.open(path)
    assert document.page_count == 3
    assert "Page one stays" in document[0].get_text("text")
    assert "Paris" not in document[0].get_text("text")
    page2 = document[1].get_text("text")
    assert "Welcome to London" in page2 and "Paris" not in page2 and "Footer two" in page2
    page3 = document[2].get_text("text")
    assert "Budget revised" in page3 and "Budget total" not in page3 and "Footer three" in page3
    document.close()


def verify_scanned(path: Path) -> None:
    from app.ocr.paddle_provider import PaddleOCRProvider
    import numpy as np

    document = fitz.open(path)
    assert document.page_count == 3
    ocr = PaddleOCRProvider()
    expectations = (
        (0, "Only", "Changed"),
        (1, "Changed", "Secret"),
        (2, "Changed", "Marker"),
    )
    for index, required, forbidden in expectations:
        pixmap = document[index].get_pixmap(matrix=fitz.Matrix(1.3, 1.3), alpha=False)
        array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
        array = array[:, :, ::-1].copy()
        text = " ".join(item.text for item in ocr.detect(array))
        preview = OUT / "samples" / f"scanned-page-{index}.png"
        pixmap.save(str(preview))
        if required not in text or forbidden in text:
            raise SystemExit(f"Scanned page {index} OCR was {text!r}")
    document.close()


if __name__ == "__main__":
    main()
