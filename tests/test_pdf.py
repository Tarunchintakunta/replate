"""Native, scanned, mixed, and multi-page PDFs."""

from __future__ import annotations

import fitz

from tests.samples import mixed_pdf, native_pdf, pdf_with_table_and_image, scanned_pdf


def _upload_pdf(client, payload: bytes, name: str = "doc.pdf") -> dict:
    response = client.post("/api/upload", files={"file": (name, payload, "application/pdf")})
    assert response.status_code == 200, response.text
    return response.json()


def _detect(client, doc_id: str) -> dict:
    response = client.post(f"/api/document/{doc_id}/detect-text")
    assert response.status_code == 200, response.text
    return response.json()["document"]


def _find(document: dict, needle: str, page: int | None = None) -> dict:
    for region in document["regions"]:
        if page is not None and region["page"] != page:
            continue
        if needle.lower() in region["text"].lower():
            return region
    raise AssertionError(needle)


def _replace(client, doc_id: str, region_id: str, text: str, mode: str = "auto") -> dict:
    response = client.post(
        f"/api/document/{doc_id}/replace-text",
        json={"region_id": region_id, "new_text": text, "mode": mode},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _exported_pdf(client, doc_id: str) -> fitz.Document:
    exported = client.post(f"/api/document/{doc_id}/export", json={"format": "pdf"})
    assert exported.status_code == 200, exported.text
    download = client.get(f"/api/document/{doc_id}/download")
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")
    return fitz.open(stream=download.content, filetype="pdf")


def test_simple_native_pdf(client, tmp_path):
    uploaded = _upload_pdf(client, native_pdf([[("Welcome to Paris", "helv", 28), ("Leave me", "tiro", 16)]]))
    assert uploaded["pages"][0]["kind"] == "native"
    document = _detect(client, uploaded["id"])
    original = (tmp_path / "storage" / uploaded["id"] / "original.pdf").read_bytes()
    region = _find(document, "Paris")
    _replace(client, uploaded["id"], region["id"], "Welcome to London")
    assert (tmp_path / "storage" / uploaded["id"] / "original.pdf").read_bytes() == original
    pdf = _exported_pdf(client, uploaded["id"])
    text = pdf[0].get_text("text")
    assert "Welcome to London" in text
    assert "Paris" not in text
    assert "Leave me" in text


def test_font_families_and_table(client):
    uploaded = _upload_pdf(client, pdf_with_table_and_image())
    document = _detect(client, uploaded["id"])
    families = {region["text"]: region["style"]["family"] for region in document["regions"]}
    bold = {region["text"]: region["style"]["bold"] for region in document["regions"]}
    assert families["Left cell"] == "mono"
    assert families["Right cell"] == "sans"
    assert bold["Right cell"] is True
    region = _find(document, "Right cell")
    _replace(client, uploaded["id"], region["id"], "East cell")
    pdf = _exported_pdf(client, uploaded["id"])
    text = pdf[0].get_text("text")
    assert "East cell" in text
    assert "Right cell" not in text
    assert "Left cell" in text
    assert len(pdf[0].get_drawings()) >= 1
    assert pdf[0].get_images()


def test_multipage_native_edits_page_two_and_three(client):
    payload = native_pdf(
        [
            [("Page one stays", "helv", 22)],
            [("Welcome to Paris", "helv", 26), ("Footer two", "tiro", 14)],
            [("Budget total", "helv", 22), ("Footer three", "tiro", 14)],
        ]
    )
    uploaded = _upload_pdf(client, payload, "notes.pdf")
    assert uploaded["page_count"] == 3
    assert [page["kind"] for page in uploaded["pages"]] == ["native", "native", "native"]
    document = _detect(client, uploaded["id"])
    page_two = _find(document, "Paris", page=1)
    page_three = _find(document, "Budget", page=2)
    _replace(client, uploaded["id"], page_two["id"], "Welcome to London")
    state = _replace(client, uploaded["id"], page_three["id"], "Budget revised")["document"]
    assert state["pages"][0]["version"] == 0
    assert state["pages"][1]["version"] == 1
    assert state["pages"][2]["version"] == 1
    pdf = _exported_pdf(client, uploaded["id"])
    assert pdf.page_count == 3
    assert "Page one stays" in pdf[0].get_text("text")
    assert "Paris" not in pdf[0].get_text("text")
    page2 = pdf[1].get_text("text")
    assert "Welcome to London" in page2
    assert "Paris" not in page2
    assert "Footer two" in page2
    page3 = pdf[2].get_text("text")
    assert "Budget revised" in page3
    assert "Budget total" not in page3
    assert "Footer three" in page3
    assert [round(page.rect.width) for page in pdf] == [595, 595, 595]
    undone = client.post(f"/api/document/{uploaded['id']}/undo")
    assert undone.status_code == 200
    pdf = _exported_pdf(client, uploaded["id"])
    assert "Budget total" in pdf[2].get_text("text")
    assert "Welcome to London" in pdf[1].get_text("text")
    redone = client.post(f"/api/document/{uploaded['id']}/redo")
    assert redone.status_code == 200
    pdf = _exported_pdf(client, uploaded["id"])
    assert "Budget revised" in pdf[2].get_text("text")


def test_scanned_multipage_pdf(client):
    payload = scanned_pdf(["Only on page one", "Secret on page two", "Marker on page three"])
    uploaded = _upload_pdf(client, payload, "scan.pdf")
    assert [page["kind"] for page in uploaded["pages"]] == ["scanned", "scanned", "scanned"]
    document = _detect(client, uploaded["id"])
    assert _find(document, "Secret", page=1)["source"] == "ocr"
    _replace(client, uploaded["id"], _find(document, "Secret", page=1)["id"], "Changed on page two", "fast")
    document = client.get(f"/api/document/{uploaded['id']}").json()
    _replace(client, uploaded["id"], _find(document, "Marker", page=2)["id"], "Changed on page three", "fast")
    pdf = _exported_pdf(client, uploaded["id"])
    assert pdf.page_count == 3
    from app.ocr.paddle_provider import PaddleOCRProvider

    ocr = PaddleOCRProvider()
    for index, expected, forbidden in (
        (0, "Only on page one", "Changed"),
        (1, "Changed on page two", "Secret"),
        (2, "Changed on page three", "Marker"),
    ):
        pixmap = pdf[index].get_pixmap(matrix=fitz.Matrix(1.3, 1.3), alpha=False)
        import numpy as np

        array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
        array = array[:, :, ::-1].copy()
        texts = " ".join(item.text for item in ocr.detect(array))
        assert expected.split()[0] in texts
        assert forbidden not in texts


def test_mixed_pdf_keeps_native_pages_vector(client):
    uploaded = _upload_pdf(client, mixed_pdf(), "mixed.pdf")
    assert [page["kind"] for page in uploaded["pages"]] == ["native", "scanned", "native"]
    document = _detect(client, uploaded["id"])
    _replace(client, uploaded["id"], _find(document, "Scanned", page=1)["id"], "Edited scan page", "fast")
    _replace(client, uploaded["id"], _find(document, "Closing", page=2)["id"], "Edited closing page")
    pdf = _exported_pdf(client, uploaded["id"])
    assert "Native introduction" in pdf[0].get_text("text")
    assert "Edited closing page" in pdf[2].get_text("text")
    assert "Closing native page" not in pdf[2].get_text("text")
    assert "Table cell" in pdf[2].get_text("text")
    assert len(pdf[2].get_drawings()) >= 1
    pixmap = pdf[1].get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
    import numpy as np
    from app.ocr.paddle_provider import PaddleOCRProvider

    array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)[:, :, ::-1].copy()
    texts = " ".join(item.text for item in PaddleOCRProvider().detect(array))
    assert "Edited" in texts
    assert "Scanned" not in texts


def test_native_edit_keeps_the_span_style(client, tmp_path):
    """Font, size, colour, outline, letter spacing and baseline come from the PDF, not a family guess."""
    serif = "fonts/LiberationSerif-Bold.ttf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=200)
    page.insert_font(fontname="S", fontfile=serif)
    font, x = fitz.Font(fontfile=serif), 40.0
    for char in "CLOUD COMPUTING":  # letter-spaced, two-colour outlined
        page.insert_text((x, 80), char, fontname="S", fontsize=24, color=(0.1, 0.1, 0.5), fill=(0.9, 0.2, 0.1), render_mode=2, border_width=0.04)
        x += font.glyph_advance(ord(char)) * 24 + 2
    doc.subset_fonts()
    uploaded = _upload_pdf(client, doc.tobytes())
    document = _detect(client, uploaded["id"])
    region = _find(document, "CLOUD")
    _replace(client, uploaded["id"], region["id"], "CLOUE COMPUTING")
    edited = _exported_pdf(client, uploaded["id"])[0]
    trace = next(t for t in edited.get_texttrace() if t["type"] == 0)
    chars = [c for t in edited.get_texttrace() if t["type"] == 0 for c in t["chars"]]
    assert "Liberation" in trace["font"] and "Bold" in trace["font"]
    assert abs(trace["size"] - 24) < 0.01
    assert max(abs(a - b) for a, b in zip(trace["color"], (0.9, 0.2, 0.1))) < 0.01
    assert any(t["type"] == 1 for t in edited.get_texttrace())  # outline kept
    assert abs(chars[0][2][1] - 80) < 0.01 and abs(chars[0][2][0] - 40) < 0.01
    gap = chars[1][2][0] - chars[0][2][0] - font.glyph_advance(ord("C")) * 24
    assert abs(gap - 2) < 0.05
